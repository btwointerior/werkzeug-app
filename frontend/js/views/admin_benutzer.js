import { api } from '../api.js';
import { state } from '../app.js';
import { btnClasses, escapeHtml, modal, spinner, toast } from '../ui.js';

export async function renderAdminBenutzer() {
  const app = document.getElementById('app');
  app.innerHTML = `
    <main class="max-w-3xl mx-auto pb-24 pt-4 px-4">
      <div class="flex items-center justify-between mb-4">
        <h1 class="text-2xl font-bold text-txt">Benutzer</h1>
        <button id="btn-neu" class="${btnClasses('primary')}">+ Neu</button>
      </div>
      <div id="liste">${spinner()}</div>
    </main>`;

  document.getElementById('btn-neu').onclick = () => oeffneFormular(null);
  await lade();

  async function lade() {
    try {
      const benutzer = await api.get('/api/admin/benutzer');
      const liste = document.getElementById('liste');
      liste.innerHTML = benutzer.map((b) => `
        <div class="bg-surface border border-border rounded-lg p-3 mb-2 flex items-center justify-between gap-3">
          <div class="min-w-0">
            <div class="font-medium text-txt truncate">${escapeHtml(b.voller_name)}</div>
            <div class="text-sm text-muted truncate">
              ${escapeHtml(b.benutzername)} · ${escapeHtml(b.rolle)}${b.aktiv ? '' : ' · <span class="text-rose-600 font-medium">gesperrt</span>'}
            </div>
            <div class="text-sm text-muted mt-1 flex items-center gap-2">
              <span>Passwort:</span>
              ${b.passwort_klartext
                ? `<span data-pw="${b.id}" class="font-mono">••••••••</span>
                   <button data-pwtoggle="${b.id}" data-shown="0"
                           class="text-accent text-xs underline">anzeigen</button>`
                : `<span class="italic">— (vor Umstellung gesetzt)</span>`}
            </div>
          </div>
          <button data-id="${b.id}" class="${btnClasses('secondary')} text-sm flex-shrink-0">Bearbeiten</button>
        </div>`).join('');
      liste.querySelectorAll('[data-id]').forEach((btn) => {
        btn.onclick = () => oeffneFormular(benutzer.find((x) => x.id === +btn.dataset.id));
      });
      liste.querySelectorAll('[data-pwtoggle]').forEach((btn) => {
        btn.onclick = () => {
          const id = +btn.dataset.pwtoggle;
          const span = liste.querySelector(`[data-pw="${id}"]`);
          const b = benutzer.find((x) => x.id === id);
          if (!span || !b) return;
          const shown = btn.dataset.shown === '1';
          span.textContent = shown ? '••••••••' : b.passwort_klartext;
          btn.textContent = shown ? 'anzeigen' : 'verbergen';
          btn.dataset.shown = shown ? '0' : '1';
        };
      });
    } catch (err) {
      document.getElementById('liste').innerHTML =
        `<div class="text-rose-600 p-4">${escapeHtml(err.detail)}</div>`;
    }
  }

  async function oeffneFormular(bestand) {
    const istNeu = !bestand;
    const body = document.createElement('div');
    body.innerHTML = `
      <div class="space-y-3 text-sm">
        ${istNeu ? `
          <div>
            <label class="block font-medium text-txt-2 mb-1">Benutzername *</label>
            <input id="bu-username" type="text"
                   class="w-full border border-border rounded-lg px-3 py-2 bg-surface text-txt placeholder:text-muted">
          </div>
          <div>
            <label class="block font-medium text-txt-2 mb-1">Passwort *</label>
            <input id="bu-pw" type="password"
                   class="w-full border border-border rounded-lg px-3 py-2 bg-surface text-txt placeholder:text-muted">
          </div>` : ''}
        <div>
          <label class="block font-medium text-txt-2 mb-1">Vorname *</label>
          <input id="bu-vorname" type="text" value="${escapeHtml(bestand?.vorname || '')}"
                 class="w-full border border-border rounded-lg px-3 py-2 bg-surface text-txt placeholder:text-muted">
        </div>
        <div>
          <label class="block font-medium text-txt-2 mb-1">Nachname *</label>
          <input id="bu-nachname" type="text" value="${escapeHtml(bestand?.nachname || '')}"
                 class="w-full border border-border rounded-lg px-3 py-2 bg-surface text-txt placeholder:text-muted">
        </div>
        <div>
          <label class="block font-medium text-txt-2 mb-1">E-Mail (optional)</label>
          <input id="bu-email" type="email" value="${escapeHtml(bestand?.email || '')}"
                 class="w-full border border-border rounded-lg px-3 py-2 bg-surface text-txt placeholder:text-muted">
        </div>
        <div>
          <label class="block font-medium text-txt-2 mb-1">Rolle</label>
          <select id="bu-rolle" class="w-full border border-border rounded-lg px-3 py-2 bg-surface text-txt">
            <option value="mitarbeiter" ${bestand?.rolle === 'mitarbeiter' ? 'selected' : ''}>Mitarbeiter</option>
            <option value="admin"       ${bestand?.rolle === 'admin'       ? 'selected' : ''}>Admin</option>
          </select>
        </div>
        ${!istNeu ? `
          <div>
            <label class="flex items-center gap-2">
              <input id="bu-aktiv" type="checkbox" ${bestand.aktiv ? 'checked' : ''} class="w-5 h-5 accent-accent">
              <span>Aktiv (Häkchen entfernen = sperren)</span>
            </label>
          </div>
          <div>
            <label class="block font-medium text-txt-2 mb-1">
              Neues Passwort (leer lassen = unverändert)
            </label>
            <input id="bu-pw-neu" type="password"
                   class="w-full border border-border rounded-lg px-3 py-2 bg-surface text-txt placeholder:text-muted">
          </div>` : ''}
      </div>`;

    const buttons = [
      { label: 'Speichern',  variant: 'primary',   value: 'save' },
      { label: 'Abbrechen',  variant: 'secondary', value: null },
    ];
    // Löschen nur bei bestehenden Benutzern und nie für das eigene Konto.
    if (!istNeu && bestand.id !== state.benutzer?.id) {
      buttons.push({ label: 'Löschen', variant: 'danger', value: 'delete' });
    }

    const res = await modal({
      titel: istNeu ? 'Neuer Benutzer' : `Bearbeiten: ${bestand.benutzername}`,
      body,
      buttons,
    });
    if (res === 'delete') { await loescheBenutzer(bestand); return; }
    if (res !== 'save') return;

    try {
      if (istNeu) {
        const benutzername = body.querySelector('#bu-username').value.trim();
        const passwort     = body.querySelector('#bu-pw').value;
        if (!benutzername || !passwort) {
          toast('Benutzername und Passwort sind Pflicht.', 'error');
          return;
        }
        await api.post('/api/admin/benutzer', {
          benutzername,
          passwort,
          vorname:  body.querySelector('#bu-vorname').value.trim(),
          nachname: body.querySelector('#bu-nachname').value.trim(),
          email:    body.querySelector('#bu-email').value.trim() || null,
          rolle:    body.querySelector('#bu-rolle').value,
        });
        toast('Benutzer angelegt.', 'success');
      } else {
        const update = {
          vorname:  body.querySelector('#bu-vorname').value.trim(),
          nachname: body.querySelector('#bu-nachname').value.trim(),
          email:    body.querySelector('#bu-email').value.trim() || null,
          rolle:    body.querySelector('#bu-rolle').value,
          aktiv:    body.querySelector('#bu-aktiv').checked,
        };
        const pw = body.querySelector('#bu-pw-neu').value;
        if (pw) update.neues_passwort = pw;
        await api.put(`/api/admin/benutzer/${bestand.id}`, update);
        toast('Benutzer aktualisiert.', 'success');
      }
      lade();
    } catch (err) {
      toast(err.detail || 'Speichern fehlgeschlagen.', 'error');
    }
  }

  async function loescheBenutzer(bestand) {
    const ok = await modal({
      titel: 'Mitarbeiter löschen',
      body: `<p class="text-sm text-txt-2">Mitarbeiter
             <strong>${escapeHtml(bestand.voller_name)}</strong>
             wirklich endgültig löschen?</p>
             <p class="text-sm text-txt-2 mt-2">Dabei wird auch die komplette
             Ausleih-Historie dieses Mitarbeiters entfernt. Das kann nicht
             rückgängig gemacht werden.</p>`,
      buttons: [
        { label: 'Endgültig löschen', variant: 'danger',    value: 'ok' },
        { label: 'Abbrechen',         variant: 'secondary', value: null },
      ],
    });
    if (ok !== 'ok') return;

    try {
      await api.del(`/api/admin/benutzer/${bestand.id}`);
      toast('Mitarbeiter gelöscht.', 'success');
      lade();
    } catch (err) {
      // z.B. 409: "… hat noch eine offene Ausleihe … zuerst Rückgabe buchen."
      toast(err.detail || 'Löschen fehlgeschlagen.', 'error');
    }
  }
}
