import os
import sys
import tempfile
from pathlib import Path

# Data test di folder sementara, bukan %APPDATA%\LKMonitoring milik pengguna.
# Harus di-set sebelum modul app diimpor.
os.environ["LKM_DATA_DIR"] = tempfile.mkdtemp(prefix="lkm-test-")
os.environ["LKM_TANPA_PEMBARUAN"] = "1"  # jangan git fetch / restart saat test
os.environ["LKM_LK_OTOMATIS_OFF"] = "1"  # jangan menulis status komunikasi ke LK sungguhan saat test
os.environ["LKM_TAG_OFF"] = "1"  # jangan pernah mewarnai sheet Broadcast sungguhan saat test
# ID sheet palsu: tes tidak pernah membuka sheet sungguhan
for _k in ("BROADCAST", "LK", "ACCESS"):
    os.environ.setdefault(f"LKM_{_k}_SHEET_ID", f"uji-{_k.lower()}-0000000000000000000000")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
