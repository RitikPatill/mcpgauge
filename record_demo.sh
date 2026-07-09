#!/usr/bin/env bash
# record_demo.sh — reproduce the MCPGauge demo recording
#
# Prerequisites (one-time):
#   pip install asciinema playwright
#   cargo install agg          # or: pip install agg
#   playwright install chromium
#
# Usage:
#   export ANTHROPIC_API_KEY=sk-ant-...
#   bash record_demo.sh

set -euo pipefail

# ── 1. Validate environment ────────────────────────────────────────────────
if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "ERROR: ANTHROPIC_API_KEY is not set." >&2
  exit 1
fi

# ── 2. Ensure docs/ directory exists ──────────────────────────────────────
mkdir -p docs

# ── 3. Record terminal session with asciinema ─────────────────────────────
echo "Recording terminal session..."
asciinema rec --overwrite docs/demo.cast -- \
  bash -c 'uv run mcpgauge run examples/poisoning.yaml'

# ── 4. Convert cast → GIF with agg ────────────────────────────────────────
echo "Converting cast to GIF..."
agg docs/demo.cast docs/demo.gif

# ── 5. Screenshot the dashboard with playwright ───────────────────────────
echo "Starting dashboard on port 8765..."
uv run mcpgauge serve --no-open --port 8765 &
SERVER_PID=$!
trap "kill $SERVER_PID 2>/dev/null || true" EXIT

sleep 4

echo "Taking screenshot..."
uv run python - <<'PYEOF'
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        await page.goto("http://localhost:8765/runs")
        await page.wait_for_load_state("networkidle")
        await page.screenshot(path="docs/screenshot.png")
        await browser.close()

asyncio.run(main())
PYEOF

echo "Done. Assets written to docs/:"
echo "  docs/demo.cast"
echo "  docs/demo.gif"
echo "  docs/screenshot.png"
