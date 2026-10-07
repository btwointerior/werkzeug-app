// Admin: Historie der freien Ausgaben (Kleinteile ohne Code) mit Filter + Suche.

import { api } from '../api.js';
import { btnClasses, escapeHtml, leerZustand, spinner } from '../ui.js';
import { freieAusgabeKarte, freieAusgabeZurueckgeben } from './freie_ausgabe.js';

export async function renderAdminFreieAusgaben() {
  const app = document.getElementById('app');
  app.innerHTML = `
    <main class="max-w-3xl mx-auto pb-24 pt-4 px-4">
      <div class="flex items-center justify-between mb-4 gap-2">
        <h1 class="text-2xl font-bold text-txt">📦 Freie Ausgaben</h1>
        <a href="#/admin" class="${btnClasses('secondary')} text-sm">Zurück</a>
      </div>
      <div class="flex gap-2 mb-4">
        <input id="fa-suche" placeholder="Suche (Text, Baustelle, Team, Name)…"
               class="flex-1 border border-border rounded-lg px-3 py-2 bg-surface text-txt placeholder:text-muted">
        <select id="fa-filter" class="border border-border rounded-lg px-3 py-2 bg-surface text-txt">
          <option value="true">Offen</option>
          <option value="alle">Alle</option>
          <option value="false">Zurückgegeben</option>
        </select>
      </div>
      <div id="fa-liste">${spinner()}</div>
    </main>`;

  const suche = document.getElementById('fa-suche');
  const filter = document.getElementById('fa-filter');
  const liste = document.getElementById('fa-liste');
  let eintraege = [];
  let timer = 0;

  async function laden() {
    const params = new URLSearchParams();
    if (filter.value !== 'alle') params.set('offen', filter.value);
    if (suche.value.trim()) params.set('suche', suche.value.trim());
    try {
      eintraege = await api.get(`/api/admin/freie-ausgaben?${params}`);
    } catch (err) {
      liste.innerHTML = `<div class="p-4 text-rose-600">${escapeHtml(err.detail || 'Fehler beim Laden.')}</div>`;
      return;
    }
    if (!eintraege.length) {
      liste.innerHTML = leerZustand('Keine Einträge.');
      return;
    }
    liste.innerHTML = eintraege.map((a) => freieAusgabeKarte(a, {
      mitBenutzer: true,
      aktion: a.ist_offen
        ? `<button data-abschluss="${a.id}" class="${btnClasses('secondary')} text-sm">Abschließen</button>`
        : '',
    })).join('');
    liste.querySelectorAll('[data-abschluss]').forEach((b) => {
      b.onclick = async () => {
        const a = eintraege.find((x) => x.id === +b.dataset.abschluss);
        if (a && await freieAusgabeZurueckgeben(a)) await laden();
      };
    });
  }

  suche.oninput = () => { clearTimeout(timer); timer = setTimeout(laden, 250); };
  filter.onchange = laden;
  await laden();
}
