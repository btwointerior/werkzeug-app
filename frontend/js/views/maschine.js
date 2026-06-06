// Maschinenprofil — Hauptbildschirm nach QR-Scan.
//
// Sticky-Bottom-Aktion gemäß State-Matrix:
//   verfuegbar              → AUSLEIHEN (grün)
//   ausgeliehen, Inhaber    → ZURÜCKGEBEN (blau)
//   ausgeliehen, andere     → disabled + Info-Box (Admin: ALS ADMIN ZURÜCKBUCHEN, orange)
//   defekt | wartung        → Info-Box; Admin: FREIGEBEN (orange)

import { api } from '../api.js';
import { state } from '../app.js';
import {
  btnClasses, confirmDialog, escapeHtml, modal, spinner, statusBadge, toast, zeitseit,
} from '../ui.js';

export async function renderMaschine(code) {
  const app = document.getElementById('app');
  app.innerHTML = `<main class="max-w-3xl mx-auto pb-32 pt-4 px-4">${spinner()}</main>`;

  let maschine;
  try {
    maschine = await api.get(`/api/maschinen/by-code/${encodeURIComponent(code)}`);
  } catch (err) {
    if (err.status === 404) {
      app.innerHTML = `
        <main class="max-w-3xl mx-auto pt-8 px-4">
          <div class="bg-surface rounded-lg p-6 border border-border text-center">
            <div class="text-4xl mb-2">❓</div>
            <h2 class="text-lg font-semibold text-txt mb-1">Maschine nicht gefunden</h2>
            <p class="text-muted mb-4">Code <code>${escapeHtml(code)}</code> existiert nicht.</p>
            <a href="#/meine" class="${btnClasses('secondary')} inline-block">Zurück</a>
          </div>
        </main>`;
    } else {
      app.innerHTML =
        `<main class="max-w-3xl mx-auto pt-8 px-4 text-rose-600">${escapeHtml(err.detail || 'Fehler')}</main>`;
    }
    return;
  }

  zeichne();

  function zeichne() {
    const m = maschine;
    const a = m.aktuelle_ausleihe;
    const userIstInhaber = !!a && a.benutzer_id === state.benutzer.id;
    const userIstAdmin   = state.istAdmin;

    const aktion = aktionFuerStatus(m, userIstInhaber, userIstAdmin);

    app.innerHTML = `
      <main class="max-w-3xl mx-auto pb-40 pt-4 px-4">
        <div class="flex items-start justify-between gap-3 mb-3">
          <div class="min-w-0">
            <h1 class="text-2xl font-bold text-txt break-words">${escapeHtml(m.name)}</h1>
            <div class="text-sm text-muted mt-1">
              ${escapeHtml(m.maschinen_code)}${m.platznummer ? ` · ${escapeHtml(m.platznummer)}` : ''}
            </div>
          </div>
          <div class="flex-shrink-0">${statusBadge(m.status)}</div>
        </div>

        ${a ? `
          <div class="bg-surface-2 border border-border rounded-lg p-4 mb-4">
            <div class="text-xs uppercase tracking-wide text-lent font-semibold">Aktuell ausgeliehen</div>
            <div class="text-txt font-medium mt-1">${escapeHtml(a.benutzer.voller_name)}</div>
            <div class="text-txt-2 text-sm">${zeitseit(a.ausleih_zeitpunkt)}</div>
          </div>` : ''}

        ${m.status === 'defekt' ? `
          <div class="bg-surface-2 border border-border text-broken rounded-lg p-4 mb-4">
            <div class="font-semibold">Als defekt gemeldet</div>
            <div class="text-sm">Die Maschine ist gesperrt und kann nur von einem Admin freigegeben werden.</div>
          </div>` : ''}

        ${m.status === 'wartung' ? `
          <div class="bg-surface-2 border border-border text-maint rounded-lg p-4 mb-4">
            <div class="font-semibold">In Wartung</div>
            <div class="text-sm">Die Maschine ist gesperrt und kann nur von einem Admin freigegeben werden.</div>
          </div>` : ''}

        ${m.foto_url ? `
          <img src="${escapeHtml(m.foto_url)}" alt="${escapeHtml(m.name)}"
               class="w-full aspect-video object-contain bg-surface-2 border border-border rounded-lg mb-4">
        ` : `
          <div class="bg-surface-2 border border-border rounded-lg aspect-video flex items-center justify-center text-muted mb-4">
            <div class="text-center">
              <div class="text-3xl">📷</div>
              <div class="text-xs mt-1">Kein Foto hinterlegt</div>
            </div>
          </div>
        `}

        <div class="bg-surface rounded-lg border border-border p-4 mb-4">
          <h2 class="text-sm font-semibold text-txt-2 mb-2">Details</h2>
          <dl class="grid grid-cols-3 gap-y-2 text-sm">
            ${m.hersteller   ? `<dt class="text-muted">Hersteller</dt><dd class="col-span-2 text-txt">${escapeHtml(m.hersteller)}</dd>` : ''}
            ${m.seriennummer ? `<dt class="text-muted">Seriennr.</dt><dd class="col-span-2 text-txt">${escapeHtml(m.seriennummer)}</dd>` : ''}
            ${m.platznummer  ? `<dt class="text-muted">Platz</dt><dd class="col-span-2 text-txt">${escapeHtml(m.platznummer)}</dd>` : ''}
          </dl>
        </div>

        ${m.beschreibung ? `
          <div class="bg-surface rounded-lg border border-border p-4 mb-4">
            <h2 class="text-sm font-semibold text-txt-2 mb-2">Beschreibung</h2>
            <p class="text-sm text-txt whitespace-pre-wrap">${escapeHtml(m.beschreibung)}</p>
          </div>` : ''}

        ${m.zubehoer_liste.length ? `
          <div class="bg-surface rounded-lg border border-border p-4 mb-4">
            <h2 class="text-sm font-semibold text-txt-2 mb-2">Zubehör</h2>
            <ul class="text-sm text-txt space-y-1">
              ${m.zubehoer_liste.map((z) => `<li>• ${escapeHtml(z.bezeichnung)}</li>`).join('')}
            </ul>
          </div>` : ''}

        ${m.anleitung_url ? `
          <a href="${escapeHtml(m.anleitung_url)}" target="_blank" rel="noopener"
             class="${btnClasses('secondary')} w-full mb-4">
            📄 Betriebsanleitung öffnen
          </a>
        ` : `
          <button class="${btnClasses('secondary')} w-full mb-4" disabled>
            📄 Keine Anleitung hinterlegt
          </button>
        `}
      </main>

      <div class="fixed bottom-16 left-0 right-0 bg-surface border-t border-border p-3 z-30">
        <div class="max-w-3xl mx-auto">
          ${aktion.html}
        </div>
      </div>`;

    if (aktion.id && aktion.handler) {
      const btn = document.getElementById(aktion.id);
      if (btn) btn.onclick = aktion.handler;
    }
  }

  function aktionFuerStatus(m, istInhaber, istAdmin) {
    if (m.status === 'verfuegbar') {
      return {
        id: 'btn-ausleihen',
        html: `<button id="btn-ausleihen" class="${btnClasses('success')} w-full min-h-[60px] text-lg font-semibold">AUSLEIHEN</button>`,
        handler: ausleihenKlick,
      };
    }
    if (m.status === 'ausgeliehen') {
      if (istInhaber) {
        return {
          id: 'btn-zurueck',
          html: `<button id="btn-zurueck" class="${btnClasses('primary')} w-full min-h-[60px] text-lg font-semibold">ZURÜCKGEBEN</button>`,
          handler: zurueckKlick,
        };
      }
      if (istAdmin) {
        return {
          id: 'btn-zurueck',
          html: `<button id="btn-zurueck" class="${btnClasses('warning')} w-full min-h-[60px] text-lg font-semibold">ALS ADMIN ZURÜCKBUCHEN</button>`,
          handler: zurueckKlick,
        };
      }
      return {
        html: `<button class="${btnClasses('secondary')} w-full min-h-[60px] text-lg" disabled>Bei jemand anderem ausgeliehen</button>`,
      };
    }
    if (m.status === 'defekt' || m.status === 'wartung') {
      if (istAdmin) {
        return {
          id: 'btn-freigeben',
          html: `<button id="btn-freigeben" class="${btnClasses('warning')} w-full min-h-[60px] text-lg font-semibold">FREIGEBEN</button>`,
          handler: freigebenKlick,
        };
      }
      const label = m.status === 'defekt' ? 'Defekt — gesperrt' : 'In Wartung — gesperrt';
      return {
        html: `<button class="${btnClasses('secondary')} w-full min-h-[60px] text-lg" disabled>${label}</button>`,
      };
    }
    return { html: '' };
  }

  async function ausleihenKlick() {
    let teams = [];
    try {
      teams = await api.get('/api/maschinen/externe-teams');
    } catch {
      teams = [];  // Dropdown bleibt leer; freie Eingabe weiterhin möglich
    }
    const auswahl = await ausleihDialog(maschine.zubehoer_liste, teams);
    if (auswahl === null) return;  // abgebrochen
    try {
      maschine = await api.post(`/api/maschinen/${maschine.id}/ausleihen`, auswahl);
      toast('Maschine erfolgreich ausgeliehen.', 'success');
      zeichne();
    } catch (err) {
      toast(err.detail || 'Fehler beim Ausleihen.', 'error');
    }
  }

  async function freigebenKlick() {
    try {
      maschine = await api.post(`/api/admin/maschinen/${maschine.id}/freigeben`);
      toast('Maschine freigegeben.', 'success');
      zeichne();
    } catch (err) {
      toast(err.detail || 'Fehler beim Freigeben.', 'error');
    }
  }

  async function zurueckKlick() {
    const mitgenommen =
      (maschine.aktuelle_ausleihe && maschine.aktuelle_ausleihe.mitgenommenes_zubehoer) || [];
    const eingabe = await rueckgabeModal(mitgenommen);
    if (!eingabe) return;
    try {
      maschine = await api.post(`/api/maschinen/${maschine.id}/zurueckgeben`, eingabe);
      toast('Maschine zurückgegeben.', 'success');
      zeichne();
    } catch (err) {
      toast(err.detail || 'Fehler bei der Rückgabe.', 'error');
    }
  }
}

