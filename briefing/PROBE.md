- `bo3gg.json.gz` 16092 bytes
- `hltv.json.gz` 129 bytes
- `hotspawn_fixtures.json.gz` 4739 bytes
- `pinnacle.json.gz` 778 bytes
- `polymarket.json.gz` 8455 bytes
- `valve_vrs.json.gz` 23559 bytes

## capture.json
- **bo3gg**: {"requests": [{"bytes": 238710, "error": null, "fetched_utc": "2026-10-14T04:21:40Z", "offset": 0, "sha256": "82e259ad8907ea6390c8f95f01c3763157ef0ce90acf4dfdae38796cd7a3e952", "status": 200, "url": "https://api.bo3.gg/api/v1/matches?page%5Boffset%5D=0&page%5Blimit%5D=100&sort=start_date&filter%5Bmatches.status%5D%5Bin%5D=upcoming&filter%5Bmatches.discipline_id%5D%5Beq%5D=1&with=teams%2Ctournament
- **hltv**: {"valve_ranking": {"bytes": 1582606, "error": null, "fetched_utc": "2026-10-14T04:21:46Z", "marker_found": false, "ranking_rows": 0, "sha256": "6590746a6aa20948d2e1be601ab7e200b6286e38be60b46e1268999016ae648d", "status": 200, "url": "https://www.hltv.org/valve-ranking/teams/2026/october/14"}, "world_ranking": {"bytes": 1032421, "error": null, "fetched_utc": "2026-10-14T04:21:46Z", "marker_found": 
- **hotspawn**: {"fixtures": 88, "pages": [{"bytes": 406883, "cs2_rows": 88, "error": null, "fetched_utc": "2026-10-14T04:21:36Z", "page": "cs2-pickems", "sha256": "6ef14a6a2a3fbfb37468382734dbef5f05b022822cbb61c378918e63f67c33c1", "status": 200, "url": "https://play.hotspawn.com/cs2-pickems"}, {"bytes": 408057, "cs2_rows": 88, "error": null, "fetched_utc": "2026-10-14T04:21:37Z", "page": "lobby", "sha256": "2ecd
- **pinnacle**: {"markets": {"bytes": 563611, "error": null, "fetched_utc": "2026-10-14T04:21:40Z", "sha256": "5e8f7b13f315e9294b6a28a14a8be56739ddaf4eb34d99661807eac9a75c6f49", "status": 200, "url": "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/markets/straight?primaryOnly=false&withSpecials=false"}, "matchups": {"bytes": 124629, "error": null, "fetched_utc": "2026-10-14T04:21:39Z", "sha256": "9c5aefb9ff
- **polymarket**: {"requests": [{"bytes": 4531429, "error": null, "fetched_utc": "2026-10-14T04:21:43Z", "offset": 0, "sha256": "29341c53c86123aaf24b479d01282e63c0b502a61f003db4ddeb7654eab576e3", "status": 200, "url": "https://gamma-api.polymarket.com/events?series_id=10310&closed=false&limit=100&offset=0"}, {"bytes": 4682238, "error": null, "fetched_utc": "2026-10-14T04:21:44Z", "offset": 100, "sha256": "dddeed3e1
- **valve_vrs**: {"dir": {"bytes": 46751, "error": null, "fetched_utc": "2026-10-14T04:21:45Z", "sha256": "a0c70433d2727db5d568fa6267b7000a2c15e92a4aa8820cabf07ae84338ee23", "status": 200, "url": "https://api.github.com/repos/ValveSoftware/counter-strike_regional_standings/contents/live/2026"}, "file": {"bytes": 77872, "error": null, "fetched_utc": "2026-10-14T04:21:45Z", "name": "standings_global_2026_10_05.md", 

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

## Pinnacle: 0 matchups, 9 moneylines
leagues (0): []
### sample matchup
```json
[]
```
### sample moneyline
```json
[
 {
  "american_a": -370,
  "american_b": 285,
  "event_id": 1638111674,
  "league": "CS2 - TP World Championship",
  "league_id": 230242,
  "market_url": "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/markets/straight?primaryOnly=false&withSpecials=false",
  "page_url": "https://www.pinnacle.com/en/esports/games/cs2/matchups/",
  "start_utc": "2026-10-14T11:00:00Z",
  "status": "pending",
  "team_a": "Falcons",
  "team_b": "Ninjas In Pyjamas"
 },
 {
  "american_a": -213,
  "american_b": 162,
  "event_id": 1637999450,
  "league": "CS2 - STK Pulse Beat",
  "league_id": 293370,
  "market_url": "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/markets/straight?primaryOnly=false&withSpecials=false",
  "page_url": "https://www.pinnacle.com/en/esports/games/cs2/matchups/",
  "start_utc": "2026-10-15T10:00:00Z",
  "status": "pending",
  "team_a": "HEROIC",
  "team_b": "Envy"
 },
 {
  "american_a": -165,
  "american_b": 123,
  "event_id": 1638339066,
  "league": "CS2 - CCT European Series 12 Qualifier",
  "league_id": 283309,
  "market_url": "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/markets/straight?primaryOnly=false&withSpecials=false",
  "page_url": "https://www.pinnacle.com/en/esports/games/cs2/matchups/",
  "start_utc": "2026-10-14T08:00:00Z",
  "status": "pending",
  "team_a": "ENJOY",
  "team_b": "B8 Academy"
 }
]
```

## bo3.gg: 344 upcoming CS2 matches, 0 team names
### sample matches
```json
[
 {
  "bet_updates": {
   "additional_markets": [],
   "bet_provider_id": 40,
   "markets_count": 7,
   "path": "https://thunderpick.io/match/2812130",
   "provider": "thunderpick",
   "team_1": {
    "active": true,
    "aggrement_score": 0.68,
    "coeff": 1.42,
    "max_coeff": 1.48,
    "name": "GenOne",
    "team_id": 1406
   },
   "team_2": {
    "active": true,
    "aggrement_score": 0.32,
    "coeff": 2.7,
    "max_coeff": 2.7,
    "name": "6666",
    "team_id": 24507
   }
  },
  "bo_type": 3,
  "id": 131159,
  "slug": "genone-vs-sixsixsixsix-14-10-2026",
  "start_date": "2026-10-14T08:00:00.000+00:00",
  "status": "upcoming",
  "team1": {
   "id": 1406,
   "name": "GenOne",
   "slug": "genone"
  },
  "team2": {
   "id": 24507,
   "name": "6666",
   "slug": "sixsixsixsix"
  },
  "tier": "b",
  "tournament": {
   "id": 6149,
   "name": "NODWIN Clutch Series 13",
   "slug": "nodwin-clutch-series-13",
   "tier": "b"
  }
 },
 {
  "bet_updates": null,
  "bo_type": 3,
  "id": 131841,
  "slug": "ctrl-esports-cs2-vs-sokerorg-14-10-2026",
  "start_date": "2026-10-14T08:00:00.000+00:00",
  "status": "upcoming",
  "team1": {
   "id": 22887,
   "name": "CTRL",
   "slug": "ctrl-esports-cs2"
  },
  "team2": {
   "id": 25400,
   "name": "S\u00f6kerorg",
   "slug": "sokerorg"
  },
  "tier": "c",
  "tournament": {
   "id": 6170,
   "name": "European Pro League Regular Season 7",
   "slug": "european-pro-league-regular-season-7",
   "tier": "c"
  }
 }
]
```

with bet_updates: 40
```json
{
 "additional_markets": [],
 "bet_provider_id": 40,
 "markets_count": 7,
 "path": "https://thunderpick.io/match/2812130",
 "provider": "thunderpick",
 "team_1": {
  "active": true,
  "aggrement_score": 0.68,
  "coeff": 1.42,
  "max_coeff": 1.48,
  "name": "GenOne",
  "team_id": 1406
 },
 "team_2": {
  "active": true,
  "aggrement_score": 0.32,
  "coeff": 2.7,
  "max_coeff": 2.7,
  "name": "6666",
  "team_id": 24507
 }
}
```
bo_type distribution: {3: 286, 1: 56, 5: 2}

## Polymarket: 94 open CS2 series events
```json
[
 {
  "active": true,
  "closed": false,
  "endDate": "2026-11-11T23:00:00Z",
  "eventMetadata": {
   "league": "DACH CS Masters",
   "leagueTier": "5",
   "pandascoreMatchId": 1661619,
   "serie": null,
   "tournament": "Regular Season"
  },
  "id": "1133922",
  "markets": [
   {
    "active": true,
    "bestAsk": 0.99,
    "bestBid": 0.01,
    "closed": false,
    "id": "5308156",
    "liquidity": "2.1145",
    "outcomePrices": "[\"0.5\", \"0.5\"]",
    "outcomes": "[\"Sissi State Punks\", \"Team LEISURE\"]",
    "question": "Counter-Strike: Sissi State Punks vs Team LEISURE (BO3) - DACH CS Masters Regular Season",
    "sportsMarketType": "moneyline",
    "spread": 0.98,
    "volume": "54.2838"
   }
  ],
  "slug": "cs2-ssp1-lei-2026-10-05",
  "startTime": "2026-11-11T17:00:00Z",
  "title": "Counter-Strike: Sissi State Punks vs Team LEISURE (BO3) - DACH CS Masters Regular Season"
 }
]
```
titles: ["Counter-Strike: Sissi State Punks vs Team LEISURE (BO3) - DACH CS Masters Regular Season", "Counter-Strike: Astralis vs Sashi Esport (BO3) - Stake Pulse Beat III Group C", "Counter-Strike: HOTU vs fnatic (BO3) - Stake Pulse Beat III Group C", "Counter-Strike: MIBR vs BC.Game Esports (BO3) - Stake Pulse Beat III Group D", "Counter-Strike: Heroic vs Envy (BO3) - Stake Pulse Beat III Group D", "Counter-Strike:  Phantom Academy vs ZOTIX (BO1) - ESEA Advanced Europe Regular Season", "Counter-Strike: aimers vs Banger Gang (BO1) - ESEA Advanced Europe Regular Season", "Counter-Strike: BLUEJAYS.de vs Reveal (BO3) - DACH CS Masters Regular Season", "Counter-Strike: 9z vs Aurora Gaming (BO3) - Thunderpick World Championship Group A", "Counter-Strike: Team Falcons vs NIP (BO3) - Thunderpick World Championship Group A", "Counter-Strike: Legacy vs PARIVISION (BO3) - Thunderpick World Championship Group B", "Counter-Strike: FURIA vs BetBoom Team (BO3) - Thunderpick World Championship Group B", "Counter-Strike: WBT vs Esport Academy Copenhagen (BO1) - Elisa BreakOut Series #2 Group A", "Counter-Strike: ENCE vs BOJONG (BO1) - Elisa BreakOut Series #2 Group A", "Counter-Strike: WBT vs ENCE (BO1) - Elisa BreakOut Series #2 Group A", "Counter-Strike: Esport Academy Copenhagen vs BOJONG (BO1) - Elisa BreakOut Series #2 Group A", "Counter-Strike: WBT vs BOJONG (BO1) - Elisa BreakOut Series #2 Group A", "Counter-Strike: Esport Academy Copenhagen vs ENCE (BO1) - Elisa BreakOut Series #2 Group A", "Counter-Strike: Voca vs Phantom (BO1) - Elisa BreakOut Series #2 Group B", "Counter-Strike: HAVU vs RoundsGG (BO1) - Elisa BreakOut Series #2 Group B", "Counter-Strike: Voca vs HAVU (BO1) - Elisa BreakOut Series #2 Group B", "Counter-Strike: Phantom vs RoundsGG (BO1) - Elisa BreakOut Series #2 Group B", "Counter-Strike: Voca vs RoundsGG (BO1) - Elisa BreakOut Series #2 Group B", "Counter-Strike: Phantom vs HAVU (BO1) - Elisa BreakOut Series #2 Group B", "Counter-Strike: BIG vs PRIVATE (BO3) - 1win Private Club #2 Playoffs", "Counter-Strike: Alliance vs TheMongolz (BO3) - 1win Private Club #2 Playoffs", "Counter-Strike: fnatic vs Liquid (BO3) - 1win Private Club #2 Playoffs", "Counter-Strike: PARIVISION vs magic (BO3) - 1win Private Club #2 Playoffs", "Counter-Strike: EAC Extra vs Bread Eaters Esports (BO3) - European Pro League Regular Playoffs", "Counter-Strike: Gothic vs Lavked (BO3) - CCT Europe Series #11 Group Stage", "Counter-Strike: ex-RUSTEC vs mellren (BO3) - CCT Europe Series #11 Group Stage", "Counter-Strike: Blitzkrieg vs realgotis22 (BO3) - CCT South America Series 7 Group Stage", "Counter-Strike: G2 Ares vs The Last Resort (BO3) - CCT Europe Series #11 Group Stage", "Counter-Strike: ARK E-sports vs RED Canids Academy (BO3) - CCT South America Series 7 Group Stage", "Counter-Strike: FORZE Reload vs S\u00f6kerorg (BO3) - CCT Europe Series #11 Group Stage", "Counter-Strike: Damajuana vs Alianza Lima Esports (BO3) - CCT South America Series 7 Group Stage", "Counter-Strike: Joga de terno vs A NATA (BO3) - CCT South America Series 7 Group Stage", "Counter-Strike: GenOne vs 6666 (BO3) - NODWIN Clutch Series Group Stage", "Counter-Strike: Bushido Wildcats vs BakS eSports (BO3) - NODWIN Clutch Series Group Stage", "Counter-Strike: BET-M 33 vs FORZE Reload (BO3) - NODWIN Clutch Series Group Stage"]

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

## HLTV: {"valve_ranking": {"rows": [], "url": "https://www.hltv.org/valve-ranking/teams/2026/october/14"}, "world_ranking": {"rows": [], "url": "https://www.hltv.org/ranking/teams/2026/october/12"}}