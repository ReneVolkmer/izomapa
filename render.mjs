// Vyrenderuje celou mapu po dlaždicích v headless Chromiu a uloží je do build/tiles/
import { chromium } from 'playwright';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const args = Object.fromEntries(process.argv.slice(2).map((a) => a.split('=')));
const mpp = args.mpp || '0.4', tile = args.tile || '1024';
const outDir = path.join(ROOT, args.out || 'build/tiles');
fs.mkdirSync(outDir, { recursive: true });

const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.png': 'image/png' };
const server = http.createServer((req, res) => {
  const p = path.join(ROOT, decodeURIComponent(new URL(req.url, 'http://x').pathname));
  fs.readFile(p, (err, data) => {
    if (err) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'content-type': MIME[path.extname(p)] || 'application/octet-stream' });
    res.end(data);
  });
}).listen(0);
const port = server.address().port;

// cloud (Linux bez GPU): předinstalovaný Chromium + SwiftShader; Mac: Chromium z Playwrightu + GPU (Metal);
// Windows: GPU přes Direct3D 11, karta s největší vlastní pamětí (RENDER_SW=1 vynutí SwiftShader)
const LINUX_CHROME = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const winLuid = () => {
  const r = spawnSync('python', [path.join(ROOT, 'nastroje', 'gpu_win.py')], { encoding: 'utf8' });
  const luid = (r.stdout || '').trim();
  return /^-?\d+,\d+$/.test(luid) ? [`--use-adapter-luid=${luid}`] : [];
};
const GPU_ARGS = {
  darwin: () => ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
  win32: () => ['--use-angle=d3d11', '--enable-gpu', '--ignore-gpu-blocklist', ...winLuid()],
};
const browser = await chromium.launch({
  ...(fs.existsSync(LINUX_CHROME) ? { executablePath: LINUX_CHROME } : {}),
  args: (!process.env.RENDER_SW && GPU_ARGS[process.platform]?.())
    || ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage();
page.on('console', (m) => console.log('[page]', m.text()));
page.on('requestfailed', (r) => console.log('[rf]', r.url(), r.failure()?.errorText));
page.on('response', (r) => { if (r.status() >= 400) console.log('[http ' + r.status() + ']', r.url()); });
page.on('pageerror', (e) => { console.log('[pageerror]', e.message); process.exit(1); });
const t0 = Date.now();
await page.goto(`http://localhost:${port}/render.html?mpp=${mpp}&tile=${tile}&season=${args.season || 'autumn'}&mode=${args.mode || 'day'}&dir=${args.dir || 'build'}&alpha=${args.alpha || '0'}&skirt=${args.skirt || 'nsew'}${args.gx0 ? `&gx0=${args.gx0}&gy1=${args.gy1}` : ''}`);
await page.waitForFunction(() => window.READY === true, null, { timeout: 240000, polling: 1000 });
const info = await page.evaluate(() => window.INFO);
console.log('scéna připravena za', (Date.now() - t0) / 1000, 's', info);
fs.writeFileSync(path.join(outDir, 'info.json'), JSON.stringify(info));
const only = args.only ? args.only.split(',').map(Number) : null;
const list = args.tiles ? new Set(args.tiles.split(';')) : null;
for (let j = 0; j < info.rows; j++) for (let i = 0; i < info.cols; i++) {
  if (only && (only[0] !== i || only[1] !== j)) continue;
  if (list && !list.has(`${i}_${j}`)) continue;
  const t = Date.now();
  const url = await page.evaluate(([a, b]) => window.renderTile(a, b), [i, j]);
  fs.writeFileSync(path.join(outDir, `${i}_${j}.png`), Buffer.from(url.split(',')[1], 'base64'));
  console.log(`dlaždice ${i},${j}`, (Date.now() - t) / 1000, 's');
}
await browser.close();
server.close();
