"""MHD podle jízdních řádů (GTFS, adresa v mesto.json mhd.gtfs) -> site/mhd.json

python mhd.py [--stahnout]   stáhne build/gtfs.zip (při --stahnout nebo když je starší než den) a převede ho:
  routes   [číslo linky, typ (0 tramvaj, 3 autobus)]
  shapes   trasy ve světových souřadnicích mapy [[x, y], ...] (zjednodušené na 1 m)
  services kalendář {id: [po..ne (7× 0/1), od, do, [přidané dny], [zrušené dny]]}
  trips    [linka, trasa, služba, začátek (s od půlnoci), [Δt, vzdálenost po trase (m)] × zastávky, cíl, [zastávka, Δt příjezdu] × zastávky]
  heads, stops  názvy cílů a zastávek (indexy v trips)
Prohlížeč z toho podle skutečného času dopočítá, kde je každé vozidlo. Bez mhd.gtfs skript nic neudělá.
"""
import csv, io, json, os, subprocess, sys, time, zipfile
import shapely
from geo import MESTO, to_local, extent, chunk_of, CHUNKS

URL = (MESTO.get('mhd') or {}).get('gtfs')
if not URL: sys.exit('mesto.json nemá mhd.gtfs – MHD se vynechá')
Z = 'build/gtfs.zip'
if '--stahnout' in sys.argv or not os.path.exists(Z) or time.time() - os.path.getmtime(Z) > 86400:
    subprocess.run(['curl', '-sL', '-m', '120', '-o', Z + '.tmp', URL], check=True)
    zipfile.ZipFile(Z + '.tmp').testzip(); os.replace(Z + '.tmp', Z)
zf = zipfile.ZipFile(Z)
I = lambda n: csv.DictReader(io.TextIOWrapper(zf.open(n + '.txt'), encoding='utf-8-sig'))   # po řádcích (velké krajské feedy)
T = lambda n: list(I(n))
sec = lambda t: (lambda h, m, s: h * 3600 + m * 60 + s)(*map(int, t.split(':')))

# jen spoje se zastávkou na území mapy (krajský feed jako PID má miliony řádků, do webu patří jen kousek)
X0, Y0, X1, Y1 = extent(0)
def in_map(s):
    if not s['stop_lat']: return False
    x, y = (float(v) for v in to_local(float(s['stop_lon']), float(s['stop_lat'])))
    return X0 <= x <= X1 and Y0 <= y <= Y1 and chunk_of(x, y) in CHUNKS
STOPS = T('stops')
inside = {s['stop_id'] for s in STOPS if in_map(s)}
keep = {r['trip_id'] for r in I('stop_times') if r['stop_id'] in inside}
trips = [t for t in I('trips') if t['trip_id'] in keep]

routes, RI = [], {}
used_routes = {t['route_id'] for t in trips}
for r in T('routes'):
    if r['route_id'] not in used_routes: continue
    RI[r['route_id']] = len(routes); routes.append([r['route_short_name'], int(r['route_type'] or 3)])
used = {t['shape_id'] for t in trips}
pts = {}
for r in I('shapes'):
    if r['shape_id'] in used: pts.setdefault(r['shape_id'], []).append((int(r['shape_pt_sequence']), float(r['shape_pt_lon']), float(r['shape_pt_lat']), float(r['shape_dist_traveled'] or 0)))
shapes, SI, SLEN = [], {}, {}
for k, v in pts.items():
    if len(v) < 2: continue
    v.sort(); x, y = to_local([p[1] for p in v], [p[2] for p in v])
    l = shapely.LineString(list(zip(x, y)))
    SI[k] = len(shapes); SLEN[k] = (l.length, v[-1][3] or 1.0)
    shapes.append([[round(a, 1), round(b, 1)] for a, b in shapely.simplify(l, 1.0).coords])
services, SV = {}, {t['service_id'] for t in trips}
for c in T('calendar'):
    if c['service_id'] not in SV: continue
    services[c['service_id']] = [[int(c[d]) for d in ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')],
                                 int(c['start_date']), int(c['end_date']), [], []]
for c in T('calendar_dates'):
    if c['service_id'] not in SV: continue
    s = services.setdefault(c['service_id'], [[0] * 7, 0, 0, [], []])
    s[3 if c['exception_type'] == '1' else 4].append(int(c['date']))
SN = {r['stop_id']: r['stop_name'] for r in STOPS}
names, NI = [], {}
def nid(n):
    if n not in NI: NI[n] = len(names); names.append(n)
    return NI[n]
st = {}
for r in I('stop_times'):
    if r['trip_id'] not in keep: continue
    st.setdefault(r['trip_id'], []).append((int(r['stop_sequence']), sec(r['arrival_time']), sec(r['departure_time']), float(r['shape_dist_traveled'] or 0), SN.get(r['stop_id'], '')))
out = []
for t in trips:
    if len(routes[RI[t['route_id']]][0]) > 4: continue           # poptávková doprava apod. bez pravidelné trasy
    s = sorted(st.get(t['trip_id'], []))
    if len(s) < 2 or t['shape_id'] not in SI: continue
    L, gl = SLEN[t['shape_id']]; k = L / gl                     # vzdálenost z jízdního řádu -> délka trasy v mapě
    t0 = s[0][1]; seq = []; zs = []
    for j, (_, a, d, dist, nm) in enumerate(s):
        if 0 < j < len(s) - 1 and d == a:                    # jízdní řád je po minutách: v zastávce stát ~20 s kolem času odjezdu
            gap = min(a - s[j - 1][2], s[j + 1][1] - d)
            w = min(10, gap // 4)
            a, d = a - w, d + w
        seq += [a - t0, round(dist * k)]
        if d > a: seq += [d - t0, round(dist * k)]              # pobyt v zastávce
        zs += [nid(nm), a - t0]
    out.append([RI[t['route_id']], SI[t['shape_id']], t['service_id'], t0, seq, nid(t['trip_headsign'] or s[-1][4]), zs])
out.sort(key=lambda q: q[3])
json.dump({'routes': routes, 'shapes': shapes, 'services': services, 'trips': out, 'names': names,
           'feed': [r for r in T('feed_info')][0].get('feed_version', '')}, open('site/mhd.json', 'w'), separators=(',', ':'), ensure_ascii=False)
print('linek', len(routes), 'tras', len(shapes), 'spojů', len(out), 'kB', os.path.getsize('site/mhd.json') // 1000)
