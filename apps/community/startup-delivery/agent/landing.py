"""Landing-page artifact publisher for T13.

This intentionally writes a static HTML artifact, not a live DNS/TLS deploy. If the
SvelteKit `web/public` static dir exists, the page is staged there so the frontend can
serve it at `/deliveries/<domain>/index.html`. Otherwise it falls back to a local file URL.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

_SAFE_PATH = re.compile(r"[^a-z0-9.-]")
ROOT = Path(__file__).resolve().parents[1]


def _safe_domain(domain: str) -> str:
    cleaned = _SAFE_PATH.sub("-", domain.strip().lower()).strip(".-")
    if not cleaned:
        raise ValueError("Cannot publish landing page for empty domain")
    return cleaned


def publish_landing_page(domain: str, html: str) -> str:
    """Write landing HTML and return the URL/path the app can render."""
    safe_domain = _safe_domain(domain)
    configured_dir = os.environ.get("LANDING_OUTPUT_DIR")
    configured_base_url = os.environ.get("LANDING_PUBLIC_BASE_URL", "").rstrip("/")

    # Point straight at index.html: SvelteKit's dev static server doesn't resolve a
    # bare directory to its index, so "/deliveries/<d>/" 404s in dev. The explicit
    # file works in dev AND on every static host.
    if configured_dir:
        output_root = Path(configured_dir).expanduser().resolve()
        public_path = f"/deliveries/{safe_domain}/index.html"
    else:
        # web/ is the SvelteKit app; its static root is web/public (svelte.config.js
        # sets files.assets = "public"), served at the site root.
        web_public = ROOT / "web" / "public"
        if (ROOT / "web").exists():
            output_root = web_public / "deliveries"
            public_path = f"/deliveries/{safe_domain}/index.html"
        else:
            output_root = ROOT / "agent" / ".generated" / "deliveries"
            public_path = ""

    output_dir = output_root / safe_domain
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "index.html"
    output_file.write_text(html, encoding="utf-8")

    if configured_base_url:
        return f"{configured_base_url}{public_path}"
    if public_path:
        return public_path
    return output_file.resolve().as_uri()
