"""Compare the captured post-relocation run with the previous revision-12 run."""
from collections import Counter, defaultdict
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PREVIOUS = HERE.parent / 'ck3-agot-plus-fix-stage12-log-2026-09-19'
PATCH = REPO / 'AGOT_Submods/AGOT_PLUS_FIX'


def read(path):
    return path.read_text(encoding='utf-8-sig')


def load(path):
    return json.loads(read(path))


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def save(name, data):
    (HERE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n',
                             encoding='utf-8', newline='\n')


def export(name, data, fields):
    with (HERE / name).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(data)


def signature(row):
    text = re.sub(r'\[args#\d+\]', '[args#*]', row['Message'])
    text = re.sub(r'\b(near line|line):\s*\d+', r'\1: *', text, flags=re.I)
    text = re.sub(r'\bline\s+\d+', 'line *', text, flags=re.I)
    return row['Component'] + ' ' + text


before = rows(PREVIOUS / 'classified-entries.csv')
after = rows(HERE / 'classified-entries.csv')
old, new = [Counter(map(signature, items)) for items in (before, after)]
samples = {signature(row): row for row in before + after}
changes = [dict(Before=old[key], After=new[key], Difference=new[key] - old[key],
                Component=samples[key]['Component'], Message=samples[key]['Message'])
           for key in sorted(old.keys() | new.keys()) if old[key] != new[key]]
fields = ['Before', 'After', 'Difference', 'Component', 'Message']
export('changed-messages.csv', changes, fields)
added = [row for row in changes if row['Difference'] > 0]
removed = [row for row in changes if row['Difference'] < 0]
export('new-messages.csv', added, fields)
export('disappeared-messages.csv', removed, fields)

by_signature = defaultdict(list)
for row in after:
    by_signature[signature(row)].append(row)
prior = rows(PREVIOUS / 'all-agot-plus-associated.csv')
associated, consumed = [], Counter()
for row in prior:
    key = signature(row)
    if consumed[key] >= len(by_signature[key]):
        continue
    current = by_signature[key][consumed[key]]
    consumed[key] += 1
    associated.append(dict(row, LogLine=current['Line'], Message=current['Message'],
                           OriginalOwner=current['Owner'], PriorLogLine=row['LogLine'],
                           EvidenceBasis='Unchanged diagnostic; attribution retained from the reviewed prior run'))
export('all-agot-plus-associated.csv', associated, list(prior[0]))
oldcounts, counts = [Counter(row['Category'] for row in data) for data in (prior, associated)]
labels = {r['Category']: r['Label'] for r in rows(PREVIOUS / 'agot-plus-categories.csv')}
categories = [dict(Category=key, Label=labels[key], Before=oldcounts[key], After=counts[key],
                   Removed=oldcounts[key] - counts[key]) for key in oldcounts]
export('agot-plus-categories.csv', categories, list(categories[0]))
for category in counts:
    selected = [row for row in associated if row['Category'] == category]
    export('remaining-' + category + '.csv', selected, list(selected[0]))

# A new diagnostic must not silently inherit a previous mod attribution.
assert all(row['Component'] == 'pdx_localize.cpp:279' and
           "'localization/russian/mde_artifacts_l_russian.yml'" in row['Message'] and
           ("'localization/russian/dp_artifacts_l_russian.yml'" in row['Message'] or
            "Key 'nagga_desc'" in row['Message']) for row in added)
assert sum(row['Difference'] for row in added) == 141
assert sum(-row['Difference'] for row in removed) == 20
assert len(associated) == 115

regressions = {}
for stage in range(1, 7):
    name = 'targeted-log-messages.csv' if stage == 1 else f'stage{stage}-targeted-log-messages.csv'
    regressions[str(stage)] = sum(new[signature(row)] > 0 for row in rows(PATCH / 'docs' / name))
for label, folder in [('7_8', 'stage8'), ('9', 'stage9'), ('10', 'stage10')]:
    targets = rows(HERE.parent / f'ck3-agot-plus-fix-{folder}-log-2026-09-19/fix-verification.csv')
    regressions[label] = sum(new[signature(row)] > 0 for row in targets)
