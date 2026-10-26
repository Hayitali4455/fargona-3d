# -*- coding: utf-8 -*-
"""Suv oqimi tahlili (2-qadam): ArcGIS Pro Spatial Analyst.

ArcGIS Pro python (arcgispro-py3) bilan ishga tushiriladi:
  "C:\\Program Files\\ArcGIS\\Pro\\bin\\Python\\envs\\arcgispro-py3\\python.exe" hydro_arc.py

- Derive Continuous Flow (D8): chuqurliklar to'ldirilmaydi, oqim ulardan eng past
  chiqish nuqtasi orqali davom etadi (tekis va to'siqli vodiyda soxta "ko'l" yo'q).
- Oqim tarmog'i: yig'ilish >= THRESH_KM2 bo'lgan kataklar, Strahler tartibi,
  Stream to Feature (SIMPLIFY).
Natija: hydro/fdir_<tag>.tif, acc_<tag>.tif, order_<tag>.tif, oqim_raw_<tag>.shp
(standart: --dem dem20_ext.tif --tag ext — viloyat tashqarisidagi yuqori havzalar bilan)
"""
import argparse
import os
import time

import arcpy
from arcpy.sa import Con, DeriveContinuousFlow, StreamOrder, StreamToFeature

HERE = os.path.dirname(os.path.abspath(__file__))
H = os.path.join(HERE, "hydro")
THRESH_KM2 = 1.0
ap = argparse.ArgumentParser()
ap.add_argument("--dem", default="dem20_ext.tif", help="hydro/ ichidagi DEM (dem20.tif yoki dem20_ext.tif)")
ap.add_argument("--tag", default="ext", help="natija fayllari qo'shimchasi")
args = ap.parse_args()

try:  # og'ir hisob boshqa ishlarga xalaqit bermasin
    import psutil
    psutil.Process().nice(psutil.IDLE_PRIORITY_CLASS)
except Exception:
    pass

arcpy.CheckOutExtension("Spatial")
arcpy.env.overwriteOutput = True
arcpy.env.workspace = H
arcpy.env.scratchWorkspace = H
dem = os.path.join(H, args.dem)
desc = arcpy.Describe(dem)
cell = desc.meanCellWidth
arcpy.env.snapRaster = dem
arcpy.env.extent = dem
arcpy.env.cellSize = dem
arcpy.env.outputCoordinateSystem = desc.spatialReference
arcpy.env.parallelProcessingFactor = "75%"
thr = int(round(THRESH_KM2 * 1e6 / (cell * cell)))
print(f"DEM {desc.width}x{desc.height}, katak {cell} m, chegara {THRESH_KM2} km2 = {thr} katak", flush=True)

t = time.time()
fdir = os.path.join(H, f"fdir_{args.tag}.tif")
acc = DeriveContinuousFlow(dem, out_flow_direction_raster=fdir, flow_direction_type="D8")
acc.save(os.path.join(H, f"acc_{args.tag}.tif"))
print(f"oqim yo'nalishi va yig'ilish: {time.time() - t:.0f} s", flush=True)

t = time.time()
streams = Con(arcpy.Raster(os.path.join(H, f"acc_{args.tag}.tif")) >= thr, 1)
order = StreamOrder(streams, fdir, "STRAHLER")
order.save(os.path.join(H, f"order_{args.tag}.tif"))
out = os.path.join(H, f"oqim_raw_{args.tag}.shp")
StreamToFeature(order, fdir, out, "SIMPLIFY")
n = int(arcpy.management.GetCount(out)[0])
print(f"oqim chiziqlari: {n} ta, {time.time() - t:.0f} s", flush=True)
