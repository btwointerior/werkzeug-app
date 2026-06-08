import { test } from 'node:test';
import assert from 'node:assert/strict';
import { filterMaschinen } from '../../frontend/js/filter.js';

const LISTE = [
  { name: 'Bohrmaschine',  maschinen_code: 'M-0001', hersteller: 'Bosch',  platznummer: 'A1', seriennummer: 'SN-111', status: 'verfuegbar' },
  { name: 'Kreissäge',     maschinen_code: 'M-0002', hersteller: 'Makita', platznummer: 'B2', seriennummer: 'SN-222', status: 'ausgeliehen' },
  { name: 'Akkuschrauber', maschinen_code: 'M-0003', hersteller: 'Bosch',  platznummer: 'A2', seriennummer: 'SN-333', status: 'defekt' },
];
const codes = (r) => r.map((m) => m.maschinen_code);

test('leere Eingabe = ungefilterte Liste', () => {
  assert.equal(filterMaschinen(LISTE, {}).length, 3);
  assert.equal(filterMaschinen(LISTE, { suche: '', status: '' }).length, 3);
});

test('Freitext findet über Name', () => {
  assert.deepEqual(codes(filterMaschinen(LISTE, { suche: 'säge' })), ['M-0002']);
});

test('Freitext findet über Code', () => {
  assert.deepEqual(codes(filterMaschinen(LISTE, { suche: 'm-0003' })), ['M-0003']);
});

test('Freitext findet über Hersteller (mehrere Treffer)', () => {
  assert.deepEqual(codes(filterMaschinen(LISTE, { suche: 'bosch' })), ['M-0001', 'M-0003']);
});

test('Freitext findet über Platznummer', () => {
  assert.deepEqual(codes(filterMaschinen(LISTE, { suche: 'b2' })), ['M-0002']);
});

test('Freitext findet über Seriennummer', () => {
  assert.deepEqual(codes(filterMaschinen(LISTE, { suche: 'sn-222' })), ['M-0002']);
});

test('case-insensitiv und getrimmt', () => {
  assert.deepEqual(codes(filterMaschinen(LISTE, { suche: '  BOHR ' })), ['M-0001']);
});

test('Status-Filter exakt', () => {
  assert.deepEqual(codes(filterMaschinen(LISTE, { status: 'defekt' })), ['M-0003']);
});

test('Suche + Status kombiniert', () => {
  assert.deepEqual(codes(filterMaschinen(LISTE, { suche: 'bosch', status: 'defekt' })), ['M-0003']);
});

test('kein Treffer = leeres Array', () => {
  assert.deepEqual(filterMaschinen(LISTE, { suche: 'xyz' }), []);
});

test('Nicht-Array = leeres Array', () => {
  assert.deepEqual(filterMaschinen(null, {}), []);
});
