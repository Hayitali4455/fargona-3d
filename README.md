# Farg‘ona viloyati — 3D relyef

Farg‘ona viloyati relyefi (DEM) va 19 ta tuman/shahar chegarasini ko‘rsatadigan interaktiv 3D xarita. Brauzerda, telefonda ham ochiladi.

**Ochish:** https://hayitali4455.github.io/fargona-3d/

- Past joylar yashil, baland joylar qizil rangda (346–2417 m).
- Tuman nomlari doim ko‘rinib turadi. Tumanni bosganda uning maydoni va balandlik ko‘rsatkichlari chiqadi.
- Istalgan nuqtani bosganda o‘sha joyning balandligi ko‘rsatiladi (DEM 50 m to‘ridan; vodiyda xato odatda 1 m dan kam, tog‘larda bir necha metr).
- **Suv oqimi yo‘llari**: relyef bo‘yicha suv oqishi mumkin bo‘lgan yo‘llar suv ko‘rinishida chiziladi: kengligi havza maydoniga bog‘liq (taxminan 2.5·√havza m, 4–180 m), to‘lqinlar oqim yo‘nalishida harakatlanadi (“Oqim animatsiyasi” bilan o‘chiriladi). Polzunok bilan ko‘rsatiladigan eng kichik havza maydoni tanlanadi (1–500 km², boshlang‘ich 25 km²). Oqim ustiga bosilsa, uning tartibi va havza maydoni chiqadi.
- **Yog‘ingarchilik** (“Yog‘in” tugmasi): tumanlar tanlangan davrdagi (7 kun, 30 kun, joriy yil, 12 oy) yog‘in miqdori bo‘yicha bo‘yaladi; tuman kartasida oxirgi 12 oy ko‘p yillik o‘rtacha bilan va 2017-yildan beri yillik jamlar ko‘rsatiladi. Ma’lumot har kuni avtomatik yangilanadi.
- **Tuproq** (“Tuproq” tugmasi): SoilGrids 2.0 bo‘yicha tuproq turi (WRB) yoki mexanik tarkib (USDA); bosilgan nuqtada loy/qum/chang, pH va organik uglerod (0–30 sm).
- **Yer qoplami** (“Yer qoplami” tugmasi): ESA WorldCover 2021 (10 m) sinflari — ekin maydoni, qurilish, daraxtzor, o‘tloq, ochiq yer, suv; tuman kartasida ulush va km².
- **3D binolar** (“Binolar” tugmasi): OpenStreetMap dagi 202 ming bino (F4Map va streets.gl ham shu OSM binolarini ko‘rsatadi); ~12 km dan yaqinlashganda yuklanadi.
- Bitta tumanni ochadigan havola: `…/fargona-3d/#t=<SOATO kodi>`, masalan `#t=1730226` (So‘x tumani).

## Boshqaruv

| | Kompyuter | Telefon |
|---|---|---|
| Aylantirish | chap tugma bilan sudrash | bir barmoq |
| Surish | o‘ng tugma yoki Shift + sudrash | ikki barmoq |
| Yaqinlashtirish | g‘ildirak, ikki marta bosish | ikki barmoqni yoyish, ikki marta bosish |
| Tuman va nuqta balandligi | bosish | bosish |

## Yog‘ingarchilik ma’lumoti

