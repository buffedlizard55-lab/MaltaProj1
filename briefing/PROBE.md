- `bo3gg.json.gz` 58 bytes
- `hltv.json.gz` 81 bytes
- `hltv_valve_ranking.json.gz` 237715 bytes
- `hltv_world_ranking.json.gz` 158983 bytes
- `hotspawn_fixtures.json.gz` 4738 bytes
- `pinnacle.json.gz` 1270 bytes
- `polymarket.json.gz` 3930 bytes
- `valve_vrs.json.gz` 23465 bytes

## capture.json
- **bo3gg**: {"pages": [{"bytes": 23014, "error": null, "fetched_utc": "2026-10-14T04:03:33Z", "page": 1, "rows": 0, "sha256": "90851b9096a3c9c8173145c7aa5b76f8ef077e781dc90706d4c22d4e5a268949", "status": 200, "url": "https://api.bo3.gg/api/v1/matches?filter[matches.status][in]=upcoming&filter[matches.discipline_id][eq]=1&with=teams,tournament&page[number]=1&page[size]=100"}]}
- **hltv**: {"valve_ranking": {"bytes": 1583165, "error": null, "fetched_utc": "2026-10-14T04:03:35Z", "sha256": "548a101e9c79ba4150bb3a9b27276919067d877f45c4e4e2578f415a89dc7b61", "status": 200, "url": "https://www.hltv.org/valve-ranking/teams/"}, "world_ranking": {"bytes": 1033661, "error": null, "fetched_utc": "2026-10-14T04:03:34Z", "sha256": "2f53c908c40b79b15033d902a1543570f466ac439aaa67f2010397812a82e9
- **hotspawn**: {"fixtures": 88, "pages": [{"bytes": 406883, "cs2_rows": 88, "error": null, "fetched_utc": "2026-10-14T04:03:31Z", "page": "cs2-pickems", "sha256": "6ef14a6a2a3fbfb37468382734dbef5f05b022822cbb61c378918e63f67c33c1", "status": 200, "url": "https://play.hotspawn.com/cs2-pickems"}, {"bytes": 408057, "cs2_rows": 88, "error": null, "fetched_utc": "2026-10-14T04:03:32Z", "page": "lobby", "sha256": "2ecd
- **pinnacle**: {"markets": {"bytes": 560677, "error": null, "fetched_utc": "2026-10-14T04:03:33Z", "sha256": "3c35df69e1211cf023818e1995f14e348792d424f57dfe001697f74b97ebb370", "status": 200, "url": "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/markets/straight?primaryOnly=false&withSpecials=false"}, "matchups": {"bytes": 121746, "error": null, "fetched_utc": "2026-10-14T04:03:33Z", "sha256": "0595594ebd
- **polymarket**: {"bytes": 4538378, "error": null, "fetched_utc": "2026-10-14T04:03:34Z", "sha256": "c5601e1690fcc33ad7280a1dd03fb99114514fbfae50ea4359d1e2bfdbf9cef7", "status": 200, "url": "https://gamma-api.polymarket.com/events?series_id=10310&closed=false&limit=500&order=startTime"}
- **valve_vrs**: {"dir": {"bytes": 46751, "error": null, "fetched_utc": "2026-10-14T04:03:34Z", "sha256": "a0c70433d2727db5d568fa6267b7000a2c15e92a4aa8820cabf07ae84338ee23", "status": 200, "url": "https://api.github.com/repos/ValveSoftware/counter-strike_regional_standings/contents/live/2026"}, "file": {"bytes": 77872, "error": null, "fetched_utc": "2026-10-14T04:03:34Z", "name": "standings_global_2026_10_05.md", 

## Hotspawn: 88 CS2 fixtures
```json
[
 {
  "base_points": 2,
  "best_of": null,
  "competition_id": "35005",
  "competition_name": "European Pro League Series 8 Play-In",
  "id": "1052746",
  "lock_epoch_ms": "1782469440000",
  "lock_utc": "2026-06-26T10:24:00Z",
  "offered_points": 2,
  "participants0_id": "251690",
  "participants0_name": "Fortress",
  "participants1_id": "239669",
  "participants1_name": "Endless Journey",
  "permalink": "",
  "series_format": null,
  "source_page": "cs2-pickems",
  "sport_alias": "cs2",
  "sport_name": "Counter-Strike 2",
  "stage": "waiting for information",
  "start_epoch_ms": "1782469800000",
  "start_utc": "2026-06-26T10:30:00Z",
  "status": "scheduled",
  "tier": "c"
 },
 {
  "base_points": 2,
  "best_of": null,
  "competition_id": "35437",
  "competition_name": "DraculaN Season 7",
  "id": "1051339",
  "lock_epoch_ms": "1782474840000",
  "lock_utc": "2026-06-26T11:54:00Z",
  "offered_points": 3,
  "participants0_id": "239293",
  "participants0_name": "Acend",
  "participants1_id": "33036",
  "participants1_name": "Infinite",
  "permalink": "",
  "series_format": null,
  "source_page": "cs2-pickems",
  "sport_alias": "cs2",
  "sport_name": "Counter-Strike 2",
  "stage": "waiting for information",
  "start_epoch_ms": "1782475200000",
  "start_utc": "2026-06-26T12:00:00Z",
  "status": "scheduled",
  "tier": "b"
 },
 {
  "base_points": 2,
  "best_of": null,
  "competition_id": "35440",
  "competition_name": "LG UltraGear Tournament 2026",
  "id": "1051301",
  "lock_epoch_ms": "1782478440000",
  "lock_utc": "2026-06-26T12:54:00Z",
  "offered_points": 2,
  "participants0_id": "242573",
  "participants0_name": "CYBERSHOKE Prospects",
  "participants1_id": "196200",
  "participants1_name": "PCIFIC",
  "permalink": "",
  "series_format": null,
  "source_page": "cs2-pickems",
  "sport_alias": "cs2",
  "sport_name": "Counter-Strike 2",
  "stage": null,
  "start_epoch_ms": "1782478800000",
  "start_utc": "2026-06-26T13:00:00Z",
  "status": "scheduled",
  "tier": "c"
 }
]
```

## Pinnacle: 42 matchups, 0 moneylines
leagues (12): ['CS2 - European Pro League', 'CS2 - STK Pulse Beat', 'CS2 - TP World Championship', 'Dota 2 - DreamLeague: Eastern Europe Qualifier', 'Dota 2 - DreamLeague: Western Europe Qualifier', 'Dota 2 - EPL Masters Play-In', 'League of Legends - Demacia Cup', 'League of Legends - EMEA Masters', 'League of Legends - World Championship Play-In', 'Rainbow Six - Challenger League', 'Rainbow Six - North America League', 'Valorant - Champions']
### sample matchup
```json
[
 {
  "id": 1638241049,
  "league": "League of Legends - World Championship Play-In",
  "participants": [
   {
    "alignment": "home",
    "name": "Karmine Corp"
   },
   {
    "alignment": "away",
    "name": "Cloud9"
   }
  ],
  "startTime": "2026-10-15T23:00:00Z",
  "status": "pending",
  "type": "matchup"
 },
 {
  "id": 1638192361,
  "league": "League of Legends - EMEA Masters",
  "participants": [
   {
    "alignment": "home",
    "name": "Solary (Kills)"
   },
   {
    "alignment": "away",
    "name": "Anubis (Kills)"
   }
  ],
  "startTime": "2026-10-14T16:00:00Z",
  "status": "pending",
  "type": "matchup"
 }
]
```
### sample moneyline
```json
[]
```

matchup keys: ['id', 'league', 'participants', 'startTime', 'status', 'type']

## bo3.gg: 0 upcoming CS2 matches, 0 team names
### sample matches
```json
[]
```

with bet_updates: 0
bo_type distribution: {}

## Polymarket: 100 open CS2 series events
```json
[
 {
  "gameStartTime": null,
  "id": "257425",
  "league": "United21",
  "markets": [],
  "pandascoreMatchId": 1392349,
  "slug": "cs2-aaa-inf1-2026-03-10",
  "startDate": "2026-03-09T21:21:45.809096Z",
  "title": "Counter-Strike: against All authority vs INFURITY Gaming (BO3) - United21 Group A"
 }
]
```
titles: ["Counter-Strike: against All authority vs INFURITY Gaming (BO3) - United21 Group A", "Counter-Strike: STATE vs B8 Academy (BO3) - United21 Playoffs", "Counter-Strike: Chicken Coop Esports vs SportsBetExpert (BO3) - PGL Astana: North American Open Qualifier #1 Playoffs", "Counter-Strike: BOSS vs Foxtrot Esports (BO3) - PGL Astana: North American Open Qualifier #1 Playoffs", "Counter-Strike: No Surrender vs OlyBet SB (BO3) - Urban Riga Open #3 Playoffs", "Counter-Strike: ENJOY vs LFO (BO3) - CCT Europe Contenders #4 Playoffs", "Counter-Strike: mixmix vs CYBERSHOKE Prospects (BO3) - CCT Europe Contenders #4 Playoffs", "Counter-Strike: Coalesce vs Eternal Fire Academy (BO3) - Exort Series Contenders Stage", "Counter-Strike: Young Ninjas vs Fire Flux Esports (BO3) - United21 Playoffs", "Counter-Strike: 3DMAX Academy vs Hermine Esports Club (BO3) - Exort Series Contenders Stage", "Counter-Strike: PLATOON vs Z7 Esports (BO3) - Exort Series Contenders Stage", "Counter-Strike: VP.Future vs KUUSAMO.gg (BO3) - Exort Series Contenders Stage", "Counter-Strike: NeverPlay vs Wave Esports (BO3) - Exort Series Contenders Stage", "Counter-Strike: Eternal Fire Academy vs CSGOPOSITIVE (BO3) - Exort Series Contenders Stage", "Counter-Strike: eternal premium vs Wingman (BO3) - Exort Series Contenders Stage", "Counter-Strike: BESTIA Academy vs Vexa (BO3) - CCT South America Challengers #1 Playoffs", "Counter-Strike: eternal premium vs KUUSAMO.gg (BO3) - Exort Series Contenders Stage", "Counter-Strike: 3DMAX Academy vs Wave Esports (BO3) - Exort Series Contenders Stage", "Counter-Strike: VP.Future vs Z7 Esports (BO3) - Exort Series Contenders Stage", "Counter-Strike: VP.Future vs Eternal Fire Academy (BO3) - Exort Series Contenders Stage", "Counter-Strike: 3DMAX Academy vs Wingman (BO3) - Exort Series Contenders Stage", "Counter-Strike: Vasco Esports vs Crashers (BO3) - CCT South America Challengers #1 Playoffs", "Counter-Strike: Partizan Esport vs INFURITY Gaming (BO3) - Exort Series Main Stage", "Counter-Strike: Ctrl Alt Defeat vs CSGOPOSITIVE (BO3) - Exort Series Main Stage", "Counter-Strike:  Phantom Academy vs Hermine Esports Club (BO3) - Exort Series Main Stage", "Counter-Strike: LPH Gaming vs Eternal Fire Academy (BO3) - Exort Series Main Stage", "Counter-Strike: aimclub vs Wingman (BO3) - Exort Series Main Stage", "Counter-Strike: Spirit Academy vs Wave Esports (BO3) - Exort Series Main Stage", "Counter-Strike: Alzon vs FURIA fe (BO1) - Gamers Club Liga S\u00e9rie A Group B", "Counter-Strike: HAVENs vs Nebula In Chaox (BO3) - Exort Series Main Stage", "Counter-Strike: paiN Academy vs Vexa (BO3) - CCT South America Challengers #1 Playoffs", "Counter-Strike: R2 Esports Club vs ALKA (BO3) - CCT South America Challengers #1 Playoffs", "Counter-Strike: AaB Esport vs BIG Academy (BO3) - European Pro League Regular Group A", "Counter-Strike: XI Esport vs Sangal ALTERS (BO3) - European Pro League Regular Group A", "Counter-Strike: aimclub vs Drama eSports (BO3) - Exort Series Main Stage", "Counter-Strike: Eternal Fire Academy vs CSGOPOSITIVE (BO3) - Exort Series Main Stage", "Counter-Strike:  Phantom Academy vs Spirit Academy (BO3) - Exort Series Main Stage", "Counter-Strike: INFURITY Gaming vs Hermine Esports Club (BO3) - Exort Series Main Stage", "Counter-Strike: BOJONG vs MASQ (BO3) - European Pro League Regular Group B", "Counter-Strike: HAVENs vs Ctrl Alt Defeat (BO3) - Exort Series Main Stage"]

## Valve VRS: file=standings_global_2026_10_05.md as_of=2026_10_05 rows=380
```json
[
 {
  "details": "details/2026_10_05/0001--spirit--donk-magixx-sh1ro-tn1r-zont1x.md",
  "points": 2046,
  "rank": 1,
  "roster": "donk, magixx, sh1ro, tN1R, zont1x",
  "team": "Spirit"
 },
 {
  "details": "details/2026_10_05/0002--legacy--art-dumau-latto-n1ssim-try.md",
  "points": 1931,
  "rank": 2,
  "roster": "arT, dumau, latto, n1ssim, try",
  "team": "Legacy"
 },
 {
  "details": "details/2026_10_05/0003--vitality--apex-flamez-mezii-ropz-zywoo.md",
  "points": 1911,
  "rank": 3,
  "roster": "apEX, flameZ, mezii, ropz, ZywOo",
  "team": "Vitality"
 }
]
```

## HLTV: {"valve_ranking": {"chars": 1582315}, "world_ranking": {"chars": 1033125}}
- `world_ranking`: 1033125 chars
```
<!DOCTYPE html>
<html lang="en" data-client-country-iso="US-VA" data-impression-tracking-endpoint="https://ncuxt.hltv.org" data-ad-tag-allowed-cookies="mobile-bottom-ad,desktop-bottom-ad" data-bc-content-allowed="true"><!--
        --Worker debug info-- 
        Ads API URL from origin: https://www.hltv.org/api/ads/rendered/[%7B%22key%22:%7B%22id%22:%22page%22%7D,%22value%22:%7B%22id%22:%22Unspecified%22%7D%7D]
        Modified Ads API URL: https://www.hltv.org/api/ads/rendered/%5B%7B%22key%22%3A%7B%22id%22%3A%22page%22%7D%2C%22value%22%3A%7B%22id%22%3A%22Unspecified%22%7D%7D%2C%7B%22key%22%3A%7B%22id%22%3A%22device%22%7D%2C%22value%22%3A%7B%22id%22%3A%22desktop%22%7D%7D%5D
        ISO Code: US-VA
        Device-type: desktop
    --><!--Active rewriter version: 2--><head><script>
window.dataLayer = window.dataLayer || []; function gtag(){dataLayer.push(arguments);}
gtag('set', 'developer_id.dNzMyY2', true);
gtag('consent', 'default', {
  'ad_storage': 'denied',
  'ad_user_data': 'denied',
  'ad_personalization': 'denied',
  'analytics_storage': 'denied'
});
gtag('js', new Date());
</script>
<!-- OneTrust Cookies Consent Notice start for hltv.org -->
<script src="https://cdn.cookielaw.org/scripttemplates/otSDKStub.js"  type="text/javascript" charset="UTF-8" data-domain-script="019a2ef9-ba74-7104-bc58-22ee3980a258" ></script>
<script type="text/javascript">
function OptanonWrapper() { }
</script>
<!-- OneTrust Cookies Consent Notice end for hltv.org --><meta charset="utf-8"><
```
  `ranking-team` occurrences: 0
  points matches: 0 -> []
- `valve_ranking`: 1582315 chars
```
<!DOCTYPE html>
<html lang="en" data-client-country-iso="US-VA" data-impression-tracking-endpoint="https://ncuxt.hltv.org" data-ad-tag-allowed-cookies="mobile-bottom-ad,desktop-bottom-ad" data-bc-content-allowed="true"><!--
        --Worker debug info-- 
        Ads API URL from origin: https://www.hltv.org/api/ads/rendered/[%7B%22key%22:%7B%22id%22:%22page%22%7D,%22value%22:%7B%22id%22:%22Unspecified%22%7D%7D]
        Modified Ads API URL: https://www.hltv.org/api/ads/rendered/%5B%7B%22key%22%3A%7B%22id%22%3A%22page%22%7D%2C%22value%22%3A%7B%22id%22%3A%22Unspecified%22%7D%7D%2C%7B%22key%22%3A%7B%22id%22%3A%22device%22%7D%2C%22value%22%3A%7B%22id%22%3A%22desktop%22%7D%7D%5D
        ISO Code: US-VA
        Device-type: desktop
    --><!--Active rewriter version: 2--><head><script>
window.dataLayer = window.dataLayer || []; function gtag(){dataLayer.push(arguments);}
gtag('set', 'developer_id.dNzMyY2', true);
gtag('consent', 'default', {
  'ad_storage': 'denied',
  'ad_user_data': 'denied',
  'ad_personalization': 'denied',
  'analytics_storage': 'denied'
});
gtag('js', new Date());
</script>
<!-- OneTrust Cookies Consent Notice start for hltv.org -->
<script src="https://cdn.cookielaw.org/scripttemplates/otSDKStub.js"  type="text/javascript" charset="UTF-8" data-domain-script="019a2ef9-ba74-7104-bc58-22ee3980a258" ></script>
<script type="text/javascript">
function OptanonWrapper() { }
</script>
<!-- OneTrust Cookies Consent Notice end for hltv.org --><meta charset="utf-8"><
```
  `ranking-team` occurrences: 0
  points matches: 0 -> []