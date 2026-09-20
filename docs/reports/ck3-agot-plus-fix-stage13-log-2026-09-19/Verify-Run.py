"""Audit the captured revision-13 startup; write reports, never game files."""
from collections import Counter, defaultdict
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PREVIOUS = HERE.parent / 'ck3-agot-plus-fix-relocation-log-2026-09-19'
STAGE12 = HERE.parent / 'ck3-agot-plus-fix-stage12-log-2026-09-19'
PATCH = REPO / 'AGOT_Submods/AGOT_PLUS_FIX'


def read(path):
    return Path(path).read_text(encoding='utf-8-sig')


def load(path):
    return json.loads(read(path))


def rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


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
export('new-messages.csv', [r for r in changes if r['Difference'] > 0], fields)
export('disappeared-messages.csv', [r for r in changes if r['Difference'] < 0], fields)

by_signature = defaultdict(list)
for row in after:
    by_signature[signature(row)].append(row)
prior = rows(PREVIOUS / 'all-agot-plus-associated.csv')
associated, consumed, verification = [], Counter(), []
for row in prior:
    key = signature(row)
    if consumed[key] < len(by_signature[key]):
        current = by_signature[key][consumed[key]]
        consumed[key] += 1
        associated.append(dict(row, LogLine=current['Line'], Message=current['Message'],
                               OriginalOwner=current['Owner'], PriorLogLine=row['LogLine'],
                               EvidenceBasis='Unchanged diagnostic; reviewed attribution retained; earlier text files hash-identical'))
    if row['Category'] == 'mesh_uv':
        verification.append(dict(Category=row['Category'], PriorLogLine=row['LogLine'],
                                 Component=row['Component'], Message=row['Message'], AfterCount=new[key]))
assert len(prior) == 115 and len(associated) == 40
assert len(verification) == 75 and all(r['AfterCount'] == 0 for r in verification)
export('all-agot-plus-associated.csv', associated, list(prior[0]))
export('fix-verification.csv', verification, list(verification[0]))
oldcounts, counts = [Counter(row['Category'] for row in data) for data in (prior, associated)]
labels = {r['Category']: r['Label'] for r in rows(PREVIOUS / 'agot-plus-categories.csv')}
categories = [dict(Category=key, Label=labels[key], Before=oldcounts[key], After=counts[key],
                   Removed=oldcounts[key] - counts[key]) for key in labels]
export('agot-plus-categories.csv', categories, list(categories[0]))
for category in counts:
    selected = [row for row in associated if row['Category'] == category]
    export('remaining-' + category + '.csv', selected, list(selected[0]))

# Review the only added string without broad normalization or hiding new errors.
removed, added = old-new, new-old
assert removed.total() == 217 and added.total() == 1
prefix = "jomini_eventmanager.cpp:428 Duplicated event ID 'agot_activity_commission_crown.0001' found."
old_keys = [key for key in removed if key.startswith(prefix)]
new_key = next(iter(added))
assert len(old_keys) == 1 and new_key.startswith(prefix)
assert old_keys[0].replace('agot_coronation_crown_commission_events.txt',
                           'agot_activity_events_crown_commission.txt') == new_key
event_sources = load(STAGE12 / 'duplicate-event-source-evidence.json')
assert len(event_sources) == 2
for row in event_sources:
    assert sha(row['Path']) == row['SHA256']
    assert re.search(r'(?m)^agot_activity_commission_crown\.0001\s*=\s*\{', read(row['Path']))
save('duplicate-event-source-evidence.json', event_sources)
save('reviewed-diagnostic-variation.json', dict(Event='agot_activity_commission_crown.0001',
     Before=old_keys[0], After=new_key, BeforeCount=1, AfterCount=1, SourceHashesUnchanged=True,
     Interpretation='Known AGOT/Crowns of Westeros duplicate; only the reported source path changed.'))
uv_removed = Counter(map(signature, [r for r in prior if r['Category'] == 'mesh_uv']))
mde_removed = removed-uv_removed-Counter({old_keys[0]: 1})
assert mde_removed.total() == 141
for key in mde_removed:
    msg = samples[key]
    assert msg['Component'] == 'pdx_localize.cpp:279'
    assert "'localization/russian/mde_artifacts_l_russian.yml'" in msg['Message']
    assert ("'localization/russian/dp_artifacts_l_russian.yml'" in msg['Message'] or
            "Key 'nagga_desc'" in msg['Message'])
assert sum(n for key,n in mde_removed.items() if "Key 'nagga_desc'" in key) == 1
export('mde-disappeared.csv', [dict(Occurrences=n, Component=samples[k]['Component'],
                                  Message=samples[k]['Message']) for k,n in mde_removed.items()],
       ['Occurrences', 'Component', 'Message'])
assert not [r for r in after if 'blendshape' in r['Message'].lower()]

regressions = {}
for stage in range(1, 7):
    name = 'targeted-log-messages.csv' if stage == 1 else f'stage{stage}-targeted-log-messages.csv'
    regressions[str(stage)] = sum(new[signature(r)] > 0 for r in rows(PATCH / 'docs' / name))
for label in ('stage8', 'stage9', 'stage10'):
    targets = rows(HERE.parent / f'ck3-agot-plus-fix-{label}-log-2026-09-19/fix-verification.csv')
    regressions[label] = sum(new[signature(r)] > 0 for r in targets)
