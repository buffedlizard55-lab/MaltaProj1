#!/usr/bin/env python3
"""Read every tracked text line; report syntax, data shape, link and review scope.

This is an inventory/consistency audit, not evidence that every inherited sports
assertion is true. Never publish detected personal-field values or credentials.
"""
from __future__ import annotations

import ast
import csv
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
REPO = "https://github.com/buffedlizard55-lab/MaltaProj1"
OWNED_PREFIXES = ("collector/", "webui/", "dashboard/", "data/snapshot/", "research/", "tests/test_")


class Document(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        for key in ("href", "src"):
            if attrs.get(key):
                self.links.append(attrs[key])


def run() -> dict:
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    records, docs, problems = [], {}, []
    total_lines = 0
    for name in names:
        if not name or name in {"research/repository-audit.json", "research/repository-audit.md"}:
            continue
        path = ROOT / name
        body = path.read_bytes()
        record = {"path": name, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(), "source_url": f"{REPO}/blob/{commit}/{name}", "scope": "evidence-dashboard" if name.startswith(OWNED_PREFIXES) else "preserved parallel/shared work", "checks": []}
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError:
            record.update(type="binary", lines=None)
            records.append(record)
            continue
        lines = text.splitlines()
        record.update(type="text", lines=len(lines))
        total_lines += len(lines)
        # Scan every line; field names only. A detection is not a credential claim.
        domains = set()
        contact_field_lines = 0
        for line in lines:
            if re.search(r'"email"\s*:\s*"[^"\s]+@', line, re.I):
                contact_field_lines += 1
            for match in re.finditer(r"https?://[^\s<>\"'`\\]+", line):
                try:
                    host = urlparse(match.group(0)).hostname
                    if host:
                        domains.add(host)
                except ValueError:
                    pass
        record["referenced_hosts"] = sorted(domains)
        if contact_field_lines and not name.startswith("tests/"):
            problems.append({"path": name, "kind": "contact-field review", "detail": f"{contact_field_lines} line(s) contain email-shaped field values. No values are copied into this report.", "source_url": record["source_url"]})
        try:
            if path.suffix == ".json":
                obj = json.loads(text)
                record["checks"].append("JSON parses")
                record["json_root"] = type(obj).__name__
            elif path.suffix == ".csv":
                reader = csv.DictReader(io.StringIO(text))
                rows = list(reader)
                record["checks"].append("CSV parses")
                record["csv_columns"] = reader.fieldnames
                record["csv_rows"] = len(rows)
                malformed = sum(None in row for row in rows)
                if malformed:
                    problems.append({"path": name, "kind": "CSV shape", "detail": f"{malformed} row(s) have excess fields.", "source_url": record["source_url"]})
            elif path.suffix == ".py":
                ast.parse(text, filename=name)
                record["checks"].append("Python AST parses in audit interpreter")
            elif path.suffix == ".html":
                doc = Document()
                doc.feed(text)
                docs[path.resolve()] = (doc, record)
                record["checks"].append("HTML links inventoried")
        except (ValueError, SyntaxError, csv.Error) as error:
            problems.append({"path": name, "kind": "syntax/data shape", "detail": type(error).__name__ + ": " + str(error), "source_url": record["source_url"]})
        records.append(record)

    link_count = 0
    for file, (doc, record) in docs.items():
        for link in doc.links:
            parsed = urlparse(link)
            if parsed.scheme or parsed.netloc:
                continue
            path = unquote(parsed.path)
            if path.startswith("/MaltaProj1/"):
                target = ROOT / path[len("/MaltaProj1/"):]
            elif path.startswith("/"):
                # Domain-root links leave the project site; do not claim their
                # successful existence from a repository filesystem lookup.
                continue
            else:
                target = file.parent / path if path else file
            target = target.resolve()
            if target.is_dir():
                target /= "index.html"
            link_count += 1
            if not target.is_file():
                problems.append({"path": record["path"], "kind": "internal link", "detail": f"Missing repository target: {link}", "source_url": record["source_url"]})
            elif parsed.fragment and target in docs and unquote(parsed.fragment) not in docs[target][0].ids:
                # Some existing pages generate anchors client-side. Flag rather
                # than declare them broken without executing their owner code.
                problems.append({"path": record["path"], "kind": "anchor review", "detail": f"No static anchor: {link}; may be client-generated.", "source_url": record["source_url"]})
    report = {
        "audit_at": datetime.now(timezone.utc).isoformat(), "base_commit": commit,
        "tracked_files_read": len(records), "text_lines_read": total_lines,
        "internal_targets_checked": link_count, "records": records, "needs_review": problems,
        "semantics": "All tracked text lines were read for inventory/shape/link checks. Sports values in parallel outputs were NOT promoted to primary-bookmaker evidence. Only data/snapshot is rechecked field-by-field against retained official responses by scripts/validate.py.",
    }
    (ROOT / "research/repository-audit.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    rows = ["# Combined repository audit", "", f"Audit UTC: **{report['audit_at']}**", f"Base commit: [`{commit[:12]}`]({REPO}/commit/{commit})", "", f"Read **{len(records)} tracked files / {total_lines:,} text lines**; checked **{link_count:,} internal HTML targets**.", "", "> This verifies inventory, syntax/data shape and link consistency—not the truth of every inherited sports assertion. Only the evidence dashboard snapshot is admitted to the primary-bookmaker calculation and rechecked field by field. Other owners' work is preserved, not silently certified or overwritten.", "", "## Review findings (non-blocking outside this dashboard's owned scope)", "", "| File | Review type | Detail | Official repository source |", "|---|---|---|---|"]
    for problem in problems:
        detail = problem["detail"].replace("|", "\\|").replace("\n", " ")
        rows.append(f"| `{problem['path']}` | {problem['kind']} | {detail} | [Review file]({problem['source_url']}) |")
    if not problems:
        rows.append(f"| Combined tracked tree | Inventory/shape/links | No structural findings in this scan. This does not verify outside sports values. | [Official tree]({REPO}/tree/{commit}) |")
    rows += ["", "## Line-by-line file ledger", "", "Each file has its complete-content SHA-256, text line count, parser checks, referenced hosts and official review link in [repository-audit.json](repository-audit.json). Values of detected personal/contact fields are never repeated in this report.", "", "## Scope-preserving source review", "", "- Legacy `scripts/model.py` and rank-derived tables are not external match-winner quotes. A rank-based estimate is a separate method, not a substitute for an unavailable bookmaker value.", "- `pipeline/inventory.py` estimates UTC from countdowns and a five-minute published rule. The official fixture transfer state has explicit UTC-millisecond schedules and explicit lock metadata; the observed 360-second offset conflicts with that 300-second rule. Our snapshot uses the exact schedule and flags the conflict instead of using that estimate.", "- `model/` has its own Valve/HLTV inputs, calibration and explicit alias documentation. Its published model estimates require their own method/evidence review and are not merged into this market-based dataset.", "- Parallel `assurance/`, `docs/`, `site/`, `pickem/`, root pages and namespace CSVs remain separate outputs. Source URLs alone do not verify a price, market period, capture time, or calibrated probability.", "- The new `dashboard/` publishes both CS2 and LoL, full captured source-state inventory, official links on every data row, blanks for unknown fields, expiry and scheduled automatic refresh.", ""]
    (ROOT / "research/repository-audit.md").write_text("\n".join(rows))
    return report


if __name__ == "__main__":
    result = run()
    print(json.dumps({key: result[key] for key in ("base_commit", "tracked_files_read", "text_lines_read", "internal_targets_checked")}, indent=2))
    print("Structural review findings:", len(result["needs_review"]))
