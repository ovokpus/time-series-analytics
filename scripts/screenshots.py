"""Capture README screenshots from the running stack (docker compose up). Real UI and data, no mocks."""
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 900})
    pg.goto("http://localhost:8080"); pg.wait_for_selector("circle.anom"); pg.wait_for_timeout(800)
    pg.screenshot(path=OUT / "01-app-anomalies.png", full_page=True)
    pg.select_option("select >> nth=0", "Dongsi"); pg.select_option("select >> nth=1", "TEMP"); pg.select_option("select >> nth=2", "-7d")
    pg.wait_for_timeout(1500)
    pg.screenshot(path=OUT / "02-app-temperature.png", full_page=True)
    for name, uid, frm in [("03-grafana-air-quality.png", "air-quality", "now-30d"), ("04-grafana-live-weather.png", "live-weather", "now-6h")]:
        pg.goto(f"http://localhost:3000/d/{uid}?orgId=1&from={frm}&to=now&kiosk")
        pg.wait_for_selector("[data-testid='data-testid panel content'], .panel-content", timeout=30000)
        pg.wait_for_timeout(5000)
        pg.screenshot(path=OUT / name, full_page=True)
    pg.goto("http://localhost:8000/docs"); pg.wait_for_selector(".opblock")
    pg.screenshot(path=OUT / "05-api-docs.png", full_page=True)
    b.close()
print("ok")
