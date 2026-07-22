// API-Basis für den nativen Betrieb (Capacitor). Im Web ist die Variable
// nicht gesetzt und alle Pfade bleiben relativ (same-origin).
export function apiUrl(path) {
  const base = globalThis.WERKZEUG_API_BASE || '';
  return base ? base.replace(/\/+$/, '') + path : path;
}
