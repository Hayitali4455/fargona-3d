# -*- coding: utf-8 -*-
"""Suv oqimi tahlili uchun DEM tayyorlash (1-qadam).

Asl 4 m DEM (EPSG:3857) overview /4 orqali o'qiladi va portal bilan bir xil
mahalliy Transverse Mercator ga 20 m qadamda (o'rtacha qiymat) o'tkaziladi.
Viloyatdan tashqarisi nodata. Viloyat ichidagi kichik DEM bo'shliqlari
eng yaqin qiymatlardan to'ldiriladi, kattalari nodata qoladi.

Natija: hydro/dem20.tif (float32, nodata -9999)
"""
import json
import math
import os

import geopandas as gpd
import numpy as np
import rasterio
from affine import Affine
from pyproj import CRS
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.warp import reproject
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
DEM = r"D:\Farg`ona\Farg`ona.tif"
SHP = r"D:\Farg`ona\tuman.shp"
OUT = os.path.join(HERE, "hydro")
RES = 20.0
MAX_FILL_M2 = 0.5e6  # shundan katta DEM bo'shlig'i to'ldirilmaydi
LAT0, LON0 = 40.45, 71.27  # build.py dagi markaz bilan bir xil
TM = CRS.from_proj4(f"+proj=tmerc +lat_0={LAT0} +lon_0={LON0} +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs")


def main():
    os.makedirs(OUT, exist_ok=True)
    gt = gpd.read_file(SHP).to_crs(TM)
    gt["geometry"] = gt.geometry.make_valid()
    minx, miny, maxx, maxy = gt.total_bounds
    x0 = math.floor(minx / RES) * RES - RES
    y1 = math.ceil(maxy / RES) * RES + RES
    W = int(math.ceil((maxx - x0) / RES)) + 1
    H = int(math.ceil((y1 - miny) / RES)) + 1
    tr = Affine(RES, 0, x0, 0, -RES, y1)  # piksel chegarasi bo'yicha

    with rasterio.open(DEM) as s:
        f = 4
        oh, ow = s.height // f, s.width // f
        src = s.read(1, out_shape=(oh, ow), resampling=Resampling.average).astype(np.float32)
        src_tr = s.transform * Affine.scale(s.width / ow, s.height / oh)
        src_crs, nod = s.crs, s.nodata
    src[(src == nod) | (src < 100)] = np.nan
    dem = np.full((H, W), np.nan, np.float32)
    reproject(src, dem, src_transform=src_tr, src_crs=src_crs, dst_transform=tr, dst_crs=TM,
              resampling=Resampling.average, src_nodata=np.nan, dst_nodata=np.nan)

    inside = rasterize(((g, 1) for g in gt.geometry), out_shape=(H, W), transform=tr, fill=0, dtype="uint8").astype(bool)
    voids = inside & np.isnan(dem)
    print(f"setka {W}x{H} ({RES:.0f} m), viloyat ichida {inside.sum():,} katak, DEM bo'shlig'i: {voids.sum():,} katak")
    # Kichik bo'shliqlar (chegaradagi tasmalar) to'ldiriladi; kattalari (Shohimardon ~38 km2) nodata qoladi:
    # u yerda to'ldirilgan sirt soxta tekislik bo'lib, oqim yo'llari o'ylab topilgan bo'lardi
    lab, n = ndimage.label(voids)
    sizes = np.bincount(lab.ravel())
    big = np.isin(lab, np.nonzero(sizes * RES * RES > MAX_FILL_M2)[0]) & voids
    big_km2 = [round(float(sz) * RES * RES / 1e6, 2) for sz in sorted(sizes[1:], reverse=True) if sz * RES * RES > MAX_FILL_M2]
    small = voids & ~big
    print(f"to'ldirildi: {small.sum():,} katak; nodata qoldi: {big.sum():,} katak ({big_km2} km2)")
    if small.any():
        idx = ndimage.distance_transform_edt(np.isnan(dem), return_distances=False, return_indices=True)
        dem = np.where(small, dem[idx[0], idx[1]], dem)
    dem = np.where(inside & ~big, dem, -9999).astype(np.float32)

    prof = dict(driver="GTiff", width=W, height=H, count=1, dtype="float32", crs=TM, transform=tr,
                nodata=-9999, compress="lzw", tiled=True, blockxsize=512, blockysize=512, BIGTIFF="IF_SAFER")
    with rasterio.open(os.path.join(OUT, "dem20.tif"), "w", **prof) as d:
        d.write(dem, 1)
    z = dem[dem > -9999]
    meta = {"res": RES, "x0": x0, "y1": y1, "w": W, "h": H, "lat0": LAT0, "lon0": LON0,
            "voids_filled": int(small.sum()), "voids_left_km2": big_km2, "zmin": float(z.min()), "zmax": float(z.max())}
    json.dump(meta, open(os.path.join(OUT, "dem20.json"), "w"), indent=1)
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
