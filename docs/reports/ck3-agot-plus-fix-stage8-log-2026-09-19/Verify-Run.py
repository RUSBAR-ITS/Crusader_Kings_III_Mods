"""Compare the captured startup with revision 6; never changes game files."""
import collections
import csv
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PATCH = REPO/'AGOT_Submods/AGOT_PLUS_FIX'
PREVIOUS = HERE.parent/'ck3-agot-plus-fix-stage6-log-2026-09-19'
HISTORY = HERE.parent/'agot-plus-character-history-analysis-2026-09-19'
SNAPSHOT = HERE/'snapshot'


def read(path): return Path(path).read_text(encoding='utf-8-sig')
def load(path): return json.loads(read(path))
def rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()
def save(name, obj): (HERE/name).write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
def export(name, data, fields):
    with (HERE/name).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(data)


def signature(row):
    message = re.sub(r'\[args#\d+\]', '[args#*]', row['Message'])
    message = re.sub(r'\b(near line|line):\s*\d+', r'\1: *', message, flags=re.I)
    message = re.sub(r'\bline\s+\d+', 'line *', message, flags=re.I)
    return row['Component']+' '+message


before, after = [rows(p/'classified-entries.csv') for p in (PREVIOUS,HERE)]
old, new = [collections.Counter(map(signature, data)) for data in (before,after)]
samples = {signature(row): row for row in before+after}
changes = []
for key in sorted(old.keys() | new.keys()):
    if old[key] == new[key]: continue
    sample = samples[key]
    changes.append(dict(BeforeCount=old[key],AfterCount=new[key],Difference=new[key]-old[key],
                        Category=sample['Category'],Owner=sample['Owner'],ExampleLine=sample['Line'],
                        Component=sample['Component'],Message=sample['Message'],Signature=key))
fields = ['BeforeCount','AfterCount','Difference','Category','Owner','ExampleLine','Component','Message','Signature']
for name, data in [('changed',changes),('new',[r for r in changes if r['Difference']>0]),
                   ('disappeared',[r for r in changes if r['Difference']<0])]:
    export(name+'-messages.csv',data,fields)

# Targets were selected in the previous analyses, not inferred from disappearance.
prior_direct = rows(PREVIOUS/'agot-plus-remaining.csv')
targets = [('Stage7_history',r) for r in prior_direct if r['IssueClass'] in ('Character_history','Secondary_PostValidate')]
targets += [('Stage8_scripts',r) for r in rows(PATCH/'docs/stage8-targeted-log-messages.csv')]
donor_ids = {r['Character'] for r in rows(HISTORY/'character-links.csv') if int(r['AppearanceDonorSites'])>0}
for row in before:
    match = re.fullmatch(r'Referencing non-existent character in script link character:(\w+)',row['Message'])
    if match and match[1] in donor_ids:
        targets.append(('Stage7_donor_links',dict(row,LogLine=row['Line'])))
    if re.match(r"Variable 'asoiaf_canon_children_Targaryen_(98|99|100|101)_born_variable' is used but is never set\.",row['Message']):
        targets.append(('Stage8_birth_variables',dict(row,LogLine=row['Line'])))
verification = []
for group, row in targets:
    key = signature(row)
    verification.append(dict(Group=group,BeforeLogLine=row['LogLine'],Component=row['Component'],Message=row['Message'],
                             PresentBefore=old[key]>0,AfterCount=new[key]))
export('fix-verification.csv',verification,['Group','BeforeLogLine','Component','Message','PresentBefore','AfterCount'])
counts = dict(collections.Counter(r['Group'] for r in verification))
assert counts == dict(Stage7_history=104,Stage8_scripts=25,Stage7_donor_links=80,Stage8_birth_variables=8), counts
assert len(verification)==217 and all(r['PresentBefore'] and r['AfterCount']==0 for r in verification)
assert collections.Counter(signature(row) for _,row in targets) == old-new

regressions = {}
for stage in range(1,7):
    file = 'targeted-log-messages.csv' if stage==1 else f'stage{stage}-targeted-log-messages.csv'
    regressions[str(stage)] = sum(new[signature(r)]>0 for r in rows(PATCH/'docs'/file))
assert not any(regressions.values()), regressions
localization = load(REPO/'AGOT_Submods/AGOT_PLUS_RUS_CORRECT/docs/runtime-localization-additions.json')['Entries']
loc_keys = {entry['Key'] for entry in localization}
loc_remaining = [r for r in after if (m:=re.match(r'Unrecognized loc key ([^. ]+)\.',r['Message'])) and m[1] in loc_keys]
assert len(loc_keys)==386 and not loc_remaining

oldmods, mods = [rows(p/'active-mods.csv') for p in (PREVIOUS,HERE)]
order = lambda data: [(r['Order'],r['Descriptor'],r['Path']) for r in data]
assert order(oldmods)==order(mods) and len(mods)==32
assert load(SNAPSHOT/'dlc_load.json')==load(PREVIOUS/'snapshot/dlc_load.json')
capture = load(HERE/'snapshot-summary.json')
manifest = load(SNAPSHOT/'patch-source-manifest.json')
assert manifest['Revision']==8 and len(manifest['Files'])==45
assert capture['PatchManifestSHA256']==sha(SNAPSHOT/'patch-source-manifest.json')==sha(PATCH/'docs/source-manifest.json')
for item in capture['Logs']:
    assert sha(SNAPSHOT/item['File'])==item['SHA256']
for stage in (7,8):
    result = load(SNAPSHOT/f'stage{stage}-static-validation.json')
    assert result['Status']=='PASS' and result['ManifestSHA256']==capture['PatchManifestSHA256']

