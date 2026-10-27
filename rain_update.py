# -*- coding: utf-8 -*-
"""Farg'ona tumanlari bo'yicha kunlik yog'ingarchilik (mm) — Open-Meteo.

Faqat standart kutubxona (GitHub Actions da har kuni ishlaydi).

- rain/nuqtalar.json: har tuman uchun bitta nuqta (tuman ichidagi eng "markaziy" nuqta).
- rain/yogin.json: 2017-01-01 dan kechagacha kunlik yog'in, 0.1 mm butun sonlarda.
  "tez" sanasidan boshlab qiymatlar operativ ob-havo modelidan (taxminiy); ERA5 arxivi
  chiqishi bilan (~5 kun) keyingi yangilanishda almashtiriladi.
- rain/soatlik/<yil>.json: o'sha nuqtalarda soatlik yog'in (0.1 mm, Toshkent vaqti). Open-Meteo qoidasi:
  "HH:00" qiymati oldingi bir soat (HH-1 .. HH) yig'indisi; kunlik qiymat = 00:00..23:00 yig'indisi.
  Ketma-ket nollar manfiy son bilan qisqartirilgan: -k = k ta 0 soat. Fayli yo'q yillar
  oddiy yangilanishda o'zi yuklab olinadi (yillar orasida ~7 min pauza).

Manba: Open-Meteo.com — ECMWF IFS (9 km) tarixiy ma'lumoti, CC BY 4.0. Bu model baholari:
quruq vodiyda stansiya o'lchovlaridan ko'proq chiqishi mumkin.

Ishga tushirish:  python rain_update.py            (oxirgi kunlarni yangilash)
                  python rain_update.py --toliq     (2017 dan qayta yuklash, ~1 soat: API soatlik chegarasi)
"""
import argparse
import datetime as dt
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAIN = os.path.join(HERE, "rain")
SOAT = os.path.join(RAIN, "soatlik")
START = dt.date(2017, 1, 1)  # ECMWF IFS (9 km) arxivi shu kundan boshlanadi
TZ = dt.timezone(dt.timedelta(hours=5))  # Toshkent
ARCH = "https://archive-api.open-meteo.com/v1/archive"
FC = "https://api.open-meteo.com/v1/forecast"
MODEL = "ecmwf_ifs"  # butun davr bitta modeldan (standart "best_match" 2016 va undan oldin ERA5 ga o'tadi)
RECHECK_DAYS = 45  # arxivdan har kuni qayta olinadigan oxirgi kunlar (operativ qiymatlarni almashtirish uchun)


def get(url, tries=8):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "fargona-3d (github.com/Hayitali4455/fargona-3d)"})
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:  # chegara yoki server: kutib qayta
                wait = 90 * (k + 1)
                print(f"  HTTP {e.code}, {wait} s kutiladi", flush=True)
                time.sleep(wait)
                continue
            raise
        except urllib.error.URLError as e:
            print(f"  tarmoq xatosi ({e.reason}), 30 s kutiladi", flush=True)
            time.sleep(30)
    raise RuntimeError("Open-Meteo javob bermadi")


def fetch(base, pts, **params):
    q = {"latitude": ",".join(f"{p['lat']:.4f}" for p in pts),
         "longitude": ",".join(f"{p['lon']:.4f}" for p in pts),
         "daily": "precipitation_sum", "hourly": "precipitation", "timezone": "Asia/Tashkent", **params}
    js = get(base + "?" + urllib.parse.urlencode(q))
    if isinstance(js, dict):
        js = [js]
    return [((o["daily"]["time"], o["daily"]["precipitation_sum"]), (o["hourly"]["time"], o["hourly"]["precipitation"]))
            for o in js]


def window(res, d0, d1):
    """Natijadan faqat d0..d1 kunlarini qoldirish (kunlik va soatlik)."""
    a, b = d0.isoformat(), d1.isoformat()
    cut = lambda tv: ([t for t in tv[0] if a <= t[:10] <= b], [v for t, v in zip(*tv) if a <= t[:10] <= b])
    return [(cut(d), cut(h)) for d, h in res]


