# -*- coding: utf-8 -*-
"""Portal uchun yer qoplami va tuproq qatlamlari.

Manbalar (ochiq, internetdan oyna bo'yicha o'qiladi):
- Yer qoplami: ESA WorldCover 2021 v200, 10 m (CC BY 4.0) — 2x overview (~20 m) o'qilib,
  portal TM setkasiga 40 m da eng ko'p uchragan sinf (mode) bilan o'tkaziladi.
- Tuproq: ISRIC SoilGrids 2.0, 250 m (CC BY 4.0) — WRB guruhi (MostProbable), loy/qum/chang,
  pH(H2O), organik uglerod; 0-30 sm qatlam uchun qalinlik bo'yicha o'rtacha (5/10/15 sm).

Natija: layers/yerqoplami.bin (gzip, uint8 sinf raqami), layers/qatlamlar.json
(setkalar, legendalar, tumanlar statistikasi, tuproq rasterlari base64+gzip).

Ishga tushirish: python layers_build.py   (index.html dagi setka parametrlaridan foydalanadi)
"""
import base64
import gzip
import json
import math
import os
import re
import urllib.request

import geopandas as gpd
import numpy as np
import rasterio
from affine import Affine
from pyproj import CRS
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.warp import reproject
from rasterio.windows import from_bounds

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "layers")
SHP = r"D:\Farg`ona\tuman.shp"
ENV = dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.vrt",
           GDAL_HTTP_MAX_RETRY="5", GDAL_HTTP_RETRY_DELAY="5", GDAL_CACHEMAX=1024)
WC = "/vsicurl/https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{t}_Map.tif"
SG = "/vsicurl/https://files.isric.org/soilgrids/latest/data/{p}/{p}_{d}_mean.vrt"
WRB = "/vsicurl/https://files.isric.org/soilgrids/latest/data/wrb/MostProbable.vrt"

LC = [  # ESA WorldCover kodi, nomi, rangi (ESA rasmiy legendasi)
    (10, "Daraxtzor", "#006400"), (20, "Butazor", "#ffbb22"), (30, "O‘tloq", "#ffff4c"),
    (40, "Ekin maydoni", "#f096ff"), (50, "Qurilish (aholi punktlari)", "#fa0000"),
    (60, "Ochiq / siyrak o‘simlikli yer", "#b4b4b4"), (70, "Qor va muz", "#f0f0f0"),
    (80, "Suv havzalari", "#0064c8"), (90, "O‘tli botqoqlik", "#0096a0"), (95, "Mangrlar", "#00cf75"),
    (100, "Mox va lishayniklar", "#fae6a0")]
TEX = [  # USDA mexanik tarkib sinflari
    ("Qum", "sand", "#f3e2a0"), ("Qumoqli qum", "loamy sand", "#e6c97a"), ("Qumli qumoq", "sandy loam", "#d2a85c"),
    ("Qumoq", "loam", "#a67c45"), ("Changli qumoq", "silt loam", "#c9b38a"), ("Chang", "silt", "#e0d6b8"),
    ("Qumli soz-qumoq", "sandy clay loam", "#c57b57"), ("Soz-qumoq", "clay loam", "#8f5a3c"),
    ("Changli soz-qumoq", "silty clay loam", "#9e8a6a"), ("Qumli soz", "sandy clay", "#b0543c"),
    ("Changli soz", "silty clay", "#7a6a55"), ("Soz", "clay", "#5e3a2a")]
WRB_UZ = {"Calcisols": "karbonatli", "Gypsisols": "gipsli", "Fluvisols": "allyuvial", "Solonchaks": "sho‘rxok",
          "Solonetz": "sho‘rtob", "Regosols": "rivojlanmagan", "Leptosols": "yupqa, toshloq", "Cambisols": "o‘zgargan",
          "Kastanozems": "kashtan", "Chernozems": "qora tuproq", "Phaeozems": "qoramtir", "Arenosols": "qumli",
          "Gleysols": "glеyli", "Luvisols": "loyqa-illyuvial", "Durisols": "kremniyli", "Anthrosols": "madaniy"}


def b64gz(a):
    return base64.b64encode(gzip.compress(np.ascontiguousarray(a).tobytes(), 9)).decode("ascii")


