"""Audit the captured revision-12 startup. Writes report artifacts only."""
from collections import Counter, defaultdict
import csv
import datetime as dt
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PATCH = REPO / 'AGOT_Submods/AGOT_PLUS_FIX'
PREVIOUS = HERE.parent / 'ck3-agot-plus-fix-stage10-log-2026-09-19'
SNAPSHOT = HERE / 'snapshot'
spec = importlib.util.spec_from_file_location('dna9', PATCH / 'tools/DNA-Stage9.py')
d = importlib.util.module_from_spec(spec); spec.loader.exec_module(d)
read, load, sha = d.read, d.load, d.sha


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream: return list(csv.DictReader(stream))


def save(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def export(name, data, fields):
    with (HERE / name).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(data)


def signature(row):
    text = re.sub(r'\[args#\d+\]', '[args#*]', row['Message'])
    text = re.sub(r'\b(near line|line):\s*\d+', r'\1: *', text, flags=re.I)
    text = re.sub(r'\bline\s+\d+', 'line *', text, flags=re.I)
    return row['Component']+' '+text


before, after = [rows(p / 'classified-entries.csv') for p in (PREVIOUS, HERE)]
old, new = [Counter(map(signature, r)) for r in (before, after)]
assert (len(before), len(after)) == (2192, 1848)
samples = {signature(r): r for r in before + after}
changes = [dict(BeforeCount=old[k], AfterCount=new[k], Difference=new[k]-old[k],
                Component=samples[k]['Component'], Message=samples[k]['Message'], Signature=k)
           for k in sorted(old.keys() | new.keys()) if old[k] != new[k]]
fields = list(changes[0])
for name, data in [('changed', changes), ('new', [r for r in changes if r['Difference'] > 0]),
                   ('disappeared', [r for r in changes if r['Difference'] < 0])]:
    export(name+'-messages.csv', data, fields)

# Preserve attribution only for exactly corresponding diagnostics. Source line
# annotations in Evidence are historical; LogLine is the new error.log position.
by_signature = defaultdict(list)
for row in after: by_signature[signature(row)].append(row)
prior_associated = rows(PREVIOUS / 'all-agot-plus-associated.csv')
associated, consumed, verification = [], Counter(), []
portrait_categories = {'portrait_templates', 'portrait_rules', 'accessory_entity', 'mesh_blendshape', 'mesh_duplicates'}
for row in prior_associated:
    key = signature(row)
    if consumed[key] < len(by_signature[key]):
        current = by_signature[key][consumed[key]]; consumed[key] += 1
        associated.append(dict(row, LogLine=current['Line'], Message=current['Message'],
                               OriginalOwner=current['Owner'], PriorLogLine=row['LogLine'],
                               EvidenceBasis='Previously reviewed source/symbol attribution; evidence line numbers precede revisions 11/12'))
    if row['Category'] in portrait_categories or row['Category'].startswith('variable_'):
        verification.append(dict(Stage=12 if row['Category'].startswith('variable_') else 11,
                                 Category=row['Category'], PriorLogLine=row['LogLine'],
                                 Component=row['Component'], Message=row['Message'], AfterCount=new[key]))
assert len(prior_associated) == 472 and len(associated) == 135
assert len(verification) == 361
export('all-agot-plus-associated.csv', associated, list(associated[0]))
export('fix-verification.csv', verification, list(verification[0]))
counts = Counter(r['Category'] for r in associated)
oldcounts = Counter(r['Category'] for r in prior_associated)
categories = [dict(Category=r['Category'], Label=r['Label'], Before=oldcounts[r['Category']],
                   After=counts[r['Category']], Removed=oldcounts[r['Category']]-counts[r['Category']])
              for r in rows(HERE.parent / 'agot-plus-remaining-inventory-2026-09-19/categories.csv')]
export('agot-plus-categories.csv', categories, list(categories[0]))
for category in sorted(counts):
    data = [r for r in associated if r['Category'] == category]
    export('remaining-'+category+'.csv', data, list(data[0]))
assert sum(r['AfterCount'] == 0 for r in verification if r['Stage'] == 11) == 207
assert sum(r['AfterCount'] > 0 for r in verification if r['Stage'] == 11) == 24
assert sum(r['Stage'] == 12 for r in verification) == 130
assert all(r['AfterCount'] == 0 for r in verification if r['Stage'] == 12)

removed, added = old-new, new-old
assert removed.total() == 345 and added.total() == 1
new_key = next(iter(added))
prefix = "jomini_eventmanager.cpp:428 Duplicated event ID 'agot_activity_commission_crown.0001' found."
old_keys = [k for k in removed if k.startswith(prefix)]
assert new_key.startswith(prefix) and len(old_keys) == 1
event_sources = load(PREVIOUS / 'duplicate-event-source-evidence.json')
for row in event_sources: assert sha(row['Path']) == row['SHA256']
save('duplicate-event-source-evidence.json', event_sources)
save('reviewed-diagnostic-variation.json', dict(Event='agot_activity_commission_crown.0001',
     Before=old_keys[0], After=new_key, BeforeCount=1, AfterCount=1, SourceHashesUnchanged=True,
     Interpretation='Known AGOT/Crowns of Westeros duplicate; reported path changed back to the already observed variant.'))
associated_removed = Counter(map(signature, prior_associated)) - Counter(map(signature, associated))
extra_removed = removed-associated_removed-Counter({old_keys[0]: 1})
assert extra_removed.total() == 7
extra = [dict(Occurrences=c, Component=samples[k]['Component'], Message=samples[k]['Message']) for k,c in extra_removed.items()]
export('other-disappeared.csv', extra, list(extra[0]))

regressions = {}
for stage in range(1,7):
    name = 'targeted-log-messages.csv' if stage == 1 else f'stage{stage}-targeted-log-messages.csv'
    regressions[str(stage)] = sum(new[signature(r)] > 0 for r in rows(PATCH / 'docs' / name))
for label, folder in [('7_8','stage8'), ('9','stage9'), ('10','stage10')]:
    regressions[label] = sum(new[signature(r)] > 0 for r in rows(HERE.parent / f'ck3-agot-plus-fix-{folder}-log-2026-09-19/fix-verification.csv'))
assert not any(regressions.values()), regressions
loc_keys = {r['Key'] for r in load(REPO / 'AGOT_Submods/AGOT_PLUS_RUS_CORRECT/docs/runtime-localization-additions.json')['Entries']}
assert len(loc_keys) == 386
assert not [r for r in after if (m := re.match(r'Unrecognized loc key ([^. ]+)\.',r['Message'])) and m[1] in loc_keys]
other_dna = [r for r in after if r['Component'].startswith('portraitcontext')]
assert len(other_dna) == 2 and all(r['Owner']=='AGOT Bookmarked' and 'props_right' in r['Message'] for r in other_dna)
export('other-mod-dna.csv', other_dna, list(other_dna[0]))

mods, oldmods = rows(HERE/'active-mods.csv'), rows(PREVIOUS/'active-mods.csv')
order = lambda data: [(str(r['Order']),r['Descriptor'],r['Path']) for r in data]
assert order(mods) == order(oldmods) and len(mods) == 32
assert load(SNAPSHOT/'dlc_load.json') == load(PREVIOUS/'snapshot/dlc_load.json')
capture = load(HERE/'snapshot-summary.json')
manifest = load(SNAPSHOT/'patch-source-manifest.json')
assert manifest['Revision'] == 12 and len(manifest['Files']) == 84
assert sha(SNAPSHOT/'patch-source-manifest.json') == capture['PatchManifestSHA256'] == sha(PATCH/'docs/source-manifest.json')
for stage in (11,12):
    static = load(SNAPSHOT/f'stage{stage}-validation.json')
    assert static['Status']=='PASS' and static['ManifestSHA256']==capture['PatchManifestSHA256']
for row in capture['Logs']: assert sha(SNAPSHOT/row['File'])==row['SHA256']
debug = read(SNAPSHOT/'debug.log')
start = re.search(r'^\[(\d\d:\d\d:\d\d)\].*Log system initialized\.',debug)[1]
error_meta = next(r for r in capture['Logs'] if r['File']=='error.log')
launch = dt.datetime.fromisoformat(error_meta['LastWriteTime']).replace(**dict(zip(('hour','minute','second'),map(int,start.split(':')))),microsecond=0)
mounts = [line for line in debug.splitlines() if 'Mounted Data:' in line and PATCH.as_posix() in line]
assert len(mounts)==1 and 'Quit: Quit from inside game' in debug
runtime = rows(HERE/'runtime-files.csv')
assert len(runtime)==92
for row in runtime:
    root = REPO/'AGOT_Submods'/row['Mod']; path = root/row['File']
    assert sha(path)==row['SHA256'] and d.native(path).stat().st_mtime < launch.timestamp()
    assert dt.datetime.fromisoformat(row['LastWriteTime']) < launch
    providers = [Path(m['Path']) for m in mods if d.native(Path(m['Path'])/row['File']).is_file()]
    assert providers[-1].resolve()==root.resolve()
source_rows=[]
roots=dict(AGOT_PLUS=d.PLUS,AGOT=d.AGOT)
for row in load(SNAPSHOT/'source-baseline.json'):
    path=roots[row['Catalog']]/row['File']
    assert sha(path)==row['SHA256'] and d.native(path).stat().st_mtime < launch.timestamp()
    source_rows.append(dict(row,LastWriteTime=dt.datetime.fromtimestamp(d.native(path).stat().st_mtime,launch.tzinfo).isoformat()))
assert len(source_rows)==139
export('source-hash-verification.csv',source_rows,list(source_rows[0]))
source_counts={}
archives=load(SNAPSHOT/'stage12-plan.json')['Archives']
for stage in (9,10,11,12):
    plan=load(SNAPSHOT/f'stage{stage}-plan.json'); pins=plan['Sources']
    pairs=[(r['Path'],r['SHA256']) for r in pins] if isinstance(pins,list) else list(pins.items())
    for path,digest in pairs:
        path=Path(path)
        if stage==11 and path.is_relative_to(PATCH) and path.relative_to(PATCH).as_posix() in archives:
            path=PATCH/'docs'/archives[path.relative_to(PATCH).as_posix()]
        assert sha(path)==digest,('Source changed',path)
    source_counts[str(stage)]=len(pairs)
save('debug-mount-evidence.json',dict(DebugLogSHA256=sha(SNAPSHOT/'debug.log'),RunStartedAt=launch.isoformat(),
     PatchMounts=mounts,QuitLines=[line for line in debug.splitlines() if 'Quit:' in line]))

# Three unconfirmed resource repairs correlate with >260-character local paths.
# This is evidence for investigation, not proof of the engine's I/O behavior.
assets=[]
for row in load(SNAPSHOT/'stage11-plan.json')['Files']:
    if not row['File'].endswith(('.mesh','.asset')): continue
    path=PATCH/row['File']
    assets.append(dict(File=row['File'],AbsolutePath=str(path),AbsolutePathLength=len(str(path)),
                       ExpectedHashMatches=sha(path)==row['OutputSHA256'],
                       RelatedDiagnosticsRemaining=0 if 'ironborn_legs_coa.asset' in row['File'] else (18 if row['File'].endswith('.mesh') else 1)))
save('resource-path-investigation.json',dict(Files=assets,ConfirmedCause=False,
     Hypothesis='The three remaining repair targets have paths above 260 characters; the repaired ironborn asset has a shorter path and its diagnostic disappeared. Engine loading of individual resources is not proven by mount/hash checks.'))
summary=dict(BeforeRevision=10,AfterRevision=12,BeforeEntries=len(before),AfterEntries=len(after),NetRemoved=344,
             RawRemovedOccurrences=345,RawAddedOccurrences=1,ReviewedExistingDiagnosticVariations=1,UnexplainedNewOccurrences=0,
             AGOTPlusAssociatedBefore=472,AGOTPlusAssociatedAfter=135,AGOTPlusAssociatedResolved=337,
             PortraitPackageTargets=231,PortraitPackageResolved=207,PortraitPackageRemaining=24,
             VariablePackageTargets=130,VariablePackageRemaining=0,SharedDarkSisterWarningsRemaining=0,
             EarlierStageTargetsRemaining=regressions,LocalizationTargetsRemaining=0,LocalizationDuplicates=1190,
             OtherDisappearedMessages=7,ActiveMods=32,SameActiveModsAndOrder=True,Categories=dict(counts),
             Normalization='Timestamps, args counters and source line numbers only; all paths and IDs preserved.')
save('comparison-summary.json',summary)
validation=dict(Revision=12,Status='PARTIAL',EngineStartupChecked=True,FreshLogChecked=True,GameplayChecked=False,
                PortraitAppearanceChecked=False,RunStartedAt=launch.isoformat(),LastErrorTime=after[-1]['Time'],
                ManifestSHA256=capture['PatchManifestSHA256'],ErrorLogSHA256=error_meta['SHA256'],
                RuntimeFilesMatched=92,RuntimeFilesPredateLaunch=True,SameActiveModsAndOrder=True,SourceHashesMatched=139,
                SourcePinsByStage=source_counts,PortraitPackageTargetsRemaining=24,VariablePackageTargetsRemaining=0,
                EarlierStageTargetsRemaining=regressions,UnexplainedNewOccurrences=0,
                IndividualResourceLoadingVerified=False,Scope='Startup and exit; 20 intended model repairs not confirmed, four texture duplicates intentionally deferred.',
                Report='../../../docs/reports/ck3-agot-plus-fix-stage12-log-2026-09-19/README.md')
save('startup-validation.json',validation)
print(json.dumps(summary,ensure_ascii=False,indent=2))
