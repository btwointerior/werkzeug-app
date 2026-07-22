// NFC-Vorbereitung: Die UI beschafft Werkzeug-Codes NUR über diese Funktion.
// Heute ist die einzige Quelle der Kamera-QR-Scanner (scanQr); später kommt
// NFC als alternative Quelle hinzu (Chip enthält denselben Code wie der QR).
export function holeWerkzeugCode(quelle) {
  return quelle();
}