def usda(cl, si, sa):
    """USDA mexanik tarkib uchburchagi -> 1..12 (TEX tartibida), 0 = ma'lumot yo'q."""
    out = np.zeros(cl.shape, np.uint8)
    rules = [
        (si + 1.5 * cl < 15, 1),
        ((si + 1.5 * cl >= 15) & (si + 2 * cl < 30), 2),
        (((cl >= 7) & (cl < 20) & (sa > 52) & (si + 2 * cl >= 30)) | ((cl < 7) & (si < 50) & (si + 2 * cl >= 30)), 3),
        ((cl >= 7) & (cl < 27) & (si >= 28) & (si < 50) & (sa <= 52), 4),
        (((si >= 50) & (cl >= 12) & (cl < 27)) | ((si >= 50) & (si < 80) & (cl < 12)), 5),
        ((si >= 80) & (cl < 12), 6),
        ((cl >= 20) & (cl < 35) & (si < 28) & (sa > 45), 7),
        ((cl >= 27) & (cl < 40) & (sa > 20) & (sa <= 45), 8),
        ((cl >= 27) & (cl < 40) & (sa <= 20), 9),
        ((cl >= 35) & (sa > 45), 10),
        ((cl >= 40) & (si >= 40), 11),
        ((cl >= 40) & (sa <= 45) & (si < 40), 12),
    ]
    for cond, k in reversed(rules):  # birinchi mos kelgan qoida ustun bo'lsin
        out[cond] = k
    return out


def grid(res, ext):
    x0, y1, wm, hm = ext
    w, h = int(math.ceil(wm / res)), int(math.ceil(hm / res))
    return w, h, Affine(res, 0, x0, 0, -res, y1)


