// Pure NFC-Helfer (node-testbar, keine DOM-/Capacitor-Abhängigkeit).
// Ein NFC-Tag trägt exakt dieselbe URL wie der QR-Code der Maschine.

import { parseScan } from './scanner.js';

// Baut die Tag-URL aus API-Basis und Maschinen-Code (Gegenstück zum QR-Inhalt).
export function baueTagUrl(base, code) {
  return base.replace(/\/+$/, '') + '/#/m/' + encodeURIComponent(code);
}

// Gelesener Tag-Inhalt (URL oder roher Code) → Maschinen-Code oder null.
export function extrahiereCode(text) {
  return parseScan(text);
}
