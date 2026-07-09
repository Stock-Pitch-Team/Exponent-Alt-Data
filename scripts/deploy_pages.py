"""Copy the built site into docs/ (the folder GitHub Pages serves from main)."""
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

DOCS = PROJECT_ROOT / "docs"


def main():
    site = PROJECT_ROOT / "site"
    if DOCS.exists():
        shutil.rmtree(DOCS)
    shutil.copytree(site, DOCS)
    # Pages runs Jekyll by default, which ignores some paths; disable it
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    print(f"site/ -> docs/ ({sum(1 for _ in DOCS.rglob('*') if _.is_file())} files). "
          "Commit + push, then enable Pages: Settings > Pages > main /docs.")


if __name__ == "__main__":
    main()
