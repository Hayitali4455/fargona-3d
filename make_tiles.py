# -*- coding: utf-8 -*-
"""Asl 4 m DEM ni bosilgan nuqta balandligi uchun bo'laklarga ajratish.

Har bo'lak 512x512 asl piksel (EPSG:3857 setkasi o'zgarmaydi), qiymat detsimetrda
(0 = nodata), har qator o'z ichida farq (delta) bilan int16, gzip.
Faqat kamida bitta haqiqiy pikseli bor bo'laklar yoziladi: dem4m/<qator>_<ustun>.bin
To'liq va to'g'ri ochiladigan mavjud bo'laklar qayta yozilmaydi (to'xtab qolsa davom ettirish mumkin).

Ishga tushirish:  python make_tiles.py [--workers 4]
"""
import argparse
import gzip
import json
import os
from multiprocessing import Pool

import numpy as np
import rasterio
from rasterio.windows import Window

HERE = os.path.dirname(os.path.abspath(__file__))
DEM = r"D:\Farg`ona\Farg`ona.tif"
TS = 512
OUT = os.path.join(HERE, "dem4m")


def low_priority():  # og'ir o'qish boshqa ishlarga (ArcGIS va h.k.) xalaqit bermasin
    try:
        import psutil
        psutil.Process().nice(psutil.IDLE_PRIORITY_CLASS)
    except Exception:
        pass


def ok_tile(path):
    try:
        return len(gzip.decompress(open(path, "rb").read())) == TS * TS * 2
    except Exception:
        return False


def do_row(r):
    n = size = 0
    with rasterio.open(DEM) as s:
        nod, nx = s.nodata, -(-s.width // TS)
        for c in range(nx):
            path = os.path.join(OUT, f"{r}_{c}.bin")
            if os.path.exists(path) and ok_tile(path):
                n += 1
                size += os.path.getsize(path)
                continue
            w = Window(c * TS, r * TS, min(TS, s.width - c * TS), min(TS, s.height - r * TS))
            a = s.read(1, window=w)
            v = (a != nod) & (a > 100)
            if not v.any():
                continue
            q = np.zeros((TS, TS), np.int32)
            q[: a.shape[0], : a.shape[1]] = np.where(v, np.round(a * 10), 0)
            d = np.diff(q, axis=1, prepend=0)
            assert np.abs(d).max() < 32767
            b = gzip.compress(d.astype("<i2").tobytes(), 6, mtime=0)
            with open(path + ".tmp", "wb") as f:
                f.write(b)
            os.replace(path + ".tmp", path)
            n += 1
            size += len(b)
    return r, n, size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    low_priority()
    os.makedirs(OUT, exist_ok=True)
    with rasterio.open(DEM) as s:
        nx, ny = -(-s.width // TS), -(-s.height // TS)
        meta = {"left": s.bounds.left, "top": s.bounds.top, "res": s.res[0], "ts": TS, "nx": nx, "ny": ny}
    tot_n = tot_s = done = 0
    with Pool(a.workers, initializer=low_priority) as pool:
        for r, n, size in pool.imap_unordered(do_row, range(ny)):
            done += 1
            tot_n += n
            tot_s += size
            print(f"{done}/{ny} qator tayyor (oxirgisi {r}): {tot_n} bo'lak, {tot_s / 1e6:.0f} MB", flush=True)
    with open(os.path.join(OUT, "meta.json"), "w") as f:
        json.dump(meta, f)
    print("tayyor:", tot_n, "bo'lak", round(tot_s / 1e6), "MB")


if __name__ == "__main__":
    main()
