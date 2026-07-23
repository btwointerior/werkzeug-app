import Foundation
import Capacitor
import CoreNFC

// Lokales Capacitor-Plugin für NFC (NDEF): Lesen für alle, Schreiben mit
// PFLICHT-Versiegelung (writeLock) für den Admin-Workflow.
// Registrierung erfolgt in MyViewController.capacitorDidLoad().
@objc(WerkzeugNfcPlugin)
public class WerkzeugNfcPlugin: CAPPlugin, CAPBridgedPlugin, NFCNDEFReaderSessionDelegate {
    public let identifier = "WerkzeugNfcPlugin"
    public let jsName = "WerkzeugNfc"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "readCode", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "writeAndLock", returnType: CAPPluginReturnPromise)
    ]

    private var session: NFCNDEFReaderSession?
    private var pendingCall: CAPPluginCall?
    private var pendingUrl: String?    // nil = Lesen, sonst Schreiben+Versiegeln

    // MARK: - JS-API

    @objc func readCode(_ call: CAPPluginCall) {
        guard NFCNDEFReaderSession.readingAvailable else {
            call.reject("NFC ist auf diesem Gerät nicht verfügbar.")
            return
        }
        pendingCall = call
        pendingUrl = nil
        session = NFCNDEFReaderSession(delegate: self, queue: nil, invalidateAfterFirstRead: false)
        session?.alertMessage = "iPhone an den NFC-Tag der Maschine halten."
        session?.begin()
    }

    @objc func writeAndLock(_ call: CAPPluginCall) {
        guard NFCNDEFReaderSession.readingAvailable else {
            call.reject("NFC ist auf diesem Gerät nicht verfügbar.")
            return
        }
        guard let url = call.getString("url"), !url.isEmpty else {
            call.reject("Keine URL zum Schreiben übergeben.")
            return
        }
        pendingCall = call
        pendingUrl = url
        session = NFCNDEFReaderSession(delegate: self, queue: nil, invalidateAfterFirstRead: false)
        session?.alertMessage = "iPhone an den NEUEN NFC-Tag halten. Der Tag wird beschrieben und dauerhaft versiegelt."
        session?.begin()
    }

    // MARK: - NFCNDEFReaderSessionDelegate

    public func readerSession(_ session: NFCNDEFReaderSession, didInvalidateWithError error: Error) {
        // Wird auch nach erfolgreichem invalidate() gerufen — dann ist pendingCall schon weg.
        if let call = pendingCall {
            let nfcError = error as? NFCReaderError
            if nfcError?.code == .readerSessionInvalidationErrorUserCanceled {
                call.reject("Abgebrochen.")
            } else {
                call.reject(error.localizedDescription)
            }
        }
        cleanup()
    }

    // Nur relevant, wenn didDetect(tags:) NICHT implementiert wäre — wir nutzen
    // durchgehend den Tag-Pfad unten, müssen die Methode aber nicht bedienen.
    public func readerSession(_ session: NFCNDEFReaderSession, didDetectNDEFs messages: [NFCNDEFMessage]) {
        // bewusst leer — didDetect(tags:) übernimmt
    }

    public func readerSession(_ session: NFCNDEFReaderSession, didDetect tags: [NFCNDEFTag]) {
        guard let tag = tags.first else {
            session.restartPolling()
            return
        }
        session.connect(to: tag) { [weak self] error in
            guard let self = self else { return }
            if let error = error {
                self.fail(session, "Verbindung zum Tag fehlgeschlagen: \(error.localizedDescription)")
                return
            }
            tag.queryNDEFStatus { status, _, error in
                if let error = error {
                    self.fail(session, "Tag nicht lesbar: \(error.localizedDescription)")
                    return
                }
                if let url = self.pendingUrl {
                    self.schreibeUndVersiegele(session, tag: tag, status: status, url: url)
                } else {
                    self.lies(session, tag: tag, status: status)
                }
            }
        }
    }

    // MARK: - Lesen

    private func lies(_ session: NFCNDEFReaderSession, tag: NFCNDEFTag, status: NFCNDEFStatus) {
        guard status != .notSupported else {
            fail(session, "Dieser Tag unterstützt kein NDEF.")
            return
        }
        tag.readNDEF { [weak self] message, error in
            guard let self = self else { return }
            if let error = error {
                self.fail(session, "Lesen fehlgeschlagen: \(error.localizedDescription)")
                return
            }
            guard let message = message, let text = Self.ersterText(message) else {
                self.fail(session, "Kein Werkzeug-Code auf dem Tag.")
                return
            }
            session.alertMessage = "Tag gelesen."
            session.invalidate()
            self.pendingCall?.resolve(["text": text])
            self.cleanup()
        }
    }

    // MARK: - Schreiben + Versiegeln (PFLICHT)

    private func schreibeUndVersiegele(_ session: NFCNDEFReaderSession, tag: NFCNDEFTag,
                                       status: NFCNDEFStatus, url: String) {
        guard status == .readWrite else {
            let grund = status == .readOnly
                ? "Tag ist bereits schreibgeschützt — bitte einen neuen Tag verwenden."
                : "Dieser Tag unterstützt kein NDEF."
            fail(session, grund)
            return
        }
        guard let payload = NFCNDEFPayload.wellKnownTypeURIPayload(string: url) else {
            fail(session, "URL konnte nicht kodiert werden.")
            return
        }
        let message = NFCNDEFMessage(records: [payload])
        tag.writeNDEF(message) { [weak self] error in
            guard let self = self else { return }
            if let error = error {
                self.fail(session, "Schreiben fehlgeschlagen: \(error.localizedDescription)")
                return
            }
            tag.writeLock { error in
                if let error = error {
                    // Tag ist beschrieben, aber nicht versiegelt — klar melden.
                    self.fail(session, "Beschrieben, aber Versiegeln fehlgeschlagen: \(error.localizedDescription)")
                    return
                }
                session.alertMessage = "Tag beschrieben und dauerhaft versiegelt."
                session.invalidate()
                self.pendingCall?.resolve()
                self.cleanup()
            }
        }
    }

    // MARK: - Helfer

    private func fail(_ session: NFCNDEFReaderSession, _ meldung: String) {
        session.invalidate(errorMessage: meldung)
        pendingCall?.reject(meldung)
        cleanup()
    }

    private func cleanup() {
        pendingCall = nil
        pendingUrl = nil
        session = nil
    }

    // Erster brauchbarer Inhalt eines NDEF-Records: URI oder Text.
    private static func ersterText(_ message: NFCNDEFMessage) -> String? {
        for record in message.records {
            if let url = record.wellKnownTypeURIPayload() {
                return url.absoluteString
            }
            let (text, _) = record.wellKnownTypeTextPayload()
            if let text = text, !text.isEmpty {
                return text
            }
        }
        return nil
    }
}
