#!/usr/bin/env python3
"""Browser acceptance, run on Actions where Chromium can be installed.

Screenshots are CI artifacts, not repository content. Reports are bounded JSON.
"""
import functools
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import json
from pathlib import Path
import threading
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def main():
    handler = functools.partial(QuietHandler, directory=str(ROOT))
    server = ThreadingHTTPServer(('0.0.0.0', 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    results = []
    errors = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for width in (360, 390, 768):
                page = browser.new_page(viewport={'width': width, 'height': 844})
                page.clock.install()
                for route in ('index.html', 'executive/picks.html', 'executive/unresolved.html', 'executive/flagged.html'):
                    response = page.goto(f'http://127.0.0.1:{server.server_port}/{route}')
                    page.wait_for_load_state('networkidle')
                    result = page.evaluate('''() => ({
                        width: innerWidth, contentWidth: document.documentElement.scrollWidth,
                        title: document.title, h1: document.querySelectorAll('h1').length,
                        sourceClock: document.querySelector('[data-age]')?.textContent || null,
                        picksLink: !!document.querySelector('a[href="executive/picks.html"],a[href="picks.html"]')
                    })''')
                    result.update(route=route, http_status=response.status)
                    if result['contentWidth'] > width + 1 or response.status != 200 or result['h1'] != 1:
                        errors.append(result)
                    results.append(result)
                    if width == 390:
                        page.screenshot(path=f'/tmp/mobile-{route.replace("/", "-")}.png', full_page=True)
                # Verify actual browser timers, not just the existence of timer source code.
                page.goto(f'http://127.0.0.1:{server.server_port}/executive/picks.html')
                if page.locator('[data-lock]').count():
                    page.locator('[data-lock]').first.evaluate("el => el.dataset.lock = '2000-01-01T00:00:00Z'")
                    page.clock.fast_forward(31000)
                    if 'Locked' not in page.locator('[data-lock]').first.inner_text():
                        errors.append({'route': 'deadline clock', 'width': width})
                page.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    report = {'checks': results, 'errors': errors, 'screenshots': 'Actions artifacts: mobile-*.png',
              'scope': 'Chromium viewport, horizontal overflow, HTTP, headings and dynamic deadlines; not a manual accessibility certification.'}
    (ROOT / 'executive/data/mobile_verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
