# -*- coding: utf-8 -*-
"""Farg'ona viloyati 3D: DEM + tuman chegaralari -> bitta HTML.

DEM (EPSG:3857, 4 m) overview orqali kichraytiriladi, viloyat markazidagi
mahalliy Transverse Mercator ga (haqiqiy metr) o'tkaziladi va tuman
poligonlari bilan niqoblanadi. Natija: Fargona_3D.html (three.js ichida).

Ishga tushirish:  python build.py [--res 50]
"""
import argparse
import base64
import gzip
import json
import math
import os

import geopandas as gpd
import numpy as np
import rasterio
import shapely
from affine import Affine
from pyproj import CRS, Transformer
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.warp import reproject
from scipy import ndimage
from shapely.ops import polylabel, unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
DEM = r"D:\Farg`ona\Farg`ona.tif"
SHP = r"D:\Farg`ona\tuman.shp"


def b64gz(arr):
    return base64.b64encode(gzip.compress(arr.tobytes(), 9)).decode("ascii")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", type=float, default=50.0, help="setka qadami, m")
    ap.add_argument("--dec", type=int, default=16, help="DEM o'qish kichraytirish koeffitsienti")
    ap.add_argument("--out", default=os.path.join(HERE, "index.html"))
    ap.add_argument("--og-image", default="", help="ulashish rasmi uchun to'liq URL")
    ap.add_argument("--no-tiles", action="store_true", help="4 m bo'laklarsiz (bosilgan nuqta 50 m to'rdan)")
    ap.add_argument("--no-streams", action="store_true", help="suv oqimi qatlamisiz")
    a = ap.parse_args()
    res = a.res

    g = gpd.read_file(SHP)
    ll = g.to_crs(4326).geometry.union_all().centroid
    lon0, lat0 = round(ll.x, 2), round(ll.y, 2)
    tm = CRS.from_proj4(f"+proj=tmerc +lat_0={lat0} +lon_0={lon0} +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs")
    gt = g.to_crs(tm)
    gt["geometry"] = gt.geometry.make_valid()

    minx, miny, maxx, maxy = gt.total_bounds
    x0 = math.floor(minx / res) * res - res
    y0 = math.ceil(maxy / res) * res + res
    W = int(math.ceil((maxx - x0) / res)) + 2
    H = int(math.ceil((y0 - miny) / res)) + 2
    # setka tugunlari = piksel markazlari
    dst_tr = Affine(res, 0, x0 - res / 2, 0, -res, y0 + res / 2)

    with rasterio.open(DEM) as s:
        oh, ow = s.height // a.dec, s.width // a.dec
        src = s.read(1, out_shape=(oh, ow), resampling=Resampling.average).astype(np.float32)
        src_tr = s.transform * Affine.scale(s.width / ow, s.height / oh)
        src_crs, nod = s.crs, s.nodata
    src[(src == nod) | (src < 100)] = np.nan
    dem = np.full((H, W), np.nan, np.float32)
    reproject(src, dem, src_transform=src_tr, src_crs=src_crs, dst_transform=dst_tr, dst_crs=tm,
              resampling=Resampling.average, src_nodata=np.nan, dst_nodata=np.nan)

    # niqob: viloyat (barcha tumanlar) ichidagi tugunlar; chegaraga tegib turganlari ham
    mask = rasterize(((gm, 1) for gm in gt.geometry), out_shape=(H, W), transform=dst_tr,
                     fill=0, dtype="uint8", all_touched=True).astype(bool)
    ids = rasterize(((gm, i + 1) for i, gm in enumerate(gt.geometry)), out_shape=(H, W), transform=dst_tr,
                    fill=0, dtype="uint8", all_touched=False)
    # all_touched bilan qo'shilgan chekka tugunlar eng yaqin tumanga beriladi
    idx = ndimage.distance_transform_edt(ids == 0, return_distances=False, return_indices=True)
    ids = np.where(mask, ids[idx[0], idx[1]], 0).astype(np.uint8)

    nan = np.isnan(dem)
    print(f"setka {W}x{H}, {res} m; niqob ichida bo'sh DEM: {(nan & mask).sum()} tugun")
    # Katta DEM bo'shliqlari (Shohimardonning ~38 km2 qismi) chizilmaydi: to'ldirilgan sirt soxta tekislik bo'lardi
    lab, _ = ndimage.label(nan & mask)
    sizes = np.bincount(lab.ravel())
    big = np.isin(lab, np.nonzero(sizes * res * res > 0.5e6)[0]) & (lab > 0)
    mask &= ~big
    ids[big] = 0
    print(f"DEM'siz qoldirilgan joy: {big.sum() * res * res / 1e6:.1f} km2")
    # portalda "DEM yo'q" yozuvi: viloyat ichidagi (chekka halqasiz) 5 km2 dan katta bo'shliqlar
    strict = rasterize(((gm, 1) for gm in gt.geometry), out_shape=(H, W), transform=dst_tr, fill=0, dtype="uint8") > 0
    vl, nv = ndimage.label(strict & nan)
    voids = []
    for k in range(1, nv + 1):
        comp = vl == k
        km2 = comp.sum() * res * res / 1e6
        if km2 < 5:
            continue
        i, j = np.unravel_index(np.argmax(ndimage.distance_transform_edt(comp)), comp.shape)
        voids.append({"x": round(x0 + j * res), "y": round(y0 - i * res), "km2": round(km2, 1)})
    print("DEM yo'q yozuvlari:", voids)
    idx = ndimage.distance_transform_edt(nan, return_distances=False, return_indices=True)
    dem = dem[idx[0], idx[1]]

    dm = np.round(dem * 10).astype(np.int32)  # detsimetr
    d = np.diff(dm.ravel(), prepend=0)
    assert np.abs(d).max() < 32767, "delta int16 ga sig'madi"
    zin = dem[mask]
    zmin, zmax = float(zin.min()), float(zin.max())
    print(f"balandlik {zmin:.1f}..{zmax:.1f} m")

    # tuman ma'lumotlari
    tum = []
    for i, r in gt.iterrows():
        gm = r.geometry
        big = max(gm.geoms, key=lambda p: p.area) if gm.geom_type == "MultiPolygon" else gm
        lp = polylabel(big, tolerance=50)
        z = dem[ids == i + 1]
        bx = gm.bounds
        tum.append({
            "name": r["district"], "cyr": r["district_k"], "code": int(r["code"]),
            "area": round(gm.area / 1e6, 1),
            "zmin": round(float(z.min())), "zmax": round(float(z.max())), "zmean": round(float(z.mean())),
            "lx": round(lp.x), "ly": round(lp.y),
            "bbox": [round(v) for v in bx],
        })

    # chegaralar: umumiy chiziqlar bir marta, viloyat tashqi chegarasi alohida
    def lines_of(geom, tol, step):
        geom = shapely.line_merge(geom)
        parts = geom.geoms if hasattr(geom, "geoms") else [geom]
        out = []
        for ln in parts:
            ln = shapely.segmentize(ln.simplify(tol), step)
            c = np.asarray(ln.coords)[:, :2]
            out.append(np.round(c).astype(int).ravel().tolist())
        return out

    outer_geom = unary_union(gt.geometry.buffer(0))
    outer = outer_geom.boundary
    inner = unary_union([gm.boundary for gm in gt.geometry]).difference(outer.buffer(20))
    L_outer = lines_of(outer, 10, res / 2)
    L_inner = lines_of(inner, 10, res / 2)
    print(f"chiziqlar: tashqi {sum(len(l) for l in L_outer)//2}, ichki {sum(len(l) for l in L_inner)//2} nuqta")

    # koordinata jadvallari (har LL_STEP m da tugun, JS da bilinear): geografik va EPSG:3857
    LL_STEP = 2500.0
    gw, gh = int(math.ceil((W - 1) * res / LL_STEP)) + 1, int(math.ceil((H - 1) * res / LL_STEP)) + 1
    gx, gy = np.meshgrid(x0 + np.arange(gw) * LL_STEP, y0 - np.arange(gh) * LL_STEP)
    lon, lat = Transformer.from_crs(tm, "EPSG:4326", always_xy=True).transform(gx, gy)
    mx, my = Transformer.from_crs(tm, "EPSG:3857", always_xy=True).transform(gx, gy)

    # asl 4 m DEM bo'laklari (make_tiles.py): qaysi bo'lak borligi '0'/'1' qatori
    t4 = None
    meta = os.path.join(HERE, "dem4m", "meta.json")
    if os.path.exists(meta) and not a.no_tiles:
        t4 = json.load(open(meta))
        have = set(os.listdir(os.path.join(HERE, "dem4m")))
        t4["has"] = "".join("1" if f"{r}_{c}.bin" in have else "0" for r in range(t4["ny"]) for c in range(t4["nx"]))
        print(f"4 m bo'laklar: {t4['has'].count('1')} ta")

    # suv oqimi yo'llari (hydro_*.py natijasi): chiziqlar 50 m dan qisqa bo'laklarga bo'linadi (relyefga yotishi uchun),
    # koordinatalar butun metr, int32 delta + gzip; har chiziq uchun nuqtalar soni, Strahler tartibi, havza km2
    oqim = None
    gp = os.path.join(HERE, "hydro", "suv_oqimi.gpkg")
    if os.path.exists(gp) and not a.no_streams:
        so = gpd.read_file(gp).to_crs(tm)
        if "manba" in so:  # portalda DEM yo'q joy (Shohimardon) teshik, u yerdagi GLO-30 chiziqlari chizilmaydi
            so = so[so["manba"] != "GLO-30"]
        so = so.sort_values("maydon_km2", kind="stable")  # kichiklari avval: katta daryo irmoqlar ustidan chiziladi
        cnt, xy = [], []
        for ln in so.geometry:
            # D8 zinapoyasini yo'qotish: soddalashtirish + Chaikin silliqlash (uchlari joyida, tutashuvlar saqlanadi)
            c = np.asarray(ln.simplify(10).coords)[:, :2]
            for _ in range(3):
                if len(c) < 3:
                    break
                p0, p1 = c[:-1], c[1:]
                mid = np.empty((2 * len(p0), 2))
                mid[0::2], mid[1::2] = 0.75 * p0 + 0.25 * p1, 0.25 * p0 + 0.75 * p1
                c = np.vstack([c[:1], mid, c[-1:]])
            sm = shapely.LineString(c).simplify(1.5)
            c = np.round(np.asarray(shapely.segmentize(sm, 50).coords)[:, :2]).astype(np.int64)
            cnt.append(len(c))
            xy.append(c)
        xy = np.concatenate(xy)
        d32 = np.diff(xy, axis=0, prepend=np.zeros((1, 2), np.int64)).ravel()  # x va y alohida delta
        assert np.abs(d32).max() < 2**31
        # q: chiziq oxiridan tarmoq chiqishigacha masofa (m) — animatsiya fazasi tutashuvlarda uzilmasin
        oqim = {"n": cnt, "o": so["tartib"].astype(int).tolist(), "a": np.round(so["maydon_km2"], 2).tolist(),
                "q": np.round(so["quyi_m"], 1).tolist(), "u": np.round(so["uzunlik_m"], 1).tolist(),
                "xy": b64gz(d32.astype("<i4"))}
        print(f"suv oqimi: {len(so)} chiziq, {len(xy)} nuqta")

    data = {
        "region": g["region_nam"].iloc[0],
        "lon0": lon0, "lat0": lat0,
        "w": W, "h": H, "res": res, "x0": x0, "y0": y0,
        "zmin": round(zmin, 1), "zmax": round(zmax, 1),
        "dem": b64gz(d.astype("<i2")),
        "ids": b64gz(ids),
        "ll": {"step": LL_STEP, "w": gw, "h": gh,
               "lat": np.round(lat, 7).ravel().tolist(), "lon": np.round(lon, 7).ravel().tolist(),
               "mx": np.round(mx, 2).ravel().tolist(), "my": np.round(my, 2).ravel().tolist()},
        "t4": t4,
        "oqim": oqim,
        "voids": voids,
        "tum": tum, "outer": L_outer, "inner": L_inner,
    }
    js = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    tpl = open(os.path.join(HERE, "Fargona_3D.template.html"), encoding="utf-8").read()
    three = open(os.path.join(HERE, "vendor", "three-r128.min.js"), encoding="utf-8").read()
    html = tpl.replace("/*__THREE__*/", three).replace("/*__DATA__*/null", js)
    if a.og_image:  # havola Telegram va boshqalarda rasm bilan ko'rinishi uchun (to'liq URL)
        html = html.replace("<!--__OGIMG__-->", f'<meta property="og:image" content="{a.og_image}">')
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"yozildi: {a.out} ({os.path.getsize(a.out)/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
