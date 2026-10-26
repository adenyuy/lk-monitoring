"""SQLite lokal: pengaturan, log kirim, status chat, riwayat tarik cutoff."""

import json
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Iterator

from . import paths

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sends (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tanggal     TEXT NOT NULL,          -- YYYY-MM-DD (Asia/Jakarta)
    waktu       TEXT NOT NULL,          -- ISO 8601
    sesi        INTEGER NOT NULL,
    nama_fasil  TEXT NOT NULL,
    nomor       TEXT NOT NULL,
    hash_pesan  TEXT NOT NULL,
    status      TEXT NOT NULL,          -- terkirim | gagal | dilewati | dicoba
    keterangan  TEXT NOT NULL DEFAULT '',
    coba        INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_sends_tanggal ON sends(tanggal);
CREATE INDEX IF NOT EXISTS idx_sends_kunci ON sends(nomor, hash_pesan);

CREATE TABLE IF NOT EXISTS chat_status (
    nomor             TEXT PRIMARY KEY,
    status            TEXT NOT NULL,    -- terkirim | dibaca | dibalas
    balasan_terakhir  TEXT NOT NULL DEFAULT '',
    waktu_balasan     TEXT NOT NULL DEFAULT '',
    dicek             TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_tahap (
    nomor  TEXT NOT NULL,
    tahap  TEXT NOT NULL,               -- terkirim | dibaca | dibalas | ditanya | lk_lengkap
    nilai  INTEGER NOT NULL,            -- 1 dicentang, 0 dibatalkan (menimpa deteksi otomatis)
    sumber TEXT NOT NULL,               -- manual | template
    waktu  TEXT NOT NULL,
    PRIMARY KEY (nomor, tahap)
);

CREATE TABLE IF NOT EXISTS kirim_ulang (
    nomor  TEXT PRIMARY KEY,
    waktu  TEXT NOT NULL                -- saat diminta; berlaku sampai ada kiriman terkirim sesudahnya
);

CREATE TABLE IF NOT EXISTS tag_warna (
    nomor  TEXT PRIMARY KEY,
    warna  TEXT NOT NULL,               -- hijau | kuning | merah (yang sudah tertulis di Broadcast P1)
    waktu  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cutoff_runs (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    waktu     TEXT NOT NULL,
    file      TEXT NOT NULL,
    mode      TEXT NOT NULL,            -- harian | mingguan
    week      TEXT NOT NULL,
    sekolah   INTEGER NOT NULL,
    ringkasan TEXT NOT NULL DEFAULT '{}'
);
"""

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None


def connect() -> sqlite3.Connection:
    """Satu koneksi bersama, dilindungi lock (app hanya dipakai satu orang)."""
    global _conn
    with _lock:
        if _conn is None:
            paths.ensure_dirs()
            _conn = sqlite3.connect(paths.DB_FILE, check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA journal_mode=WAL")
            _conn.executescript(SCHEMA)
            _conn.commit()
        return _conn


def close() -> None:
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    """Transaksi: commit kalau sukses, rollback kalau error."""
    conn = connect()
    with _lock:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def query(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    """SELECT yang aman dipanggil dari thread mana pun (koneksi dipakai bersama)."""
    conn = connect()
    with _lock:
        return conn.execute(sql, params).fetchall()


def query_one(sql: str, params: tuple = ()) -> sqlite3.Row | None:
    rows = query(sql, params)
    return rows[0] if rows else None


# --- settings (nilai disimpan sebagai JSON) ---

def get_setting(key: str, default: Any = None) -> Any:
    row = query_one("SELECT value FROM settings WHERE key = ?", (key,))
    return json.loads(row["value"]) if row else default


def set_setting(key: str, value: Any) -> None:
    with tx() as c:
        c.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value)),
        )


def delete_setting(key: str) -> None:
    with tx() as c:
        c.execute("DELETE FROM settings WHERE key = ?", (key,))
