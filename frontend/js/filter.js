// Gemeinsame, reine Filterfunktion für Maschinenlisten.
// Genutzt von der Geräte-Übersicht (views/geraete.js) und der
// Admin-Maschinenliste (views/admin_maschinen.js). Ohne DOM-Abhängigkeit,
// damit sie mit node:test unit-getestet werden kann.

// Felder, die die Freitext-Suche durchsucht.
const SUCH_FELDER = ['name', 'maschinen_code', 'hersteller', 'platznummer', 'seriennummer'];

// Filtert eine Maschinenliste nach Freitext (suche) und Status.
// - suche:  durchsucht SUCH_FELDER, case-insensitiv & getrimmt; leer = kein Filter
// - status: exakter Vergleich gegen m.status; leer/falsy = alle Status
export function filterMaschinen(liste, { suche = '', status = '' } = {}) {
  if (!Array.isArray(liste)) return [];
  const q = String(suche).trim().toLowerCase();
  return liste.filter((m) => {
    if (status && m.status !== status) return false;
    if (!q) return true;
    return SUCH_FELDER.some((feld) => {
      const wert = m[feld];
      return typeof wert === 'string' && wert.toLowerCase().includes(q);
    });
  });
}
