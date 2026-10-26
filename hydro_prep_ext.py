# -*- coding: utf-8 -*-
"""Suv oqimi uchun kengaytirilgan DEM (1b-qadam).

Viloyat DEM i chegarada kesilgan, shuning uchun Qirg'iziston tomondan kiradigan
daryolarning (So'x, Isfayramsoy, Shohimardonsoy, Isfara ...) yuqori havzasi
hisobga kirmaydi. Bu skript dem20.tif ni tashqarida Copernicus GLO-30 bilan
to'ldiradi (AWS ochiq COG, 2x overview ~60 m, bilinear) va tuzatadi:
chegara bo'yidagi umumiy kataklarda ikki DEM farqining medianasi ayiriladi.

Oqim yo'llari keyin faqat viloyat ichida ko'rsatiladi; tashqi DEM faqat
yuqori havza maydonini hisoblash uchun.

Natija: hydro/dem20_ext.tif, hydro/dem20_ext.json
"""
import json
import math
import os

import numpy as np
import rasterio
from affine import Affine
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.warp import reproject
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
H = os.path.join(HERE, "hydro")
LON0, LON1, LAT0, LAT1 = 70.20, 72.45, 39.30, 41.08  # janubdagi suv ayirg'ichgacha
COG = "/vsicurl/https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N{la:02d}_00_E{lo:03d}_00_DEM/Copernicus_DSM_COG_10_N{la:02d}_00_E{lo:03d}_00_DEM.tif"


def main():
    with rasterio.open(os.path.join(H, "dem20.tif")) as d:
        loc, tr, crs, res = d.read(1), d.transform, d.crs, d.res[0]
    # kengaytirilgan setka: dem20 bilan bir xil katak chegaralari
    t = Transformer.from_crs(4326, crs, always_xy=True)
    xs, ys = t.transform([LON0, LON1, LON0, LON1, (LON0 + LON1) / 2, (LON0 + LON1) / 2], [LAT0, LAT0, LAT1, LAT1, LAT0, LAT1])
    ex0 = tr.c - math.ceil((tr.c - min(xs)) / res) * res
    ey1 = tr.f + math.ceil((max(ys) - tr.f) / res) * res
    W = int(math.ceil((max(xs) - ex0) / res))
    Hh = int(math.ceil((ey1 - min(ys)) / res))
    etr = Affine(res, 0, ex0, 0, -res, ey1)
    print(f"kengaytirilgan setka {W}x{Hh} ({W * res / 1e3:.0f} x {Hh * res / 1e3:.0f} km)", flush=True)

    glo = np.full((Hh, W), np.nan, np.float32)
    env = dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif", GDAL_HTTP_MAX_RETRY="4", GDAL_HTTP_RETRY_DELAY="3")
    with rasterio.Env(**env):
        for la in range(math.floor(LAT0), math.floor(LAT1) + 1):
            for lo in range(math.floor(LON0), math.floor(LON1) + 1):
                u = COG.format(la=la, lo=lo)
                part = np.full((Hh, W), np.nan, np.float32)
                with rasterio.open(u, OVERVIEW_LEVEL=0) as s:  # 2x overview (~60 m)
                    a = s.read(1).astype(np.float32)
                    reproject(a, part, src_transform=s.transform, src_crs=s.crs, dst_transform=etr, dst_crs=crs,
                              resampling=Resampling.bilinear, dst_nodata=np.nan)
                glo = np.where(np.isnan(glo), part, glo)
                print(f"  N{la} E{lo:03d}: tayyor", flush=True)

    # mahalliy dem20 ni kengaytirilgan setkaga joylash (kataklar mos)
    c0 = int(round((tr.c - ex0) / res)); r0 = int(round((ey1 - tr.f) / res))
    big = np.full((Hh, W), np.nan, np.float32)
    lv = np.where(loc > -9999, loc, np.nan)
    big[r0:r0 + loc.shape[0], c0:c0 + loc.shape[1]] = lv
    have = ~np.isnan(big)

    # vertikal moslash: viloyat chegarasidan 2 km ichkaridagi tasmada farq medianasi
    sub = have[r0:r0 + loc.shape[0], c0:c0 + loc.shape[1]]
    near = np.zeros_like(have)
    near[r0:r0 + loc.shape[0], c0:c0 + loc.shape[1]] = sub & (ndimage.distance_transform_cdt(sub, metric="chessboard") <= 100)
    band = near & ~np.isnan(glo)
    off = float(np.median(glo[band] - big[band]))
    mad = float(np.median(np.abs(glo[band] - big[band] - off)))
    print(f"GLO-30 - viloyat DEM (chegara tasmasi, {band.sum():,} katak): mediana {off:+.1f} m, MAD {mad:.1f} m", flush=True)
    ext = np.where(have, big, glo - off)
    ext = np.where(np.isnan(ext), -9999, ext).astype(np.float32)

    prof = dict(driver="GTiff", width=W, height=Hh, count=1, dtype="float32", crs=crs, transform=etr, nodata=-9999,
                compress="lzw", tiled=True, blockxsize=512, blockysize=512, BIGTIFF="IF_SAFER")
    with rasterio.open(os.path.join(H, "dem20_ext.tif"), "w", **prof) as d:
        d.write(ext, 1)
    json.dump({"w": W, "h": Hh, "x0": ex0, "y1": ey1, "res": res, "glo_offset_m": round(off, 2), "glo_mad_m": round(mad, 2),
               "lonlat": [LON0, LAT0, LON1, LAT1], "source_outside": "Copernicus GLO-30 DSM (2x overview), AWS open data"},
              open(os.path.join(H, "dem20_ext.json"), "w"), indent=1)
    print("yozildi: hydro/dem20_ext.tif")


if __name__ == "__main__":
    main()
