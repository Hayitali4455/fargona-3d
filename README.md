# Farg‘ona viloyati — 3D relyef

Farg‘ona viloyati relyefi (DEM) va 19 ta tuman/shahar chegarasini ko‘rsatadigan interaktiv 3D xarita. Brauzerda, telefonda ham ochiladi.

**Ochish:** https://hayitali4455.github.io/fargona-3d/

- Past joylar yashil, baland joylar qizil rangda (346–2417 m).
- Tuman nomlari doim ko‘rinib turadi. Tumanni bosganda uning maydoni va balandlik ko‘rsatkichlari chiqadi.
- Istalgan nuqtani bosganda o‘sha joyning balandligi ko‘rsatiladi (DEM 50 m to‘ridan; vodiyda xato odatda 1 m dan kam, tog‘larda bir necha metr).
- **Suv oqimi yo‘llari**: relyef bo‘yicha suv oqishi mumkin bo‘lgan yo‘llar (ko‘k chiziqlar, qalinligi Strahler tartibiga qarab). Polzunok bilan ko‘rsatiladigan eng kichik havza maydoni tanlanadi (1–500 km², boshlang‘ich 25 km²). Oqim ustiga bosilsa, uning tartibi va havza maydoni chiqadi.
- Bitta tumanni ochadigan havola: `…/fargona-3d/#t=<SOATO kodi>`, masalan `#t=1730226` (So‘x tumani).

## Boshqaruv

| | Kompyuter | Telefon |
|---|---|---|
| Aylantirish | chap tugma bilan sudrash | bir barmoq |
| Surish | o‘ng tugma yoki Shift + sudrash | ikki barmoq |
| Yaqinlashtirish | g‘ildirak, ikki marta bosish | ikki barmoqni yoyish, ikki marta bosish |
| Tuman va nuqta balandligi | bosish | bosish |

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
