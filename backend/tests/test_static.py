from app import main, paths


def test_prefetch_next_dipetakan_ke_folder(tmp_path, monkeypatch):
    seg = tmp_path / "admin" / "__next.!KGFwcCk" / "admin"
    seg.mkdir(parents=True)
    (seg / "__PAGE__.txt").write_text("x")
    (tmp_path / "admin" / "index.html").write_text("<html></html>")
    monkeypatch.setattr(paths, "WEB_OUT_DIR", tmp_path)
    assert main._resolve_static("/admin/__next.!KGFwcCk.admin.__PAGE__.txt") == (seg / "__PAGE__.txt").resolve()
    assert main._resolve_static("/admin/") == (tmp_path / "admin" / "index.html").resolve()
    assert main._resolve_static("/../luar/__next.a.b.txt") is None
    assert main._resolve_static("/admin/__next.!KGFwcCk.tidakada.__PAGE__.txt") is None
