from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_v2_scaffold_files_exist():
    assert (ROOT / "ui" / "build" / "index.html").exists()
    assert (ROOT / "ui" / "src" / "routes" / "+page.svelte").exists()
    assert (ROOT / "ui" / "src" / "lib" / "api.ts").exists()
    v2_html = (ROOT / "ui" / "build" / "index.html").read_text(encoding="utf-8")
    assert "/v2/_app/" in v2_html


def test_app_registers_v2_mount_when_build_exists():
    app_py = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "self.ui_build_dir = self.root / \"ui\" / \"build\"" in app_py
    assert "app.mount(\"/v2\", StaticFiles(directory=str(state.ui_build_dir), html=True), name=\"ui_v2\")" in app_py
    assert "def ui_v2_unavailable()" in app_py
    assert "UI V2 build not found. Run: cd ui && npm install && npm run build" in app_py
    assert "def legacy_index()" in app_py
    assert "index_file = state.static_dir / \"index.html\"" in app_py
