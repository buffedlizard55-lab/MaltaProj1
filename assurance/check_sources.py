#!/usr/bin/env python3
"""Source HTTP checks ONLY. No price extraction or inferred verification.
Public GETs with timeouts and size caps; no auth/captcha bypass. Run on Actions
because this agent's shell egress excludes source hosts. Output stays isolated.
"""
import concurrent.futures
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
import sys
import re
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
ALLOWED = {'play.hotspawn.com', 'www.hotspawn.com', 'polymarket.com', 'www.bwin.com', 'www.hltv.org'}


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


class RestrictedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlparse(newurl).hostname not in ALLOWED or urlparse(newurl).scheme != 'https':
            raise urllib.error.URLError('Redirect left the explicitly permitted source hosts')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def check(url):
    result = {'url': url, 'checked_at': now(), 'http_status': None, 'final_url': None,
              'title': None, 'body_sha256': None, 'byte_count': None,
              'truncated': None, 'error': None, 'status': 'unverified',
              'numerical_verification': False,
              'warning': 'HTTP accessibility is not fixture, market or numerical verification.'}
    if urlparse(url).hostname not in ALLOWED or urlparse(url).scheme != 'https':
        result['error'] = 'Host is outside explicit audit scope'
        return result
    opener = urllib.request.build_opener(RestrictedRedirect())
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'MaltaProj1-evidence-audit/1.0 (public-source accessibility; no trading)', 'Accept': 'text/html,application/json'})
        with opener.open(request, timeout=20) as response:
            body = response.read(1_000_001)
            result.update(http_status=response.status, final_url=response.url,
                          byte_count=len(body), body_sha256=hashlib.sha256(body).hexdigest(),
                          truncated=len(body) > 1_000_000)
            text = body.decode('utf-8', errors='replace')
            title = re.search(r'<title[^>]*>(.*?)</title>', text, re.I | re.S)
            result['title'] = re.sub(r'\s+', ' ', title.group(1)).strip()[:300] if title else None
            blocked = any(s in text[:100_000].casefold() for s in ('just a moment...', 'verify you are human', 'cf-chl-', 'access denied'))
            result['status'] = 'challenge or block' if blocked else 'reachable; content unverified'
    except urllib.error.HTTPError as exc:
        result.update(http_status=exc.code, error=str(exc), status='HTTP failure; unverified')
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        result.update(error=str(exc)[:500], status='request failed; unverified')
    return result


def run():
    data = json.loads((HERE / 'observations.json').read_text())
    urls = {data['facet_source'], 'https://play.hotspawn.com/lobby', data['bwin_check']['url']}
    # Target every inspected primary market; no scraping across arbitrary links.
    urls.update(row['market_url'] for row in data['fixtures'])
    urls.update(row['observed_page'] for row in data['fixtures'])
    started = now()
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(check, sorted(urls)))
    report = {'schema_version': 1, 'started_at': started, 'completed_at': now(),
              'purpose': 'HTTP accessibility only; never numerical source verification',
              'observation_timestamp_unchanged': data['checked_at'],
              'checked_urls': len(rows), 'rows': rows}
    (HERE / 'source_checks.json').write_text(json.dumps(report, indent=2)+'\n')
    print(f"Checked {len(rows)} primary URLs; {sum(row['http_status'] == 200 for row in rows)} HTTP 200 responses. No numbers promoted to verified.")
    return report


def publish_check(report):
    """Expose the report on GitHub's API without committing to anyone's branch."""
    token = os.environ.get('GITHUB_TOKEN')
    repo = os.environ.get('GITHUB_REPOSITORY')
    sha = os.environ.get('GITHUB_SHA')
    if not all((token, repo, sha)):
        raise RuntimeError('GitHub Actions context is required to publish a check report')
    # GitHub sanitizes Unicode escape sequences in Markdown check output.
    # An ASCII base64 payload preserves exact machine-readable report bytes.
    text = base64.b64encode(json.dumps(report, ensure_ascii=False).encode('utf-8')).decode('ascii')
    payload = {
        'name': 'Primary source accessibility — evidence audit', 'head_sha': sha,
        'status': 'completed', 'conclusion': 'neutral',
        'output': {
            'title': f"{report['checked_urls']} HTTP source checks; numerical verification NOT performed",
            'summary': 'Accessibility results only. A reachable page never verifies an odds value. Snapshot timestamps are not refreshed.',
            'text': 'Exact report bytes, UTF-8 JSON encoded as base64:\n\n```text\n' + text + '\n```',
        },
    }
    request = urllib.request.Request(
        'https://api.github.com/repos/' + repo + '/check-runs',
        data=json.dumps(payload).encode(), method='POST',
        headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json',
                 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        check_run = json.load(response)
        print('Published accessibility report:', check_run['html_url'])


if __name__ == '__main__':
    report = run()
    if '--publish-check' in sys.argv:
        publish_check(report)
