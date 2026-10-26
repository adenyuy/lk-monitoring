import pytest
from fastapi import HTTPException

from app.routers import chat


def test_hanya_nomor_fasil_sendiri(monkeypatch):
    import app.routers.chat as c
    monkeypatch.setattr(c, "nomor_milik", lambda: {"6281200000001"})
    assert chat._nomor_fasil("081200000001") == "6281200000001"
    with pytest.raises(HTTPException) as e:
        chat._nomor_fasil("081299999999")
    assert e.value.status_code == 403


def test_ditolak_saat_pengiriman_berjalan(monkeypatch):
    monkeypatch.setattr(chat.sender.state, "running", True)
    with pytest.raises(HTTPException) as e:
        chat._siap()
    assert e.value.status_code == 409
