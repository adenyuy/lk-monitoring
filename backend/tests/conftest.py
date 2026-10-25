import os
import sys
import tempfile
from pathlib import Path

# Data test di folder sementara, bukan %APPDATA%\LKMonitoring milik pengguna.
# Harus di-set sebelum modul app diimpor.
os.environ["LKM_DATA_DIR"] = tempfile.mkdtemp(prefix="lkm-test-")
os.environ.pop("LKM_ACCESS_SHEET_ID", None)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
