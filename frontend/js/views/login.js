import { api, setToken } from '../api.js';
import { state } from '../app.js';
import { btnClasses, escapeHtml } from '../ui.js';

export async function renderLogin() {
  state.benutzer = null;
  const app = document.getElementById('app');
  app.innerHTML = `
    <div class="min-h-screen flex items-center justify-center px-4 bg-bg">
      <div class="bg-surface rounded-xl shadow-md p-6 w-full max-w-sm">
        <h1 class="text-2xl font-bold text-txt mb-1">Werkzeug-Ausleihe</h1>
        <p class="text-sm text-muted mb-6">Bitte anmelden.</p>
        <form id="login-form" class="space-y-4" novalidate>
          <div>
            <label class="block text-sm font-medium text-txt-2 mb-1" for="benutzername">Benutzername</label>
            <input id="benutzername" type="text" autocomplete="username" required
                   class="w-full border border-border rounded-lg px-3 py-3 text-base bg-surface text-txt placeholder:text-muted">
          </div>
          <div>
            <label class="block text-sm font-medium text-txt-2 mb-1" for="passwort">Passwort</label>
            <input id="passwort" type="password" autocomplete="current-password" required
                   class="w-full border border-border rounded-lg px-3 py-3 text-base bg-surface text-txt placeholder:text-muted">
          </div>
          <div id="login-fehler" class="text-sm text-rose-600 hidden"></div>
          <button type="submit" class="${btnClasses('primary')} w-full min-h-[56px] text-base font-semibold">
            Anmelden
          </button>
        </form>
      </div>
    </div>`;

  const form    = document.getElementById('login-form');
  const fehler  = document.getElementById('login-fehler');

  form.onsubmit = async (e) => {
    e.preventDefault();
    fehler.classList.add('hidden');
    const benutzername = document.getElementById('benutzername').value.trim();
    const passwort     = document.getElementById('passwort').value;
    if (!benutzername || !passwort) {
      fehler.textContent = 'Bitte beides ausfüllen.';
      fehler.classList.remove('hidden');
      return;
    }
    try {
      const res = await api.post('/api/login', { benutzername, passwort });
      setToken(res.access_token);
      state.benutzer = res.benutzer;
      location.hash = state.istAdmin ? '#/admin' : '#/meine';
    } catch (err) {
      fehler.textContent = err.detail || 'Anmeldung fehlgeschlagen.';
      fehler.classList.remove('hidden');
    }
  };
}
