"""Read-only source inspection for the captured 32-mod playset.

Outputs are confined to this report directory. Same-path replacement and
replace_path are modeled; duplicate object IDs across different files still
require manual review. No claim to emulate the game's complete loader.
"""
import collections
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')

HERE = Path(__file__).resolve().parent
LOG = HERE.parent / 'ck3-agot-plus-fix-stage14-log-2026-09-19'
GAME = Path('E:/SteamLibrary/steamapps/common/Crusader Kings III/game')


def read(p):
    return Path(p).read_text(encoding='utf-8-sig', errors='replace')


def rows(p):
    with Path(p).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def save(name, data):
    (HERE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n',
                             encoding='utf-8', newline='\n')


def uncomment(line):
    return re.sub(r'"(?:\\.|[^"\\])*"|#.*', lambda m: '' if m[0].startswith('#') else m[0], line)


def index():
    effective, sources = {}, []
    mods = [dict(Order='0', Name='CK3', Path=str(GAME))] + rows(LOG / 'active-mods.csv')
    for m in mods:
        root = Path(m['Path'])
        desc = LOG / 'snapshot' / ('descriptor-%02d.mod' % int(m['Order']))
        for prefix in re.findall(r'^replace_path\s*=\s*"([^"]+)"', read(desc) if desc.exists() else '', re.M):
            for key in list(effective):
                if key == prefix or key.startswith(prefix.rstrip('/') + '/'):
                    del effective[key]
        files = subprocess.run(['rg', '--files', '--hidden', '-g', '*.txt', '-g', '*.gui', '-g', '*.yml', '-g', '*.asset', str(root)], capture_output=True, check=True).stdout.decode('utf-8').splitlines()
        for f in files:
            p = Path(f)
            rel = p.relative_to(root).as_posix()
            if rel.split('/')[0] not in {'common', 'events', 'history', 'gfx', 'gui', 'localization', 'map_data'}:
                continue
            item = dict(owner=m['Name'], order=int(m['Order']), path=str(p), relative=rel)
            effective[rel] = item
            sources.append(item)
    save('effective-files.json', list(effective.values()))
    save('all-source-files.json', sources)
    return list(effective.values())


def loadindex():
    return json.loads(read(HERE / 'effective-files.json'))


def candidates(pattern, prefix=''):
    items = loadindex()
    known = {str(Path(x['path'])).casefold(): x for x in items if x['relative'].startswith(prefix)}
    mods = [dict(Path=str(GAME))] + rows(LOG / 'active-mods.csv')
    result = subprocess.run(['rg', '-l', '--hidden', '--pcre2', '-g', '*.txt', '-g', '*.gui', '-g', '*.yml', '-g', '*.asset', '-e', pattern] + [m['Path'] for m in mods], capture_output=True)
    if result.returncode not in (0,1):
        raise RuntimeError(result.stderr.decode('utf-8'))
    paths = [str(Path(p)).casefold() for p in result.stdout.decode('utf-8').splitlines()]
    return [known[p] for p in paths if p in known]


def search(pattern, context=0, raw=False, prefix=''):
    rex = re.compile(pattern)
    for item in candidates(pattern, prefix):
        lines = read(item['path']).splitlines()
        hits = [i for i, line in enumerate(lines) if rex.search(line if raw else uncomment(line))]
        if not hits:
            continue
        print('\nFILE', item['owner'], item['path'])
        selected = set()
        for i in hits:
            selected.update(range(max(0, i-context), min(len(lines), i+context+1)))
        for i in sorted(selected):
            print(f'{i+1}: {lines[i]}')


def variables():
    names = {}
    for cat in ['read_not_set', 'set_not_read']:
        for r in rows(LOG / f'remaining-{cat}.csv'):
            typ, key = re.search(r"(Flag|Variable) '([^']+)'", r['Message']).groups()
            names.setdefault((typ, key, cat), []).append(int(r['Line']))
    unique = set(key for _, key, _ in names)
    rex = re.compile(r'(?<![\w])(' + '|'.join(re.escape(x) for x in sorted(unique, key=len, reverse=True)) + r')(?![\w])')
    hits = collections.defaultdict(list)
    for item in candidates(rex.pattern):
        lines = read(item['path']).splitlines()
        for i, line in enumerate(lines):
            code = uncomment(line)
            for key in set(rex.findall(code)):
                if key == 'global' and not re.search(r'(flag\s*[:=]\s*global\b|value\s*=\s*global\b)', code):
                    continue
                hits[key].append(dict(item, line=i+1, text=line, context='\n'.join(lines[max(0,i-2):i+3])))
    result = [dict(kind=typ, key=key, category=cat, log_lines=ln, references=hits[key]) for (typ,key,cat),ln in names.items()]
    save('variable-references.json', result)
    for row in result:
        print(row['category'],row['kind'],row['key'],collections.Counter(x['owner'] for x in row['references']))


if __name__ == '__main__':
    if sys.argv[1] == 'index':
        print('Effective files:', len(index()))
        variables()
    elif sys.argv[1] == 'variables':
        variables()
    elif sys.argv[1] == 'search':
        search(sys.argv[2], int(sys.argv[3]) if len(sys.argv)>3 else 0,
               prefix=sys.argv[4] if len(sys.argv)>4 else '')
