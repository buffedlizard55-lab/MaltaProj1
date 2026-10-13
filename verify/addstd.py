"""Append one match's EGamersWorld bookmaker table (standard 29-book order) to egw_books.csv.
Usage: python3 addstd.py ROW URL ORDER NOTE "o1a o1b o2a o2b ..."   (pairs in EGW page order)
ORDER = same | swapped  (swapped: EGW lists Hotspawn team_b first; pairs are flipped to Hotspawn order)
"""
import csv, sys, pathlib
here = pathlib.Path(__file__).parent / "data"
books = [b for b in (here / ".std_books.txt").read_text().splitlines() if b.strip()]
row, url, order, note, odds = sys.argv[1:6]
vals = odds.split()
assert len(vals) == 2 * len(books), (len(vals), 2 * len(books))
with open(here / "egw_books.csv", "a", newline="") as fh:
    w = csv.writer(fh)
    for i, b in enumerate(books):
        a, c = vals[2 * i], vals[2 * i + 1]
        if order == "swapped":
            a, c = c, a
        w.writerow([row, b, a, c, order, url, note])
print("added", len(books), "books for row", row)
