// Reine Helfer für den Bereich „Schneidwerkzeuge" (unit-getestet, ohne DOM).

// Codes der Schneidwerkzeuge tragen einen Zwei-Buchstaben-Präfix je Art; Geräte heißen M-….
const PRAEFIXE = ['SB', 'VR', 'FR', 'BO', 'ME', 'SW'];

/** Gehört der Code zu einem Schneidwerkzeug (und nicht zu einem Gerät)? */
export function istSchneidwerkzeugCode(code) {
  const m = String(code ?? '').trim().toUpperCase().match(/^([A-Z]{2})-\d{3,5}$/);
  return !!m && PRAEFIXE.includes(m[1]);
}

/** 1450 → „14,50 €"; null/undefined → „—". */
export function euro(cent) {
  if (cent == null) return '—';
  return `${(cent / 100).toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
}

/** „14,5" / „14.50" / „1.234,50 €" → Cent. Leer → null, Unsinn oder negativ → NaN. */
export function centAusEingabe(text) {
  let s = String(text ?? '').replace(/[€\s]/g, '');
  if (!s) return null;
  if (s.includes(',')) s = s.replace(/\./g, '').replace(',', '.');
  if (!/^\d+(\.\d{1,2})?$/.test(s)) return NaN;
  return Math.round(parseFloat(s) * 100);
}

/** „12,5" → 12.5; leer → null; Unsinn → NaN. */
export function zahlAusEingabe(text) {
  const s = String(text ?? '').trim().replace(',', '.');
  if (!s) return null;
  return /^\d+(\.\d+)?$/.test(s) ? parseFloat(s) : NaN;
}

/** Kurzzeile mit den Kenndaten: „Sägeblatt · Ø 300 mm · Z 72 · HW". */
export function kenndaten(w) {
  const teile = [w.art_text];
  if (w.durchmesser_mm) teile.push(`Ø ${String(w.durchmesser_mm).replace('.', ',')} mm`);
  if (w.zaehnezahl) teile.push(`Z ${w.zaehnezahl}`);
  if (w.schneidstoff) teile.push(w.schneidstoff);
  return teile.filter(Boolean).join(' · ');
}

/** Wo ist das Werkzeug? „In Holzma, Platz 3" / „Lager: Schrank 1" / „Beim Schärfdienst". */
export function ortText(w) {
  if (w.status === 'maschine') return `In ${w.maschine || 'Maschine'}${w.platz ? `, Platz ${w.platz}` : ''}`;
  if (w.status === 'schaerfdienst') return 'Beim Schärfdienst';
  if (w.status === 'verschrottet') return 'Verschrottet';
  return w.lagerort ? `Lager: ${w.lagerort}` : 'Lager (ohne Fach)';
}

/** „3 von 15 geschärft" / „3× geschärft" – und ob die Grenze erreicht ist. */
export function schaerfText(w) {
  if (w.max_schaerfungen == null) return { text: `${w.anzahl_schaerfungen}× geschärft`, erschoepft: false };
  return { text: `${w.anzahl_schaerfungen} von ${w.max_schaerfungen} geschärft`, erschoepft: w.rest_schaerfungen === 0 };
}

const ERGEBNIS_TEXT = { geschaerft: 'geschärft', neu_bestueckt: 'neu bestückt', ausgemustert: 'ausgemustert' };

/** Ergebnis einer Rückkehr vom Schärfdienst als Text. */
export function ergebnisText(key) {
  return ERGEBNIS_TEXT[key] || key || '';
}

/** Braucht die Art nach dem Schärfen neue Maße an der CNC? (Fräser und Bohrer, Sägeblätter nicht) */
export function brauchtMasse(art) {
  return art === 'fraeser' || art === 'bohrer';
}

/** Empfohlene Parameter als kurze Zeile: „18.000 1/min · 6,5 m/min" (leer, wenn nichts hinterlegt). */
export function parameterText(w) {
  const teile = [];
  if (w.drehzahl_empfohlen) teile.push(`${w.drehzahl_empfohlen.toLocaleString('de-DE')} 1/min`);
  if (w.vorschub_empfohlen) teile.push(`${String(w.vorschub_empfohlen).replace('.', ',')} m/min`);
  return teile.join(' · ');
}
