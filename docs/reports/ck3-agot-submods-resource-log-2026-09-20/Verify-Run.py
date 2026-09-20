"""Audit the frozen pre-hotfix run; preserve diagnostic multiplicity and exceptions."""
from collections import Counter, defaultdict, deque
from pathlib import Path
import ast
import csv
import hashlib
import json
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
OLD = HERE.parent / 'ck3-agot-submods-fix-stage1-log-2026-09-20'
PATCH = REPO / 'AGOT_Submods/AGOT_SUBMODS_FIX'

def read(p): return Path(p).read_text(encoding='utf-8-sig')
def load(p): return json.loads(read(p))
def rows(p):
    with Path(p).open(encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))
def save(name, value):
    (HERE/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
def export(name, data, fields=None):
    with (HERE/name).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields or list(data[0]), lineterminator='\n')
        w.writeheader(); w.writerows(data)
def signature(r):
    text = re.sub(r'\[args#\d+\]', '[args#*]', r['Message'])
    text = re.sub(r'\b(near line|line):\s*\d+', r'\1: *', text, flags=re.I)
    text = re.sub(r'\bline\s+\d+', 'line *', text, flags=re.I)
    return r['Component']+' '+text

before = rows(OLD/'classified-entries.csv')
after = rows(HERE/'classified-entries.csv')
old, new = [Counter(map(signature, data)) for data in (before, after)]
samples = {signature(r): r for r in before+after}
changes = [dict(Before=old[k], After=new[k], Difference=new[k]-old[k],
                Component=samples[k]['Component'], Message=samples[k]['Message'])
           for k in sorted(old.keys() | new.keys()) if old[k] != new[k]]
fields = ['Before', 'After', 'Difference', 'Component', 'Message']
export('changed-messages.csv', changes, fields)
export('new-messages.csv', [r for r in changes if r['Difference'] > 0], fields)
export('disappeared-messages.csv', [r for r in changes if r['Difference'] < 0], fields)

old_by_line = {r['Line']: r for r in before}
available = defaultdict(deque)
for r in after: available[signature(r)].append(r)
resources = []
for r in rows(HERE/'snapshot/submods-resource-disposition.csv'):
    original = old_by_line[r['Line']]
    assert original['Message'] == r['Message']
    q = available[signature(original)]
    current = q.popleft() if q else None
    resources.append(dict(**r, Observed='present' if current else 'absent',
                          CurrentLogLine=current['Line'] if current else '',
                          Component=original['Component']))
export('resource-verification.csv', resources)
resource_status = Counter((r['AppliedDisposition'], r['Observed']) for r in resources)

# The prior audit already mapped all first-stage signatures, including the
# two expanded COW religion diagnostics. Match their observed run if available.
available = defaultdict(deque)
for r in after: available[signature(r)].append(r)
script_results = []
for r in rows(OLD/'diagnostic-verification.csv'):
    original = old_by_line[r['CurrentLogLine']] if r['CurrentLogLine'] else dict(
        Component=r['OriginalComponent'], Message=r['OriginalFullMessage'])
    q = available[signature(original)]
    current = q.popleft() if q else None
    script_results.append(dict(**r, ResourceRunObserved='present' if current else 'absent',
                               ResourceRunLine=current['Line'] if current else ''))
export('scripts-variables-verification.csv', script_results)
script_status = Counter((r['status'], r['ResourceRunObserved']) for r in script_results)

tree = ast.parse(read(HERE.parent/'ck3-agot-plus-fix-stage14-log-2026-09-19/Verify-Run.py'))
specs = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == 'category_specs' for t in n.targets))
specs.append(('encoding', 'Кодировка скрипта: UTF-8 BOM', 0, ['lexer.cpp:306']))
components = {comp: key for key, _, _, comps in specs for comp in comps}
remaining = []
for r in after:
    if r['Component'] == 'pdx_localize.cpp:279': continue
    category = components.get(r['Component'], 'unclassified')
    if r['Component'] == 'pdx_persistent_reader.cpp:216' and 'Failed to read key reference:' in r['Message']:
        category = 'rule_references'
    remaining.append(dict(FineCategory=category, **r))
export('remaining-all.csv', remaining)
previous_categories = {r['Category']: int(r['After']) for r in rows(OLD/'remaining-categories.csv')}
categories = []
for key, label, _, _ in specs+[('unclassified', 'Новые типы сообщений', 0, [])]:
    selected = [r for r in remaining if r['FineCategory'] == key]
    categories.append(dict(Category=key, Label=label, Before=previous_categories[key],
                           After=len(selected), Change=len(selected)-previous_categories[key],
                           DistinctMessages=len({signature(r) for r in selected})))
    export('remaining-'+key+'.csv', selected, list(remaining[0]))