assert not any(regressions.values()), regressions
variables = [r for r in rows(STAGE12 / 'fix-verification.csv') if r['Category'].startswith('variable_')]
assert len(variables) == 130 and all(new[signature(r)] == 0 for r in variables)
loc_keys = {r['Key'] for r in load(REPO / 'AGOT_Submods/AGOT_PLUS_RUS_CORRECT/docs/runtime-localization-additions.json')['Entries']}
assert not [r for r in after if (m := re.match(r'Unrecognized loc key ([^. ]+)\.', r['Message'])) and m[1] in loc_keys]
other_dna = [r for r in after if r['Component'].startswith('portraitcontext')]
assert len(other_dna) == 2 and all(r['Owner'] == 'AGOT Bookmarked' for r in other_dna)
export('other-mod-dna.csv', other_dna, list(other_dna[0]))

mods, previous_mods = [rows(path / 'active-mods.csv') for path in (HERE, PREVIOUS)]
assert [(m['Order'], m['Descriptor'], m['Path']) for m in mods] == [(m['Order'], m['Descriptor'], m['Path']) for m in previous_mods]
capture = load(HERE / 'snapshot-summary.json')
for row in capture['Copies']:
    assert sha(HERE / 'snapshot' / row['Snapshot']) == row['SnapshotSHA256']
debug = read(HERE / 'snapshot/debug.log')
start = re.search(r'^\[(\d\d:\d\d:\d\d)\].*Log system initialized\.', debug)[1]
exit_line = next(line for line in debug.splitlines() if 'Quit: Quit from inside game' in line)
meta = next(row for row in capture['Logs'] if row['File'] == 'error.log')
launch = dt.datetime.fromisoformat(meta['LastWriteTime']).replace(
    **dict(zip(('hour', 'minute', 'second'), map(int, start.split(':')))), microsecond=0)
mounts = [line for line in debug.splitlines() if 'Mounted Data:' in line and PATCH.as_posix() in line]
assert len(mounts) == 1
runtime = rows(HERE / 'runtime-files.csv')
for row in runtime:
    path = REPO / 'AGOT_Submods' / row['Mod'] / row['File']
    assert sha(path) == row['SHA256']
    assert dt.datetime.fromisoformat(row['LastWriteTime']) < launch
previous_files = {(r['Mod'],r['File']): r for r in rows(PREVIOUS / 'runtime-files.csv')}
for row in runtime:
    key = (row['Mod'],row['File'])
    if key in previous_files:
        assert row['SHA256'] == previous_files[key]['SHA256']
assert len(previous_files) == 92
manifest = load(HERE / 'snapshot/patch-source-manifest.json')
assert manifest['Revision'] == 13 and len(manifest['Files']) == 132
plan = load(HERE / 'snapshot/stage13-plan.json')
for row in plan['Sources'] + plan['Evidence']:
    path = REPO / row['Path'] if row['Repository'] else Path(row['Path'])
    assert sha(path) == row['SHA256']
for row in plan['PreviousFiles']:
    assert sha(PATCH / row['File']) == row['SHA256']
assert len(plan['PreviousFiles']) == 84
roots = {'AGOT_PLUS': Path('E:/SteamLibrary/steamapps/workshop/content/1158310/2950245430'),
         'AGOT': Path('E:/SteamLibrary/steamapps/workshop/content/1158310/2962333032')}
sources = load(HERE / 'snapshot/source-baseline.json')
for row in sources:
    assert sha(roots[row['Catalog']] / row['File']) == row['SHA256']

summary = dict(PreviousEntries=len(before), CurrentEntries=len(after),
    RawRemovedMessages=removed.total(), RawAddedMessages=added.total(), ReviewedSourcePathVariations=1,
    ResolvedMessages=216, NewDiagnosticsAfterReview=0,
    PreviousAGOTPlusAssociated=len(prior), CurrentAGOTPlusAssociated=len(associated),
    UVTargetsResolved=75, UVExcessChannelsResolved=39, UVDegenerateChannelsResolved=36,
    NewBlendshapeDiagnostics=0, NewAGOTPlusDiagnostics=0, MDELocalizationDuplicatesResolved=141,
    NaggaDuplicateResolved=True, Categories=categories, ActiveMods=len(mods),
    DescriptorOrderAndPathsUnchanged=True, PatchRevision=13, PatchRuntimeFiles=132,
    PreviousPatchFilesUnchanged=84, VerifiedOutputs=len(runtime), MDEOutputsVerified=20,
    SourcePinsVerified=len(sources), UVSourceAndEvidencePinsVerified=len(plan['Sources'])+len(plan['Evidence']),
    PriorFixRegressions=regressions, VariableTargetsStillAbsent=len(variables),
    LocalizationTargetsStillAbsent=len(loc_keys), OtherModDNAMessages=len(other_dna),
    Started=launch.isoformat(), ExitLine=exit_line, MountEvidence=mounts,
    SnapshotErrorSHA256=sha(HERE / 'snapshot/error.log'),
    VisualEquivalenceChecked=False, InCampaignBehaviorChecked=False)
save('comparison-summary.json', summary)
print(json.dumps({k: summary[k] for k in ('PreviousEntries','CurrentEntries',
      'CurrentAGOTPlusAssociated','UVTargetsResolved','NewBlendshapeDiagnostics',
      'MDELocalizationDuplicatesResolved','NewDiagnosticsAfterReview','VerifiedOutputs')}))
