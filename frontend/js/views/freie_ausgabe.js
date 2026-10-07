// Freie Ausgabe: Kleinteile ohne Maschinen-Code (Schraubzwingen, Spritzen, …).
// Ablauf: Kamera (Pflicht-Foto) → Dialog (Fotos, Beschreibung, Empfänger) →
// POST. Rückgabe schließt den Eintrag ab; Karte wird auf „Meine" + Admin genutzt.

import { api } from '../api.js';
import { apiUrl } from '../api_base.js';
import { kameraOverlay, verkleinereDatei } from '../kamera.js';
import {
  btnClasses, escapeHtml, modal, safeUrl, toast, zeitseit, formatDatum,
} from '../ui.js';

const MAX_FOTOS = 3;

function hatKamera() {
  return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
}

// Startet den kompletten Erfassungs-Ablauf. Liefert die angelegte Ausgabe
// oder null (abgebrochen). Zeigt selbst Toasts.
export async function neueFreieAusgabe() {
  let fotos = [];
  if (hatKamera()) {
    fotos = await kameraOverlay(MAX_FOTOS, { titel: 'Foto von dem, was ausgegeben wird (Pflicht)' });
    if (!fotos.length) {
      toast('Ohne Foto keine Ausgabe — bitte Foto aufnehmen.', 'info');
      // Dialog trotzdem öffnen: dort kann erneut fotografiert oder eine Datei gewählt werden.
    }
  }

  let bekannteTeams = [];
  try { bekannteTeams = await api.get('/api/maschinen/externe-teams'); } catch { /* optional */ }

  const body = document.createElement('div');
  body.innerHTML = `
    <p class="text-sm text-muted mb-2">Foto (Pflicht, max. ${MAX_FOTOS})</p>
    <div id="fa-fotos" class="flex gap-2 flex-wrap mb-2"></div>
    <div class="flex gap-2 mb-4 flex-wrap">
      ${hatKamera() ? `<button type="button" id="fa-kamera" class="${btnClasses('secondary')} text-sm">📷 Foto aufnehmen</button>` : ''}
      <label class="${btnClasses('ghost')} text-sm cursor-pointer">
        Datei wählen
        <input type="file" id="fa-datei" accept="image/*" multiple class="hidden">
      </label>
    </div>
    <p id="fa-foto-fehler" class="text-sm text-rose-600 mb-3 hidden">Mindestens ein Foto ist Pflicht.</p>

    <label class="block text-sm font-medium text-txt-2 mb-1" for="fa-text">Was wird ausgegeben?</label>
    <textarea id="fa-text" rows="2" maxlength="500" placeholder="z.B. 2 Schraubzwingen 300 mm"
              class="w-full border border-border rounded-lg px-3 py-2 text-base bg-surface text-txt placeholder:text-muted mb-1"></textarea>
    <p id="fa-text-fehler" class="text-sm text-rose-600 mb-3 hidden">Bitte eine Beschreibung eingeben.</p>

    <label class="block text-sm font-medium text-txt-2 mb-1 mt-3" for="fa-baustelle">Baustelle <span class="text-muted font-normal">(optional)</span></label>
    <input id="fa-baustelle" type="text" maxlength="120" placeholder="z.B. Klinikum Böblingen"
           class="w-full border border-border rounded-lg px-3 py-2 text-base bg-surface text-txt placeholder:text-muted">

    <p class="text-sm text-muted mb-2 mt-3">An wen?</p>
    <div class="space-y-2 mb-2">
      <label class="flex items-center gap-3 p-3 border border-border rounded-lg cursor-pointer hover:bg-surface-2">
        <input type="radio" name="fa-empf" value="mich" checked class="w-5 h-5">
        <span class="font-medium">Für mich</span>
      </label>
      <label class="flex items-center gap-3 p-3 border border-border rounded-lg cursor-pointer hover:bg-surface-2">
        <input type="radio" name="fa-empf" value="team" class="w-5 h-5">
        <span class="font-medium">Externes Montageteam</span>
      </label>
    </div>
    <div id="fa-team-feld" class="hidden mb-2">
      <input id="fa-team" list="fa-team-liste" type="text" maxlength="120"
             class="w-full border border-border rounded-lg p-2 text-sm bg-surface text-txt placeholder:text-muted"
             placeholder="Team auswählen oder neu eingeben">
      <datalist id="fa-team-liste">
        ${bekannteTeams.map((t) => `<option value="${escapeHtml(t)}"></option>`).join('')}
      </datalist>
      <p id="fa-team-fehler" class="text-sm text-rose-600 mt-1 hidden">Bitte einen Team-Namen eingeben.</p>
    </div>`;

  const fotoWrap = body.querySelector('#fa-fotos');
  const urls = [];
  const renderFotos = () => {
    urls.forEach((u) => URL.revokeObjectURL(u));
    urls.length = 0;
    fotoWrap.innerHTML = fotos.map((f, i) => {
      const u = URL.createObjectURL(f);
      urls.push(u);
      return `
        <div class="relative w-20 h-20">
          <img src="${u}" alt="Foto ${i + 1}" class="w-20 h-20 object-cover rounded-lg border border-border">
          <button type="button" data-del="${i}" aria-label="Foto entfernen"
                  class="absolute -top-2 -right-2 w-6 h-6 rounded-full bg-broken text-accent-ink text-xs leading-6 text-center">✕</button>
        </div>`;
    }).join('') || '<div class="text-sm text-muted">Noch kein Foto.</div>';
    fotoWrap.querySelectorAll('[data-del]').forEach((b) => {
      b.onclick = () => { fotos.splice(+b.dataset.del, 1); renderFotos(); };
    });
    if (fotos.length) body.querySelector('#fa-foto-fehler').classList.add('hidden');
  };
  renderFotos();

  const kamBtn = body.querySelector('#fa-kamera');
  if (kamBtn) {
    kamBtn.onclick = async () => {
      const neue = await kameraOverlay(MAX_FOTOS - fotos.length);
      fotos = fotos.concat(neue).slice(0, MAX_FOTOS);
      renderFotos();
    };
  }
  body.querySelector('#fa-datei').onchange = async (e) => {
    const gewaehlt = [...(e.target.files || [])].slice(0, MAX_FOTOS - fotos.length);
    e.target.value = '';
    if (!gewaehlt.length) { if (fotos.length >= MAX_FOTOS) toast(`Maximal ${MAX_FOTOS} Fotos.`, 'info'); return; }
    const klein = await Promise.all(gewaehlt.map((f) => verkleinereDatei(f)));
    fotos = fotos.concat(klein);
    renderFotos();
  };
  body.querySelector('#fa-text').addEventListener('input', (e) => {
    if (e.target.value.trim()) body.querySelector('#fa-text-fehler').classList.add('hidden');
  });
  body.querySelectorAll('input[name=fa-empf]').forEach((r) => {
    r.addEventListener('change', () => {
      const istTeam = body.querySelector('input[name=fa-empf]:checked').value === 'team';
      body.querySelector('#fa-team-feld').classList.toggle('hidden', !istTeam);
      if (istTeam) body.querySelector('#fa-team').focus();
    });
  });

  let ergebnis = null;
  const result = await modal({
    titel: 'Ohne Code ausgeben',
    body,
    buttons: [
      {
        label: 'Ausgeben',
        variant: 'success',
        value: 'go',
        onClick: async () => {
          let ok = true;
          const text = body.querySelector('#fa-text').value.trim();
          body.querySelector('#fa-foto-fehler').classList.toggle('hidden', fotos.length > 0);
          body.querySelector('#fa-text-fehler').classList.toggle('hidden', !!text);
          if (!fotos.length || !text) ok = false;
          const istTeam = body.querySelector('input[name=fa-empf]:checked').value === 'team';
          const team = istTeam ? body.querySelector('#fa-team').value.trim() : '';
          body.querySelector('#fa-team-fehler').classList.toggle('hidden', !(istTeam && !team));
          if (istTeam && !team) ok = false;
          if (!ok) return false;

          const fd = new FormData();
          fd.append('beschreibung', text);
          const baustelle = body.querySelector('#fa-baustelle').value.trim();
          if (baustelle) fd.append('baustelle', baustelle);
          if (team) fd.append('externes_team', team);
          fotos.forEach((f) => fd.append('dateien', f, f.name));
          try {
            ergebnis = await api.post('/api/freie-ausgaben', fd);
            return true;
          } catch (err) {
            toast(err.detail || 'Fehler beim Ausgeben.', 'error');
            return false;
          }
        },
      },
      { label: 'Abbrechen', variant: 'secondary', value: null },
    ],
  });
  urls.forEach((u) => URL.revokeObjectURL(u));
  if (result !== 'go' || !ergebnis) return null;
  toast('Ausgabe erfasst.', 'success');
  return ergebnis;
}

