import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def test_record_demo_script_exists():
    p = REPO_ROOT / "record_demo.sh"
    assert p.exists(), "record_demo.sh missing"
    if sys.platform != "win32":
        assert os.access(p, os.X_OK), "record_demo.sh not executable"


def test_docs_screenshot_placeholder_exists():
    p = REPO_ROOT / "docs" / "screenshot.png"
    assert p.exists()
    assert p.stat().st_size > 0


def test_docs_demo_gif_placeholder_exists():
    p = REPO_ROOT / "docs" / "demo.gif"
    assert p.exists()
    assert p.stat().st_size > 0


def test_makefile_has_required_targets():
    mk = (REPO_ROOT / "Makefile").read_text()
    for target in ("install", "demo", "serve", "record"):
        assert f"{target}:" in mk, f"Makefile missing target: {target}"
