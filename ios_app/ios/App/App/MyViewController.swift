import UIKit
import Capacitor

// Eigener Bridge-ViewController: registriert lokale Plugins (Capacitor 6+
// registriert lokale, nicht per npm installierte Plugins nicht mehr selbst).
class MyViewController: CAPBridgeViewController {
    override open func capacitorDidLoad() {
        bridge?.registerPluginInstance(WerkzeugNfcPlugin())
    }
}
