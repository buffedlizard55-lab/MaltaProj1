"""Append an explicit bookmaker list for one match to data/egw_books.csv.
Usage: python3 addlist.py ROW URL ORDER NOTE "Name a b; Name a b; ..."  (EGW page order; names may contain spaces)
"""
import csv, sys, pathlib
here = pathlib.Path(__file__).parent / "data"
row, url, order, note, spec = sys.argv[1:6]
n = 0
with open(here / "egw_books.csv", "a", newline="") as fh:
    w = csv.writer(fh)
    for item in [s.strip() for s in spec.split(";") if s.strip()]:
        parts = item.split()
        name, a, b = " ".join(parts[:-2]), parts[-2], parts[-1]
        float(a); float(b)
        if order == "swapped":
            a, b = b, a
        w.writerow([row, name, a, b, order, url, note]); n += 1
print("added", n, "books for row", row)
