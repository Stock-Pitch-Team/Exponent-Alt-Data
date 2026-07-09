"""Bundle the entire dashboard into ONE self-contained HTML file.

Inlines css/main.css, vendor/echarts, every data/*.data.js, and the app JS
into site/index.html's structure -> EXPO-dashboard.html (project root).
The result opens from anywhere - email attachment, USB stick, double-click.
Run scripts/build_site_data.py first.
"""
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config import settings  # noqa: E402

OUT = PROJECT_ROOT / "EXPO-dashboard.html"


def main():
    site = settings.SITE_DIR
    html = (site / "index.html").read_text(encoding="utf-8")

    # inline the stylesheet
    css = (site / "css" / "main.css").read_text(encoding="utf-8")
    html = html.replace('<link rel="stylesheet" href="css/main.css">',
                        "<style>\n" + css + "\n</style>")

    # inline every <script src="..."> in document order
    def inline_script(m):
        src = m.group(1)
        path = site / src.replace("/", "\\")
        if not path.exists():
            print(f"  WARNING: {src} missing -> dropped (page will show its unavailable card)")
            return f"<!-- {src} not present at build time -->"
        body = path.read_text(encoding="utf-8")
        # </script> inside JS strings would terminate the tag early
        body = body.replace("</script>", "<\\/script>")
        return "<script>\n" + body + "\n</script>"

    html = re.sub(r'<script src="([^"]+)"></script>', inline_script, html)

    OUT.write_text(html, encoding="utf-8")
    size_mb = OUT.stat().st_size / 1e6
    print(f"wrote {OUT} ({size_mb:.1f} MB, fully self-contained)")


if __name__ == "__main__":
    main()
