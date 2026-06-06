import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseScan } from '../../frontend/js/scanner.js';

test('volle QR-URL → Code', () => {
  assert.equal(parseScan('https://werkzeug.b2interior.de/#/m/M-0042'), 'M-0042');
});

test('QR-URL mit Kleinbuchstaben → Großbuchstaben', () => {
  assert.equal(parseScan('https://werkzeug.b2interior.de/#/m/m-0042'), 'M-0042');
});

test('nur Hash-Route → Code', () => {
  assert.equal(parseScan('#/m/M-0099'), 'M-0099');
});

test('roher Code → unverändert (groß)', () => {
  assert.equal(parseScan('M-0042'), 'M-0042');
  assert.equal(parseScan('m-0042'), 'M-0042');
});

test('Whitespace wird getrimmt', () => {
  assert.equal(parseScan('  M-0042  '), 'M-0042');
});

test('leer / nur Whitespace → null', () => {
  assert.equal(parseScan(''), null);
  assert.equal(parseScan('   '), null);
});

test('fremde URL ohne #/m/ → null', () => {
  assert.equal(parseScan('https://example.com/etwas'), null);
});

test('Nicht-String → null', () => {
  assert.equal(parseScan(null), null);
  assert.equal(parseScan(undefined), null);
});

test('QR-URL mit Query nach dem Code → nur Code', () => {
  assert.equal(parseScan('https://werkzeug.b2interior.de/#/m/M-0042?x=1'), 'M-0042');
});

test('percent-kodierter Code wird dekodiert', () => {
  assert.equal(parseScan('#/m/M%2D0042'), 'M-0042');
});