def rle(arr):
    """Ketma-ket nollar -> -k; None -> null."""
    out, z = [], 0
    for v in arr:
        if v == 0:
            z += 1
            continue
        if z:
            out.append(-z)
            z = 0
        out.append(v)
    if z:
        out.append(-z)
    return out


def unrle(seq):
    out = []
    for v in seq:
        if v is not None and v < 0:
            out.extend([0] * -v)
        else:
            out.append(v)
    return out


class Soatlik:
    """Yil fayllari: har nuqta uchun yil boshidan soatlar massivi (0.1 mm)."""

    def __init__(self, pts, fresh):
        self.pts, self.fresh, self.y, self.touched = pts, fresh, {}, set()

    def arr(self, year):
        if year not in self.y:
            n = (dt.date(year + 1, 1, 1) - dt.date(year, 1, 1)).days * 24
            a = [[None] * n for _ in self.pts]
            path = os.path.join(SOAT, f"{year}.json")
            if not self.fresh and os.path.exists(path):
                idx = {t["code"]: unrle(t["h"]) for t in json.load(open(path, encoding="utf-8"))["tuman"]}
                for p, arr in zip(self.pts, a):
                    for i, v in enumerate(idx.get(p["code"], [])[:n]):
                        arr[i] = v
            self.y[year] = a
        return self.y[year]

    def put(self, res):
        for k, (_, (times, vals)) in enumerate(res):
            for t, v in zip(times, vals):
                if v is None:
                    continue
                d = dt.datetime.fromisoformat(t)
                i = (d.date() - dt.date(d.year, 1, 1)).days * 24 + d.hour
                self.arr(d.year)[k][i] = int(round(v * 10))
                self.touched.add(d.year)

    def write(self):
        os.makedirs(SOAT, exist_ok=True)
        for year in sorted(self.touched):
            a = self.y[year]
            n = max((next((i + 1 for i in range(len(arr) - 1, -1, -1) if arr[i] is not None), 0) for arr in a), default=0)
            head = json.dumps({"yil": year, "boshi": f"{year}-01-01T00:00", "soat": n,
                               "birlik": "0.1 mm (oldingi 1 soat yig'indisi, Toshkent vaqti)",
                               "kodlash": "manfiy son -k = ketma-ket k ta 0 qiymat"},
                              ensure_ascii=False, separators=(",", ":"))[:-1]
            # har tuman alohida qatorda (git farqi kichik bo'ladi)
            body = ",\n".join(json.dumps({"code": p["code"], "h": rle(arr[:n])}, separators=(",", ":"))
                              for p, arr in zip(self.pts, a))
            with open(os.path.join(SOAT, f"{year}.json"), "w", encoding="utf-8") as f:
                f.write(head + ',"tuman":[\n' + body + "\n]}\n")
            print(f"soatlik: {year} ({n} soat)")


