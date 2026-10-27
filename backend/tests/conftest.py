import os
import sys
import tempfile
from pathlib import Path

# Data test di folder sementara, bukan %APPDATA%\LKMonitoring milik pengguna.
# Harus di-set sebelum modul app diimpor.
os.environ["LKM_DATA_DIR"] = tempfile.mkdtemp(prefix="lkm-test-")
os.environ.pop("LKM_ACCESS_SHEET_ID", None)
os.environ["LKM_TANPA_PEMBARUAN"] = "1"  # jangan git fetch / restart saat test
os.environ["LKM_TAG_OFF"] = "1"  # jangan pernah mewarnai sheet Broadcast sungguhan saat test

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
