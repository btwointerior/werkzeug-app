import { test } from 'node:test';
import assert from 'node:assert/strict';
import { zielMasse, MAX_KANTE_PX } from '../../frontend/js/kamera.js';

test('kleine Bilder bleiben unverändert', () => {
  assert.deepEqual(zielMasse(800, 600), { w: 800, h: 600 });
});

test('Querformat wird auf lange Kante 1600 verkleinert', () => {
  assert.deepEqual(zielMasse(4032, 3024), { w: 1600, h: 1200 });
});

test('Hochformat wird auf lange Kante 1600 verkleinert', () => {
  assert.deepEqual(zielMasse(3024, 4032), { w: 1200, h: 1600 });
});

test('eigene maximale Kante', () => {
  assert.deepEqual(zielMasse(4000, 2000, 1000), { w: 1000, h: 500 });
});

test('ungültige Maße liefern 0x0', () => {
  assert.deepEqual(zielMasse(0, 0), { w: 0, h: 0 });
});

test('Standardkante ist 1600', () => {
  assert.equal(MAX_KANTE_PX, 1600);
});
