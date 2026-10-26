# Farg‘ona viloyati — 3D relyef

Farg‘ona viloyati relyefi (DEM) va 19 ta tuman/shahar chegarasini ko‘rsatadigan interaktiv 3D xarita. Brauzerda, telefonda ham ochiladi.

**Ochish:** https://hayitali4455.github.io/fargona-3d/

- Past joylar yashil, baland joylar qizil rangda (346–2417 m).
- Tuman nomlari doim ko‘rinib turadi. Tumanni bosganda uning maydoni va balandlik ko‘rsatkichlari chiqadi.
- Istalgan nuqtani bosganda o‘sha joyning balandligi ko‘rsatiladi (DEM 50 m to‘ridan; vodiyda xato odatda 1 m dan kam, tog‘larda bir necha metr).
- Bitta tumanni ochadigan havola: `…/fargona-3d/#t=<SOATO kodi>`, masalan `#t=1730226` (So‘x tumani).

## Boshqaruv

| | Kompyuter | Telefon |
|---|---|---|
| Aylantirish | chap tugma bilan sudrash | bir barmoq |
| Surish | o‘ng tugma yoki Shift + sudrash | ikki barmoq |
| Yaqinlashtirish | g‘ildirak, ikki marta bosish | ikki barmoqni yoyish, ikki marta bosish |
| Tuman va nuqta balandligi | bosish | bosish |

## Qayta yig‘ish

Manba ma’lumotlar (repoda yo‘q): ``Farg`ona.tif`` (DEM, EPSG:3857, 4 m) va `tuman.shp`.

```
python build.py --no-tiles   # index.html — 50 m relyef to‘ri, chegaralar, nomlar

# ixtiyoriy: bosilgan nuqtada asl 4 m piksel qiymati (dem4m/ ~250 MB, bu repoga qo‘yilmagan)
python make_tiles.py && python build.py
```

Kerakli Python paketlari: rasterio, geopandas, shapely, scipy, pyproj. Sahifa three.js r128 dan foydalanadi (`vendor/`, MIT litsenziyasi).
