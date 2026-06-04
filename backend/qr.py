"""QR-Code-Etiketten als PDF (einzeln A6 / Sammel 4-up A4)."""

from io import BytesIO

import qrcode
from qrcode.constants import ERROR_CORRECT_M
from reportlab.lib.colors import lightgrey
from reportlab.lib.pagesizes import A4, A6
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from backend.config import settings
from backend.models import Maschine


def _qr_url(maschine: Maschine) -> str:
    """Hash-Route, damit der SPA-Router beim QR-Scan direkt auf die Maschine springt."""
    return f"{settings.BASE_URL}/#/m/{maschine.maschinen_code}"


def _qr_bild(url: str) -> ImageReader:
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


def _angepasste_groesse(c: canvas.Canvas, text: str, font: str,
                        max_pt: int, min_pt: int, max_breite: float) -> int:
    """Sucht die größte Schriftgröße, in der `text` noch in `max_breite` passt."""
    for pt in range(max_pt, min_pt - 1, -1):
        if c.stringWidth(text, font, pt) <= max_breite:
            return pt
    return min_pt


def _zeichne_etikett(c: canvas.Canvas, x0: float, y0: float,
                     breite: float, hoehe: float, maschine: Maschine) -> None:
    """Zeichnet ein einzelnes Etikett innerhalb der angegebenen Box.

    Koordinaten-Ursprung in reportlab: links unten. (x0, y0) = links-untere Ecke.
    """
    rand = 6 * mm
    inner_breite = breite - 2 * rand

    # 1) QR-Code oben mittig
    qr_size = min(55 * mm, inner_breite, hoehe * 0.55)
    qr_x = x0 + (breite - qr_size) / 2
    qr_y = y0 + hoehe - qr_size - 10 * mm
    c.drawImage(_qr_bild(_qr_url(maschine)), qr_x, qr_y,
                width=qr_size, height=qr_size)

    # 2) Maschinen-Code groß darunter
    code_pt = _angepasste_groesse(c, maschine.maschinen_code, "Helvetica-Bold",
                                  28, 14, inner_breite)
    c.setFont("Helvetica-Bold", code_pt)
    code_y = qr_y - 10 * mm
    c.drawCentredString(x0 + breite / 2, code_y, maschine.maschinen_code)

    # 3) Name (Schriftgröße passend zur Länge)
    name_pt = _angepasste_groesse(c, maschine.name, "Helvetica",
                                  14, 8, inner_breite)
    c.setFont("Helvetica", name_pt)
    name_y = code_y - 7 * mm
    c.drawCentredString(x0 + breite / 2, name_y, maschine.name)

    # 4) Platznummer in klein
    if maschine.platznummer:
        c.setFont("Helvetica-Oblique", 9)
        c.drawCentredString(x0 + breite / 2, name_y - 5 * mm, maschine.platznummer)


def _zeichne_schnittlinien(c: canvas.Canvas, breite: float, hoehe: float) -> None:
    """Hilfslinien zum Auseinanderschneiden der 4 Etiketten."""
    c.saveState()
    c.setStrokeColor(lightgrey)
    c.setDash(3, 3)
    c.line(breite / 2, 0, breite / 2, hoehe)
    c.line(0, hoehe / 2, breite, hoehe / 2)
    c.restoreState()


def einzel_pdf(maschine: Maschine) -> bytes:
    """Liefert ein A6-PDF mit dem QR-Etikett dieser Maschine."""
    buf = BytesIO()
    b, h = A6
    c = canvas.Canvas(buf, pagesize=A6)
    _zeichne_etikett(c, 0, 0, b, h, maschine)
    c.showPage()
    c.save()
    return buf.getvalue()


def sammel_pdf(maschinen: list[Maschine]) -> bytes:
    """Liefert ein A4-PDF mit 4 Etiketten pro Seite (2×2) inkl. Schnittlinien."""
    buf = BytesIO()
    a4_b, a4_h = A4
    box_b = a4_b / 2
    box_h = a4_h / 2
    c = canvas.Canvas(buf, pagesize=A4)

    for idx, m in enumerate(maschinen):
        pos = idx % 4
        if idx > 0 and pos == 0:
            _zeichne_schnittlinien(c, a4_b, a4_h)
            c.showPage()
        col = pos % 2
        row = pos // 2
        x0 = col * box_b
        y0 = a4_h - (row + 1) * box_h
        _zeichne_etikett(c, x0, y0, box_b, box_h, m)

    _zeichne_schnittlinien(c, a4_b, a4_h)
    c.showPage()
    c.save()
    return buf.getvalue()
