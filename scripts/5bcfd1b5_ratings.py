#!/usr/bin/env python3
"""arena/5bcfd1b5 — official-rating resolution for every Hotspawn CS2 fixture.

Purpose
-------
Main's boards leave 25 of 89 CS2 fixtures without a pick because a team could not be
found in the **2026-10-05** Valve Regional Standings file.  Most of those fixtures were
played in June/July 2026, so the October file is the wrong official source for them.

This module resolves every team against the official Valve Regional Standings period
that was actually in force at the match date, then walks a documented fallback cascade.
It never invents a rating: a team that cannot be resolved from an official source keeps
an empty candidate set, and the caller must leave the probability blank and flag it.

Inputs (read-only)
------------------
data/5bcfd1b5/vrs/standings_global_2026_{06_01,07_06,08_03,09_07,10_05}.md.gz
    Valve's own published standings, downloaded from
    https://github.com/ValveSoftware/counter-strike_regional_standings
    (pinned commit recorded in data/5bcfd1b5/coverage.json).

Nothing here reads Hotspawn crowd percentages.  They are never a probability input.
"""

from __future__ import annotations

import datetime as _dt
import gzip
import os
import re
import unicodedata

VRS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "data", "5bcfd1b5", "vrs")

VALVE_REPO = "ValveSoftware/counter-strike_regional_standings"
VALVE_COMMIT = "eec4853d7bcf0f1f7efe7f0d901234bef7e98b75"  # HEAD of live/2026 at capture time
VALVE_BLOB = ("https://github.com/%s/blob/%s/live/2026/%%s?plain=1#L%%d"
              % (VALVE_REPO, VALVE_COMMIT))


def norm(name: str) -> str:
    """Fold a team name for comparison: strip accents, case, punctuation and spaces."""
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def _parse(path: str) -> list[dict]:
    rows: list[dict] = []
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            if not line.startswith("|"):
                continue
            parts = [p.strip() for p in line.strip().strip("|").split("|")]
            if len(parts) < 4:
                continue
            standing = re.fullmatch(r"(\d+)", parts[0])
            if not standing:
                continue
            points = re.sub(r"[^0-9]", "", parts[1])
            if not points:
                continue
            details = ""
            dm = re.search(r"\((details/[^)]+)\)", line)
            if dm:
                details = dm.group(1)
            rows.append({
                "standing": int(standing.group(1)),
                "points": int(points),
                "team": parts[2],
                "roster": parts[3],
                "details": details,
                "line": lineno,
                "file": os.path.basename(path).replace(".gz", ""),
            })
    return rows


class Standings:
    """Official Valve Regional Standings, indexed by publication period."""

    def __init__(self, directory: str = VRS_DIR) -> None:
        self.periods: dict[_dt.date, list[dict]] = {}
        self.index: dict[_dt.date, dict[str, list[dict]]] = {}
        for fname in sorted(os.listdir(directory)):
            m = re.match(r"standings_global_(\d{4})_(\d{2})_(\d{2})\.md(?:\.gz)?$", fname)
            if not m:
                continue
            as_of = _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            rows = _parse(os.path.join(directory, fname))
            self.periods[as_of] = rows
            bucket: dict[str, list[dict]] = {}
            for r in rows:
                bucket.setdefault(norm(r["team"]), []).append(r)
            self.index[as_of] = bucket
        if not self.periods:
            raise SystemExit("no Valve standings found in %s" % directory)
        self.ordered = sorted(self.periods)

    # -- period selection -------------------------------------------------
    def period_in_force(self, when: _dt.datetime) -> _dt.date | None:
        """Latest official publication on or before the match date."""
        best = None
        for p in self.ordered:
            if p <= when.date():
                best = p
        return best

    def source_url(self, row: dict) -> str:
        name = row["file"] if row["file"].endswith(".md") else row["file"] + ".md"
        return VALVE_BLOB % (name, row["line"])

    def details_url(self, row: dict) -> str:
        if not row.get("details"):
            return ""
        return ("https://github.com/%s/blob/%s/live/2026/%s"
                % (VALVE_REPO, VALVE_COMMIT, row["details"]))

    # -- lookups ----------------------------------------------------------
    def exact(self, period: _dt.date, team: str) -> list[dict]:
        return list(self.index.get(period, {}).get(norm(team), []))

    def first_period_containing(self, team: str,
                                after: _dt.date) -> tuple[_dt.date, list[dict]] | None:
        """Earliest official period at/after `after` in which this exact name appears."""
        tn = norm(team)
        for p in self.ordered:
            if p < after:
                continue
            hits = self.index.get(p, {}).get(tn, [])
            if hits:
                return p, list(hits)
        return None

    def any_period_containing(self, team: str) -> tuple[_dt.date, list[dict]] | None:
        tn = norm(team)
        for p in self.ordered:
            hits = self.index.get(p, {}).get(tn, [])
            if hits:
                return p, list(hits)
        return None

    def roster_matches(self, players: set[str], min_overlap: int = 3) -> list[dict]:
        """Every VRS row (all periods) whose roster shares >= min_overlap players."""
        want = {norm(p) for p in players}
        out = []
        for p in self.ordered:
            for r in self.periods[p]:
                have = {norm(x) for x in r["roster"].split(",")}
                overlap = want & have
                if len(overlap) >= min_overlap:
                    hit = dict(r)
                    hit["overlap"] = sorted(overlap)
                    hit["period"] = p.isoformat()
                    out.append(hit)
        out.sort(key=lambda r: (-len(r["overlap"]), r["period"]))
        return out


if __name__ == "__main__":  # pragma: no cover - manual smoke check
    s = Standings()
    print("periods:", [p.isoformat() for p in s.ordered])
    for p in s.ordered:
        print(" ", p, len(s.periods[p]), "teams")
    print("in force 2026-06-28:", s.period_in_force(_dt.datetime(2026, 6, 28)))
    print("in force 2026-10-14:", s.period_in_force(_dt.datetime(2026, 10, 14)))
    print("Sharks @2026-06-01:", s.exact(_dt.date(2026, 6, 1), "Sharks"))
    print("LFO 10 anywhere:", s.any_period_containing("LFO 10"))
    print("roster>=3 of LFO 10:", [(r["team"], r["period"], r["overlap"])
                                   for r in s.roster_matches(
                                       {"Jackinho", "Sapec", "flaw", "dottie", "tvs"})][:4])
