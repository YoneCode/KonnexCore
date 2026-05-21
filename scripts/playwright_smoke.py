#!/usr/bin/env python3
"""End-to-end browser smoke test for a deployed KonnexCore URL.

Uses Playwright (the browser automation toolkit referenced by the
``webapp-testing`` skill). The test:

1. Opens the home page; asserts the hero headline renders and there
   are no JS console errors.
2. Navigates to /full-stack, waits for the cascade to populate, and
   asserts the verdict pill appears.
3. Switches to the "Deepfake video" scenario and asserts the verdict
   flips to "failure".

Exit code 0 if everything passes, 1 otherwise.

Setup (one-time)::

    pip install 'playwright==1.46.0'
    playwright install chromium

Run::

    python scripts/playwright_smoke.py http://127.0.0.1:80
    python scripts/playwright_smoke.py https://demo.example.com
"""

from __future__ import annotations

import argparse
import sys
import time

from playwright.sync_api import (
    ConsoleMessage,
    Page,
    sync_playwright,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="playwright_smoke")
    parser.add_argument("url", help="Base URL of the deployed dashboard.")
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=20_000,
        help="Per-action timeout (default 20 000 ms).",
    )
    return parser.parse_args()


def wire_console(page: Page, errors: list[str]) -> None:
    """Capture console errors so we can assert on them at the end."""

    def handler(msg: ConsoleMessage) -> None:
        if msg.type == "error":
            errors.append(f"[{msg.location}] {msg.text}")

    page.on("console", handler)
    page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))


def assert_text_visible(page: Page, text: str, timeout_ms: int) -> None:
    """Wait for ``text`` to appear; raise on timeout."""
    page.get_by_text(text, exact=False).first.wait_for(
        state="visible",
        timeout=timeout_ms,
    )


def main() -> int:
    args = parse_args()
    base = args.url.rstrip("/")

    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(args.timeout_ms)
        wire_console(page, errors)

        # 1. Home page renders.
        print(f"[smoke] visiting {base}/", flush=True)
        page.goto(base + "/", wait_until="networkidle")
        assert_text_visible(page, "validator stack", args.timeout_ms)
        assert_text_visible(page, "RootID", args.timeout_ms)

        # 2. Full-stack demo loads and runs a clean scenario.
        print(f"[smoke] visiting {base}/full-stack", flush=True)
        page.goto(base + "/full-stack", wait_until="networkidle")
        # Verdict pill should appear once the API responds.
        assert_text_visible(page, "success", args.timeout_ms)

        # 3. Click the deepfake scenario, verify verdict flips to failure.
        print("[smoke] switching to deepfake scenario", flush=True)
        page.get_by_role("button", name="Deepfake video").click()
        # Allow the new request to complete.
        time.sleep(0.6)
        page.wait_for_load_state("networkidle")
        assert_text_visible(page, "failure", args.timeout_ms)

        browser.close()

    if errors:
        print(f"[smoke] FAIL — {len(errors)} console error(s):", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return 1

    print("[smoke] OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
