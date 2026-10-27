"""Capture UI screenshots with headless Chromium.

Usage: python frontend/scripts/screenshots.py [base_url]   (default http://localhost:8000)
Writes docs/screenshots/*.png.
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
OUT = Path(__file__).resolve().parents[2] / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        page.goto(f"{BASE}/")
        page.wait_for_selector("text=Households", timeout=60000)
        page.wait_for_timeout(800)
        page.screenshot(path=OUT / "dashboard.png")

        page.goto(f"{BASE}/households/HH-001")
        page.wait_for_selector("text=Pension Credit", timeout=180000)
        page.wait_for_timeout(500)
        page.screenshot(path=OUT / "household.png")
        page.get_by_role("button", name="Why?").first.click()
        page.wait_for_timeout(400)
        page.screenshot(path=OUT / "household_why.png", full_page=True)

        page.goto(f"{BASE}/households/HH-001/trace")
        page.wait_for_selector("text=How the decision was made", timeout=60000)
        page.wait_for_timeout(500)
        page.screenshot(path=OUT / "trace.png", full_page=True)

        page.goto(f"{BASE}/evaluation")
        page.wait_for_timeout(1500)
        page.screenshot(path=OUT / "evaluation.png", full_page=True)

        page.goto(f"{BASE}/rules")
        page.wait_for_timeout(1000)
        page.screenshot(path=OUT / "rules.png")
        browser.close()
    print("screenshots in", OUT)


if __name__ == "__main__":
    main()
