"""SSO-Anbindung an das Portal b² (home.b2interior.de) – Stufe 2.

Caddy prüft vor jedem Seitenaufruf das Portal-Cookie (forward_auth) und reicht die
Header X-B2-User / X-B2-Role / X-B2-Email / X-B2-Auth an die App weiter. X-B2-Auth ist
eine HMAC-SHA256-Signatur des Portals über (Zeitstempel, Kürzel, Rolle, E-Mail) mit dem
gemeinsamen Secret B2_SSO_SECRET (= B2_SSO_SECRET des Portals). Ohne gültige
Signatur werden die Header ignoriert – niemand kann sich die Header selbst setzen.
Kein Secret gesetzt = SSO aus, die App verhält sich wie bisher.
"""
import hashlib
import hmac
import os
import time

ZEITFENSTER_SEK = 300


def secret():
    return os.environ.get("B2_SSO_SECRET", "")


def portal_url():
    return os.environ.get("B2_PORTAL_URL", "https://home.b2interior.de")


def benutzer_aus_headern(headers, sec=None, now=None):
    """Liefert {'kuerzel','rolle','email'} aus signierten Portal-Headern oder None."""
    sec = secret() if sec is None else sec
    if not sec:
        return None
    kuerzel = (headers.get("X-B2-User") or "").strip()
    rolle = (headers.get("X-B2-Role") or "").strip()
    email = (headers.get("X-B2-Email") or "").strip()
    auth = (headers.get("X-B2-Auth") or "").strip()
    if not kuerzel or "." not in auth:
        return None
    ts_roh, sig = auth.split(".", 1)
    if not ts_roh.isdigit():
        return None
    now = time.time() if now is None else now
    if abs(now - int(ts_roh)) > ZEITFENSTER_SEK:
        return None
    msg = f"{ts_roh}\n{kuerzel}\n{rolle}\n{email}".encode("utf-8")
    erwartet = hmac.new(sec.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(erwartet, sig):
        return None
    return {"kuerzel": kuerzel, "rolle": rolle, "email": email}


def signatur(sec, kuerzel, rolle="", email="", ts=None):
    """Gegenstück zum Portal – für Tests."""
    ts = int(time.time()) if ts is None else int(ts)
    msg = f"{ts}\n{kuerzel}\n{rolle}\n{email}".encode("utf-8")
    return f"{ts}.{hmac.new(sec.encode('utf-8'), msg, hashlib.sha256).hexdigest()}"