// Rückgabe-Dialog; liefert die aktualisierte Ausgabe oder null.
export async function freieAusgabeZurueckgeben(ausgabe) {
  const body = document.createElement('div');
  body.innerHTML = `
    <p class="text-sm text-txt-2 mb-3">„${escapeHtml(ausgabe.beschreibung)}" zurückgeben?</p>
    <label class="block text-sm font-medium text-txt-2 mb-1" for="fa-rk">Bemerkung (optional)</label>
    <textarea id="fa-rk" rows="2" maxlength="1000" placeholder="z.B. eine Zwinge verbogen"
              class="w-full border border-border rounded-lg px-3 py-2 text-base bg-surface text-txt placeholder:text-muted"></textarea>`;
  let ergebnis = null;
  const result = await modal({
    titel: 'Zurückgeben',
    body,
    buttons: [
      {
        label: 'Zurückgeben',
        variant: 'success',
        value: 'go',
        onClick: async () => {
          try {
            const kommentar = body.querySelector('#fa-rk').value.trim() || null;
            ergebnis = await api.post(`/api/freie-ausgaben/${ausgabe.id}/zurueckgeben`, { kommentar });
            return true;
          } catch (err) {
            toast(err.detail || 'Fehler bei der Rückgabe.', 'error');
            return false;
          }
        },
      },
      { label: 'Abbrechen', variant: 'secondary', value: null },
    ],
  });
  if (result !== 'go' || !ergebnis) return null;
  toast('Zurückgegeben.', 'success');
  return ergebnis;
}

