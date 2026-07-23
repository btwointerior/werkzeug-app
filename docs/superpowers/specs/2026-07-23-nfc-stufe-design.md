# Design: NFC-Stufe (Lesen für alle, Schreiben+Versiegeln nur Admin)

**Datum:** 2026-07-23 · **Status:** vom User freigegeben (Konversation 2026-07-23)

## Ziel

Werkzeuge zusätzlich per NFC-Chip identifizieren (On-Metal-NTAG am Werkzeug).
Nur in der nativen iOS-App (Apple erlaubt NFC nicht im Web); die Webapp bleibt
unverändert beim QR-Weg.

- **Lesen (alle Nutzer):** Im Kamera-Scan-Overlay erscheint (nur in der App,
  wenn NFC verfügbar) ein Button „NFC-Tag lesen" → iOS-NFC-Dialog → Tag liefert
  denselben Code/URL wie der QR-Code → gleiche Navigation wie nach QR-Scan.
- **Schreiben (nur Admin, nur App):** Auf der Maschinen-Seite Button
  „NFC-Tag beschreiben" → Bestätigungs-Dialog (DOM, kein window.confirm!) →
  App schreibt die QR-URL der Maschine als NDEF-URI und **versiegelt den Tag
  dauerhaft** (writeLock, User-Entscheidung: PFLICHT, keine Option).
  Bei Maschinenwechsel wird ein neuer Tag beschrieben.

## Technik

- **Eigenes lokales Capacitor-Plugin** `WerkzeugNfc` (Swift, Core NFC,
  NFCNDEFReaderSession): Methoden `readCode()` → `{text}` und
  `writeAndLock({url})`. Kein Fremd-Plugin (die etablierten sind Sponsorware);
  Core NFC bietet `writeNDEF` + `writeLock` direkt.
- Registrierung: `MyViewController` (CAPBridgeViewController-Subklasse,
  `capacitorDidLoad` → `registerPluginInstance`), Main.storyboard auf die
  Subklasse umgestellt. JS-Seite ohne Bundler via
  `window.Capacitor.registerPlugin('WerkzeugNfc')`.
- **Code-Extraktion:** gelesener NDEF-Text läuft durch das bestehende
  `parseScan` (akzeptiert URL und rohen Code) → `holeWerkzeugCode`-Abstraktion
  aus der Vorbereitung wird eingelöst.
- **Schreib-URL:** `window.WERKZEUG_API_BASE + '/#/m/' + maschinen_code`
  (identisch zum QR-Inhalt; Schreiben existiert nur in der App, wo die
  Variable immer gesetzt ist).
- **Apple-Seite:** Capability `NFC_TAG_READING` an der Bundle-ID (ASC-API),
  Provisioning-Profil neu erzeugen (alt löschen, neu anlegen),
  **User muss in Codemagic einmal „Fetch profiles" klicken** (bekannter
  Ablauf), `App.entitlements` mit
  `com.apple.developer.nfc.readersession.formats = [NDEF]` +
  `CODE_SIGN_ENTITLEMENTS` im pbxproj, `NFCReaderUsageDescription` in
  Info.plist.
- **Sichtbarkeits-Gate:** NFC-Buttons nur wenn `window.Capacitor` + Plugin
  vorhanden; Schreib-Button zusätzlich nur bei Rolle ADMIN. Web sieht nichts.

## Fehlerbehandlung

- NFC-Session-Fehler/Abbruch → Toast mit Apple-Fehlertext bzw. „Abgebrochen",
  kein App-Zustand verändert.
- Bereits versiegelter/read-only Tag beim Schreiben → verständliche Meldung
  („Tag ist schreibgeschützt — neuen Tag verwenden").
- Leerer/fremder Tag beim Lesen → „Kein Werkzeug-Code auf dem Tag".

## Tests & Abnahme

- JS: Unit-Tests für neue pure Helfer (URL-Bau, Payload→Code über parseScan).
- Swift ist lokal nicht kompilierbar (kein Xcode) → Verifikation über
  Codemagic-Build (kompiliert = Syntax/API ok) und Geräte-Abnahme durch den
  User, sobald die bestellten On-Metal-Tags da sind: lesen (alle), schreiben+
  versiegeln (Admin), Versiegelung gegen Fremd-App („NFC Tools") prüfen.

## Außerhalb des Umfangs

- Android, Web-NFC, Tag-Inventar/Verwaltung im Backend (Tag trägt nur die URL)
