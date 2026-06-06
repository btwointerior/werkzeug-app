// Wiederverwendbarer QR-Scanner. parseScan ist rein und unit-getestet;
// scanQr (in einem späteren Schritt) kapselt Kamera + Overlay.

const MARKER = '#/m/';

// Macht aus einem gescannten String den Maschinen-Code (oder null).
// Akzeptiert die QR-URL (…/#/m/CODE) ebenso wie einen rohen Code.
export function parseScan(text) {
  if (typeof text !== 'string') return null;
  const s = text.trim();
  if (!s) return null;

  const i = s.indexOf(MARKER);
  if (i !== -1) {
    const raw = s.slice(i + MARKER.length).trim();
    if (!raw) return null;
    try {
      return decodeURIComponent(raw).trim().toUpperCase();
    } catch {
      return raw.toUpperCase();
    }
  }

  // Kein Marker: nur einen "nackten" Code akzeptieren (kein Schema, kein Whitespace).
  if (s.includes('://') || /\s/.test(s)) return null;
  return s.toUpperCase();
}
