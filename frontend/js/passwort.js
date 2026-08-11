// Overlay „Eigenes Passwort ändern" — für alle eingeloggten Benutzer.
// Nach der Änderung sieht der Admin das Passwort nicht mehr im Klartext.

import { api } from './api.js';
import { modal, toast } from './ui.js';

function feld(id, label) {
  return `
    <div>
      <label class="block font-medium text-txt-2 mb-1">${label}</label>
      <input id="${id}" type="password"
             autocomplete="${id === 'pw-alt' ? 'current-password' : 'new-password'}"
             class="w-full border border-border rounded-lg px-3 py-2 bg-surface text-txt placeholder:text-muted">
    </div>`;
}

export async function passwortAendernDialog() {
  let werte = { alt: '', neu: '', neu2: '' };

  // Schleife: bei Validierungs-/Serverfehler öffnet der Dialog erneut,
  // die bereits eingegebenen Werte bleiben erhalten.
  for (;;) {
    const body = document.createElement('div');
    body.innerHTML = `
      <div class="space-y-3 text-sm">
        ${feld('pw-alt', 'Aktuelles Passwort')}
        ${feld('pw-neu', 'Neues Passwort (min. 4 Zeichen)')}
        ${feld('pw-neu2', 'Neues Passwort wiederholen')}
      </div>`;
    body.querySelector('#pw-alt').value = werte.alt;
    body.querySelector('#pw-neu').value = werte.neu;
    body.querySelector('#pw-neu2').value = werte.neu2;

    const res = await modal({
      titel: 'Passwort ändern',
      body,
      buttons: [
        { label: 'Ändern',    variant: 'primary',   value: 'save' },
        { label: 'Abbrechen', variant: 'secondary', value: null },
      ],
    });
    if (res !== 'save') return;

    werte = {
      alt:  body.querySelector('#pw-alt').value,
      neu:  body.querySelector('#pw-neu').value,
      neu2: body.querySelector('#pw-neu2').value,
    };
    if (!werte.alt) {
      toast('Bitte das aktuelle Passwort eingeben.', 'error');
      continue;
    }
    if (werte.neu.length < 4) {
      toast('Das neue Passwort muss mindestens 4 Zeichen haben.', 'error');
      continue;
    }
    if (werte.neu !== werte.neu2) {
      toast('Die Wiederholung stimmt nicht mit dem neuen Passwort überein.', 'error');
      continue;
    }

    try {
      await api.post('/api/passwort-aendern', {
        aktuelles_passwort: werte.alt,
        neues_passwort: werte.neu,
      });
      toast('Passwort geändert.', 'success');
      return;
    } catch (err) {
      toast(err.detail || 'Passwort-Änderung fehlgeschlagen.', 'error');
    }
  }
}
