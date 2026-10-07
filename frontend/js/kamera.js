// In-App-Kamera (getUserMedia) mit Mehrfach-Auslöser + clientseitige
// Verkleinerung. Gemeinsam genutzt von Maschinen-Formular (Admin) und
// Freier Ausgabe (alle). iOS: `playsinline` ist Pflicht, sonst Vollbild-Player.

import { toast } from './ui.js';

export const MAX_KANTE_PX = 1600;

// Reine Funktion (testbar): Zielmaße, sodass die lange Kante <= maxKante ist.
export function zielMasse(breite, hoehe, maxKante = MAX_KANTE_PX) {
  if (!breite || !hoehe) return { w: 0, h: 0 };
  const faktor = Math.min(1, maxKante / Math.max(breite, hoehe));
  return { w: Math.round(breite * faktor), h: Math.round(hoehe * faktor) };
}

// Verkleinert eine Bilddatei (aus <input type=file>) im Browser. Bei Fehlern
// (z.B. HEIC ohne Decoder) kommt die Originaldatei zurück — der Server
// verkleinert ohnehin nochmal.
export async function verkleinereDatei(datei, maxKante = MAX_KANTE_PX) {
  try {
    if (!datei.type.startsWith('image/')) return datei;
    const bmp = await createImageBitmap(datei);
    const { w, h } = zielMasse(bmp.width, bmp.height, maxKante);
    if (w === bmp.width && h === bmp.height && datei.type === 'image/jpeg') {
      bmp.close?.();
      return datei;
    }
    const c = document.createElement('canvas');
    c.width = w;
    c.height = h;
    c.getContext('2d').drawImage(bmp, 0, 0, w, h);
    bmp.close?.();
    const blob = await new Promise((res) => c.toBlob(res, 'image/jpeg', 0.85));
    if (!blob) return datei;
    const name = datei.name.replace(/\.[^.]+$/, '') + '.jpg';
    return new File([blob], name, { type: 'image/jpeg' });
  } catch {
    return datei;
  }
}

// Öffnet die Kamera EINMAL; Auslöser beliebig oft (bis maxFotos), „Fertig (N)"
// liefert alle Aufnahmen als File[] (JPEG, lange Kante <= MAX_KANTE_PX).
export function kameraOverlay(maxFotos, { titel = '' } = {}) {
  return new Promise((resolve) => {
    const md = navigator.mediaDevices;
    if (!md || !md.getUserMedia) { toast('Kamera nicht verfügbar.', 'error'); resolve([]); return; }
    if (maxFotos < 1) { toast('Maximale Fotoanzahl erreicht.', 'info'); resolve([]); return; }

    const wrap = document.createElement('div');
    wrap.className = 'fixed inset-0 z-50 bg-black flex flex-col';
    wrap.innerHTML = `
      ${titel ? `<div class="text-white text-sm px-4 py-2 bg-black/90" style="padding-top: calc(0.5rem + env(safe-area-inset-top))">${titel}</div>` : ''}
      <video class="flex-1 w-full min-h-0 object-cover" autoplay playsinline muted></video>
      <div class="bg-black/90 flex items-center justify-between px-6 pt-4"
           style="padding-bottom: calc(1.5rem + env(safe-area-inset-bottom))">
        <button type="button" id="kam-abbruch" class="text-white min-h-[44px] px-3">Abbrechen</button>
        <button type="button" id="kam-ausloeser" aria-label="Foto aufnehmen"
                class="w-16 h-16 rounded-full bg-white border-4 border-neutral-400 active:scale-90 transition"></button>
        <button type="button" id="kam-fertig" class="text-accent font-semibold min-h-[44px] px-3">Fertig (0)</button>
      </div>`;
    document.body.appendChild(wrap);
    const video = wrap.querySelector('video');
    const fotos = [];
    let stream = null;
    let zu = false;

    const schliessen = (ergebnis) => {
      if (zu) return;
      zu = true;
      if (stream) stream.getTracks().forEach((t) => t.stop());
      wrap.remove();
      resolve(ergebnis);
    };

    md.getUserMedia({ video: { facingMode: 'environment' } })
      .then((s) => {
        if (zu) { s.getTracks().forEach((t) => t.stop()); return; }
        stream = s;
        video.srcObject = s;
      })
      .catch(() => { toast('Kamera-Zugriff nicht möglich.', 'error'); schliessen([]); });

    wrap.querySelector('#kam-ausloeser').onclick = () => {
      if (!video.videoWidth) return; // Stream noch nicht bereit
      if (fotos.length >= maxFotos) { toast(`Maximal ${maxFotos} Foto${maxFotos === 1 ? '' : 's'}.`, 'info'); return; }
      const { w, h } = zielMasse(video.videoWidth, video.videoHeight);
      const c = document.createElement('canvas');
      c.width = w;
      c.height = h;
      c.getContext('2d').drawImage(video, 0, 0, w, h);
      c.toBlob((blob) => {
        if (!blob || zu) return;
        fotos.push(new File([blob], `kamera_${Date.now()}_${fotos.length}.jpg`, { type: 'image/jpeg' }));
        wrap.querySelector('#kam-fertig').textContent = `Fertig (${fotos.length})`;
        video.style.opacity = '0.3'; // kurzer Blitz-Effekt als Rückmeldung
        setTimeout(() => { video.style.opacity = '1'; }, 120);
      }, 'image/jpeg', 0.85);
    };
    wrap.querySelector('#kam-fertig').onclick = () => schliessen(fotos);
    wrap.querySelector('#kam-abbruch').onclick = () => schliessen([]);
  });
}
