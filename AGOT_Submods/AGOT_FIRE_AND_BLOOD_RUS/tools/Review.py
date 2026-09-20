"""Display English/Russian pairs for editorial review; never changes texts."""
from Localization import ROOT, MAIN, read_catalog
import argparse

p = argparse.ArgumentParser()
p.add_argument('file', nargs='?', default='')
p.add_argument('start', nargs='?', type=int, default=1)
p.add_argument('end', nargs='?', type=int, default=10000)
a = p.parse_args()
en, _ = read_catalog(MAIN, 'english')
ru, _ = read_catalog(ROOT, 'russian')
rows = [r for r in ru.values() if a.file in r['file']]
for i, r in enumerate(rows, 1):
    if a.start <= i <= a.end:
        print(f"{i}. {r['key']}\nEN: {en.get(r['key'], {}).get('text', '[MISSING]')}\nRU: {r['text']}\n")
