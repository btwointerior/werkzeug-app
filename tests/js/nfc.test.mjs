import { test } from 'node:test';
import assert from 'node:assert/strict';
import { baueTagUrl, extrahiereCode } from '../../frontend/js/nfc_helfer.js';

test('baueTagUrl setzt Basis und Code zur QR-URL zusammen', () => {
  assert.equal(
    baueTagUrl('https://werkzeug.b2interior.de', 'M-0001'),
    'https://werkzeug.b2interior.de/#/m/M-0001'
  );
});

test('baueTagUrl toleriert End-Slash und kodiert den Code', () => {
  assert.equal(
    baueTagUrl('https://werkzeug.b2interior.de/', 'M 1/A'),
    'https://werkzeug.b2interior.de/#/m/M%201%2FA'
  );
});

test('extrahiereCode holt den Code aus einer Tag-URL (via parseScan)', () => {
  assert.equal(extrahiereCode('https://werkzeug.b2interior.de/#/m/M-0001'), 'M-0001');
});

test('extrahiereCode akzeptiert rohe Codes und lehnt Müll ab', () => {
  assert.equal(extrahiereCode('m-0001'), 'M-0001');
  assert.equal(extrahiereCode('https://fremde-seite.de/irgendwas'), null);
  assert.equal(extrahiereCode(''), null);
});