async function ausleihDialog(zubehoerListe, bekannteTeams = []) {
  const body = document.createElement('div');
  body.innerHTML = `
    <p class="text-sm font-medium text-txt-2 mb-2">Für wen leihst du aus?</p>
    <div class="space-y-2 mb-3">
      <label class="flex items-center gap-3 p-3 border border-border rounded-lg cursor-pointer hover:bg-surface-2">
        <input type="radio" name="empf" value="mich" checked class="w-5 h-5">
        <span class="font-medium">Für mich</span>
      </label>
      <label class="flex items-center gap-3 p-3 border border-border rounded-lg cursor-pointer hover:bg-surface-2">
        <input type="radio" name="empf" value="team" class="w-5 h-5">
        <span class="font-medium">Für externes Montageteam</span>
      </label>
    </div>
    <div id="team-feld" class="mb-4 hidden">
      <label class="block text-sm font-medium text-txt-2 mb-1" for="team-name">Team-Name</label>
      <input id="team-name" list="team-liste" autocomplete="off"
             class="w-full border border-border rounded-lg p-2 text-sm bg-surface text-txt placeholder:text-muted-2"
             placeholder="Team auswählen oder neu eingeben">
      <datalist id="team-liste">
        ${bekannteTeams.map((t) => `<option value="${escapeHtml(t)}"></option>`).join('')}
      </datalist>
      <p id="team-fehler" class="text-sm text-rose-600 mt-1 hidden">
        Bitte einen Team-Namen eingeben.
      </p>
    </div>
    ${zubehoerListe.length ? `
      <p class="text-sm text-muted mb-2">Welches Zubehör nimmst du mit? Hake an, was du mitnimmst.</p>
      <div class="space-y-2">
        ${zubehoerListe.map((z) => `
          <label class="flex items-center gap-3 p-3 border border-border rounded-lg cursor-pointer hover:bg-surface-2">
            <input type="checkbox" value="${escapeHtml(z.bezeichnung)}" class="w-5 h-5">
            <span class="font-medium">${escapeHtml(z.bezeichnung)}</span>
          </label>`).join('')}
      </div>` : ''}`;

  // Team-Eingabefeld nur zeigen, wenn "externes Montageteam" gewählt ist.
  body.querySelectorAll('input[name=empf]').forEach((r) => {
    r.addEventListener('change', () => {
      const istTeam = body.querySelector('input[name=empf]:checked').value === 'team';
      body.querySelector('#team-feld').classList.toggle('hidden', !istTeam);
    });
  });

  const result = await modal({
    titel: 'Maschine ausleihen',
    body,
    buttons: [
      {
        label: 'Ausleihen',
        variant: 'success',
        value: 'go',
        onClick: () => {
          body.querySelector('#team-fehler').classList.add('hidden');
          const istTeam = body.querySelector('input[name=empf]:checked').value === 'team';
          if (istTeam && !body.querySelector('#team-name').value.trim()) {
            body.querySelector('#team-fehler').classList.remove('hidden');
            body.querySelector('#team-name').focus();
            return false;  // Modal offen lassen
          }
          return true;
        },
      },
      { label: 'Abbrechen', variant: 'secondary', value: null },
    ],
  });
  if (result !== 'go') return null;

  const istTeam = body.querySelector('input[name=empf]:checked').value === 'team';
  const externes_team = istTeam ? body.querySelector('#team-name').value.trim() : null;

  const zubehoer_bezeichnungen = [...body.querySelectorAll('input[type=checkbox]:checked')]
    .map((c) => c.value);

  if (zubehoerListe.length && zubehoer_bezeichnungen.length === 0) {
    const ok = await confirmDialog('Wirklich ohne Zubehör ausleihen?', {
      titel: 'Ohne Zubehör?',
      okLabel: 'Ja, ohne Zubehör',
    });
    if (!ok) return null;
  }
  return { zubehoer_bezeichnungen, externes_team };
}

