"""Buat docs/knowledge/TEMPLATE_JAWABAN.md dari web/lib/jawaban.json (sumber yang dipakai aplikasi).

Ubah isi template di web/lib/jawaban.json, lalu jalankan:
    python scripts/jawaban_ke_md.py
"""

import json
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
SUMBER = AKAR / "web" / "lib" / "jawaban.json"
HASIL = AKAR / "docs" / "knowledge" / "TEMPLATE_JAWABAN.md"


def main() -> None:
    d = json.loads(SUMBER.read_text(encoding="utf-8"))
    total = sum(len(k["items"]) for k in d["kategori"])
    out = [
        "# Template jawaban untuk pertanyaan fasil",
        "",
        f"{total} template dalam {len(d['kategori'])} topik. Versi {d['versi']}.",
        "",
        "Di aplikasi: buka panel fasil → kolom **Di WhatsApp** → **Jawab pertanyaan…** → cari kata kunci → **Pakai**. "
        "Teks masuk ke kotak balasan dan bisa diedit dulu sebelum dikirim. "
        "`{nama}` otomatis diganti nama fasil.",
        "",
        "Sumber:",
        *[f"- {s}" for s in d["sumber"]],
        "",
        "## Daftar isi",
        "",
    ]
    for k in d["kategori"]:
        out.append(f"- **{k['judul']}**: " + "; ".join(it["tanya"] for it in k["items"]))
    for k in d["kategori"]:
        out += ["", f"## {k['judul']}"]
        for it in k["items"]:
            out += ["", f"### {it['tanya']}", "", f"Kata kunci: {', '.join(it['kata'])}", "", "```text",
                    it["jawab"], "```"]
    out.append("")
    HASIL.write_text("\n".join(out), encoding="utf-8")
    print(f"Ditulis: {HASIL} ({total} template)")


if __name__ == "__main__":
    main()
