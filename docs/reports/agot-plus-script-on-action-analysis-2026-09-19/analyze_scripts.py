"""Read-only installed-source audit; writes evidence only to this report directory."""
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[2]
PATCH = REPO / 'AGOT_Submods/AGOT_PLUS_FIX'
LOG = OUT.parent / 'ck3-agot-plus-fix-stage6-log-2026-09-19'
PROFILE = Path('C:/Users/RUSBAR/Documents/Paradox Interactive/Crusader Kings III')
GAME = Path('E:/SteamLibrary/steamapps/common/Crusader Kings III/game')


def read(p):
    return Path(p).read_text(encoding='utf-8-sig')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest().upper()


def load(p):
    return json.loads(read(p))


def csv_read(p):
    with Path(p).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def csv_write(name, rows):
    with (OUT / name).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def json_write(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def clean(text):
    return re.sub(r'"(?:\\.|[^"\\])*"|#[^\r\n]*',
                  lambda m: re.sub(r'[^\r\n]', ' ', m[0]), text)


def blocks(text):
    masked = clean(text)
    stack, ends, depths = [], {}, {}
    for m in re.finditer('[{}]', masked):
        if m[0] == '{':
            depths[m.start()] = len(stack)
            stack.append(m.start())
        elif stack:
            ends[stack.pop()] = m.end()
    found = []
    for m in re.finditer(r'(?m)^[ \t]*([\w.]+)\s*=\s*\{', masked):
        opening = masked.index('{', m.start(), m.end())
        end = ends.get(opening, len(text))
        found.append(dict(Id=m[1], Start=m.start(), End=end, Depth=depths[opening],
                          Line=text.count('\n', 0, m.start()) + 1, Body=text[m.start():end]))
    return found


def vfs():
    mods = csv_read(LOG / 'active-mods.csv')
    active = load(PROFILE / 'dlc_load.json')['enabled_mods']
    assert active == [m['Descriptor'] for m in mods]
    files = {}
    for mod in [{'Name': 'CK3', 'Path': str(GAME), 'Descriptor': ''}] + mods:
        root = Path(mod['Path'])
        if mod['Descriptor']:
            desc = read(PROFILE / mod['Descriptor'])
            assert Path(re.search(r'(?m)^\s*path\s*=\s*"([^"]+)"', desc)[1]).resolve() == root.resolve()
            for prefix in re.findall(r'(?m)^\s*replace_path\s*=\s*"([^"]+)"', desc):
                files = {k: v for k, v in files.items() if not k.startswith(prefix.rstrip('/') + '/')}
        for category in ('common', 'events', 'history', 'gui', 'localization/english'):
            for p in (root / category).rglob('*'):
                if p.is_file() and p.suffix in ('.txt', '.gui', '.info', '.yml'):
                    files[p.relative_to(root).as_posix()] = {'Path': p, 'Mod': mod['Name']}
    return mods, files


SYMBOLS = [
    'asoiaf_mega_war_effect', 'asoiaf_mega_war_events.0001', 'asoiaf_mega_war_cleanup_rule',
    'asoiaf_destroy_crownlands_title_effect', 'agot_on_title_inheritance_lannister_baratheon_coa',
    'is_busy_in_events_localised', 'is_busy_in_events_localized', 'is_busy_in_events',
    'can_be_busy_in_events', 'start_diarchy', 'try_start_diarchy',
] + [f'asoiaf_canon_children_Targaryen_{i}_{suffix}' for i in range(98, 105)
     for suffix in ('trigger', 'birth_effect')]


def main():
    manifest = load(PATCH / 'docs/source-manifest.json')
    assert manifest['Revision'] == 7
    before = {str(PATCH / r['File']): sha(PATCH / r['File']) for r in manifest['Files']}
    assert all(before[str(PATCH / r['File'])] == r['PatchedSHA256'] for r in manifest['Files'])
    manifest_hash = sha(PATCH / 'docs/source-manifest.json')
    mods, files = vfs()
    entries = [r for r in csv_read(LOG / 'agot-plus-without-portraits.csv')
               if r['IssueClass'] in ('Triggers_effects_and_syntax', 'On_action_structure')]
    assert len(entries) == 25
    csv_write('target-messages.csv', entries)
    pattern = re.compile(r'(?<![\w.])(' + '|'.join(map(re.escape, SYMBOLS)) + r')(?![\w.])')
    refs, sources, digests = [], {}, []
    definitions = Counter()
    for rel, item in sorted(files.items()):
        text = read(item['Path'])
        digest = sha(item['Path'])
        digests.append(f"{rel}|{item['Path']}|{digest}")
        if not pattern.search(text):
            continue
        masked = clean(text)
        defs = {d['Id']: d for d in blocks(text) if d['Depth'] == 0}
        for m in pattern.finditer(text):
            code = bool(pattern.match(masked, m.start()))
            line = text.count('\n', 0, m.start()) + 1
            definition = code and any(d['Id'] == m[1] and d['Line'] == line for d in blocks(text) if d['Depth'] == 0)
            refs.append(dict(Symbol=m[1], File=rel, Mod=item['Mod'], Line=line,
                             ActiveCode=code, RootDefinition=definition,
                             Text=text.splitlines()[line-1].strip()))
            if definition:
                definitions[m[1]] += 1
        sources[str(item['Path'])] = dict(File=rel, Mod=item['Mod'], Path=str(item['Path']), SHA256=digest)
    csv_write('symbol-references.csv', refs)
    csv_write('source-hashes.csv', list(sources.values()))
    csv_write('symbol-definitions.csv', [dict(Symbol=s, ActiveRootDefinitions=definitions[s]) for s in SYMBOLS])
    # Preserve numbered current code for the seven implicated files; the old
    # log refers to revision 6, so use actual current offsets for the analysis.
    excerpts = []
    for rel in sorted({r['Evidence'] for r in entries}):
        item = files[rel]
        text = read(item['Path'])
        excerpts += [f'# {rel}', f'# Effective provider: {item["Mod"]}', f'# SHA256: {sha(item["Path"])}']
        excerpts.extend(f'{n}: {line}' for n, line in enumerate(text.splitlines(), 1))
        excerpts.append('')
    (OUT / 'current-source-excerpts.txt').write_text('\n'.join(excerpts), encoding='utf-8', newline='\n')
    assert all(sha(p) == h for p, h in before.items())
    assert sha(PATCH / 'docs/source-manifest.json') == manifest_hash
    json_write('audit-summary.json', dict(PatchRevision=7, ManifestSHA256=manifest_hash,
               ActiveMods=len(mods), Messages=len(entries), ScriptMessages=23, OnActionMessages=2,
               LogSHA256=sha(LOG / 'snapshot/error.log'),
               LiveLogMatchesHistoricalSnapshot=sha(PROFILE / 'logs/error.log') == sha(LOG / 'snapshot/error.log'),
               EffectiveFilesScanned=len(files), SymbolReferences=len(refs), EvidenceFiles=len(sources),
               EffectiveScanSHA256=hashlib.sha256('\n'.join(digests).encode()).hexdigest().upper(),
               RuntimeFilesUnchanged=len(before), GameExecutionChecked=False))
    print(f'Analyzed 25 messages; {len(files)} effective files; {len(refs)} symbol references. Runtime files unchanged.')


if __name__ == '__main__':
    main()