def put(mm, res, start):
    """API natijasini massivga yozish; yozilgan eng oxirgi to'liq kun (hamma nuqtada qiymat bor)."""
    full = None
    for ((times, vals), _), arr in zip(res, mm):
        for t, v in zip(times, vals):
            if v is None:
                continue
            i = (dt.date.fromisoformat(t) - start).days
            if 0 <= i < len(arr):
                arr[i] = int(round(v * 10))
    days = res[0][0][0]
    for j, t in enumerate(days):
        if all(r[0][1][j] is not None for r in res):
            full = dt.date.fromisoformat(t)
    return full


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--toliq", action="store_true", help="2017 dan to'liq qayta yuklash")
    ap.add_argument("--pauza", type=float, default=400, help="to'liq yuklashda yillik so'rovlar orasidagi pauza, s")
    a = ap.parse_args()

    pts = json.load(open(os.path.join(RAIN, "nuqtalar.json"), encoding="utf-8"))
    yesterday = dt.datetime.now(TZ).date() - dt.timedelta(days=1)
    n = (yesterday - START).days + 1
    mm = [[None] * n for _ in pts]
    path = os.path.join(RAIN, "yogin.json")
    old = None if a.toliq or not os.path.exists(path) else json.load(open(path, encoding="utf-8"))
    if old:
        idx = {t["code"]: t["mm"] for t in old["tuman"]}
        off = (dt.date.fromisoformat(old["boshi"]) - START).days
        for p, arr in zip(pts, mm):
            for i, v in enumerate(idx.get(p["code"], [])):
                if 0 <= i + off < n:
                    arr[i + off] = v

    sh = Soatlik(pts, fresh=not old)

    # 1) arxiv: to'liq yuklashda yilma-yil, aks holda oxirgi RECHECK_DAYS kun + soatlik fayli yo'q yillar (to'liq)
    if old:
        tez = dt.date.fromisoformat(old["tez"]) if old.get("tez") else yesterday
        frm = min(tez, yesterday - dt.timedelta(days=RECHECK_DAYS))
    else:
        frm = START
    need = {y for y in range(START.year, yesterday.year + 1)
            if not os.path.exists(os.path.join(SOAT, f"{y}.json"))} if old else set()
    chunks = [(dt.date(y, 1, 1), min(dt.date(y, 12, 31), yesterday)) for y in sorted(need)]
    y = frm
    while y <= yesterday:
        to = min(dt.date(y.year, 12, 31), yesterday)
        if y.year not in need:
            chunks.append((y, to))
        y = to + dt.timedelta(days=1)
    chunks.sort()
    last_arch = None
    for k, (y, to) in enumerate(chunks):
        if k and len(chunks) > 2:
            time.sleep(a.pauza)  # Open-Meteo bepul chegarasi: soatiga ~5000 "chaqiruv birligi"
        print(f"arxiv {y} .. {to}", flush=True)
        res = fetch(ARCH, pts, start_date=y.isoformat(), end_date=to.isoformat(), models=MODEL)
        full = put(mm, res, START)
        sh.put(res)
        if full and to >= frm:
            last_arch = full
    if last_arch is None:
        last_arch = frm - dt.timedelta(days=1)

    # 2) arxivda hali yo'q kunlar: operativ model (prognoz API ning o'tgan kunlari)
    tez = last_arch + dt.timedelta(days=1)
    if tez <= yesterday:
        past = min(92, (dt.datetime.now(TZ).date() - tez).days + 1)
        print(f"operativ {tez} .. {yesterday} (past_days={past})", flush=True)
        res = window(fetch(FC, pts, past_days=past, forecast_days=1), tez, yesterday)
        put(mm, res, START)
        sh.put(res)

    out = {
        "manba": "Open-Meteo.com: ECMWF IFS (9 km) tarixiy ma'lumoti, CC BY 4.0; arxivda yo'q oxirgi kunlar — operativ model",
        "birlik": "0.1 mm (kunlik yog'ingarchilik: yomg'ir + qor suvi)",
        "boshi": START.isoformat(), "oxiri": yesterday.isoformat(),
        "tez": tez.isoformat() if tez <= yesterday else None,
        "yangilandi": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "tuman": [{"code": p["code"], "name": p["name"], "area_km2": p["area_km2"], "lat": p["lat"], "lon": p["lon"], "mm": arr}
                  for p, arr in zip(pts, mm)],
    }
    # har tuman alohida qatorda: git har kunlik o'zgarishni kichik farq sifatida saqlaydi
    body = ",\n".join(json.dumps(t, ensure_ascii=False, separators=(",", ":")) for t in out.pop("tuman"))
    head = json.dumps(out, ensure_ascii=False, separators=(",", ":"))[:-1]
    with open(path, "w", encoding="utf-8") as f:
        f.write(head + ',"tuman":[\n' + body + "\n]}\n")
    sh.write()
    miss = sum(v is None for arr in mm for v in arr)
    print(f"yozildi: {path} ({START} .. {yesterday}, arxiv {last_arch} gacha, bo'sh {miss})")


if __name__ == "__main__":
    main()