// Karte für Listen („Meine", Admin-Historie). `aktion` = HTML für Buttons rechts.
export function freieAusgabeKarte(a, { aktion = '', mitBenutzer = false } = {}) {
  const foto = a.fotos && a.fotos[0];
  const fotoHtml = foto
    ? `<a href="${escapeHtml(safeUrl(apiUrl(foto.url)))}" target="_blank" rel="noopener" class="flex-shrink-0">
         <img src="${escapeHtml(safeUrl(apiUrl(foto.url)))}" alt="" class="w-16 h-16 object-cover rounded-lg border border-border">
       </a>`
    : '<div class="w-16 h-16 rounded-lg bg-surface-2 flex-shrink-0"></div>';
  const weitere = (a.fotos || []).slice(1).map((f) =>
    `<a href="${escapeHtml(safeUrl(apiUrl(f.url)))}" target="_blank" rel="noopener"
        class="text-xs text-accent underline">weiteres Foto</a>`).join(' ');
  const wer = mitBenutzer ? `${escapeHtml(a.benutzer.voller_name)}` : '';
  const an = a.externes_team_name ? `<span class="text-muted">für</span> ${escapeHtml(a.externes_team_name)}` : '';
  const zeit = a.ist_offen
    ? `${zeitseit(a.ausgabe_zeitpunkt)}`
    : `${formatDatum(a.ausgabe_zeitpunkt)} – ${formatDatum(a.rueckgabe_zeitpunkt)} (${a.dauer_tage} Tag${a.dauer_tage === 1 ? '' : 'e'})`;
  return `
    <div class="bg-surface rounded-lg shadow-sm p-3 mb-3 border border-border flex gap-3 items-start" data-fa-id="${a.id}">
      ${fotoHtml}
      <div class="min-w-0 flex-1">
        <div class="font-semibold text-txt [overflow-wrap:anywhere]">${escapeHtml(a.beschreibung)}</div>
        <div class="text-sm text-muted">${[wer, an].filter(Boolean).join(' ')}</div>
        ${a.baustelle ? `<div class="text-sm text-txt-2">🏗️ ${escapeHtml(a.baustelle)}</div>` : ''}
        <div class="text-sm text-muted">${zeit}${a.ist_offen ? '' : ' · <span class="text-ok">zurück</span>'}</div>
        ${a.rueckgabe_kommentar ? `<div class="text-xs mt-1 text-txt-2 italic">„${escapeHtml(a.rueckgabe_kommentar)}"</div>` : ''}
        ${weitere ? `<div class="mt-1">${weitere}</div>` : ''}
        ${aktion ? `<div class="mt-2 flex justify-end">${aktion}</div>` : ''}
      </div>
    </div>`;
}
