import subprocess
import sys

from app import kunci_server


def test_hanya_satu_pemegang_kunci(tmp_path):
    file = tmp_path / "server.lock"
    a = kunci_server.ambil(file)
    assert a is not None
    # proses lain (server kedua) tidak boleh mendapat kunci selama yang pertama hidup
    kode = "import sys; from pathlib import Path; from app import kunci_server; " \
           f"sys.exit(0 if kunci_server.ambil(Path(r'{file}')) is None else 1)"
    assert subprocess.run([sys.executable, "-c", kode]).returncode == 0
    a.close()
    assert subprocess.run([sys.executable, "-c", kode]).returncode == 1  # kunci lepas: boleh jalan
