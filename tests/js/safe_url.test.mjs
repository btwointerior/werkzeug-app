import { test } from 'node:test';
import assert from 'node:assert/strict';
import { safeUrl } from '../../frontend/js/ui.js';

test('http- und https-URLs bleiben erhalten', () => {
  assert.equal(safeUrl('https://example.com/foo.pdf'), 'https://example.com/foo.pdf');
  assert.equal(safeUrl('http://example.com/bild.jpg'), 'http://example.com/bild.jpg');
});

test('relative Pfade (Uploads) bleiben erhalten', () => {
  assert.equal(safeUrl('/uploads/maschine_1_foto.jpg?t=abc'), '/uploads/maschine_1_foto.jpg?t=abc');
});

test('javascript:-URLs werden geblockt', () => {
  assert.equal(safeUrl('javascript:alert(1)'), '#');
  assert.equal(safeUrl('  JavaScript:alert(1)'), '#');
});

test('data:- und andere Schemata werden geblockt', () => {
  assert.equal(safeUrl('data:text/html,<script>'), '#');
  assert.equal(safeUrl('vbscript:msgbox'), '#');
});

test('leer / nicht-String → leer', () => {
  assert.equal(safeUrl(''), '');
  assert.equal(safeUrl(null), '');
  assert.equal(safeUrl(undefined), '');
});