export('remaining-categories.csv', categories)
by_mod = []
for key in ['scripts', 'read_not_set', 'set_not_read']:
    for owner in sorted({r['owner'] for r in script_results if r['category'] == key}):
        chosen = [r for r in script_results if r['category'] == key and r['owner'] == owner]
        by_mod.append(dict(Category=key, Mod=owner,
                           Remaining=sum(r['ResourceRunObserved'] == 'present' for r in chosen),
                           Exceptions=sum(r['ResourceRunObserved'] == 'present' and r['status'] == 'exception' for r in chosen),
                           PriorFixedReappeared=sum(r['ResourceRunObserved'] == 'present' and r['status'] == 'expected_fixed' for r in chosen),
                           DeferredStillPresent=sum(r['ResourceRunObserved'] == 'present' and r['status'] == 'deferred' for r in chosen)))
export('scripts-variables-by-mod.csv', by_mod)

regressions = {}
plus = REPO/'AGOT_Submods/AGOT_PLUS_FIX'
for stage in range(1, 7):
    name = 'targeted-log-messages.csv' if stage == 1 else f'stage{stage}-targeted-log-messages.csv'
    regressions[str(stage)] = sum(new[signature(r)] > 0 for r in rows(plus/'docs'/name))
for label in ['stage8', 'stage9', 'stage10', 'stage13', 'stage14']:
    targets = rows(HERE.parent/f'ck3-agot-plus-fix-{label}-log-2026-09-19/fix-verification.csv')
    regressions[label] = sum(new[signature(r)] > 0 for r in targets)
variables = [r for r in rows(HERE.parent/'ck3-agot-plus-fix-stage12-log-2026-09-19/fix-verification.csv')
             if r['Category'].startswith('variable_')]
regressions['stage12_variables'] = sum(new[signature(r)] > 0 for r in variables)
regressions['mde'] = sum(new[signature(r)] > 0 for r in rows(HERE.parent/'ck3-agot-plus-fix-stage13-log-2026-09-19/mde-disappeared.csv'))
loc_keys = {r['Key'] for r in load(REPO/'AGOT_Submods/AGOT_PLUS_RUS_CORRECT/docs/runtime-localization-additions.json')['Entries']}
regressions['plus_localization'] = sum(bool((m := re.match(r'Unrecognized loc key ([^. ]+)\.', r['Message'])) and m[1] in loc_keys) for r in after)

capture = load(HERE/'snapshot-summary.json')
assert all(hashlib.sha256((HERE/'snapshot'/r['Snapshot']).read_bytes()).hexdigest() == r['SnapshotSHA256'] for r in capture['Copies'])
summary = dict(Started=capture['Started'], ExitLines=capture['ExitLines'],
               PreviousEntries=len(before), CurrentEntries=len(after), Removed=(old-new).total(), Added=(new-old).total(),
               ResourceTargetsGone=resource_status['applied_pending_game_log', 'absent'],
               ResourceTargetsStillPresent=resource_status['applied_pending_game_log', 'present'],
               ResourceExceptionsPresent=resource_status['retain', 'present'],
               ResourceExceptionsAbsent=resource_status['retain', 'absent'],
               EarlierScriptTargetsStillAbsent=script_status['expected_fixed', 'absent'],
               EarlierScriptTargetsReappeared=script_status['expected_fixed', 'present'],
               DeferredCowCreatorGone=script_status['deferred', 'absent'],
               DeferredCowCreatorStillPresent=script_status['deferred', 'present'],
               ScriptVariableExceptionsPresent=script_status['exception', 'present'],
               ScriptVariableExceptionsAbsent=script_status['exception', 'absent'],
               EncodingErrors=sum(r['FineCategory'] == 'encoding' for r in remaining),
               OtherDiagnostics=len(remaining), LocalizationDuplicates=len(after)-len(remaining),
               PriorFixRegressions=regressions, ActiveMods=capture['ActiveMods'],
               VerifiedRuntimeFiles=capture['RuntimeFiles'], Categories=categories,
               InCampaignBehaviorChecked=False, VisualEquivalenceChecked=False,
               Limitation='This snapshot precedes the texture-reference hotfix; new texture diagnostics remain in this run.')
save('comparison-summary.json', summary)
print(json.dumps({k: v for k, v in summary.items() if k != 'Categories'}, ensure_ascii=False, indent=2))
