# Endpoint probe (temporary file, deleted before the pull request)

```
=== PINNACLE ===
sport matchups (key+origin): 200 bytes=400 head=b'[\n  {\n    "ageLimit": 0,\n    "altTeaser": false,\n    "bestOfX": 3,\n    "featureOrder": -1,\n    "hasAltSpread": true,\n   '
sport matchups (key only): 200 bytes=400 head=b'[\n  {\n    "ageLimit": 0,\n    "altTeaser": false,\n    "bestOfX": 3,\n    "featureOrder": -1,\n    "hasAltSpread": true,\n   '
sport matchups (no key): 200 bytes=400 head=b'[\n  {\n    "ageLimit": 0,\n    "altTeaser": false,\n    "bestOfX": 3,\n    "featureOrder": -1,\n    "hasAltSpread": true,\n   '
sport matchups (browser UA): 200 bytes=400 head=b'[\n  {\n    "ageLimit": 0,\n    "altTeaser": false,\n    "bestOfX": 3,\n    "featureOrder": -1,\n    "hasAltSpread": true,\n   '
sport straight markets: 200 bytes=400 head=b'[\n  {\n    "cutoffAt": "2026-10-14T16:00:00+00:00",\n    "isAlternate": false,\n    "key": "s;1;m",\n    "limits": [\n      {'
leagues: 200 bytes=400 head=b'[\n  {\n    "ageLimit": 0,\n    "featureOrder": 0,\n    "group": "World",\n    "id": 212178,\n    "isFeatured": true,\n    "isH'
league 230488 matchups plain: 200 bytes=400 head=b'[\n  {\n    "ageLimit": 0,\n    "altTeaser": false,\n    "featureOrder": -1,\n    "hasAltSpread": false,\n    "hasAltTotal": f'
league 230488 matchups query: HTTPError 403 body=b'{\n  "detail": "Access from United States is prohibited",\n  "reason": "location",\n  "status": 403,\n  "title": "BAD_LOCATION",\n  "type": "about:blank"\n}\n'
league 293370 matchups plain: 200 bytes=400 head=b'[\n  {\n    "ageLimit": 0,\n    "altTeaser": false,\n    "featureOrder": -1,\n    "hasAltSpread": false,\n    "hasAltTotal": f'
league 293370 matchups query: HTTPError 403 body=b'{\n  "detail": "Access from United States is prohibited",\n  "reason": "location",\n  "status": 403,\n  "title": "BAD_LOCATION",\n  "type": "about:blank"\n}\n'
league 230242 matchups plain: 200 bytes=400 head=b'[\n  {\n    "ageLimit": 0,\n    "altTeaser": false,\n    "featureOrder": -1,\n    "hasAltSpread": false,\n    "hasAltTotal": f'
league 230242 matchups query: HTTPError 403 body=b'{\n  "detail": "Access from United States is prohibited",\n  "reason": "location",\n  "status": 403,\n  "title": "BAD_LOCATION",\n  "type": "about:blank"\n}\n'
=== HLTV ===
honest /matches: HTTPError 403 body=b'<!DOCTYPE html><html lang="en-US"><head><title>Just a moment...</title><meta http-equiv="Content-Type" content="text/html; charset=UTF-8"><meta http-equiv="X-UA'
browser /matches: HTTPError 403 body=b'<!DOCTYPE html><html lang="en-US"><head><title>Just a moment...</title><meta http-equiv="Content-Type" content="text/html; charset=UTF-8"><meta http-equiv="X-UA'
honest /matches?offset=0: HTTPError 403 body=b'<!DOCTYPE html><html lang="en-US"><head><title>Just a moment...</title><meta http-equiv="Content-Type" content="text/html; charset=UTF-8"><meta http-equiv="X-UA'
browser /matches?offset=0: HTTPError 403 body=b'<!DOCTYPE html><html lang="en-US"><head><title>Just a moment...</title><meta http-equiv="Content-Type" content="text/html; charset=UTF-8"><meta http-equiv="X-UA'
honest /events/matches: HTTPError 403 body=b'<!DOCTYPE html><html lang="en-US"><head><title>Just a moment...</title><meta http-equiv="Content-Type" content="text/html; charset=UTF-8"><meta http-equiv="X-UA'
browser /events/matches: HTTPError 403 body=b'<!DOCTYPE html><html lang="en-US"><head><title>Just a moment...</title><meta http-equiv="Content-Type" content="text/html; charset=UTF-8"><meta http-equiv="X-UA'
honest /results?offset=0: 200 bytes=400 head=b'<!DOCTYPE html>\n<html lang="en" data-client-country-iso="US-AZ" data-impression-tracking-endpoint="https://ncuxt.hltv.or'
browser /results?offset=0: HTTPError 403 body=b'<!DOCTYPE html><html lang="en-US"><head><title>Just a moment...</title><meta http-equiv="Content-Type" content="text/html; charset=UTF-8"><meta http-equiv="X-UA'
team page (browser UA): HTTPError 403 body=b'<!DOCTYPE html><html lang="en-US"><head><title>Just a moment...</title><meta http-equiv="Content-Type" content="text/html; charset=UTF-8"><meta http-equiv="X-UA'
team page (honest UA): 200 bytes=400 head=b'<!DOCTYPE html>\n<html lang="en" data-client-country-iso="US-AZ" data-impression-tracking-endpoint="https://ncuxt.hltv.or'
=== EGAMERSWORLD ===
egw browser UA: HTTPError 403 body=b'<!DOCTYPE html>\n<!--[if lt IE 7]> <html class="no-js ie6 oldie" lang="en-US"> <![endif]-->\n<!--[if IE 7]>    <html class="no-js ie7 oldie" lang="en-US"> <![endi'
egw honest UA: HTTPError 403 body=b'<!DOCTYPE html><html lang="en-US"><head><title>Just a moment...</title><meta http-equiv="Content-Type" content="text/html; charset=UTF-8"><meta http-equiv="X-UA'
```
