#!/usr/bin/env python3
"""Originate OUR OWN match-win probabilities and combine them with external lines.

Hotspawn pick % is NEVER used here (it is not an input anywhere in this file).

Inputs (all in data/):
  ratings.csv        HLTV World Ranks (each row carries its source URL)
  matches.csv        26 verbatim Hotspawn fixtures
  external_lines.csv one row per source reading, status = accepted | indicative | rejected

Own model (documented, reproducible, rank-only):
  rating(team)  = 2000 - 300 * log10(rank)
  P(A beats B)  = 1 / (1 + 10 ** (-(rating_A - rating_B) / 400))   (Elo logistic)
  If either team has no verified HLTV rank -> own P is BLANK (never inferred).

External lines:
  Polymarket cents  -> no-vig P(A) = a / (a + b)            (only if a+b in 98..106)
  Decimal odds      -> implied 1/odds, normalised: P(A) = (1/oA) / (1/oA + 1/oB)
  Only status=accepted rows feed the external probability; indicative rows are shown
  but never used for a pick; rejected rows are shown for audit only.

Pick rule (conservative):
  A side is picked only when BOTH the own model and the accepted external reading
  favour the same side with P >= MIN_EDGE (55%). Otherwise pick = "no pick" (or "single-source
  lean" when only one of the two exists, which is NOT a pick).

Run: python3 scripts/model.py  -> writes data/analysis.csv and prints a summary.
"""
import csv
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def read(name):
    with open(DATA / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_ratings():
    out = {}
    for row in read("ratings.csv"):
        if row["hltv_world_rank"].strip():
            out[row["team"].strip().lower()] = int(row["hltv_world_rank"])
    return out


MIN_EDGE = 0.55


def rating(rank):
    return 2000 - 300 * math.log10(rank)


def own_p(rank_a, rank_b):
    """Own-model P(A wins). Returns None when a rank is missing."""
    if rank_a is None or rank_b is None:
        return None
    ra, rb = rating(rank_a), rating(rank_b)
    return 1 / (1 + 10 ** (-(ra - rb) / 400))


def external_p(row):
    """No-vig P(A) for one external reading, or None if not usable."""
    unit = row["unit"].strip()
    try:
        a = float(row["team_a_value"])
        b = float(row["team_b_value"])
    except ValueError:
        return None
    if unit == "cents":
        if not (98 <= a + b <= 106):
            return None
        return a / (a + b)
    if unit == "decimal":
        ia, ib = 1 / a, 1 / b
        return ia / (ia + ib)
    return None


def pct(p):
    return "" if p is None else f"{100 * p:.1f}"


def main():
    ranks = load_ratings()
    matches = read("matches.csv")
    lines = read("external_lines.csv")
    by_match = {}
    for ln in lines:
        by_match.setdefault(ln["match_id"], []).append(ln)

    out_rows = []
    for m in matches:
        mid = m["id"]
        a, b = m["team_a"], m["team_b"]
        ra = ranks.get(a.lower())
        rb = ranks.get(b.lower())
        op = own_p(ra, rb)

        accepted = [ln for ln in by_match.get(mid, []) if ln["status"] == "accepted"]
        ext_ps = [(ln, external_p(ln)) for ln in accepted]
        ext_ps = [(ln, p) for ln, p in ext_ps if p is not None]
        ext_mean = sum(p for _, p in ext_ps) / len(ext_ps) if ext_ps else None

        # Pick logic (see module docstring)
        if op is None and ext_mean is None:
            pick, basis = "no pick", "no usable own or external line"
        elif op is None or ext_mean is None:
            pick, basis = "no pick", "single source only (not a pick)"
        elif (op > 0.5) != (ext_mean > 0.5):
            pick, basis = "no pick", "own model and external disagree"
        elif max(op, 1 - op) < MIN_EDGE or max(ext_mean, 1 - ext_mean) < MIN_EDGE:
            pick, basis = "no pick", "edge below 55% on at least one source"
        else:
            fav = a if op > 0.5 else b
            pick, basis = fav, "own model and accepted external agree (both >= 55%)"

        statuses = sorted({ln["status"] for ln in by_match.get(mid, [])})
        out_rows.append({
            "id": mid,
            "team_a": a,
            "team_b": b,
            "hltv_rank_a": ra or "",
            "hltv_rank_b": rb or "",
            "own_pA_pct": pct(op),
            "own_pB_pct": pct(None if op is None else 1 - op),
            "external_accepted_readings": len(ext_ps),
            "external_pA_pct_mean_nova": pct(ext_mean),
            "external_pB_pct_mean_nova": pct(None if ext_mean is None else 1 - ext_mean),
            "reading_statuses": ";".join(statuses),
            "pick": pick,
            "pick_basis": basis,
        })

    fields = list(out_rows[0].keys())
    with open(DATA / "analysis.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(out_rows)

    for r in out_rows:
        print(r["id"], f'{r["team_a"]} vs {r["team_b"]}',
              "own A%:", r["own_pA_pct"] or "-",
              "ext A%:", r["external_pA_pct_mean_nova"] or "-",
              "pick:", r["pick"])


if __name__ == "__main__":
    main()
