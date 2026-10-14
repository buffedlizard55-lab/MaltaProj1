"""Confirm actual public Pages responses after a validated main refresh requests a build.

Runs on GitHub Actions, where the public Pages host is reachable. Does not verify bookmaker values.
"""
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
BASE = 'https://buffedlizard55-lab.github.io/MaltaProj1/'
expected = json.loads((HERE / 'data/coverage.json').read_text())['generated_utc']
deadline = time.monotonic() + 300
last_error = None
while time.monotonic() < deadline:
    try:
        urls = ('slate/data/coverage.json', '', 'slate/cs2.html', 'slate/flagged.html')
        bodies = {}
        for path in urls:
            req = Request(BASE + path + '?verify=' + str(time.time_ns()), headers={'User-Agent': 'MaltaProj1-Pages-Verification', 'Cache-Control': 'no-cache'})
            with urlopen(req, timeout=15) as response:
                assert response.status == 200, (path, response.status)
                bodies[path] = response.read(8_000_000).decode('utf-8')
        actual = json.loads(bodies['slate/data/coverage.json'])['generated_utc']
        assert actual >= expected, f'Pages snapshot {actual} is older than validated snapshot {expected}'
        assert 'The match board.' in bodies[''], 'Landing not deployed'
        assert '<h1>Counter-Strike 2</h1>' in bodies['slate/cs2.html'], 'CS2 category not deployed'
        assert 'Provisional estimate, not calibrated' in bodies['slate/cs2.html'], 'Model labels missing'
        assert '<h1>Flagged for review</h1>' in bodies['slate/flagged.html'], 'Flagged page missing'
        print(f'PUBLIC PAGES VERIFIED: HTTP 200 root, CS2, flags and JSON. Snapshot {actual}; expected {expected}.')
        break
    except Exception as exc:
        last_error = f'{type(exc).__name__}: {exc}'
        time.sleep(5)
else:
    raise SystemExit(f'Public Pages verification failed after 5 minutes: {last_error}')
