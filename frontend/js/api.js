// Fetch-Wrapper: Bearer-Token, Sliding-Window via X-New-Token,
// einheitliche Fehler. Stellt sowohl `api.get/post/put/del` (JSON) als auch
// `authFetch` (für Blobs/Form-Data) bereit.

import { toast } from './ui.js';
import { apiUrl } from './api_base.js';

const TOKEN_KEY = 'wkz_token';

export const getToken   = () => localStorage.getItem(TOKEN_KEY);
export const setToken   = (t) => localStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

export class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === 'string' ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = typeof detail === 'string' ? detail : JSON.stringify(detail);
  }
}

// Low-Level: fetch mit Bearer-Header + Token-Refresh + 401-Handling.
// Liefert die rohe Response zurück — Aufrufer entscheidet .json() / .blob().
export async function authFetch(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  const token = getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;

  let res;
  try {
    res = await fetch(apiUrl(path), { ...options, headers });
  } catch {
    throw new ApiError(0, 'Netzwerkfehler. Server nicht erreichbar.');
  }

  const newToken = res.headers.get('X-New-Token');
  if (newToken) setToken(newToken);

  if (res.status === 401) {
    clearToken();
    if (location.hash !== '#/login') {
      toast('Sitzung abgelaufen. Bitte erneut anmelden.', 'error');
      location.hash = '#/login';
    }
    throw new ApiError(401, 'Nicht angemeldet.');
  }
  return res;
}

async function request(method, path, body) {
  const opts = { method, headers: {} };

  if (body instanceof FormData) {
    opts.body = body;  // Content-Type setzt der Browser selbst (mit boundary)
  } else if (body !== undefined && body !== null) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }

  const res = await authFetch(path, opts);

  if (res.status === 204) return null;

  let data = null;
  try { data = await res.json(); } catch { /* ignore */ }

  if (!res.ok) {
    const detail = data && data.detail ? data.detail : `Fehler ${res.status}`;
    throw new ApiError(res.status, detail);
  }
  return data;
}

export const api = {
  get:  (path)         => request('GET',    path),
  post: (path, body)   => request('POST',   path, body !== undefined ? body : {}),
  put:  (path, body)   => request('PUT',    path, body !== undefined ? body : {}),
  del:  (path)         => request('DELETE', path),
};

// Helfer: lädt eine URL und öffnet sie als Blob im neuen Tab (für PDFs etc.).
export async function oeffneBlobImNeuenTab(path, options = {}) {
  const res = await authFetch(path, options);
  if (!res.ok) {
    let detail = `Fehler ${res.status}`;
    try { const d = await res.json(); if (d.detail) detail = d.detail; } catch {}
    throw new ApiError(res.status, detail);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  window.open(url, '_blank');
  // Erst nach 60s aufräumen, damit der neue Tab Zeit hatte zu laden
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
