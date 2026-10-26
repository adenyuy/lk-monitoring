import pytest
from fastapi import HTTPException

from app.routers import chat
from app.sheets import BroadcastRow


def test_hanya_nomor_fasil_sendiri(monkeypatch):
    import app.routers.chat as c
    row = BroadcastRow.__new__(BroadcastRow)
    object.__setattr__(row, "nomor", "6281200000001")
    monkeypatch.setattr(c, "read_broadcast", lambda: [row])
    monkeypatch.setattr(c, "filter_petugas", lambda rows, p: rows)
    assert chat._nomor_fasil("081200000001") == "6281200000001"
    with pytest.raises(HTTPException) as e:
        chat._nomor_fasil("081299999999")
    assert e.value.status_code == 403


def test_ditolak_saat_pengiriman_berjalan(monkeypatch):
    monkeypatch.setattr(chat.sender.state, "running", True)
    with pytest.raises(HTTPException) as e:
        chat._siap()
    assert e.value.status_code == 409