debug = read(SNAPSHOT/'debug.log')
start_time = re.search(r'^\[(\d\d:\d\d:\d\d)\].*Log system initialized\.',debug)[1]
error_meta = next(r for r in capture['Logs'] if r['File']=='error.log')
launch = dt.datetime.fromisoformat(error_meta['LastWriteTime']).replace(**dict(zip(('hour','minute','second'),map(int,start_time.split(':')))),microsecond=0)
mounts = [line for line in debug.splitlines() if 'Mounted Data:' in line]
patch_mounts = [line for line in mounts if PATCH.as_posix() in line]
assert len(patch_mounts)==1 and 'Quit: Quit from inside game' in debug
runtime = rows(HERE/'runtime-files.csv')
assert len(runtime)==53 and all(dt.datetime.fromisoformat(r['LastWriteTime'])<launch for r in runtime)
for row in runtime:
    root = REPO/'AGOT_Submods'/row['Mod']
    path = root/row['File']
    assert sha(path)==row['SHA256'] and path.stat().st_mtime<launch.timestamp()
    providers = [Path(m['Path']) for m in mods if (Path(m['Path'])/row['File']).is_file()]
    assert providers[-1].resolve()==root.resolve()

roots = dict(AGOT_PLUS=Path('E:/SteamLibrary/steamapps/workshop/content/1158310/2950245430'),
             AGOT=Path('E:/SteamLibrary/steamapps/workshop/content/1158310/2962333032'))
source_rows = []
for entry in load(SNAPSHOT/'source-baseline.json'):
    path = roots[entry['Catalog']]/entry['File']
    assert sha(path)==entry['SHA256'] and path.stat().st_mtime<launch.timestamp()
    source_rows.append(dict(entry,LastWriteTime=dt.datetime.fromtimestamp(path.stat().st_mtime,launch.tzinfo).isoformat()))
assert len(source_rows)==100
export('source-hash-verification.csv',source_rows,['Catalog','File','SHA256','LastWriteTime'])
direct = rows(HERE/'agot-plus-remaining.csv')
outside_portraits = [r for r in direct if 'gfx/portraits/' not in r['Evidence']]
export('agot-plus-without-portraits.csv',outside_portraits,list(direct[0]))
links = [r for r in after if r['Component']=='history.cpp:644']
export('remaining-character-links.csv',links,list(after[0]))

summary = dict(BeforeRevision=6,AfterRevision=8,BeforeEntries=len(before),AfterEntries=len(after),
               NetRemoved=len(before)-len(after),AddedOccurrences=sum((new-old).values()),RemovedOccurrences=sum((old-new).values()),
               TargetGroups=counts,Targets=len(verification),TargetsRemaining=sum(r['AfterCount']>0 for r in verification),
               EarlierStagesRemaining=regressions,LocalizationTargets=386,LocalizationTargetsRemaining=0,
               ActiveMods=32,SameActiveModsAndOrder=True,AGOTPlusDirectBefore=len(prior_direct),AGOTPlusDirectAfter=len(direct),
               AGOTPlusOutsidePortraitsBefore=129,AGOTPlusOutsidePortraitsAfter=len(outside_portraits),
               CharacterLinkMessagesRemaining=len(links),
               BeforeWithoutDuplicatesOrGraphics=sum(not r['Key'] and r['Category'] not in ('Graphics / portrait source error','Save portrait / DNA compatibility') for r in before),
               AfterWithoutDuplicatesOrGraphics=sum(not r['Key'] and r['Category'] not in ('Graphics / portrait source error','Save portrait / DNA compatibility') for r in after),
               LocalizationDuplicates=sum(bool(r['Key']) for r in after),
               GraphicsMessages=sum(r['Category']=='Graphics / portrait source error' for r in after),
               Normalization='Header timestamps omitted; args counters and source line references normalized. Components, paths, IDs, messages and multiplicities retained. Localization duplicates also compared.')
assert summary['AddedOccurrences']==0 and summary['NetRemoved']==217 and not outside_portraits
save('comparison-summary.json',summary)
save('debug-mount-evidence.json',dict(DebugLogSHA256=sha(SNAPSHOT/'debug.log'),PatchMounts=patch_mounts,
     RunStartedAt=launch.isoformat(),QuitLines=[line for line in debug.splitlines() if 'Quit:' in line]))
validation = dict(Revision=8,Status='PASS',EngineStartupChecked=True,FreshLogChecked=True,GameplayChecked=False,
                  RunStartedAt=launch.isoformat(),LastErrorEntry='2026-09-19T07:00:50+07:00',
                  Scope='Startup diagnostics only. Births, bonding, portraits, decision clicks, regency and sieges were not exercised.',
                  ManifestSHA256=capture['PatchManifestSHA256'],ErrorLogSHA256=error_meta['SHA256'],
                  SourceHashesMatched=len(source_rows),RuntimeFilesMatched=len(runtime),RuntimeFilesPredateLaunch=True,
                  SameActiveModsAndOrder=True,DiagnosticGroupsAbsent=counts,EarlierStageTargetsRemaining=regressions,
                  LocalizationTargetsRemaining=0,NewDiagnosticOccurrences=0,RemovedDiagnosticOccurrences=217,
                  AGOTPlusSourceAttributedMessagesOutsidePortraits=0,AGOTPlusPortraitScriptMessages=12,
                  UnresolvedCharacterLinkMessages=15,Report='../../../docs/reports/ck3-agot-plus-fix-stage8-log-2026-09-19/README.md')
save('startup-validation.json',validation)
print(json.dumps(summary,ensure_ascii=False,indent=2))
print('PASS: revision 8 startup; all 217 target/related diagnostics absent; no added messages. Gameplay not checked.')
