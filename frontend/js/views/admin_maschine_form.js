// Neu/Edit-Formular für Maschinen + Foto- und Anleitung-Upload (nur Edit-Modus).
// Hinweis: Das Backend hat keinen GET-Einzelendpunkt, daher holen wir die Daten
// für den Edit-Fall aus GET /api/admin/maschinen und filtern nach ID.

import { api } from '../api.js';
import { apiUrl } from '../api_base.js';
import { btnClasses, confirmDialog, escapeHtml, safeUrl, spinner, toast } from '../ui.js';

export async function renderAdminMaschineForm(maschineId) {
  const app = document.getElementById('app');
  app.innerHTML = `<main class="max-w-3xl mx-auto pb-24 pt-4 px-4">${spinner()}</main>`;

  let daten = leerDaten();

  // KI-Foto-Analyse (nur Neu-Modus): gewählte Dateien, Objekt-URLs für die
  // Vorschau und Index des Fotos, das nach dem Anlegen übernommen werden soll.
  let kiDateien = [];
  let kiUrls = [];
  let kiGewaehlt = -1;

  if (maschineId) {
    try {
      const alle = await api.get('/api/admin/maschinen');
      const m = alle.find((x) => x.id === maschineId);
      if (!m) {
        app.innerHTML = `
          <main class="max-w-3xl mx-auto pt-8 px-4 text-center">
            <p class="text-rose-600 mb-3">Maschine nicht gefunden.</p>
            <a href="#/admin/maschinen" class="${btnClasses('secondary')} inline-block">Zurück</a>
          </main>`;
        return;
      }
      daten = ausMaschine(m);
    } catch (err) {
      app.innerHTML =
        `<main class="max-w-3xl mx-auto pt-8 px-4 text-rose-600">${escapeHtml(err.detail)}</main>`;
      return;
    }
  }

  zeichne();

  // -----------------------------------------------------------

  function zeichne() {
    app.innerHTML = `
      <main class="max-w-3xl mx-auto pb-24 pt-4 px-4">
        <h1 class="text-2xl font-bold text-txt mb-4">
          ${maschineId ? 'Maschine bearbeiten' : 'Neue Maschine'}
        </h1>
        ${maschineId ? '' : kiSektion()}
        <form id="form" class="space-y-3 bg-surface border border-border rounded-lg p-4">
          ${feldText('maschinen_code', 'Maschinen-Code (z.B. M-005)', daten.maschinen_code, { uppercase: true, disabled: !!maschineId })}
          ${maschineId ? '' : '<p id="code-hinweis" class="text-xs text-muted -mt-2"></p>'}
          ${feldText('name', 'Name', daten.name, { required: true })}
          ${feldText('platznummer', 'Platznummer', daten.platznummer)}
          ${feldText('hersteller', 'Hersteller', daten.hersteller)}
          ${feldText('seriennummer', 'Seriennummer', daten.seriennummer)}
          <div>
            <label class="block text-sm font-medium text-txt-2 mb-1">Status</label>
            <select id="f-status" class="w-full border border-border rounded-lg px-3 py-2 bg-surface text-txt">
              <option value="verfuegbar" ${daten.status === 'verfuegbar' ? 'selected' : ''}>Verfügbar</option>
              <option value="defekt"     ${daten.status === 'defekt'     ? 'selected' : ''}>Defekt</option>
              <option value="wartung"    ${daten.status === 'wartung'    ? 'selected' : ''}>In Wartung</option>
              ${daten.status === 'ausgeliehen'
                ? '<option value="ausgeliehen" selected disabled>Ausgeliehen (nur über Rückgabe änderbar)</option>'
                : ''}
            </select>
            ${daten.status === 'ausgeliehen'
              ? '<p class="text-xs text-muted mt-1">Status kann nicht geändert werden, solange die Maschine ausgeliehen ist.</p>'
              : ''}
          </div>
          <div>
            <label class="block text-sm font-medium text-txt-2 mb-1">Beschreibung</label>
            <textarea id="f-beschreibung" rows="3"
                      class="w-full border border-border rounded-lg px-3 py-2 bg-surface text-txt placeholder:text-muted">${escapeHtml(daten.beschreibung)}</textarea>
          </div>
          <div>
            <label class="block text-sm font-medium text-txt-2 mb-1">Zubehör</label>
            <div id="zub-liste" class="space-y-2 mb-2"></div>
            <button type="button" id="zub-add" class="${btnClasses('secondary')} text-sm">+ Zubehör</button>
          </div>
          <div class="flex gap-2 pt-2">
            <button type="submit" id="form-submit" class="${btnClasses('primary')} flex-1">
              ${maschineId ? 'Speichern' : 'Anlegen'}
            </button>
            <a href="#/admin/maschinen" class="${btnClasses('secondary')}">Abbrechen</a>
          </div>
        </form>

        ${maschineId ? galerieSektion(daten.fotos)
          : '<p class="text-sm text-muted mt-3">Weitere Fotos und die Anleitung können nach dem Anlegen gepflegt werden.</p>'}

        ${maschineId ? uploadSektion('anl', 'Betriebsanleitung', daten.anleitung_url, daten.anleitung_pfad,
            'Nur PDF, max 10 MB.', 'application/pdf', /* istBild */ false,
            `<button id="anl-suche" type="button"
                     class="${btnClasses('secondary')} w-full mt-2 text-sm">
               🔎 Automatisch im Internet suchen (KI)
             </button>`)
          : ''}
      </main>`;

    setupZubehoer();
    setupSubmit();
    if (maschineId) {
      setupGalerie();
      setupUpload('anl');
      setupAnleitungSuche();
    } else {
      setupKiAnalyse();
      setupCodeHinweis();
    }
  }

  // Nächste freie Maschinennummer (Format M-xxx) als antippbaren Hinweis anzeigen.
  async function setupCodeHinweis() {
    try {
      const alle = await api.get('/api/admin/maschinen');
      let max = 0;
      for (const m of alle) {
        const t = /^M-(\d+)$/.exec(m.maschinen_code || '');
        if (t) max = Math.max(max, parseInt(t[1], 10));
      }
      const code = 'M-' + String(max + 1).padStart(3, '0');
      const el = document.getElementById('code-hinweis');
      const input = document.getElementById('f-maschinen_code');
      if (!el || !input) return;
      el.innerHTML = `Nächste freie Nummer:
        <button type="button" id="code-uebernehmen" class="text-accent underline font-medium">${code}</button>
        (antippen zum Übernehmen)`;
      document.getElementById('code-uebernehmen').onclick = () => { input.value = code; };
    } catch { /* Hinweis ist optional – Fehler hier nie blockierend */ }
  }

  // -----------------------------------------------------------
  //  Foto-Galerie (nur Edit-Modus)
  // -----------------------------------------------------------

  function galerieSektion(fotos) {
    const thumbs = fotos.map((f, i) => `
      <div class="relative">
        <button type="button" data-gal-start="${i}" title="Als Startbild festlegen"
                class="block w-full rounded-lg overflow-hidden border-2 ${f.ist_start ? 'border-accent' : 'border-border'}">
          <img src="${escapeHtml(safeUrl(apiUrl(f.url)))}" class="h-24 w-full object-cover" alt="Foto ${i + 1}">
        </button>
        ${f.ist_start
          ? '<span class="absolute top-1 left-1 bg-accent text-accent-ink text-xs rounded px-1.5 py-0.5 pointer-events-none">Startbild</span>'
          : ''}
        <button type="button" data-gal-del="${i}" aria-label="Foto löschen"
                class="absolute top-1 right-1 bg-rose-600 hover:bg-rose-700 text-white rounded w-7 h-7 text-sm leading-none">×</button>
      </div>`).join('');

    return `
      <section class="bg-surface rounded-lg border border-border p-4 mt-4">
        <h2 class="font-semibold text-txt mb-1">Fotos</h2>
        <p class="text-xs text-muted mb-3">
          Foto antippen = als Startbild/Vorschaubild festlegen. Mehrere Dateien auswählbar,
          JPG / PNG / WebP, je max 10 MB (werden auf 1600 px verkleinert).
        </p>
        ${fotos.length
          ? `<div class="grid grid-cols-3 gap-2 mb-3" id="gal-liste">${thumbs}</div>`
          : '<p class="text-sm text-muted mb-3 text-center">Noch keine Fotos hinterlegt.</p>'}
        <div class="flex gap-2 flex-wrap items-stretch">
          <input type="file" id="gal-input" accept="image/jpeg,image/png,image/webp" multiple
                 class="flex-1 min-w-0 text-sm border border-border rounded-lg p-2 bg-surface text-txt">
          <button id="gal-upload" type="button"
                  class="bg-accent hover:brightness-95 text-accent-ink min-h-[44px] px-4 rounded-lg text-sm">
            Hochladen
          </button>
        </div>
      </section>`;
  }

  function setupGalerie() {
    document.getElementById('gal-upload').onclick = async () => {
      const input = document.getElementById('gal-input');
      if (!input.files.length) { toast('Bitte zuerst Fotos auswählen.', 'error'); return; }
      const fd = new FormData();
      Array.from(input.files).slice(0, 10).forEach((f) => fd.append('dateien', f));
      toast('Fotos werden hochgeladen…', 'info', 2000);
      try {
        const m = await api.post(`/api/admin/maschinen/${maschineId}/fotos`, fd);
        Object.assign(daten, ausMaschine(m));
        toast('Fotos hochgeladen.', 'success');
        zeichne();
      } catch (err) {
        toast(err.detail || 'Upload fehlgeschlagen.', 'error');
      }
    };

    document.querySelectorAll('[data-gal-start]').forEach((el) => {
      el.onclick = async () => {
        const foto = daten.fotos[+el.dataset.galStart];
        if (!foto || foto.ist_start) return;
        try {
          const m = await api.put(`/api/admin/maschinen/${maschineId}/fotos/${foto.id}/start`);
          Object.assign(daten, ausMaschine(m));
          toast('Startbild festgelegt.', 'success');
          zeichne();
        } catch (err) {
          toast(err.detail || 'Festlegen fehlgeschlagen.', 'error');
        }
      };
    });

    document.querySelectorAll('[data-gal-del]').forEach((el) => {
      el.onclick = async () => {
        const foto = daten.fotos[+el.dataset.galDel];
        if (!foto) return;
        const ok = await confirmDialog('Foto wirklich löschen?',
          { dangerous: true, okLabel: 'Löschen' });
        if (!ok) return;
        try {
          const m = await api.del(`/api/admin/maschinen/${maschineId}/fotos/${foto.id}`);
          Object.assign(daten, ausMaschine(m));
          toast('Foto gelöscht.', 'success');
          zeichne();
        } catch (err) {
          toast(err.detail || 'Löschen fehlgeschlagen.', 'error');
        }
      };
    });
  }

  function setupAnleitungSuche() {
    const btn = document.getElementById('anl-suche');
    if (!btn) return;
    btn.onclick = async () => {
      btn.disabled = true;
      btn.textContent = 'Suche läuft… (bis zu 1 Minute)';
      try {
        const m = await api.post(`/api/admin/maschinen/${maschineId}/anleitung-suche`);
        Object.assign(daten, ausMaschine(m));
        toast('Anleitung gefunden und hinterlegt.', 'success');
        zeichne();
      } catch (err) {
        toast(err.detail || 'Keine Anleitung gefunden.', 'error', 6000);
        btn.disabled = false;
        btn.textContent = '🔎 Automatisch im Internet suchen (KI)';
      }
    };
  }

  // -----------------------------------------------------------
  //  KI-Foto-Analyse (nur Neu-Modus)
  // -----------------------------------------------------------

  function kiSektion() {
    return `
      <section class="bg-surface rounded-lg border border-border p-4 mb-4">
        <h2 class="font-semibold text-txt mb-1">Per Foto ausfüllen (KI)</h2>
        <p class="text-xs text-muted mb-3">
          Typenschild/Etiketten fotografieren oder auswählen (bis zu 5 Fotos –
          einfach mehrmals aufnehmen, jedes Foto wird angehängt). Name, Hersteller
          und Seriennummer werden automatisch vorgeschlagen. Gerätenummer und
          Platznummer trägst du weiterhin selbst ein.
        </p>
        <input type="file" id="ki-input" accept="image/jpeg,image/png,image/webp" multiple
               class="w-full text-sm border border-border rounded-lg p-2 bg-surface text-txt">
        <div id="ki-thumbs" class="grid grid-cols-3 gap-2 my-2"></div>
        <p id="ki-foto-wahl" class="text-xs text-muted mb-2 hidden">
          Tippe ein Foto an, um es nach dem Anlegen als Maschinen-Foto zu übernehmen (optional).
        </p>
        <button type="button" id="ki-analyse" disabled
                class="bg-accent hover:brightness-95 text-accent-ink min-h-[44px] px-4 rounded-lg text-sm w-full disabled:opacity-50">
          Fotos analysieren
        </button>
        <p id="ki-hinweis" class="text-sm text-amber-500 mt-2"></p>
      </section>`;
  }

  function setupKiAnalyse() {
    const input = document.getElementById('ki-input');
    const analyseBtn = document.getElementById('ki-analyse');
    const thumbs = document.getElementById('ki-thumbs');
    const wahlHinweis = document.getElementById('ki-foto-wahl');
    const hinweisEl = document.getElementById('ki-hinweis');

    const zeichneStatus = () => {
      analyseBtn.disabled = !kiDateien.length;
      wahlHinweis.classList.toggle('hidden', !kiDateien.length);
    };

    const zeichneThumbs = () => {
      thumbs.innerHTML = kiUrls.map((url, i) => `
        <div class="relative">
          <button type="button" data-ki-thumb="${i}"
                  class="block w-full rounded-lg overflow-hidden border-2 ${i === kiGewaehlt ? 'border-accent' : 'border-border'}"
                  aria-pressed="${i === kiGewaehlt}">
            <img src="${escapeHtml(url)}" class="h-24 w-full object-cover" alt="Foto ${i + 1}">
            ${i === kiGewaehlt
              ? '<span class="absolute bottom-1 left-1 bg-accent text-accent-ink text-xs rounded px-1.5 py-0.5 pointer-events-none">Maschinen-Foto</span>'
              : ''}
          </button>
          <button type="button" data-ki-del="${i}" aria-label="Foto entfernen"
                  class="absolute top-1 right-1 bg-rose-600 hover:bg-rose-700 text-white rounded w-7 h-7 text-sm leading-none">×</button>
        </div>`).join('');
      thumbs.querySelectorAll('[data-ki-thumb]').forEach((el) => {
        el.onclick = () => {
          const i = +el.dataset.kiThumb;
          kiGewaehlt = kiGewaehlt === i ? -1 : i; // erneut antippen = Abwahl
          zeichneThumbs();
        };
      });
      thumbs.querySelectorAll('[data-ki-del]').forEach((el) => {
        el.onclick = () => {
          const i = +el.dataset.kiDel;
          URL.revokeObjectURL(kiUrls[i]);
          kiDateien.splice(i, 1);
          kiUrls.splice(i, 1);
          if (kiGewaehlt === i) kiGewaehlt = kiDateien.length ? 0 : -1;
          else if (kiGewaehlt > i) kiGewaehlt -= 1;
          zeichneStatus();
          zeichneThumbs();
        };
      });
    };

    input.onchange = () => {
      // Sammeln statt ersetzen: die iPhone-Kamera liefert pro Aufnahme nur EIN
      // Foto - jede weitere Auswahl/Aufnahme haengt an die bisherigen an.
      const neue = Array.from(input.files);
      input.value = '';
      for (const f of neue) {
        if (kiDateien.length >= 5) { toast('Maximal 5 Fotos.', 'info'); break; }
        kiDateien.push(f);
        kiUrls.push(URL.createObjectURL(f));
      }
      if (kiGewaehlt < 0 && kiDateien.length) kiGewaehlt = 0;
      zeichneStatus();
      zeichneThumbs();
    };

    analyseBtn.onclick = async () => {
      if (!kiDateien.length) return;
      const fd = new FormData();
      kiDateien.forEach((f) => fd.append('dateien', f));
      analyseBtn.disabled = true;
      analyseBtn.textContent = 'Analysiere…';
      hinweisEl.textContent = '';
      try {
        const erg = await api.post('/api/admin/maschinen/foto-analyse', fd);
        let befuellt = 0;
        for (const [feld, wert] of Object.entries({
          name: erg.name, hersteller: erg.hersteller, seriennummer: erg.seriennummer,
        })) {
          const el = document.getElementById(`f-${feld}`);
          if (wert && el && !el.value.trim()) {
            el.value = wert;
            el.classList.add('border-accent');
            befuellt += 1;
          }
        }
        const beschr = document.getElementById('f-beschreibung');
        if (erg.beschreibung && beschr && !beschr.value.trim()) {
          beschr.value = erg.beschreibung;
          beschr.classList.add('border-accent');
          befuellt += 1;
        }
        if (erg.hinweis) hinweisEl.textContent = `Hinweis der KI: ${erg.hinweis}`;
        toast(befuellt
          ? `${befuellt} Feld${befuellt === 1 ? '' : 'er'} vorbefüllt – bitte prüfen.`
          : 'Auf den Fotos wurde nichts Verwertbares erkannt.',
          befuellt ? 'success' : 'info');
      } catch (err) {
        toast(err.detail || 'Analyse fehlgeschlagen.', 'error');
      } finally {
        analyseBtn.disabled = false;
        analyseBtn.textContent = 'Fotos analysieren';
      }
    };
  }

  // -----------------------------------------------------------

  function setupZubehoer() {
    const zList = document.getElementById('zub-liste');
    const zeichneZ = () => {
      zList.innerHTML = daten.zubehoer.map((z, i) => `
        <div class="flex gap-2">
          <input data-z="${i}" type="text" value="${escapeHtml(z)}"
                 class="flex-1 border border-border rounded-lg px-3 py-2 bg-surface text-txt placeholder:text-muted">
          <button type="button" data-zdel="${i}"
                  class="${btnClasses('danger')} px-3 text-sm">×</button>
        </div>`).join('');
      zList.querySelectorAll('[data-z]').forEach((el) => {
        el.oninput = () => { daten.zubehoer[+el.dataset.z] = el.value; };
      });
      zList.querySelectorAll('[data-zdel]').forEach((el) => {
        el.onclick = () => { daten.zubehoer.splice(+el.dataset.zdel, 1); zeichneZ(); };
      });
    };
    zeichneZ();
    document.getElementById('zub-add').onclick = () => {
      daten.zubehoer.push('');
      zeichneZ();
      const inputs = zList.querySelectorAll('input');
      if (inputs.length) inputs[inputs.length - 1].focus();
    };
  }

  function setupSubmit() {
    document.getElementById('form').onsubmit = async (e) => {
      e.preventDefault();
      const zubehoer = daten.zubehoer
        .filter((z) => z.trim())
        .map((z) => ({ bezeichnung: z.trim() }));

      const body = {
        name:         document.getElementById('f-name').value.trim(),
        platznummer:  document.getElementById('f-platznummer').value.trim() || null,
        hersteller:   document.getElementById('f-hersteller').value.trim() || null,
        seriennummer: document.getElementById('f-seriennummer').value.trim() || null,
        beschreibung: document.getElementById('f-beschreibung').value.trim() || null,
        status:       document.getElementById('f-status').value,
        zubehoer,
      };

      const submitBtn = document.getElementById('form-submit');
      const beschriftung = submitBtn.textContent;
      submitBtn.disabled = true;
      try {
        if (maschineId) {
          submitBtn.textContent = 'Speichert…';
          await api.put(`/api/admin/maschinen/${maschineId}`, body);
          toast('Gespeichert.', 'success');
          location.hash = '#/admin/maschinen';
        } else {
          const code = document.getElementById('f-maschinen_code').value.trim().toUpperCase();
          if (!code) { toast('Maschinen-Code ist Pflicht.', 'error'); return; }
          submitBtn.textContent = 'Legt an…';
          const neu = await api.post('/api/admin/maschinen', { maschinen_code: code, ...body });
          toast('Maschine angelegt.', 'success');
          // Alle Analyse-Fotos an die Maschine hängen; das angetippte wird
          // Startbild. Schlägt nur der Upload fehl, bleibt die Maschine angelegt.
          if (kiDateien.length) {
            submitBtn.textContent = `Lädt ${kiDateien.length} Foto${kiDateien.length === 1 ? '' : 's'} hoch…`;
            const fd = new FormData();
            kiDateien.forEach((f) => fd.append('dateien', f));
            fd.append('start_index', String(kiGewaehlt >= 0 ? kiGewaehlt : 0));
            try {
              await api.post(`/api/admin/maschinen/${neu.id}/fotos`, fd);
              toast(`${kiDateien.length} Foto${kiDateien.length === 1 ? '' : 's'} übernommen.`, 'success');
            } catch (fotoErr) {
              toast('Maschine angelegt, aber Foto-Upload fehlgeschlagen – bitte im Bearbeiten-Modus nachholen.', 'error', 6000);
            }
          }
          // Anleitung im Hintergrund suchen - der Server pflegt sie selbst ein,
          // auch wenn wir gleich ins Menü wechseln.
          if (body.hersteller && body.name) {
            api.post(`/api/admin/maschinen/${neu.id}/anleitung-suche`).catch(() => {});
            toast('Bedienungsanleitung wird im Hintergrund gesucht…', 'info', 4000);
          }
          // Nach erfolgreichem Anlegen zurück ins Admin-Menü.
          location.hash = '#/admin';
        }
      } catch (err) {
        toast(err.detail || 'Speichern fehlgeschlagen.', 'error');
      } finally {
        // Nur relevant, wenn wir wegen eines Fehlers auf dem Formular bleiben.
        submitBtn.disabled = false;
        submitBtn.textContent = beschriftung;
      }
    };
  }

  function setupUpload(prefix) {
    const dropZone = document.getElementById(`${prefix}-drop`);
    const fileIn   = document.getElementById(`${prefix}-input`);
    const upload   = document.getElementById(`${prefix}-upload`);
    const del      = document.getElementById(`${prefix}-delete`);

    // Drag-and-Drop
    ['dragenter', 'dragover'].forEach((ev) => dropZone.addEventListener(ev, (e) => {
      e.preventDefault(); e.stopPropagation();
      dropZone.classList.add('border-accent', 'bg-surface-2');
    }));
    ['dragleave', 'drop'].forEach((ev) => dropZone.addEventListener(ev, (e) => {
      e.preventDefault(); e.stopPropagation();
      dropZone.classList.remove('border-accent', 'bg-surface-2');
    }));
    dropZone.addEventListener('drop', (e) => {
      if (e.dataTransfer.files.length) {
        fileIn.files = e.dataTransfer.files;
        upload.focus();
      }
    });

    const endpoint = prefix === 'foto' ? 'foto' : 'anleitung';
    const labelDeutsch = prefix === 'foto' ? 'Foto' : 'Anleitung';

    upload.onclick = async () => {
      const file = fileIn.files[0];
      if (!file) { toast('Bitte zuerst eine Datei auswählen.', 'error'); return; }
      const fd = new FormData();
      fd.append('datei', file);
      toast(`${labelDeutsch} wird hochgeladen…`, 'info', 2000);
      try {
        const m = await api.post(`/api/admin/maschinen/${maschineId}/${endpoint}`, fd);
        Object.assign(daten, ausMaschine(m));
        toast(`${labelDeutsch} hochgeladen.`, 'success');
        zeichne();
      } catch (err) {
        toast(err.detail || 'Upload fehlgeschlagen.', 'error');
      }
    };

    if (del) {
      del.onclick = async () => {
        const ok = await confirmDialog(`${labelDeutsch} wirklich entfernen?`,
          { dangerous: true, okLabel: 'Entfernen' });
        if (!ok) return;
        try {
          const m = await api.del(`/api/admin/maschinen/${maschineId}/${endpoint}`);
          Object.assign(daten, ausMaschine(m));
          toast(`${labelDeutsch} entfernt.`, 'success');
          zeichne();
        } catch (err) {
          toast(err.detail || 'Entfernen fehlgeschlagen.', 'error');
        }
      };
    }
  }

  // -----------------------------------------------------------

  function feldText(name, label, val, opt = {}) {
    const cls = `w-full border border-border rounded-lg px-3 py-2 bg-surface text-txt placeholder:text-muted${opt.uppercase ? ' uppercase' : ''}`;
    return `
      <div>
        <label class="block text-sm font-medium text-txt-2 mb-1" for="f-${name}">
          ${escapeHtml(label)}${opt.required ? ' *' : ''}
        </label>
        <input id="f-${name}" type="text" value="${escapeHtml(val)}"
               class="${cls}"
               ${opt.disabled ? 'disabled' : ''}
               ${opt.required ? 'required' : ''}>
      </div>`;
  }
}

