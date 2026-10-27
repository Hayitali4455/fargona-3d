# -*- coding: utf-8 -*-
"""OpenStreetMap binolarini portal uchun 3D bo'laklarga ajratish.

F4Map va streets.gl ikkalasi ham OSM binolarini ko'rsatadi; bu yerda OSM ning o'zi
(Geofabrik O'zbekiston .osm.pbf) olinadi — ikkala saytdagi barcha binolar shunda.

Balandlik: height -> building:levels*3 m (+roof:levels) -> bino turi bo'yicha standart.
min_height / building:min_level bo'lsa bino yerdan ko'tarilgan.
Bo'laklar 4 km (portal TM setkasida), har biri bino/<i>_<j>.bin (gzip):
  u32 nb, nr, nv | u16 h_dm[nb], minh_dm[nb], rings[nb], ringlen[nr] | i16 xy_dm[2nv] (bo'lak markazidan) |
  u8 turi[nb], qavat[nb]   (qavat 0 = noma'lum; turi bino/index.json dagi ro'yxatdan)
Ishga tushirish: python bino_build.py [--pbf ...]
"""
import argparse
import gzip
import json
import math
import os
import re
from collections import defaultdict

import geopandas as gpd
import numpy as np
import pyogrio
import shapely

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "bino")
SHP = r"D:\Farg`ona\tuman.shp"
PBF = r"D:\exe\geodar_antenna\osm\src\uzbekistan-261021.osm.pbf"
TILE = 4000.0
DEF_H = {  # standart balandlik, m (OSM da balandlik/qavat yo'q bo'lsa)
    "yes": 4, "house": 4, "detached": 4, "residential": 6, "apartments": 15, "dormitory": 12, "hotel": 15,
    "school": 10, "university": 12, "college": 10, "kindergarten": 7, "hospital": 12, "clinic": 8,
    "commercial": 7, "retail": 6, "office": 12, "public": 8, "civic": 8, "government": 10, "mosque": 9,
    "industrial": 8, "warehouse": 7, "garage": 3, "garages": 3, "shed": 3, "greenhouse": 3, "roof": 3,
    "construction": 3, "service": 3, "farm_auxiliary": 4, "barn": 5, "stadium": 12, "train_station": 8}
LEVEL_M = 3.0


def tag(ot, key):
    m = re.search(r'"' + re.escape(key) + r'"=>"([^"]*)"', ot if isinstance(ot, str) else "")
    return m.group(1) if m else None


def num(s):
    if s is None:
        return None
    m = re.match(r"\s*([0-9]+(?:[.,][0-9]+)?)", s)
    return float(m.group(1).replace(",", ".")) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pbf", default=PBF)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    html = open(os.path.join(HERE, "index.html"), encoding="utf-8").read()
    i = html.index("const D = ") + 10
    D = json.loads(html[i:html.index(";\n(async function main", i)])
    tm = f"+proj=tmerc +lat_0={D['lat0']} +lon_0={D['lon0']} +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
    reg = gpd.read_file(SHP).to_crs(4326)
    df = pyogrio.read_dataframe(a.pbf, layer="multipolygons", where="building IS NOT NULL",
                                bbox=tuple(reg.total_bounds), columns=["osm_id", "osm_way_id", "building", "other_tags"])
    df = df.set_crs(4326, allow_override=True)
    df = df[df.intersects(reg.geometry.union_all())].to_crs(tm)
    print("binolar:", len(df), flush=True)

    types = ["yes"] + sorted(set(df["building"]) - {"yes"})
    tix = {t: k for k, t in enumerate(types)}
    tiles = defaultdict(list)
    n_h = n_lv = 0
    for b, ot, g in zip(df["building"], df["other_tags"], df.geometry):
        if g is None or g.is_empty:
            continue
        h, lv = num(tag(ot, "height")), num(tag(ot, "building:levels"))
        minh, minlv = num(tag(ot, "min_height")), num(tag(ot, "building:min_level"))
        rl = num(tag(ot, "roof:levels")) or 0
        if h:
            n_h += 1
        elif lv:
            h = (lv + rl) * LEVEL_M; n_lv += 1
        else:
            h = DEF_H.get(b, 4)
        minh = minh if minh is not None else (minlv * LEVEL_M if minlv else 0)
        h = max(min(h, 300), minh + 1)
        for p in getattr(g, "geoms", [g]):
            p = p.simplify(0.3)
            if p.is_empty or p.area < 4 or p.geom_type != "Polygon":
                continue
            p = shapely.geometry.polygon.orient(p, 1.0)  # tashqi halqa soat miliga teskari
            c = p.centroid
            tiles[(math.floor(c.x / TILE), math.floor(c.y / TILE))].append((p, h, minh, tix[b], int(lv or 0)))
    index = []
    for (ti, tj), items in tiles.items():
        ox, oy = (ti + 0.5) * TILE, (tj + 0.5) * TILE
        hs, mh, rings, rlen, xy, ty, lvs = [], [], [], [], [], [], []
        for p, h, minh, t, lv in items:
            rr = [p.exterior] + list(p.interiors)
            rr = [r for r in rr if len(r.coords) >= 4][:60]
            ok = []
            for r in rr:
                c = np.asarray(r.coords)[:-1, :2]
                q = np.round((c - [ox, oy]) * 10)
                if np.abs(q).max() > 32000 or len(q) > 2000:
                    continue
                ok.append(q.astype(np.int16))
            if not ok:
                continue
            hs.append(int(round(h * 10))); mh.append(int(round(minh * 10))); rings.append(len(ok)); ty.append(t); lvs.append(min(lv, 255))
            for q in ok:
                rlen.append(len(q)); xy.append(q.ravel())
        nb, nr = len(hs), len(rlen)
        xyc = np.concatenate(xy)
        body = (np.array([nb, nr, len(xyc) // 2], "<u4").tobytes() + np.array(hs, "<u2").tobytes() + np.array(mh, "<u2").tobytes() +
                np.array(rings, "<u2").tobytes() + np.array(rlen, "<u2").tobytes() + xyc.astype("<i2").tobytes() +
                np.array(ty, "u1").tobytes() + np.array(lvs, "u1").tobytes())
        with open(os.path.join(OUT, f"{ti}_{tj}.bin"), "wb") as f:
            f.write(gzip.compress(body, 9, mtime=0))
        index.append([ti, tj, nb])
    json.dump({"tile": TILE, "level_m": LEVEL_M, "types": types, "tiles": sorted(index),
               "manba": "© OpenStreetMap hissadorlari (ODbL), Geofabrik 2026-10-21",
               "jami": sum(t[2] for t in index), "height_tag": n_h, "levels_tag": n_lv},
              open(os.path.join(OUT, "index.json"), "w", encoding="utf-8"), ensure_ascii=False)
    size = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT))
    print(f"bo'laklar: {len(index)}, binolar: {sum(t[2] for t in index)}, height: {n_h}, levels: {n_lv}, hajm {size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
