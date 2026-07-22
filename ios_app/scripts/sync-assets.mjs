#!/usr/bin/env node
// Bündelt frontend/ ins Capacitor-www (www-ROOT, Lehre BAU.OS) und macht es nativ:
// 1. Kopie von frontend/ (ohne package.json/node_modules)
// 2. "/static/-Pfade → relative Pfade (Drift-Guard: exit 1 wenn nicht gefunden)
// 3. app-config.js mit WERKZEUG_API_BASE erzeugen + in index.html einbinden
import { cpSync, rmSync, mkdirSync, writeFileSync, readFileSync, existsSync } from 'node:fs';
import { basename, dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const SRC = resolve(here, '..', '..', 'frontend');
const OUT = resolve(here, '..', 'www');
const API_BASE = 'https://werkzeug.b2interior.de';

if (!existsSync(join(SRC, 'index.html'))) {
  console.error(`sync-assets: Quelle nicht gefunden: ${SRC}`);
  process.exit(1);
}

rmSync(OUT, { recursive: true, force: true });
mkdirSync(OUT, { recursive: true });
cpSync(SRC, OUT, {
  recursive: true,
  filter: (src) => !['package.json', 'node_modules'].includes(basename(src)),
});

// index.html: /static/-Präfixe entfernen + app-config.js einbinden
{
  const p = join(OUT, 'index.html');
  let html = readFileSync(p, 'utf8');
  if (!html.includes('"/static/')) {
    console.error('sync-assets: DRIFT — "/static/" nicht in index.html (Pfad-Struktur geändert?)');
    process.exit(1);
  }
  html = html.replaceAll('"/static/', '"');
  if (!html.includes('<script type="module" src="js/app.js">')) {
    console.error('sync-assets: DRIFT — app.js-Script-Tag nach Rewrite nicht gefunden');
    process.exit(1);
  }
  html = html.replace('<script type="module" src="js/app.js">',
    '<script src="app-config.js"></script>\n  <script type="module" src="js/app.js">');
  writeFileSync(p, html);
}

// Logo-Pfad in ui.js relativieren (nutzt /static/assets/…)
{
  const p = join(OUT, 'js', 'ui.js');
  let js = readFileSync(p, 'utf8');
  if (!js.includes('/static/assets/')) {
    console.error('sync-assets: DRIFT — /static/assets/ nicht in ui.js gefunden');
    process.exit(1);
  }
  js = js.replaceAll('/static/assets/', 'assets/');
  writeFileSync(p, js);
}

writeFileSync(join(OUT, 'app-config.js'),
  `window.WERKZEUG_API_BASE = '${API_BASE}';\n`);

console.log(`sync-assets: ok → ${OUT}`);
