"""Render checks on real committed data; no external-value verification implied."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
server = ThreadingHTTPServer(('0.0.0.0', 0), partial(SimpleHTTPRequestHandler, directory=str(ROOT)))
Thread(target=server.serve_forever, daemon=True).start()
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for width in (390, 1280):
            page = browser.new_page(viewport={'width': width, 'height': 844})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            for path in ('/', '/slate/cs2.html', '/slate/own-lines.html', '/slate/flagged.html'):
                page.goto(f'http://127.0.0.1:{server.server_port}{path}', wait_until='networkidle')
                page.wait_for_function("document.querySelector('#freshness').textContent.includes('Captured')")
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (width, path, 'overflow')
                assert not errors, errors
                if path == '/slate/cs2.html':
                    inp = page.locator('.table-search input').first
                    inp.fill('__no_such_team__')
                    assert page.locator('.fixture-row:visible').count() == 0, 'filter did not hide rows'
                    inp.fill('')
                    assert page.locator('.fixture-row:visible').count() > 0
                    page.screenshot(path=f'/tmp/slate-{width}.png', full_page=False)
                if path == '/':
                    assert page.locator('#cs-count').inner_text() != '—', 'snapshot did not load'
            # Failed fetches must explicitly mark unknowns, not show stale picks as active.
            page.route('**/data/analysis.json', lambda route: route.fulfill(status=503, body='unavailable'))
            page.goto(f'http://127.0.0.1:{server.server_port}/slate/cs2.html', wait_until='networkidle')
            assert 'unavailable' in page.locator('#freshness').inner_text().lower()
            assert page.locator('.pick-cell .pick:not(.none)').count() == 0
            page.close()
        browser.close()
    print('Browser checks: mobile/desktop layout, filtering, source snapshot loading and failure states passed.')
finally:
    server.shutdown()
    server.server_close()
