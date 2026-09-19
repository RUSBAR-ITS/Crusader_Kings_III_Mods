"""Audit installed translation 1.2 against the reviewed 1.1 catalog; no mod writes."""
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
OLD = HERE.parent / 'agot-more-dragon-eggs-russian-2026-09-18'
PATCH = REPO / 'AGOT_Submods/AGOT_More_Dragon_Eggs_RUS_CORRECT'
ROOTS = {label: Path('E:/SteamLibrary/steamapps/workshop/content/1158310') / ident
         for label, ident in [('Main', '3388366564'), ('Translation', '3736931686'),
                              ('AGOT', '2962333032'), ('AGOT_RU', '2962803371')]}


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def export(name, data, fields):
    with (HERE / name).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(data)


def save(name, data):
    (HERE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n',
                             encoding='utf-8', newline='\n')


def catalog(root, language, malformed=False):
    result = []
    for path in sorted((root / 'localization').rglob('*_l_' + language + '.yml')):
        text = path.read_text(encoding='utf-8-sig')
        assert re.search(r'(?m)^\s*l_' + language + r':\s*$', text), path
        for number, line in enumerate(text.splitlines(), 1):
            if not line.strip() or line.lstrip().startswith('#') or re.match(r'^\s*l_\w+:\s*$', line):
                continue
            match = re.match(r'^\s*([^\s#":]+):\s*(?:\d+\s*)?"(.*)"\s*(?:#.*)?$', line)
            if not match and malformed:
                match = re.match(r'^\s*([^\s#":]+):\s*(?:\d+\s*)?"(.*)$', line)
            assert match, (path, number, line)
            result.append(dict(Key=match[1], Text=match[2], File=path.relative_to(root).as_posix(), Line=number))
    return result


def first_map(data):
    return {row['Key']: row for row in reversed(data)}


baseline = load(PATCH / 'docs/source-baseline.json')
file_changes = []
for pin in baseline:
    path = ROOTS[pin['Catalog']] / pin['File']
    actual = sha(path) if path.is_file() else 'MISSING'
    if actual != pin['SHA256']:
        file_changes.append(dict(Catalog=pin['Catalog'], File=pin['File'], Status='changed' if path.exists() else 'removed',
                                 BeforeSHA256=pin['SHA256'], AfterSHA256=actual))
known = {(pin['Catalog'], pin['File']) for pin in baseline}
for label in ('Main', 'Translation'):
    for path in (ROOTS[label] / 'localization').rglob('*.yml'):
        if not re.search(r'_l_(english|russian)\.yml$', path.name):
            continue
        rel = path.relative_to(ROOTS[label]).as_posix()
        if (label, rel) not in known:
            file_changes.append(dict(Catalog=label, File=rel, Status='added', BeforeSHA256='', AfterSHA256=sha(path)))
assert all(row['Catalog'] == 'Translation' for row in file_changes)
export('upstream-file-changes.csv', file_changes, ['Catalog', 'File', 'Status', 'BeforeSHA256', 'AfterSHA256'])

old = [row for row in rows(OLD / 'catalog-entries.csv') if row['Catalog'] == 'Translation']
current = catalog(ROOTS['Translation'], 'russian')
english = first_map(catalog(ROOTS['Main'], 'english', malformed=True))
builtin = first_map(catalog(ROOTS['Main'], 'russian', malformed=True))
previous, updated = first_map(old), first_map(current)
patch = first_map(catalog(PATCH, 'russian'))
key_changes = []
for key in sorted(previous.keys() | updated.keys()):
    before, after = previous.get(key), updated.get(key)
    status = 'added' if before is None else 'removed' if after is None else 'changed' if before['Text'] != after['Text'] else ''
    if status:
        key_changes.append(dict(Key=key, Status=status, Before=before['Text'] if before else '',
                                After=after['Text'] if after else '', English=english.get(key, {}).get('Text', ''),
                                InCurrentEnglish=key in english, DefinedByPatch=key in patch,
                                PatchText=patch.get(key, {}).get('Text', ''),
                                PreviousFile=before['File'] if before else '', CurrentFile=after['File'] if after else ''))
export('key-changes.csv', key_changes, list(key_changes[0]))
export('changed-existing-translations.csv', [r for r in key_changes if r['Status'] == 'changed'], list(key_changes[0]))

by_key = defaultdict(list)
for row in current:
    by_key[row['Key']].append(row)
duplicates = [dict(Key=key, Definitions=len(values), Identical=len({r['Text'] for r in values}) == 1,
                   Files='; '.join(r['File'] for r in values), Texts=json.dumps([r['Text'] for r in values], ensure_ascii=False))
              for key, values in sorted(by_key.items()) if len(values) > 1]
