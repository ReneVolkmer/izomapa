"""Stáhne digitální model reliéfu DMR 5G (ČÚZK, CC BY 4.0, terén z laserového skenování bez budov a stromů)
pro celou mapu -> build/dmr5g.npy (float32, m n. m., NaN = bez dat) + build/dmr5g.json (lon0, lat1, krok ve stupních).

python nastroje/dmr.py [krok_m]   (výchozí 2 m od severu k jihu; prep.py ho pak bere místo Terraria)
Mřížka je ve stupních EPSG:4326 se STEJNÝM krokem v obou osách: služba (ArcGIS ImageServer) jinak obraz
uvnitř bloku tiše natáhne na čtvercové pixely a bloky na sebe nesedí (skoky o desítky metrů).
"""
import io, json, os, sys, time, urllib.parse, urllib.request
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import geo

URL = 'https://ags.cuzk.gov.cz/arcgis2/rest/services/dmr5g/ImageServer/exportImage'
R = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
DD = R / geo.KY                                    # krok ve stupních (v. d. pak vychází asi 1,3 m)
B = 2000                                           # px na jeden požadavek (služba dovolí max. 4100)
lo0, lo1, la0, la1 = geo.bbox_lonlat(geo.MARGIN + 30)
lo0, la1 = np.floor(lo0 / DD) * DD, np.ceil(la1 / DD) * DD
W, H = int(np.ceil((lo1 - lo0) / DD)), int(np.ceil((la1 - la0) / DD))
out = np.full((H, W), np.nan, np.float32)
print('DMR 5G', W, 'x', H, 'px, krok', R, 'm (s–j)')


def get(i0, j0, w, h):
    q = {'bbox': f'{lo0 + i0 * DD},{la1 - (j0 + h) * DD},{lo0 + (i0 + w) * DD},{la1 - j0 * DD}', 'bboxSR': 4326, 'imageSR': 4326,
         'size': f'{w},{h}', 'format': 'tiff', 'pixelType': 'F32', 'noData': -9999, 'interpolation': 'RSP_BilinearInterpolation', 'f': 'image'}
    for k in range(5):
        try:
            d = urllib.request.urlopen(URL + '?' + urllib.parse.urlencode(q), timeout=180).read()
            a = np.array(Image.open(io.BytesIO(d)), np.float32)
            assert a.shape == (h, w), a.shape
            a[a < -1000] = np.nan
            return a
        except Exception as e:
            print('  znovu', k + 1, e); time.sleep(5 * (k + 1))
    raise SystemExit('DMR 5G se nepodařilo stáhnout')


for j in range(0, H, B):
    for i in range(0, W, B):
        w, h = min(B, W - i), min(B, H - j)
        out[j:j + h, i:i + w] = get(i, j, w, h)
        print(f'  blok {i // B},{j // B}', 'nan', int(np.isnan(out[j:j + h, i:i + w]).sum()))
# kontrola: na hranicích bloků nesmí být skoky (sousední body se liší nejvýš jako jinde)
d = np.abs(np.diff(out, axis=0)); e = np.abs(np.diff(out, axis=1))
print('největší skok mezi sousedními body', round(float(np.nanmax(d)), 1), round(float(np.nanmax(e)), 1), 'm')
np.save('build/dmr5g.npy', out)
json.dump({'lon0': float(lo0), 'lat1': float(la1), 'dd': DD, 'r': R, 'w': W, 'h': H}, open('build/dmr5g.json', 'w'))
print('hotovo, výšky', float(np.nanmin(out)), '–', float(np.nanmax(out)), 'm n. m.')
