// NFC-Anbindung an das lokale Capacitor-Plugin "WerkzeugNfc" (nur native App).
// Im Web ist window.Capacitor nicht vorhanden -> alle Funktionen melden
// "nicht verfügbar" und die UI zeigt keine NFC-Elemente.

import { baueTagUrl, extrahiereCode } from './nfc_helfer.js';

let _plugin;   // einmalig aufgelöst; null = nicht verfügbar

function nfcPlugin() {
  if (_plugin === undefined) {
    try {
      _plugin = window.Capacitor?.registerPlugin?.('WerkzeugNfc') || null;
    } catch {
      _plugin = null;
    }
  }
  return _plugin;
}

export function istNfcVerfuegbar() {
  return !!nfcPlugin();
}

// Liest einen Tag und liefert den Maschinen-Code (string) oder null (Abbruch/
// kein Code). Wirft bei Plugin-Fehlern mit verständlicher Meldung.
export async function nfcLeseCode() {
  const plugin = nfcPlugin();
  if (!plugin) return null;
  const { text } = await plugin.readCode();
  return extrahiereCode(text || '');
}

// Schreibt die Tag-URL der Maschine und versiegelt den Tag DAUERHAFT.
export async function nfcSchreibeUndVersiegele(code) {
  const plugin = nfcPlugin();
  if (!plugin) throw new Error('NFC ist auf diesem Gerät nicht verfügbar.');
  const base = window.WERKZEUG_API_BASE || location.origin;
  await plugin.writeAndLock({ url: baueTagUrl(base, code) });
}
