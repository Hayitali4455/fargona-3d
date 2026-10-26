# -*- coding: utf-8 -*-
"""Suv oqimi tahlili (3-qadam): chiziqlarni boyitish, saqlash va tekshirish.

- Kengaytirilgan DEM tarmog'i viloyat chegarasi bo'yicha kesiladi.
- Har chiziqqa: Strahler tartibi, yuqoridagi havza maydoni (km2, chiziq bo'ylab
  eng katta yig'ilish, viloyatdan tashqaridagi yuqori havza bilan), uzunlik, tuman,
  manba (viloyat DEM i yoki DEM yo'q joyda GLO-30).
- hydro/suv_oqimi.gpkg (mahalliy TM) va hydro/suv_oqimi_3857.shp (asl DEM CRS i).
- OSM daryolari bilan solishtirish va chegara (threshold) sezgirligi jadvali.
"""
import argparse
import json
import os

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import rasterio.features
import shapely

HERE = os.path.dirname(os.path.abspath(__file__))
H = os.path.join(HERE, "hydro")
SHP = r"D:\Farg`ona\tuman.shp"
NEAR_M = 150  # OSM daryosi modeldagi oqimga shu masofada bo'lsa "mos" deb olinadi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="ext", help="hydro_arc.py natijasi qo'shimchasi")
    tag = ap.parse_args().tag
    meta = json.load(open(os.path.join(H, "dem20.json")))
    with rasterio.open(os.path.join(H, f"acc_{tag}.tif")) as r:
        acc, tr, crs = r.read(1, masked=True).filled(0), r.transform, r.crs
        cell = r.res[0]
    raw = gpd.read_file(os.path.join(H, f"oqim_raw_{tag}.shp")).set_crs(crs, allow_override=True)

    # faqat viloyat ichidagi qismlar (kengaytirilgan DEM da tashqaridagi tarmoq ham bor)
    tum = gpd.read_file(SHP).to_crs(crs)[["district", "geometry"]]
    tum["geometry"] = tum.geometry.make_valid()
    region = tum.geometry.union_all()
    s = raw.clip(region).explode(index_parts=False)
    s = s[s.geom_type == "LineString"]
    s = s[s.length >= 20].reset_index(drop=True)

    # Havza: chiziq bo'ylab (har 10 m) eng katta yig'ilish. Ikkala uchidan 30 m olinmaydi: chiziq
    # qo'shilish katagida tugaydi va u yerdagi yig'ilish quyiladigan daryoniki (yo'nalishdan qat'i nazar).
    inv = ~tr
    areas = []
    for g in s.geometry:
        L = g.length
        d = np.arange(30.0, L - 30 + 1e-6, 10.0) if L > 70 else np.array([L / 2])
        pts = shapely.line_interpolate_point(g, d)
        cols, rows = inv * (shapely.get_x(pts), shapely.get_y(pts))
        rows = np.clip(np.floor(rows).astype(int), 0, acc.shape[0] - 1)
        cols = np.clip(np.floor(cols).astype(int), 0, acc.shape[1] - 1)
        areas.append((acc[rows, cols].max() + 1) * cell * cell / 1e6)
    mid = gpd.GeoDataFrame(geometry=s.geometry.interpolate(0.5, normalized=True), crs=crs)
    j = gpd.sjoin(mid, tum, how="left", predicate="within")
    j = j[~j.index.duplicated()]
    # viloyat DEM i bo'lmagan joy (Shohimardon) da chiziq GLO-30 bo'yicha
    with rasterio.open(os.path.join(H, "dem20.tif")) as r:
        loc = r.read(1)
        lc, lr = (~r.transform) * (mid.geometry.x.values, mid.geometry.y.values)
        lr = np.clip(np.floor(lr).astype(int), 0, loc.shape[0] - 1)
        lc = np.clip(np.floor(lc).astype(int), 0, loc.shape[1] - 1)
        src = np.where(loc[lr, lc] > -9999, "Fargona DEM", "GLO-30")
    out = gpd.GeoDataFrame({
        "tartib": s["grid_code"].astype(int),
        "maydon_km2": np.round(areas, 2),
        "uzunlik_m": np.round(s.length, 1),
        "tuman": j["district"].fillna(""),
        "manba": src,
    }, geometry=s.geometry, crs=crs)
    out.to_file(os.path.join(H, "suv_oqimi.gpkg"), driver="GPKG")
    out.to_crs(3857).to_file(os.path.join(H, "suv_oqimi_3857.shp"), encoding="utf-8")

    print(f"chiziqlar: {len(out)}, jami {out.length.sum() / 1e3:.0f} km, Strahler 1..{out.tartib.max()}")
    print("tartib bo'yicha:", out.groupby("tartib")["uzunlik_m"].agg(["count", "sum"]).assign(sum=lambda d: (d["sum"] / 1e3).round(0)).to_dict("index"))
    rows = []
    for a in (1, 5, 25, 100, 500):
        sel = out[out.maydon_km2 >= a]
        rows.append({"chegara_km2": a, "chiziq": len(sel), "uzunlik_km": round(sel.length.sum() / 1e3)})
    print(pd.DataFrame(rows).to_string(index=False))

    # OSM bilan solishtirish: faqat DEM mavjud hudud ichidagi OSM daryolari
    osm = gpd.read_file(os.path.join(H, "osm_waterways_tm.gpkg")).to_crs(crs)
    with rasterio.open(os.path.join(H, "dem20.tif")) as r:
        valid = r.read(1) > -9999
        vpoly = shapely.union_all([shapely.geometry.shape(gm) for gm, v in rasterio.features.shapes(valid.astype("uint8"), mask=valid, transform=r.transform) if v == 1])
    rivers = osm[osm.waterway == "river"].clip(vpoly)
    rl = rivers.length.sum()
    res = {}
    for a in (1, 5, 25):
        buf = out[out.maydon_km2 >= a].buffer(NEAR_M).union_all()
        res[a] = rivers.intersection(buf).length.sum() / rl
    print(f"OSM daryolari (DEM hududida {rl / 1e3:.0f} km): modeldagi oqimdan {NEAR_M} m ichida:",
          {f">={a} km2": f"{v:.0%}" for a, v in res.items()})
    big = out[out.maydon_km2 >= 25]
    anyw = osm[osm.waterway.isin(["river", "stream", "canal", "drain", "ditch"])].buffer(NEAR_M).union_all()
    print(f"model (>=25 km2, {big.length.sum() / 1e3:.0f} km) OSM suv yo'lidan {NEAR_M} m ichida: "
          f"{big.intersection(anyw).length.sum() / big.length.sum():.0%}")
    for nm in ["Sirdaryo", "Исфайрам-Сай", "Soʻx", "Исфара", "Маргилан-сай", "Shohimardonsoy"]:
        rv = rivers[rivers["name"] == nm]
        if len(rv):
            buf = out[out.maydon_km2 >= 5].buffer(NEAR_M).union_all()
            print(f"  {nm}: {rv.length.sum() / 1e3:.0f} km, mos {rv.intersection(buf).length.sum() / rv.length.sum():.0%}")
    json.dump({"tag": tag, "thresholds": rows, "osm_match": res, "near_m": NEAR_M, "voids_left_km2": meta["voids_left_km2"]},
              open(os.path.join(H, "tekshiruv.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