async function rueckgabeModal(mitgenommen = []) {
  const body = document.createElement('div');
  body.innerHTML = `
    <p class="text-sm text-muted mb-3">Wie ist der Zustand?</p>
    <div class="space-y-2 mb-4">
      <label class="flex items-center gap-3 p-3 border border-border rounded-lg cursor-pointer hover:bg-surface-2">
        <input type="radio" name="zust" value="ok" checked class="w-5 h-5">
        <span class="font-medium">Alles in Ordnung</span>
      </label>
      <label class="flex items-center gap-3 p-3 border border-border rounded-lg cursor-pointer hover:bg-surface-2">
        <input type="radio" name="zust" value="defekt" class="w-5 h-5">
        <span class="font-medium text-broken">Defekt</span>
      </label>
      <label class="flex items-center gap-3 p-3 border border-border rounded-lg cursor-pointer hover:bg-surface-2">
        <input type="radio" name="zust" value="wartung" class="w-5 h-5">
        <span class="font-medium text-maint">Wartung nötig</span>
      </label>
    </div>
    ${mitgenommen.length ? `
      <div class="mb-4">
        <p class="text-sm font-medium text-txt-2 mb-2">Zubehör zurückgegeben?</p>
        <div class="space-y-2">
          ${mitgenommen.map((z) => `
            <label class="flex items-center gap-3 p-3 border border-border rounded-lg cursor-pointer hover:bg-surface-2">
              <input type="checkbox" data-zid="${z.id}" checked class="w-5 h-5">
              <span class="text-sm">${escapeHtml(z.bezeichnung)}</span>
            </label>`).join('')}
        </div>
      </div>` : ''}
    <label class="block text-sm font-medium text-txt-2 mb-1" for="r-komm">Kommentar (optional)</label>
    <p id="r-komm-pflicht" class="text-sm text-rose-600 mb-2 hidden">
      Es fehlt Zubehör — bitte im Kommentar angeben, was los ist.
    </p>
    <textarea id="r-komm" rows="3"
              class="w-full border border-border rounded-lg p-2 text-sm bg-surface text-txt placeholder:text-muted-2"
              placeholder="Was ist passiert?"></textarea>`;

  const result = await modal({
    titel: 'Maschine zurückgeben',
    body,
    buttons: [
      {
        label: 'Bestätigen',
        variant: 'primary',
        value: 'go',
        onClick: () => {
          body.querySelector('#r-komm-pflicht').classList.add('hidden');
          if (mitgenommen.length) {
            const zurueck = body.querySelectorAll('input[data-zid]:checked').length;
            const fehlt = zurueck < mitgenommen.length;
            const komm = body.querySelector('#r-komm').value.trim();
            if (fehlt && !komm) {
              body.querySelector('#r-komm-pflicht').classList.remove('hidden');
              body.querySelector('#r-komm').focus();
              return false;  // Modal offen lassen
            }
          }
          return true;
        },
      },
      { label: 'Abbrechen', variant: 'secondary', value: null },
    ],
  });
  if (result !== 'go') return null;

  const zustand   = body.querySelector('input[name=zust]:checked').value;
  const kommentar = body.querySelector('#r-komm').value.trim() || null;

  const payload = { zustand, kommentar };
  if (mitgenommen.length) {
    payload.zurueckgebrachte_zubehoer_ids =
      [...body.querySelectorAll('input[data-zid]:checked')]
        .map((c) => Number(c.dataset.zid));
  }
  return payload;
}
