"""Z web/app.html a mesto.json vyrobí site/index.html (texty, meta, sitemap). Výsledná složka site/ je statický web."""
import html, json, os, re
from PIL import Image
import geo
from geo import MESTO


def og_obrazek(out='site/og.jpg', W=1200, H=630, dolu=1):
    """náhled pro sdílení (og:image) 1200×630: výřez středu města z letních dlaždic (o úroveň menší než plné rozlišení)"""
    t = json.load(open('site/tiles.json')); base = t['base']; I = t['summer']['Image']
    T = int(I['TileSize']); SW, SH = int(I['Size']['Width']), int(I['Size']['Height'])
    lv = max(int(n) for n in os.listdir('site/tiles/summer') if n.isdigit()) - dolu; k = 2 ** dolu
    vx, vy, _ = geo.view(0, 0, 0)
    cx, cy = (vx - base['x0']) / base['mpp'] / k, (base['y1'] - vy) / base['mpp'] / k
    lw, lh = -(-SW // k), -(-SH // k)
    x0 = int(min(max(cx - W / 2, 0), max(lw - W, 0))); y0 = int(min(max(cy - H / 2, 0), max(lh - H, 0)))
    img = Image.new('RGB', (W, H), (27, 33, 48))
    for i in range(x0 // T, (x0 + W) // T + 1):
        for j in range(y0 // T, (y0 + H) // T + 1):
            f = f'site/tiles/summer/{lv}/{i}_{j}.webp'
            if os.path.exists(f):
                q = Image.open(f).convert('RGBA'); img.paste(q, (i * T - x0, j * T - y0), q)
    img.save(out, quality=85)


M = MESTO
SITE_URL = (M.get('url') or '').rstrip('/')          # plná adresa webu (kvůli og:image a sitemap); prázdné = bez nich
mhd = M.get('mhd') or {}
E = lambda t: html.escape(t or '', quote=True)
fill = {
    'TITULEK': E(M['titulek']), 'POPIS': E(M['popis']), 'MESTO': E(M['nazev']), 'H1_A': E(M['h1'][0]), 'H1_B': E(M['h1'][1]),
    'PODTITUL': E(M['podtitul']),
    'HLASENI': 'true' if M.get('hlaseni') else 'false',
    # terén: DMR 5G z nastroje/dmr.py (ČÚZK), jinak Terrarium
    'TEREN': 'z digitálního modelu reliéfu DMR 5G (ČÚZK)' if os.path.exists('build/dmr5g.npy') else 'z modelu Terrarium',
    'TEREN_ZDROJ': '' if os.path.exists('build/dmr5g.npy') else 'terén Terrarium (AWS Open Data), ',
    'TEREN_CUZK': 'terén DMR 5G, ' if os.path.exists('build/dmr5g.npy') else '',
    'MHD_ZDROJ': f', jízdní řády MHD © <a href="{E(mhd["zdroj_url"])}" target="_blank" rel="noopener">{E(mhd["zdroj"])}</a>'
                 if mhd.get('gtfs') and mhd.get('zdroj') else '',
}
app = re.sub(r'\{\{(\w+)\}\}', lambda m: fill[m.group(1)], open('web/app.html', encoding='utf-8').read())
og = f'''<meta property="og:image" content="{SITE_URL}/og.jpg">
<meta property="og:url" content="{SITE_URL}/">
<link rel="canonical" href="{SITE_URL}/">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{SITE_URL}/og.jpg">
''' if SITE_URL else ''
LD = json.dumps({'@context': 'https://schema.org', '@type': 'WebApplication', 'name': M['titulek'], 'description': M['popis'],
                 'inLanguage': 'cs', 'applicationCategory': 'TravelApplication', 'operatingSystem': 'Web',
                 'spatialCoverage': {'@type': 'Place', 'name': M['nazev']},
                 'isBasedOn': ['https://www.openstreetmap.org/', 'https://overturemaps.org/', 'https://geoportal.cuzk.cz/']},
                ensure_ascii=False)
head = f'''<!doctype html>
<html lang="cs">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta property="og:title" content="{E(M['titulek'])}">
<meta property="og:description" content="{E(M['popis'])}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{E(M['titulek'])}">
<meta property="og:locale" content="cs_CZ">
{og}<script type="application/ld+json">{LD}</script>
<style>:root{{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}}body{{margin:0;font:14px system-ui}}[hidden]{{display:none!important}}</style>
'''
body_start = app.index('</style>') + len('</style>')
page = head + app[:body_start] + '\n</head>\n<body>\n' + app[body_start:] + '\n</body>\n</html>\n'
open('site/index.html', 'w', encoding='utf-8').write(page)
open('site/robots.txt', 'w').write('User-agent: *\nAllow: /\n' + (f'Sitemap: {SITE_URL}/sitemap.xml\n' if SITE_URL else ''))
if SITE_URL:
    open('site/sitemap.xml', 'w').write(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{SITE_URL}/</loc></url></urlset>\n')
if M.get('hlaseni'):                                  # volitelná administrace hlášení (server v hlaseni/)
    open('site/admin.html', 'w', encoding='utf-8').write(open('hlaseni/admin.html', encoding='utf-8').read())
print('site/index.html', len(page))

# og:image: vyrobí se jednou ze středu města; vlastní site/og.jpg (1200×630) se nepřepisuje
if SITE_URL and not os.path.exists('site/og.jpg') and os.path.exists('site/tiles.json'):
    og_obrazek(); print('site/og.jpg')
