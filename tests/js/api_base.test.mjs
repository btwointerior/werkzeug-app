import { test, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { apiUrl } from '../../frontend/js/api_base.js';

afterEach(() => { delete globalThis.WERKZEUG_API_BASE; });

test('ohne Basis bleibt der Pfad unverändert', () => {
  assert.equal(apiUrl('/api/me'), '/api/me');
});

test('mit Basis wird der Pfad gepräfixt', () => {
  globalThis.WERKZEUG_API_BASE = 'https://werkzeug.b2interior.de';
  assert.equal(apiUrl('/api/me'), 'https://werkzeug.b2interior.de/api/me');
});

test('Basis mit End-Slash erzeugt keinen Doppel-Slash', () => {
  globalThis.WERKZEUG_API_BASE = 'https://werkzeug.b2interior.de/';
  assert.equal(apiUrl('/api/me'), 'https://werkzeug.b2interior.de/api/me');
});
