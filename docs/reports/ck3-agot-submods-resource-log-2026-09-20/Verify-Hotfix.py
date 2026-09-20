"""Verify the post-run texture correction separately from the captured game log."""
from collections import Counter
from pathlib import Path
import csv
import hashlib
import json
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PATCH = REPO/'AGOT_Submods/AGOT_SUBMODS_FIX'
PROFILE = Path('C:/Users/RUSBAR/Documents/Paradox Interactive/Crusader Kings III')
GAME = Path('E:/SteamLibrary/steamapps/common/Crusader Kings III/game')
def load(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p, obj): p.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')

old = load(HERE/'snapshot/submods-source-manifest.json')
new = load(PATCH/'docs/source-manifest.json')
assert set(old) <= set(new)
changed = sorted(p for p in old if old[p] != new[p])
added = sorted(set(new)-set(old))
assert len(changed) == 5 and all(p.endswith('.asset') for p in changed)
assert set(added) == {'gfx/models/buildings/special/castamere/usf_castamere_neutral_'+s+'.dds'
                      for s in ('normal', 'properties')}
replacements, counts = [], Counter()
for rel in changed:
    previous = (HERE/'hotfix-before'/rel).read_bytes()
    assert hashlib.sha256(previous).hexdigest() == old[rel]['sha256']
    after = previous
    for token in sorted(set(re.findall(rb'"(gfx/[^"\r\n]+\.dds)"', previous))):
        name = token.decode('utf-8')
        if name.startswith('gfx/models/debug/no_'):
            value = 'usf_castamere_neutral_'+Path(name).name.removeprefix('no_')
        else:
            value = Path(name).name
        count = previous.count(b'"'+token+b'"')
        after = after.replace(b'"'+token+b'"', ('"'+value+'"').encode('utf-8'))
        replacements.append(dict(File=rel, Before=name, After=value, Fields=count))
        counts[name] += count
    assert after == (PATCH/rel).read_bytes(), 'Unexpected non-reference edit: '+rel
assert counts.total() == 20
for rel in added:
    source = GAME/'gfx/models/debug'/Path(rel).name.replace('usf_castamere_neutral_', 'no_')
    assert (PATCH/rel).read_bytes() == source.read_bytes()
    assert (PATCH/rel).stat().st_size == 176
for rel, item in new.items(): assert sha(PATCH/rel) == item['sha256']
assert load(PATCH/'docs/source-baseline.json') == load(HERE/'snapshot/submods-source-baseline.json')

with (HERE/'new-messages.csv').open(encoding='utf-8-sig', newline='') as f: messages = list(csv.DictReader(f))
missing = Counter()
for r in messages:
    if r['Component'] == 'pdxassetutil.cpp:1053':
        missing[re.fullmatch(r"Failed to find texture '([^']+)'", r['Message'])[1]] += int(r['Difference'])
    else:
        assert r['Component'] == 'virtualfilesystem.cpp:456'
        assert 'not found' in r['Message']
assert counts == missing, 'Every failed material reference must have an exact correction'
assert sum(int(r['Difference']) for r in messages) == 40

capture = load(HERE/'snapshot-summary.json')
for r in capture['Copies']:
    assert sha(HERE/'snapshot'/r['Snapshot']) == r['SnapshotSHA256']
    if r['Snapshot'].endswith('.log'):
        assert sha(r['Source']) == r['SourceSHA256'], 'Live log was changed or another run has started'
for prefix, name in [('plus','AGOT_PLUS_FIX'), ('plus-rus','AGOT_PLUS_RUS_CORRECT'), ('mde','AGOT_More_Dragon_Eggs_RUS_CORRECT')]:
    assert (REPO/'AGOT_Submods'/name/'docs/source-manifest.json').read_bytes() == (HERE/'snapshot'/f'{prefix}-source-manifest.json').read_bytes()
for i, registry in enumerate(load(HERE/'snapshot/dlc_load.json')['enabled_mods'], 1):
    assert (PROFILE/registry).read_bytes().replace(b'\r\n', b'\n') == (HERE/'snapshot'/f'descriptor-{i:02d}.mod').read_bytes()
assert load(PROFILE/'dlc_load.json') == load(HERE/'snapshot/dlc_load.json')
# Launcher rewrites indentation and top-level field order on launch.
sys.path.insert(0, str(PATCH/'tools'))
from ScriptBlocks import parse, semantic
def descriptor(p):
    return sorted(repr(semantic(n)) for n in parse(p.read_text(encoding='utf-8-sig')))
assert descriptor(PROFILE/'mod/AGOT_SUBMODS_FIX.mod') == descriptor(PATCH.parent/'AGOT_SUBMODS_FIX.mod')
validation = load(PATCH/'docs/validation.json')
resources = load(PATCH/'docs/resource-validation.json')
assert resources['status'] == 'PASS' and not resources['candidate_only']
result = dict(Status='APPLIED_STATICALLY_VERIFIED_AWAITING_GAME_RUN', ChangedFiles=changed,
               ChangedTextureFields=20, AddedFiles=added, AddedTextureBytes=352,
               Other80RuntimeFilesByteIdentical=len(old)-len(changed),
               AllExistingMeshAndDDSBytesUnchanged=True, Replacements=replacements,
               DistinctEthiopianDiffusePreserved=True, SourcePinsUnchanged=True,
               DescriptorsAndPlaysetUnchanged=True, LogsUnchanged=True,
               CapturedManifestSHA256=sha(HERE/'snapshot/submods-source-manifest.json'),
               CurrentManifestSHA256=sha(PATCH/'docs/source-manifest.json'),
               GeneralValidation=validation, ResourceChecks=resources['checks'],
               PredictedTextureMessagesRemoved=40, PredictedOtherMessagesRemaining=191,
               RuntimeRetestPending=True, VisualEquivalenceChecked=False)
save(HERE/'hotfix-validation.json', result)
summary = load(HERE/'comparison-summary.json')
save(PATCH/'docs/resource-runtime-validation.json', dict(
    Report='../../../docs/reports/ck3-agot-submods-resource-log-2026-09-20/README.md',
    SnapshotResult=summary, PostLaunchTextureFix={k:v for k,v in result.items() if k != 'GeneralValidation'}))
print(json.dumps({k:v for k,v in result.items() if k not in ('GeneralValidation','Replacements')}, ensure_ascii=False, indent=2))