def main():
    os.makedirs(OUT, exist_ok=True)
    html = open(os.path.join(HERE, "index.html"), encoding="utf-8").read()
    i = html.index("const D = ") + 10
    D = json.loads(html[i:html.index(";\n(async function main", i)])
    tm = CRS.from_proj4(f"+proj=tmerc +lat_0={D['lat0']} +lon_0={D['lon0']} +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs")
    # portal setkasi bilan bir xil qamrov: chap-yuqori burchak, eni, bo'yi (m)
    ext = (D["x0"] - D["res"] / 2, D["y0"] + D["res"] / 2, D["w"] * D["res"], D["h"] * D["res"])
    g = gpd.read_file(SHP).to_crs(tm)
    g["geometry"] = g.geometry.make_valid()
    ll = g.to_crs(4326).total_bounds + np.array([-0.02, -0.02, 0.02, 0.02])

    def districts(tr, w, h):
        return rasterize(((gm, k + 1) for k, gm in enumerate(g.geometry)), out_shape=(h, w), transform=tr, fill=0, dtype="uint8")

    meta = {"ext": ext, "districts": [{"code": int(c), "name": n} for c, n in zip(g["code"], g["district"])]}

    # ---------------- Yer qoplami ----------------
    W, H, tr = grid(40.0, ext)
    lc = np.zeros((H, W), np.uint8)
    with rasterio.Env(**ENV):
        for t in ("N39E069", "N39E072"):
            with rasterio.open(WC.format(t=t)) as s:
                b = s.bounds
                bx = (max(ll[0], b.left), max(ll[1], b.bottom), min(ll[2], b.right), min(ll[3], b.top))
                if bx[0] >= bx[2] or bx[1] >= bx[3]:
                    continue
                win = from_bounds(*bx, s.transform).round_offsets().round_lengths()
                f = 2  # ~20 m overview
                a = s.read(1, window=win, out_shape=(int(win.height // f), int(win.width // f)), resampling=Resampling.nearest)
                wtr = s.window_transform(win) * Affine.scale(win.width / a.shape[1], win.height / a.shape[0])
                part = np.zeros((H, W), np.uint8)
                reproject(a, part, src_transform=wtr, src_crs=s.crs, dst_transform=tr, dst_crs=tm,
                          resampling=Resampling.mode, src_nodata=0, dst_nodata=0)
                lc = np.where(lc == 0, part, lc)
                print(f"yer qoplami {t}: {a.shape} o'qildi", flush=True)
    code2i = {c: k + 1 for k, (c, _, _) in enumerate(LC)}
    lut = np.zeros(256, np.uint8)
    for c, k in code2i.items():
        lut[c] = k
    lci = lut[lc]
    dl = districts(tr, W, H)
    lci[dl == 0] = 0
    px_km2 = (40.0 * 40.0) / 1e6
    def lc_stats(mask):
        cnt = np.bincount(lci[mask], minlength=len(LC) + 1)[1:]
        tot = cnt.sum()
        return {"km2": [round(float(c) * px_km2, 2) for c in cnt], "pct": [round(100 * float(c) / tot, 2) if tot else 0 for c in cnt]}
    meta["lc"] = {"res": 40.0, "w": W, "h": H, "classes": [{"code": c, "name": n, "color": col} for c, n, col in LC],
                  "region": lc_stats(dl > 0), "tuman": [lc_stats(dl == k + 1) for k in range(len(g))],
                  "manba": "ESA WorldCover 2021 v200 (10 m), © ESA WorldCover project / Copernicus Sentinel data 2021, CC BY 4.0"}
    with open(os.path.join(OUT, "yerqoplami.bin"), "wb") as fo:
        fo.write(gzip.compress(lci.tobytes(), 9))
    print("yer qoplami viloyat %:", {LC[k][1]: p for k, p in enumerate(meta["lc"]["region"]["pct"]) if p >= 0.5}, flush=True)

    # ---------------- Tuproq ----------------
    W2, H2, tr2 = grid(250.0, ext)
    ds = districts(tr2, W2, H2)

    def warp(url, resampling, dtype=np.float32, nod=None):
        out = np.full((H2, W2), np.nan if dtype == np.float32 else 255, dtype)
        with rasterio.open(url) as s:
            reproject(rasterio.band(s, 1), out, dst_transform=tr2, dst_crs=tm, resampling=resampling,
                      src_nodata=s.nodata if nod is None else nod, dst_nodata=np.nan if dtype == np.float32 else 255)
        return out

    props = {}
    with rasterio.Env(**ENV):
        for p in ("clay", "sand", "silt", "phh2o", "soc"):
            layers = [warp(SG.format(p=p, d=d), Resampling.bilinear) for d in ("0-5cm", "5-15cm", "15-30cm")]
            props[p] = (5 * layers[0] + 10 * layers[1] + 15 * layers[2]) / 30
            print(f"tuproq {p}: o'qildi", flush=True)
        wrb = warp(WRB, Resampling.nearest, np.uint8)
    qml = urllib.request.urlopen("https://files.isric.org/soilgrids/latest/data/wrb/MostProbable.qml", timeout=60).read().decode()
    wrb_cls = [(int(v), lab, col) for v, lab, col in re.findall(r'paletteEntry value="(\d+)"[^>]*label="([^"]+)" color="(#[0-9a-fA-F]{6})"', qml)]
    clay, sand, silt = props["clay"] / 10, props["sand"] / 10, props["silt"] / 10  # g/kg -> %
    ph, soc = props["phh2o"] / 10, props["soc"] / 10  # pH, g/kg
    ok = (ds > 0) & np.isfinite(clay) & np.isfinite(sand) & np.isfinite(silt)
    tex = np.where(ok, usda(clay, silt, sand), 0).astype(np.uint8)
    wrbi = np.where((ds > 0) & (wrb != 255), wrb.astype(np.int16) + 1, 0).astype(np.uint8)  # 0 = yo'q

    def q8(a, scale):
        return np.where((ds > 0) & np.isfinite(a), np.clip(np.round(a * scale), 0, 254), 255).astype(np.uint8)

    def soil_stats(mask):
        m = mask & ok
        tc = np.bincount(tex[mask], minlength=13)[1:]
        wc = np.bincount(wrbi[mask], minlength=len(wrb_cls) + 1)[1:]
        mean = lambda a: round(float(np.nanmean(a[m])), 1) if m.any() else None
        return {"tex_pct": [round(100 * float(c) / max(1, tc.sum()), 1) for c in tc],
                "wrb_pct": [round(100 * float(c) / max(1, wc.sum()), 1) for c in wc],
                "clay": mean(clay), "sand": mean(sand), "silt": mean(silt), "ph": mean(ph), "soc": mean(soc)}
    meta["soil"] = {
        "res": 250.0, "w": W2, "h": H2, "depth": "0–30 sm",
        "tex": [{"name": n, "en": e, "color": c} for n, e, c in TEX],
        "wrb": [{"name": lab, "uz": WRB_UZ.get(lab, ""), "color": col} for _, lab, col in wrb_cls],
        "region": soil_stats(ds > 0), "tuman": [soil_stats(ds == k + 1) for k in range(len(g))],
        # rasterlar: 255 = ma'lumot yo'q; loy/qum/chang %, pH*20, organik uglerod g/kg*5
        "r": {"tex": b64gz(tex), "wrb": b64gz(wrbi), "clay": b64gz(q8(clay, 1)), "sand": b64gz(q8(sand, 1)),
              "silt": b64gz(q8(silt, 1)), "ph": b64gz(q8(ph, 20)), "soc": b64gz(q8(soc, 5))},
        "manba": "ISRIC SoilGrids 2.0 (250 m), CC BY 4.0",
    }
    rs = meta["soil"]["region"]
    print("tuproq viloyat: loy/qum/chang", rs["clay"], rs["sand"], rs["silt"], "pH", rs["ph"], "SOC", rs["soc"])
    print("mexanik tarkib %:", {TEX[k][0]: p for k, p in enumerate(rs["tex_pct"]) if p >= 0.5})
    print("WRB %:", {wrb_cls[k][1]: p for k, p in enumerate(rs["wrb_pct"]) if p >= 0.5})
    json.dump(meta, open(os.path.join(OUT, "qatlamlar.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("yozildi:", OUT, {f: os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT)})


if __name__ == "__main__":
    main()
