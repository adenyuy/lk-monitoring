import socket
import threading
import urllib.request
from urllib.parse import urlsplit

from app import google_auth


class _FlowPalsu:
    redirect_uri = ""

    def authorization_url(self, **kw):
        return "https://accounts.google.com/o/oauth2/auth?x=1", "state"


def test_redirect_tetap_diterima_walau_ada_koneksi_kosong(monkeypatch):
    flow = _FlowPalsu()
    kosong = []

    def buka(url, **kw):
        port = urlsplit(flow.redirect_uri).port

        def browser():
            # Chrome sering membuka koneksi lebih dulu tanpa mengirim apa pun (preconnect), lalu meminta favicon
            kosong.append(socket.create_connection(("localhost", port)))
            with urllib.request.urlopen(f"http://localhost:{port}/?state=s&code=abc", timeout=5) as r:
                assert b"Login berhasil" in r.read()

        threading.Thread(target=browser, daemon=True).start()

    monkeypatch.setattr(google_auth.webbrowser, "open", buka)
    hasil = google_auth._tunggu_redirect(flow, threading.Event())
    assert "code=abc" in hasil
    for s in kosong:
        s.close()


def test_login_lama_dihentikan_bila_dibatalkan(monkeypatch):
    monkeypatch.setattr(google_auth.webbrowser, "open", lambda url, **kw: None)
    batal = threading.Event()
    hasil = []
    t = threading.Thread(target=lambda: hasil.append(google_auth._tunggu_redirect(_FlowPalsu(), batal)))
    t.start()
    batal.set()
    t.join(5)
    assert not t.is_alive() and hasil == [""]