export('translation-duplicates.csv', duplicates, list(duplicates[0]))

run = HERE.parent / 'ck3-agot-plus-fix-relocation-log-2026-09-19'
new_messages = rows(run / 'new-messages.csv')
new_pairs = []
for row in new_messages:
    match = re.match(r"Duplicate localization key\. Key '([^']+)' is defined in both '([^']+)' and '([^']+)'.", row['Message'])
    assert match, row
    key, first, second = match.groups()
    if key == 'nagga_desc':
        continue
    values = [r['Text'] for r in by_key[key] if r['File'] in (first, second)]
    assert len(values) == 2
    new_pairs.append(dict(Key=key, Identical=values[0] == values[1], FirstFile=first, SecondFile=second))
assert len(new_pairs) == 140 and all(row['Identical'] for row in new_pairs)
export('new-log-duplicate-pairs.csv', new_pairs, list(new_pairs[0]))

# Resolve the competing Russian definition of nagga_desc from the active source file.
agot_nagga = [row for row in catalog(ROOTS['AGOT_RU'], 'russian', malformed=True) if row['Key'] == 'nagga_desc']
assert len(agot_nagga) == 1
save('nagga-conflict.json', dict(Translation=by_key['nagga_desc'], AGOTRussian=agot_nagga,
                                ProtectedPatchAlias=patch['MDE_nagga_desc']))

runtime = load(PATCH / 'docs/source-manifest.json')
for item in runtime['Outputs']:
    assert sha(PATCH / item['File']) == item['SHA256']
assert sha(PATCH.parent / 'AGOT_More_Dragon_Eggs_RUS_CORRECT.mod') == runtime['ExternalDescriptorSHA256']
snapshot = HERE / 'translation-1.2'
snapshot.mkdir(exist_ok=True)
pins = []
for source in [*sorted((ROOTS['Translation'] / 'localization').rglob('*.yml')), ROOTS['Translation'] / 'descriptor.mod']:
    rel = source.relative_to(ROOTS['Translation'])
    target = snapshot / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = source.read_bytes()
    data = raw.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
    if target.exists():
        assert target.read_bytes() == data, ('Captured upstream version changed', source)
    else:
        target.write_bytes(data)
    pins.append(dict(File=rel.as_posix(), SourceSHA256=sha(source), SnapshotSHA256=sha(target)))
save('source-snapshot.json', pins)

required = set(english) - {'nagga_desc'} | {'MDE_nagga_desc', 'MDE_gui_exit', 'MDE_gui_move_outside',
                                        'NEEDS_ABSOLUTE_CROWN_AUTHORITY', 'stop_cradling_egg'}
missing = sorted(required - (updated.keys() | builtin.keys() | patch.keys()))
assert not missing
removed = [r for r in key_changes if r['Status'] == 'removed']
changed = [r for r in key_changes if r['Status'] == 'changed']
summary = dict(PreviousTranslationVersion=runtime['TranslationVersion'], CurrentTranslationVersion='1.2',
    BaselinePins=len(baseline), ChangedPinnedFiles=sum(r['Status'] == 'changed' for r in file_changes),
    AddedFiles=sum(r['Status'] == 'added' for r in file_changes), MainSourcesUnchanged=True,
    PreviousRussianKeys=len(previous), CurrentRussianKeys=len(updated), CurrentPhysicalEntries=len(current),
    KeyChanges=dict(Counter(row['Status'] for row in key_changes)),
    RemovedKeysStillRequiredByEnglish=[r['Key'] for r in removed if r['InCurrentEnglish']],
    MissingCurrentEnglishKeys=sorted(english.keys() - updated.keys()),
    MissingRuntimeRequiredKeys=missing, RequiredRuntimeKeys=len(required),
    ExistingChangedKeysCoveredByPatch=sum(r['DefinedByPatch'] for r in changed),
    ChangedExistingKeysNotCoveredByPatch=[r['Key'] for r in changed if not r['DefinedByPatch']],
    TranslationDuplicateKeys=len(duplicates), ConflictingTranslationDuplicates=sum(not r['Identical'] for r in duplicates),
    NewLogDuplicateMessages=len(new_messages), NewIdenticalArtifactDuplicateMessages=len(new_pairs),
    NewNaggaConflictMessages=1, CurrentPatchOutputsVerified=len(runtime['Outputs']),
    HistoricalComparison='Parsed keys and values; comments and original whitespace were not archived in the old catalog.',
    GameFilesChanged=False, BaselineHashesUpdated=False)
save('summary.json', summary)
print(json.dumps(summary, ensure_ascii=True))