assert not any(regressions.values()), regressions
earlier = rows(PREVIOUS / 'fix-verification.csv')
variables = [row for row in earlier if row['Category'].startswith('variable_')]
assert all(new[signature(row)] == 0 for row in variables)
loc_keys = {r['Key'] for r in load(REPO / 'AGOT_Submods/AGOT_PLUS_RUS_CORRECT/docs/runtime-localization-additions.json')['Entries']}
assert not [row for row in after if (m := re.match(r'Unrecognized loc key ([^. ]+)\.', row['Message'])) and m[1] in loc_keys]
other_dna = [row for row in after if row['Component'].startswith('portraitcontext')]
assert len(other_dna) == 2 and all(row['Owner'] == 'AGOT Bookmarked' for row in other_dna)
export('other-mod-dna.csv', other_dna, list(other_dna[0]))

mods, previous_mods = [rows(path / 'active-mods.csv') for path in (HERE, PREVIOUS)]
assert [(m['Order'], m['Descriptor']) for m in mods] == [(m['Order'], m['Descriptor']) for m in previous_mods]
capture = load(HERE / 'snapshot-summary.json')
for item in capture['Copies']:
    assert sha(HERE / 'snapshot' / item['Snapshot']) == item['SnapshotSHA256']
debug = read(HERE / 'snapshot/debug.log')
start = re.search(r'^\[(\d\d:\d\d:\d\d)\].*Log system initialized\.', debug)[1]
exit_line = next(line for line in debug.splitlines() if 'Quit: Quit from inside game' in line)
meta = next(item for item in capture['Logs'] if item['File'] == 'error.log')
launch = dt.datetime.fromisoformat(meta['LastWriteTime']).replace(
    **dict(zip(('hour', 'minute', 'second'), map(int, start.split(':')))), microsecond=0)
mounts = [line for line in debug.splitlines() if 'Mounted Data:' in line and PATCH.as_posix() in line]
assert len(mounts) == 1
runtime = rows(HERE / 'runtime-files.csv')
for item in runtime:
    path = REPO / 'AGOT_Submods' / item['Mod'] / item['File']
    assert sha(path) == item['SHA256']
    assert dt.datetime.fromisoformat(item['LastWriteTime']) < launch
previous_files = {(item['Mod'], item['File']): item for item in rows(PREVIOUS / 'runtime-files.csv')}
for item in runtime:
    # Previous runtime fingerprints predate the intentional LF migration.
    key = (item['Mod'], item['File'])
    assert key in previous_files
original = {item['File']: item for item in load(HERE.parent / 'repository-lf-migration-2026-09-19/original-file-hashes.json')}
for item in runtime:
    rel = 'AGOT_Submods/' + item['Mod'] + '/' + item['File']
    assert original[rel]['LFOnlySHA256'] == item['SHA256'], rel

roots = {'AGOT_PLUS': Path('E:/SteamLibrary/steamapps/workshop/content/1158310/2950245430'),
         'AGOT': Path('E:/SteamLibrary/steamapps/workshop/content/1158310/2962333032'),
         'CK3': Path('E:/SteamLibrary/steamapps/common/Crusader Kings III/game')}
sources = load(HERE / 'snapshot/source-baseline.json')
for item in sources:
    assert sha(roots[item['Catalog']] / item['File']) == item['SHA256']

save('comparison-summary.json', dict(
    PreviousEntries=len(before), CurrentEntries=len(after), RemovedMessages=20, AddedMessages=141,
    PreviousAGOTPlusAssociated=len(prior), CurrentAGOTPlusAssociated=len(associated),
    NewAGOTPlusDiagnostics=0, NewMDELocalizationDuplicates=141,
    UVComponents=dict(Counter(row['Component'] for row in associated if row['Category'] == 'mesh_uv')),
    Categories=categories, ActiveMods=len(mods), DescriptorOrderUnchanged=True,
    RuntimeFilesVerified=len(runtime), RuntimeChangedOnlyByLFMigration=True,
    SourcePinsVerified=len(sources), PriorFixRegressions=regressions,
    VariableTargetsStillAbsent=len(variables), LocalizationTargetsStillAbsent=len(loc_keys),
    OtherModDNAMessages=len(other_dna), Started=launch.isoformat(), ExitLine=exit_line,
    MountEvidence=mounts, SnapshotErrorSHA256=sha(HERE / 'snapshot/error.log')))
print(json.dumps(dict(AGOTPlusRemaining=len(associated), Removed=20, MDEDuplicatesAdded=141,
                      RuntimeVerified=len(runtime), SourcePinsVerified=len(sources))))