// HTML einer Upload-Sektion: Drag-Zone + File-Input + Hochladen-/Entfernen-Buttons.
function uploadSektion(prefix, titel, url, pfad, hinweis, accept, istBild = true, extra = '') {
  const vorschau = url
    ? (istBild
        ? `<img src="${escapeHtml(safeUrl(apiUrl(url)))}" class="max-h-64 mx-auto mb-3 object-contain rounded">`
        : `<a href="${escapeHtml(safeUrl(apiUrl(url)))}" target="_blank" rel="noopener"
              class="block text-sm text-accent underline mb-3 text-center">Aktuelle Datei öffnen</a>`)
    : `<p class="text-sm text-muted mb-3 text-center">Noch nichts hinterlegt.</p>`;

  const delBtn = pfad
    ? `<button id="${prefix}-delete" type="button" class="bg-rose-600 hover:bg-rose-700 text-white min-h-[44px] px-3 rounded-lg text-sm">Entfernen</button>`
    : '';

  return `
    <section class="bg-surface rounded-lg border border-border p-4 mt-4">
      <h2 class="font-semibold text-txt mb-3">${titel}</h2>
      ${vorschau}
      <div id="${prefix}-drop"
           class="border-2 border-dashed border-border rounded-lg p-4 text-center text-muted text-sm mb-2 transition">
        Datei hier ablegen
      </div>
      <div class="flex gap-2 flex-wrap items-stretch">
        <input type="file" id="${prefix}-input" accept="${accept}"
               class="flex-1 min-w-0 text-sm border border-border rounded-lg p-2 bg-surface text-txt">
        <button id="${prefix}-upload" type="button"
                class="bg-accent hover:brightness-95 text-accent-ink min-h-[44px] px-4 rounded-lg text-sm">
          Hochladen
        </button>
        ${delBtn}
      </div>
      <p class="text-xs text-muted mt-2">${escapeHtml(hinweis)}</p>
      ${extra}
    </section>`;
}

function leerDaten() {
  return {
    maschinen_code: '', name: '', platznummer: '', hersteller: '', seriennummer: '',
    beschreibung: '', status: 'verfuegbar', zubehoer: [], fotos: [],
    foto_pfad: null, foto_url: null, anleitung_pfad: null, anleitung_url: null,
  };
}

function ausMaschine(m) {
  return {
    maschinen_code: m.maschinen_code,
    name: m.name,
    platznummer:  m.platznummer  || '',
    hersteller:   m.hersteller   || '',
    seriennummer: m.seriennummer || '',
    beschreibung: m.beschreibung || '',
    status: m.status,
    zubehoer: m.zubehoer_liste.map((z) => z.bezeichnung),
    fotos: m.fotos || [],
    foto_pfad: m.foto_pfad,
    foto_url:  m.foto_url,
    anleitung_pfad: m.anleitung_pfad,
    anleitung_url:  m.anleitung_url,
  };
}
