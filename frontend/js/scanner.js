// Wiederverwendbarer QR-Scanner. parseScan ist rein und unit-getestet;
// scanQr (in einem späteren Schritt) kapselt Kamera + Overlay.

import { btnClasses } from './ui.js';

const MARKER = '#/m/';

// Macht aus einem gescannten String den Maschinen-Code (oder null).
// Akzeptiert die QR-URL (…/#/m/CODE) ebenso wie einen rohen Code.
export function parseScan(text) {
  if (typeof text !== 'string') return null;
  const s = text.trim();
  if (!s) return null;

  const i = s.indexOf(MARKER);
  if (i !== -1) {
    const raw = s.slice(i + MARKER.length).split(/[?#&/\s]/)[0].trim();
    if (!raw) return null;
    try {
      return decodeURIComponent(raw).trim().toUpperCase();
    } catch {
      return raw.toUpperCase();
    }
  }

  // Kein Marker: nur einen "nackten" Code akzeptieren (kein Schema, kein Whitespace).
  if (s.includes('://') || /\s/.test(s)) return null;
  return s.toUpperCase();
}

// Öffnet ein Vollbild-Overlay mit Live-Kamera und scannt QR-Codes.
// Optional: nfc = async Funktion, die einen Code per NFC liefert (nur native
// App) — dann zeigt das Overlay zusätzlich einen "NFC-Tag lesen"-Button.
// Auflösung: gefundener Maschinen-Code (string) | null (Abbruch/Kamera nicht möglich).
export function scanQr({ nfc = null } = {}) {
  return new Promise((resolve) => {
    const root = document.getElementById('modal-root');
    let stream = null;
    let raf = 0;
    let done = false;

    const overlay = document.createElement('div');
    overlay.className = 'fixed inset-0 z-50 bg-black flex flex-col';
    // iOS-Safe-Area: Overlay-Kopf nicht unter der Statusleiste (Browser: 0).
    overlay.style.paddingTop = 'env(safe-area-inset-top)';
    overlay.style.paddingBottom = 'env(safe-area-inset-bottom)';
    overlay.innerHTML = `
      <div class="px-4 py-3 text-txt font-semibold">QR-Code scannen</div>
      <div class="relative flex-1 overflow-hidden">
        <video class="absolute inset-0 w-full h-full object-cover" autoplay playsinline muted></video>
        <div class="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div id="qr-frame" class="w-64 h-64 max-w-[70vw] max-h-[70vw] rounded-2xl border-4 border-accent"></div>
        </div>
        <div id="qr-hint" class="absolute bottom-4 left-0 right-0 text-center text-txt-2 text-sm px-4">
          QR-Code der Maschine in den Rahmen halten
        </div>
      </div>
      <div class="p-4 space-y-2">
        ${nfc ? `<button id="qr-nfc" class="${btnClasses('primary')} w-full">NFC-Tag lesen</button>` : ''}
        <button id="qr-cancel" class="${btnClasses('secondary')} w-full">Abbrechen</button>
      </div>`;
    root.appendChild(overlay);

    const video = overlay.querySelector('video');
    const frame = overlay.querySelector('#qr-frame');
    const hint = overlay.querySelector('#qr-hint');
    const cancelBtn = overlay.querySelector('#qr-cancel');
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d', { willReadFrequently: true });

    const cleanup = () => {
      if (raf) cancelAnimationFrame(raf);
      if (stream) stream.getTracks().forEach((t) => t.stop());
      overlay.remove();
    };
    const finish = (value) => {
      if (done) return;
      done = true;
      cleanup();
      resolve(value);
    };

    cancelBtn.onclick = () => finish(null);

    if (nfc) {
      overlay.querySelector('#qr-nfc').onclick = async () => {
        if (done) return;
        done = true;
        cleanup();       // Kamera stoppen, Overlay schließen — dann iOS-NFC-Dialog
        let code = null;
        try { code = await nfc(); } catch { /* Abbruch/Fehler -> wie "nichts gescannt" */ }
        resolve(code);
      };
    }

    const showError = () => {
      hint.textContent = 'Kamerazugriff nicht möglich.';
      cancelBtn.textContent = 'Code manuell eingeben';
    };

    const tick = () => {
      if (done) return;
      if (video.readyState === video.HAVE_ENOUGH_DATA && video.videoWidth) {
        if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
          canvas.width = video.videoWidth;
          canvas.height = video.videoHeight;
        }
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        const img = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const result = window.jsQR ? window.jsQR(img.data, img.width, img.height) : null;
        if (result) {
          const code = parseScan(result.data);
          if (code) {
            frame.classList.remove('border-accent');
            frame.classList.add('border-ok');
            finish(code);
            return;
          }
          hint.textContent = 'Kein gültiger Maschinen-Code.';
        }
      }
      raf = requestAnimationFrame(tick);
    };

    const md = navigator.mediaDevices;
    if (!md || !md.getUserMedia) {
      showError();
      return;
    }
    md.getUserMedia({ video: { facingMode: 'environment' } })
      .then((s) => {
        if (done) { s.getTracks().forEach((t) => t.stop()); return; }
        stream = s;
        video.srcObject = s;
        return video.play();
      })
      .then(() => { if (!done) raf = requestAnimationFrame(tick); })
      .catch(() => { if (!done) showError(); });
  });
}
