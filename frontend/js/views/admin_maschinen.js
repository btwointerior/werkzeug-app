import { api, oeffneBlobImNeuenTab } from '../api.js';
import {
  btnClasses, confirmDialog, escapeHtml, spinner, statusBadge, toast,
} from '../ui.js';

export async function renderAdminMaschinen() {
  const app = document.getElementById('app');
  const auswahl = new Set();  // ausgewählte Maschinen-IDs

  app.innerHTML = `
    <main class="max-w-3xl mx-auto pb-32 pt-4 px-4">
      <div class="flex items-center justify-between mb-4 gap-2">
        <h1 class="text-2xl font-bold text-slate-900">Maschinen</h1>
        <a href="#/admin/maschinen/neu" class="${btnClasses('primary')}">+ Neu</a>
      </div>
      <div class="flex gap-2 mb-4">
        <input id="filter-suche" placeholder="Suche..."
               class="flex-1 border border-slate-300 rounded-lg px-3 py-2">
        <select id="filter-status" class="border border-slate-300 rounded-lg px-3 py-2">
          <option value="">Alle Status</option>
          <option value="verfuegbar">Verfügbar</option>
          <option value="ausgeliehen">Ausgeliehen</option>
          <option value="defekt">Defekt</option>
          <option value="wartung">In Wartung</option>
        </select>
      </div>
      <div id="liste">${spinner()}</div>
    </main>
    <div id="sammel-bar"
         class="fixed bottom-16 left-0 right-0 bg-white border-t border-slate-200 p-3 z-30 hidden">
      <div class="max-w-3xl mx-auto flex items-center gap-3">
        <span id="sammel-count" class="text-sm text-slate-700"></span>
        <button id="sammel-clear" class="${btnClasses('ghost')} text-sm ml-auto">Auswahl löschen</button>
        <button id="sammel-druck" class="${btnClasses('primary')}">QR-Codes drucken</button>
      </div>
    </div>`;

  const suche = document.getElementById('filter-suche');
  const stat  = document.getElementById('filter-status');
  const liste = document.getElementById('liste');
  const bar   = document.getElementById('sammel-bar');
  const cnt   = document.getElementById('sammel-count');

  document.getElementById('sammel-clear').onclick = () => {
    auswahl.clear();
    aktualisiereBar();
    document.querySelectorAll('input[data-sel]').forEach((c) => { c.checked = false; });
  };
  document.getElementById('sammel-druck').onclick = async () => {
    if (!auswahl.size) return;
    try {
      await oeffneBlobImNeuenTab('/api/admin/qr-codes/sammeldruck', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ maschine_ids: [...auswahl] }),
      });
    } catch (err) {
      toast(err.detail || 'Sammeldruck fehlgeschlagen.', 'error');
    }
  };

  function aktualisiereBar() {
    if (!auswahl.size) {
      bar.classList.add('hidden');
      return;
    }
    bar.classList.remove('hidden');
    cnt.textContent = `${auswahl.size} Maschine${auswahl.size === 1 ? '' : 'n'} ausgewählt`;
  }

  let timer;
  const lade = async () => {
    const params = new URLSearchParams();
    if (suche.value.trim()) params.set('suche', suche.value.trim());
    if (stat.value)         params.set('status', stat.value);

    try {
      const maschinen = await api.get(`/api/admin/maschinen?${params}`);
      if (!maschinen.length) {
        liste.innerHTML = '<div class="text-center py-12 text-slate-500">Keine Treffer.</div>';
        return;
      }
      liste.innerHTML = maschinen.map((m) => `
        <div class="bg-white border border-slate-200 rounded-lg p-3 mb-2">
          <div class="flex items-start gap-3">
            <label class="flex items-center pt-1 cursor-pointer">
              <input type="checkbox" data-sel="${m.id}" ${auswahl.has(m.id) ? 'checked' : ''}
                     class="w-5 h-5">
            </label>
            <a href="#/m/${encodeURIComponent(m.maschinen_code)}" class="flex-1 min-w-0">
              <div class="font-semibold text-slate-900 truncate">${escapeHtml(m.name)}</div>
              <div class="text-sm text-slate-500 truncate">
                ${escapeHtml(m.maschinen_code)}${m.platznummer ? ` · ${escapeHtml(m.platznummer)}` : ''}
              </div>
            </a>
            <div class="flex-shrink-0">${statusBadge(m.status)}</div>
          </div>
          <div class="flex gap-2 mt-3 flex-wrap">
            <a href="#/admin/maschinen/${m.id}/edit" class="${btnClasses('secondary')} text-sm">Bearbeiten</a>
            <a href="#/admin/maschinen/${m.id}/historie" class="${btnClasses('secondary')} text-sm">Historie</a>
            <button data-qr="${m.id}" class="${btnClasses('secondary')} text-sm">QR-Code</button>
            <button data-del="${m.id}" data-name="${escapeHtml(m.name)}"
                    class="${btnClasses('danger')} text-sm ml-auto">Löschen</button>
          </div>
        </div>`).join('');

      liste.querySelectorAll('input[data-sel]').forEach((c) => {
        c.onchange = () => {
          const id = +c.dataset.sel;
          if (c.checked) auswahl.add(id);
          else auswahl.delete(id);
          aktualisiereBar();
        };
      });

      liste.querySelectorAll('[data-qr]').forEach((b) => {
        b.onclick = async () => {
          try {
            await oeffneBlobImNeuenTab(`/api/admin/maschinen/${b.dataset.qr}/qr-code`);
          } catch (err) {
            toast(err.detail || 'QR-Code-Fehler.', 'error');
          }
        };
      });

      liste.querySelectorAll('[data-del]').forEach((b) => {
        b.onclick = async () => {
          const ok = await confirmDialog(
            `Maschine "${b.dataset.name}" wirklich löschen?`,
            { dangerous: true, okLabel: 'Löschen' },
          );
          if (!ok) return;
          try {
            await api.del(`/api/admin/maschinen/${b.dataset.del}`);
            toast('Maschine gelöscht.', 'success');
            auswahl.delete(+b.dataset.del);
            aktualisiereBar();
            lade();
          } catch (err) {
            toast(err.detail || 'Löschen fehlgeschlagen.', 'error');
          }
        };
      });
    } catch (err) {
      liste.innerHTML = `<div class="text-rose-600 p-4">${escapeHtml(err.detail)}</div>`;
    }
  };

  suche.oninput = () => { clearTimeout(timer); timer = setTimeout(lade, 250); };
  stat.onchange = lade;
  lade();
}
