"""The repo's required check: every page asset exists and the page loads it."""

import sys
from pathlib import Path

page = Path("checkout.html").read_text()
missing = [name for name in ("api.js", "app.js", "styles.css")
           if not Path(name).is_file() or name not in page]
print("missing: " + ", ".join(missing) if missing else "static assets ok")
sys.exit(1 if missing else 0)
