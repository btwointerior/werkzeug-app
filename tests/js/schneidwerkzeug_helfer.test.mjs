import { test } from 'node:test';
import assert from 'node:assert/strict';
import { istSchneidwerkzeugCode, euro, centAusEingabe, zahlAusEingabe, kenndaten, ortText, schaerfText } from '../../frontend/js/schneidwerkzeug_helfer.js';

test('istSchneidwerkzeugCode: nur die Präfixe der Schneidwerkzeuge, nie Geräte', () => {
  for (const c of ['SB-001', 'sb-001', ' VR-012 ', 'FR-0001', 'BO-123', 'ME-001', 'SW-99999']) assert.equal(istSchneidwerkzeugCode(c), true, c);
  for (const c of ['M-001', 'M-0001', 'SB-1', 'SB001', 'XX-001', '', null, undefined, 'SB-001x']) assert.equal(istSchneidwerkzeugCode(c), false, String(c));
});

test('euro und centAusEingabe', () => {
  assert.equal(euro(1450), '14,50 €');
  assert.equal(euro(0), '0,00 €');
  assert.equal(euro(123456), '1.234,56 €');
  assert.equal(euro(null), '—');
  assert.equal(centAusEingabe('14,5'), 1450);
  assert.equal(centAusEingabe('14.50'), 1450);
  assert.equal(centAusEingabe(' 1.234,50 € '), 123450);
  assert.equal(centAusEingabe('12'), 1200);
  assert.equal(centAusEingabe(''), null);
  assert.ok(Number.isNaN(centAusEingabe('abc')));
  assert.ok(Number.isNaN(centAusEingabe('-5')));
  assert.ok(Number.isNaN(centAusEingabe('1,234')));
});

test('zahlAusEingabe', () => {
  assert.equal(zahlAusEingabe('12,5'), 12.5);
  assert.equal(zahlAusEingabe('300'), 300);
  assert.equal(zahlAusEingabe(' '), null);
  assert.ok(Number.isNaN(zahlAusEingabe('12 mm')));
});

test('kenndaten, ortText, schaerfText', () => {
  const w = { art_text: 'Sägeblatt', durchmesser_mm: 300, zaehnezahl: 72, schneidstoff: 'HW', status: 'lager', lagerort: 'Schrank 1', anzahl_schaerfungen: 3, max_schaerfungen: 15, rest_schaerfungen: 12 };
  assert.equal(kenndaten(w), 'Sägeblatt · Ø 300 mm · Z 72 · HW');
  assert.equal(kenndaten({ art_text: 'Fräser', durchmesser_mm: 12.5 }), 'Fräser · Ø 12,5 mm');
  assert.equal(ortText(w), 'Lager: Schrank 1');
  assert.equal(ortText({ status: 'lager' }), 'Lager (ohne Fach)');
  assert.equal(ortText({ status: 'maschine', maschine: 'Holzma', platz: 'T3' }), 'In Holzma, Platz T3');
  assert.equal(ortText({ status: 'schaerfdienst' }), 'Beim Schärfdienst');
  assert.deepEqual(schaerfText(w), { text: '3 von 15 geschärft', erschoepft: false });
  assert.deepEqual(schaerfText({ anzahl_schaerfungen: 2, max_schaerfungen: 2, rest_schaerfungen: 0 }), { text: '2 von 2 geschärft', erschoepft: true });
  assert.deepEqual(schaerfText({ anzahl_schaerfungen: 4, max_schaerfungen: null }), { text: '4× geschärft', erschoepft: false });
});
