import { test } from 'node:test';
import assert from 'node:assert/strict';
import { holeWerkzeugCode } from '../../frontend/js/scanner_quelle.js';

test('liefert den Code der übergebenen Quelle', async () => {
  assert.equal(await holeWerkzeugCode(async () => 'M-0001'), 'M-0001');
});

test('reicht null (Abbruch) durch', async () => {
  assert.equal(await holeWerkzeugCode(async () => null), null);
});