- **Manba**: [Open-Meteo](https://open-meteo.com) — ECMWF IFS (9 km) tarixiy ma’lumoti, CC BY 4.0. Bu o‘lchov stansiyasi emas, model baholari; har tuman uchun tuman ichidagi bitta nuqta (`rain/nuqtalar.json`) olinadi. Quruq vodiyda model yillik yog‘inni stansiya o‘lchovlaridan ancha ko‘p ko‘rsatishi mumkin (masalan, Farg‘ona shahri uchun ~300 mm), shuning uchun raqamlarni tumanlar, oylar va yillar orasidagi nisbiy farqlarni ko‘rish uchun ishlating.
- **Davr**: 2017-01-01 dan (IFS arxivi shu kundan) kechagi kungacha, kunlik yig‘indi (yomg‘ir + qor suvi), `rain/yogin.json` (0.1 mm butun sonlarda).
- **Yangilanish**: GitHub Actions (`.github/workflows/yogin.yml`) har kuni 06:30 (Toshkent) da `rain_update.py` ni ishga tushiradi: oxirgi 45 kun arxivdan qayta olinadi, arxivda hali yo‘q kunlar operativ modeldan to‘ldiriladi va keyinroq almashtiriladi. Qo‘lda ishga tushirish: GitHub → Actions → “Yog'in ma'lumotini yangilash” → Run workflow.

## Tuproq, yer qoplami va binolar

- **Tuproq**: ISRIC SoilGrids 2.0, 250 m, CC BY 4.0 (`layers_build.py`). 0–30 sm uchun 0–5/5–15/15–30 sm qatlamlar qalinlik bo‘yicha o‘rtacha. Global model: Farg‘ona uchun umumlashtirilgan (WRB da asosan Cambisols, mexanik tarkibda soz-qumoq va qumoq), mahalliy tuproq xaritasi o‘rnini bosmaydi.
- **Yer qoplami**: ESA WorldCover 2021 v200, 10 m, CC BY 4.0 — portalda 40 m setkada (eng ko‘p uchragan sinf), statistika shu setkada.
- **Binolar**: © OpenStreetMap hissadorlari, ODbL (`bino_build.py`, Geofabrik 2026-10-21). Balandlik: `height` → `building:levels` × 3 m → bino turi bo‘yicha standart (oddiy uy 4 m, ko‘p qavatli 15 m, maktab 10 m …); OSM da balandlik/qavat atigi ~1 400 binoda bor, qolganlari taxminiy.

## Suv oqimi yo‘llari qanday hisoblangan

- **DEM**: viloyat DEM i (4 m) 20 m qadamli setkaga o‘rtacha qiymat bilan o‘tkazilgan. Viloyatdan tashqarida (janubdagi tog‘ havzalari, 39.3°N gacha) Copernicus GLO-30 (~60 m) qo‘shilgan; ikki DEM chegara bo‘yida mos keladi (farq medianasi +0.5 m).
- **Hisob**: ArcGIS Pro 3.5 Spatial Analyst — *Derive Continuous Flow* (D8, chuqurliklar to‘ldirilmaydi, oqim eng past chiqish orqali davom etadi), oqim boshlanishi ≥ 1 km² havza, *Stream Order* (Strahler), *Stream to Feature*.
- **Tekshiruv**: OSM daryolarining 86% i modeldagi oqim yo‘lidan 150 m ichida (Isfayramsoy, Shohimardonsoy 100%, So‘x 85%).
- **Cheklovlar**:
  - Bu relyef bo‘yicha *ehtimoliy* yo‘llar. Vodiyda suv asosan kanal va zovurlar orqali boshqariladi, ular hisobga olinmagan; tekis sug‘oriladigan yerlarda chiziqlar haqiqiy suv yo‘liga to‘g‘ri kelmasligi mumkin.
  - Sirdaryo havzasi asosan hisob hududidan tashqarida, uning havza maydoni ancha kam ko‘rsatiladi.
  - Shohimardon anklavida viloyat DEM i yo‘q (38.5 km²), portalda u yer chizilmagan.

Copernicus GLO-30: © DLR e.V. 2010–2014 va © Airbus Defence and Space GmbH 2014–2018, Yevropa Ittifoqi va ESA ning COPERNICUS dasturi doirasida taqdim etilgan.

## Qayta yig‘ish

Manba ma’lumotlar (repoda yo‘q): ``Farg`ona.tif`` (DEM, EPSG:3857, 4 m) va `tuman.shp`.

```
python build.py --no-tiles   # index.html — 50 m relyef to‘ri, chegaralar, nomlar

# suv oqimi (hydro/, repoga qo‘yilmagan): DEM tayyorlash, ArcGIS hisobi, chiziqlarni boyitish
python hydro_prep.py && python hydro_prep_ext.py
"C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe" hydro_arc.py
python hydro_post.py     # keyin build.py ni qayta ishga tushiring

# ixtiyoriy: bosilgan nuqtada asl 4 m piksel qiymati (dem4m/ ~250 MB, bu repoga qo‘yilmagan)
python make_tiles.py && python build.py
```

Kerakli Python paketlari: rasterio, geopandas, shapely, scipy, pyproj. Sahifa three.js r128 dan foydalanadi (`vendor/`, MIT litsenziyasi).
