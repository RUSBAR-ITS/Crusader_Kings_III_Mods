"""Verify the captured revision-9 startup against the reviewed DNA targets.

Only report artifacts are written. No runtime files, profile or Workshop writes.
Raw diagnostic differences remain visible; the known crown-event path variation
is reviewed separately against unchanged source hashes from an earlier run.
"""
from collections import Counter, defaultdict
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PATCH = REPO / 'AGOT_Submods/AGOT_PLUS_FIX'
PREVIOUS = HERE.parent / 'ck3-agot-plus-fix-stage8-log-2026-09-19'
INVENTORY = HERE.parent / 'agot-plus-remaining-inventory-2026-09-19'
SNAPSHOT = HERE / 'snapshot'


def read(path): return Path(path).read_text(encoding='utf-8-sig')
def load(path): return json.loads(read(path))
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


def rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def save(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def export(name, data, fields):
    with (HERE / name).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(data)


def signature(row):
    message = re.sub(r'\[args#\d+\]', '[args#*]', row['Message'])
    message = re.sub(r'\b(near line|line):\s*\d+', r'\1: *', message, flags=re.I)
    message = re.sub(r'\bline\s+\d+', 'line *', message, flags=re.I)
    return row['Component'] + ' ' + message


before, after = [rows(path / 'classified-entries.csv') for path in (PREVIOUS, HERE)]
old, new = [Counter(map(signature, data)) for data in (before, after)]
assert (len(before), len(after)) == (10560, 2442)
by_line = {r['Line']: r for r in before}
samples = {signature(r): r for r in before + after}
changes = []
for key in sorted(old.keys() | new.keys()):
    if old[key] == new[key]: continue
    row = samples[key]
    changes.append(dict(BeforeCount=old[key], AfterCount=new[key], Difference=new[key]-old[key],
                        Component=row['Component'], Message=row['Message'], Signature=key))
fields = ['BeforeCount', 'AfterCount', 'Difference', 'Component', 'Message', 'Signature']
for name, data in [('changed', changes), ('new', [r for r in changes if r['Difference'] > 0]),
                   ('disappeared', [r for r in changes if r['Difference'] < 0])]:
    export(name + '-messages.csv', data, fields)

targets = rows(SNAPSHOT / 'stage9-targeted-log-messages.csv')
deferred = rows(SNAPSHOT / 'stage9-deferred-log-messages.csv')
verification = []
target_counts = Counter()
for issue in targets:
    original = by_line[issue['LogLine']]
    key = signature(original)
    target_counts[key] += 1
    verification.append(dict(issue, Component=original['Component'], Message=original['Message'], AfterCount=new[key]))
assert len(verification) == 8118 and all(r['AfterCount'] == 0 for r in verification)
export('fix-verification.csv', verification, list(verification[0]))

# Retain exact multiplicities for all 250 deliberately deferred diagnostics.
deferred_counts = Counter(signature(by_line[r['LogLine']]) for r in deferred)
assert deferred_counts.total() == 250
assert all(new[key] == count for key, count in deferred_counts.items())
remaining_dna = []
for row in after:
    if signature(row) not in deferred_counts: continue
    issue = next(r for r in deferred if signature(by_line[r['LogLine']]) == signature(row))
    remaining_dna.append(dict(Category=issue['Category'], Gene=issue['Gene'], DNA=issue['DNA'],
                              File=issue['File'], LogLine=row['Line'], Component=row['Component'], Message=row['Message']))
assert len(remaining_dna) == 250
export('remaining-dna.csv', remaining_dna, list(remaining_dna[0]))
gene_counts = Counter(r['Gene'] for r in remaining_dna)
assert gene_counts == Counter(dict(gene_eye_size=53, gene_eye_shut_top=53, gene_eye_shut_bottom=53,
                                   gene_forehead_inner_brow_width=20, gene_bs_eye_fold_2=65, legwear=4,
                                   gene_bs_ear_outward=2))

# The sole non-DNA textual difference is an already observed duplicate-event
# source-path variant. Never erase arbitrary paths or event IDs from comparison.
removed, added = old - new, new - old
extra_removed = removed - target_counts
assert removed.total() == 8119 and added.total() == extra_removed.total() == 1
crown_prefix = "jomini_eventmanager.cpp:428 Duplicated event ID 'agot_activity_commission_crown.0001' found."
old_key, new_key = next(iter(extra_removed)), next(iter(added))
assert old_key.startswith(crown_prefix) and new_key.startswith(crown_prefix)
old_name = 'agot_activity_events_crown_commission.txt'
new_name = 'agot_coronation_crown_commission_events.txt'
assert old_key.replace(old_name, new_name) == new_key
assert target_counts == removed - extra_removed
event_sources = load(HERE.parent / 'ck3-agot-plus-fix-stage6-log-2026-09-19/duplicate-event-source-evidence.json')
assert len(event_sources) == 2
for entry in event_sources:
    assert sha(entry['Path']) == entry['SHA256']
    assert re.search(r'(?m)^agot_activity_commission_crown\.0001\s*=\s*\{', read(entry['Path']))
save('duplicate-event-source-evidence.json', event_sources)
save('reviewed-diagnostic-variation.json', dict(Event='agot_activity_commission_crown.0001',
     Before=old_key, After=new_key, BeforeCount=1, AfterCount=1, SourceHashesUnchanged=True,
     Interpretation='Previously observed duplicate between AGOT and Crowns of Westeros. Only reported file path changed; engine path-selection reason unverified.'))

# All earlier targeted fixes remain absent, not merely the newest DNA fixes.
regressions = {}
for stage in range(1, 7):
    name = 'targeted-log-messages.csv' if stage == 1 else f'stage{stage}-targeted-log-messages.csv'
    regressions[str(stage)] = sum(new[signature(r)] > 0 for r in rows(PATCH / 'docs' / name))
regressions['7_8'] = sum(new[signature(r)] > 0 for r in rows(PREVIOUS / 'fix-verification.csv'))
assert not any(regressions.values()), regressions
loc_keys = {r['Key'] for r in load(REPO / 'AGOT_Submods/AGOT_PLUS_RUS_CORRECT/docs/runtime-localization-additions.json')['Entries']}
assert len(loc_keys) == 386
assert not [r for r in after if (m := re.match(r'Unrecognized loc key ([^. ]+)\.', r['Message'])) and m[1] in loc_keys]

# Transfer the already reviewed AGOT+ attribution only for matching diagnostics.
# Other errors retain their separate source attribution; no new ownership inferred.
by_signature = defaultdict(list)
for row in after:
    by_signature[signature(row)].append(row)
associated = []
consumed = Counter()
prior_associated = rows(INVENTORY / 'all-agot-plus-associated.csv')
for row in prior_associated:
    key = signature(row)
    if consumed[key] >= len(by_signature[key]): continue
    current = by_signature[key][consumed[key]]
    consumed[key] += 1
    associated.append(dict(row, LogLine=current['Line'], Message=current['Message'], OriginalOwner=current['Owner'],
                           PriorLogLine=row['LogLine']))
assert len(prior_associated) == 8840 and len(associated) == 722
assert sum(r['Category'].startswith('dna_') for r in associated) == 250
export('all-agot-plus-associated.csv', associated, list(associated[0]))
category_rows = []
old_categories, categories = Counter(r['Category'] for r in prior_associated), Counter(r['Category'] for r in associated)
for row in rows(INVENTORY / 'categories.csv'):
    category_rows.append(dict(Category=row['Category'], Label=row['Label'], Before=old_categories[row['Category']],
                              After=categories[row['Category']], Removed=old_categories[row['Category']]-categories[row['Category']]))
export('agot-plus-categories.csv', category_rows, list(category_rows[0]))

# Identify the actual run and confirm it loaded the exact revision-9 package.
mods, oldmods = rows(HERE / 'active-mods.csv'), rows(PREVIOUS / 'active-mods.csv')
order = lambda data: [(r['Order'], r['Descriptor'], r['Path']) for r in data]
assert order(mods) == order(oldmods) and len(mods) == 32
assert load(SNAPSHOT / 'dlc_load.json') == load(PREVIOUS / 'snapshot/dlc_load.json')
capture = load(HERE / 'snapshot-summary.json')
manifest = load(SNAPSHOT / 'patch-source-manifest.json')
assert manifest['Revision'] == 9 and len(manifest['Files']) == 64
assert sha(SNAPSHOT / 'patch-source-manifest.json') == capture['PatchManifestSHA256'] == sha(PATCH / 'docs/source-manifest.json')
static = load(SNAPSHOT / 'stage9-validation.json')
assert static['Status'] == 'PASS' and static['ManifestSHA256'] == capture['PatchManifestSHA256']
for entry in capture['Logs']:
    assert sha(SNAPSHOT / entry['File']) == entry['SHA256']
debug = read(SNAPSHOT / 'debug.log')
start_time = re.search(r'^\[(\d\d:\d\d:\d\d)\].*Log system initialized\.', debug)[1]
error_meta = next(r for r in capture['Logs'] if r['File'] == 'error.log')
launch = dt.datetime.fromisoformat(error_meta['LastWriteTime']).replace(**dict(zip(('hour', 'minute', 'second'), map(int, start_time.split(':')))), microsecond=0)
mounts = [line for line in debug.splitlines() if 'Mounted Data:' in line and PATCH.as_posix() in line]
assert len(mounts) == 1 and 'Quit: Quit from inside game' in debug
runtime = rows(HERE / 'runtime-files.csv')
assert len(runtime) == 72
for row in runtime:
    root = REPO / 'AGOT_Submods' / row['Mod']
    path = root / row['File']
    assert sha(path) == row['SHA256'] and path.stat().st_mtime < launch.timestamp()
    assert dt.datetime.fromisoformat(row['LastWriteTime']) < launch
    providers = [Path(m['Path']) for m in mods if (Path(m['Path']) / row['File']).is_file()]
    assert providers[-1].resolve() == root.resolve()
source_rows = []
roots = dict(AGOT_PLUS=Path('E:/SteamLibrary/steamapps/workshop/content/1158310/2950245430'),
             AGOT=Path('E:/SteamLibrary/steamapps/workshop/content/1158310/2962333032'))
for row in load(SNAPSHOT / 'source-baseline.json'):
    path = roots[row['Catalog']] / row['File']
    assert sha(path) == row['SHA256'] and path.stat().st_mtime < launch.timestamp()
    source_rows.append(dict(row, LastWriteTime=dt.datetime.fromtimestamp(path.stat().st_mtime, launch.tzinfo).isoformat()))
assert len(source_rows) == 119
export('source-hash-verification.csv', source_rows, list(source_rows[0]))
dna_pins = load(SNAPSHOT / 'stage9-plan.json')['Sources']
for pin in dna_pins:
    assert sha(pin['Path']) == pin['SHA256'] and Path(pin['Path']).stat().st_mtime < launch.timestamp()
assert len(dna_pins) == 219
save('debug-mount-evidence.json', dict(DebugLogSHA256=sha(SNAPSHOT / 'debug.log'), RunStartedAt=launch.isoformat(),
     PatchMounts=mounts, QuitLines=[line for line in debug.splitlines() if 'Quit:' in line]))

summary = dict(BeforeRevision=8, AfterRevision=9, BeforeEntries=len(before), AfterEntries=len(after),
               NetRemoved=len(before)-len(after), RawRemovedOccurrences=removed.total(), RawAddedOccurrences=added.total(),
               ReviewedExistingDiagnosticVariations=1, UnexplainedNewOccurrences=0,
               DNABefore=8368, DNAAfter=250, DNATargets=8118, DNATargetsRemaining=0,
               DNARemainingByGene=dict(gene_counts), EarlierStageTargetsRemaining=regressions,
               LocalizationTargetsRemaining=0, LocalizationDuplicates=sum(bool(r['Key']) for r in after),
               GraphicsMessagesBefore=8890, GraphicsMessagesAfter=sum(r['Category']=='Graphics / portrait source error' for r in after),
               AGOTPlusAssociatedBefore=8840, AGOTPlusAssociatedAfter=722,
               AGOTPlusPortraitScriptMessages=len(rows(HERE / 'agot-plus-remaining.csv')),
               ActiveMods=32, SameActiveModsAndOrder=True,
               Normalization='Only timestamps, args counters and source line numbers normalized. Paths/IDs/counts retained. Crown-event source path reviewed separately.')
assert summary['GraphicsMessagesAfter'] == 772 and summary['AGOTPlusPortraitScriptMessages'] == 12
save('comparison-summary.json', summary)
validation = dict(Revision=9, Status='PASS', EngineStartupChecked=True, FreshLogChecked=True, GameplayChecked=False,
                  PortraitAppearanceChecked=False, RunStartedAt=launch.isoformat(), LastErrorTime=after[-1]['Time'],
                  ManifestSHA256=capture['PatchManifestSHA256'], ErrorLogSHA256=error_meta['SHA256'],
                  SourceHashesMatched=119, DNASourceHashesMatched=219, RuntimeFilesMatched=72,
                  RuntimeFilesPredateLaunch=True, SameActiveModsAndOrder=True,
                  DNATargets=8118, DNATargetsRemaining=0, DeferredDNAMessages=250,
                  EarlierStageTargetsRemaining=regressions, LocalizationTargetsRemaining=0,
                  RawNewOccurrences=1, ReviewedExistingDiagnosticVariations=1, UnexplainedNewOccurrences=0,
                  NetRemoved=8118, Scope='Startup diagnostics only; appearance and inheritance in a campaign were not checked.',
                  Report='../../../docs/reports/ck3-agot-plus-fix-stage9-log-2026-09-19/README.md')
save('startup-validation.json', validation)
print(json.dumps(summary, ensure_ascii=False, indent=2))
print('PASS: all 8118 selected DNA diagnostics absent; all 250 deferred messages remain; only the known crown-event path variation.')
