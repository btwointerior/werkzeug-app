// NFC-Anbindung an das lokale Capacitor-Plugin "WerkzeugNfc" (nur native App).
//
// WICHTIG (No-Bundler-Betrieb): Die von Capacitor injizierte Bridge stellt
// KEIN window.Capacitor.registerPlugin bereit — das existiert nur im
// @capacitor/core-Modul (Bundler). Ohne Bundler gilt:
// - Verfügbarkeit:  window.Capacitor.PluginHeaders (via JSExport injiziert)
// - Methodenaufruf: window.Capacitor.nativePromise(plugin, methode, optionen)
// Im Web ist window.Capacitor nicht vorhanden -> keine NFC-Elemente.

import { baueTagUrl, extrahiereCode } from './nfc_helfer.js';

export function istNfcVerfuegbar() {
  const cap = window.Capacitor;
  if (!cap || typeof cap.isNativePlatform !== 'function' || !cap.isNativePlatform()) return false;
  if (typeof cap.nativePromise !== 'function') return false;
  return (cap.PluginHeaders || []).some((h) => h && h.name === 'WerkzeugNfc');
}

async function rufeNfc(methode, optionen = {}) {
  try {
    return await window.Capacitor.nativePromise('WerkzeugNfc', methode, optionen);
  } catch (err) {
    const msg = (err && (err.message || err.errorMessage)) || 'NFC-Fehler.';
    throw new Error(msg);
  }
}

// Liest einen Tag und liefert den Maschinen-Code (string) oder null (Abbruch/
// kein Code). Wirft bei Plugin-Fehlern mit verständlicher Meldung.
export async function nfcLeseCode() {
  if (!istNfcVerfuegbar()) return null;
  const ergebnis = await rufeNfc('readCode');
  return extrahiereCode((ergebnis && ergebnis.text) || '');
}

// Schreibt die Tag-URL der Maschine und versiegelt den Tag DAUERHAFT.
export async function nfcSchreibeUndVersiegele(code) {
  if (!istNfcVerfuegbar()) throw new Error('NFC ist auf diesem Gerät nicht verfügbar.');
  const base = window.WERKZEUG_API_BASE || location.origin;
  await rufeNfc('writeAndLock', { url: baueTagUrl(base, code) });
}
