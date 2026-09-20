"""Compare captured diagnostics with the approved inventory, preserving multiplicity."""
from collections import Counter, defaultdict, deque
from pathlib import Path
import ast
import csv
import hashlib
import json
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
OLD=HERE.parent/'ck3-agot-plus-fix-stage14-log-2026-09-19'
PATCH=REPO/'AGOT_Submods/AGOT_SUBMODS_FIX'
def read(p):return Path(p).read_text(encoding='utf-8-sig')
def load(p):return json.loads(read(p))
def rows(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def save(name,value):
    (HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def export(name,data,fields=None):
    if fields is None:fields=list(data[0])
    with (HERE/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(data)
def signature(r):
    text=re.sub(r'\[args#\d+\]','[args#*]',r['Message'])
    text=re.sub(r'\b(near line|line):\s*\d+',r'\1: *',text,flags=re.I)
    text=re.sub(r'\bline\s+\d+','line *',text,flags=re.I)
    return r['Component']+' '+text

before=rows(OLD/'classified-entries.csv');after=rows(HERE/'classified-entries.csv')
old,new=[Counter(map(signature,data)) for data in (before,after)]
samples={signature(r):r for r in before+after}
changes=[dict(Before=old[k],After=new[k],Difference=new[k]-old[k],Component=samples[k]['Component'],Message=samples[k]['Message']) for k in sorted(old.keys()|new.keys()) if old[k]!=new[k]]
fields=['Before','After','Difference','Component','Message']
export('changed-messages.csv',changes,fields)
export('new-messages.csv',[r for r in changes if r['Difference']>0],fields)
export('disappeared-messages.csv',[r for r in changes if r['Difference']<0],fields)

dispositions=rows(HERE/'snapshot/submods-diagnostic-disposition.csv')
old_by_line={r['Line']:r for r in before}
available=defaultdict(deque)
for r in after:available[signature(r)].append(r)
verification=[]
variations=[]
for r in dispositions:
    original=old_by_line[r['log_line']]
    key=signature(original)
    current=available[key].popleft() if available[key] else None
    # COW still contains both unchanged rhoynish bonuses. This run adds an
    # expanded-from parenthesis to the same two parser diagnostics. Constrain
    # matching to that reviewed issue, exact component and full relative path.
    if current is None and r['issue']=='cow-religion-opinion':
        for candidate, items in available.items():
            if items and items[0]['Component']==original['Component']:
                without_expansion=re.sub(r' \(expanded from file: common/buildings/yy_agotcities_special_buildings_westeros\.txt line: \*\)','',candidate)
                if without_expansion==key:
                    current=items.popleft()
                    variations.append(dict(PriorLogLine=r['log_line'],CurrentLogLine=current['Line'],Issue=r['issue'],Before=original['Message'],After=current['Message']))
                    break
    verification.append(dict(**r,Observed='present' if current else 'absent',CurrentLogLine=current['Line'] if current else '',CurrentFileOwner=current['Owner'] if current else '',OriginalComponent=original['Component'],OriginalFullMessage=original['Message']))
export('diagnostic-verification.csv',verification)
export('reviewed-diagnostic-variations.csv',variations,['PriorLogLine','CurrentLogLine','Issue','Before','After'])
status=Counter((r['status'],r['Observed']) for r in verification)
by_mod=[]
for owner in sorted({r['owner'] for r in verification}):
    s=Counter((r['status'],r['Observed']) for r in verification if r['owner']==owner)
    by_mod.append(dict(Mod=owner,ExpectedFixedGone=s['expected_fixed','absent'],ExpectedFixedStillPresent=s['expected_fixed','present'],ExceptionsPresent=s['exception','present'],ExceptionsAbsent=s['exception','absent'],DeferredPresent=s['deferred','present'],DeferredAbsent=s['deferred','absent']))
export('verification-by-mod.csv',by_mod)

# Read only the literal category specification from the earlier script. Do not
# execute its old-run assertions or reuse its expected counts.
tree=ast.parse(read(OLD/'Verify-Run.py'))
specs=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='category_specs' for t in n.targets))
specs.append(('encoding','Кодировка скрипта: UTF-8 BOM',0,['lexer.cpp:306']))
components={comp:key for key,_,_,comps in specs for comp in comps}
remaining=[]
for r in after:
    if r['Component']=='pdx_localize.cpp:279':continue
    category=components.get(r['Component'],'unclassified')
    if r['Component']=='pdx_persistent_reader.cpp:216' and 'Failed to read key reference:' in r['Message']:category='rule_references'
    remaining.append(dict(FineCategory=category,**r))
export('remaining-all.csv',remaining)
fine=[]
for key,label,previous_count,_ in specs+[('unclassified','Новые типы сообщений',0,[])]:
    chosen=[r for r in remaining if r['FineCategory']==key]
    fine.append(dict(Category=key,Label=label,Before=previous_count,After=len(chosen),Change=len(chosen)-previous_count,DistinctMessages=len({r['Message'] for r in chosen})))
    export('remaining-'+key+'.csv',chosen,list(remaining[0]))
export('remaining-categories.csv',fine)
by_category_mod=[]
for category in ['scripts','read_not_set','set_not_read']:
    for owner in sorted({r['owner'] for r in verification if r['category']==category}):
        chosen=[r for r in verification if r['category']==category and r['owner']==owner]
        by_category_mod.append(dict(Category=category,Mod=owner,Before=len(chosen),Gone=sum(r['Observed']=='absent' for r in chosen),After=sum(r['Observed']=='present' for r in chosen),Exceptions=sum(r['Observed']=='present' and r['status']=='exception' for r in chosen),Deferred=sum(r['Observed']=='present' and r['status']=='deferred' for r in chosen)))
export('target-categories-by-mod.csv',by_category_mod)

plus=REPO/'AGOT_Submods/AGOT_PLUS_FIX'
regressions={}
for stage in range(1,7):
    name='targeted-log-messages.csv' if stage==1 else f'stage{stage}-targeted-log-messages.csv'
    regressions[str(stage)]=sum(new[signature(r)]>0 for r in rows(plus/'docs'/name))
for label in ['stage8','stage9','stage10','stage13','stage14']:
    targets=rows(HERE.parent/f'ck3-agot-plus-fix-{label}-log-2026-09-19/fix-verification.csv')
    regressions[label]=sum(new[signature(r)]>0 for r in targets)
variables=[r for r in rows(HERE.parent/'ck3-agot-plus-fix-stage12-log-2026-09-19/fix-verification.csv') if r['Category'].startswith('variable_')]
regressions['stage12_variables']=sum(new[signature(r)]>0 for r in variables)
mde=rows(OLD/'mde-disappeared.csv') if (OLD/'mde-disappeared.csv').exists() else rows(HERE.parent/'ck3-agot-plus-fix-stage13-log-2026-09-19/mde-disappeared.csv')
regressions['mde']=sum(new[signature(r)]>0 for r in mde)
loc_keys={r['Key'] for r in load(REPO/'AGOT_Submods/AGOT_PLUS_RUS_CORRECT/docs/runtime-localization-additions.json')['Entries']}
regressions['plus_localization']=sum(bool((m:=re.match(r'Unrecognized loc key ([^. ]+)\.',r['Message'])) and m[1] in loc_keys) for r in after)

source_results=[]
pins=load(HERE.parent/'scripts-variables-analysis-2026-09-19/source-evidence-manifest.json')
# Accommodate the analysis manifest's path/hash record structure explicitly.
for item in pins:
    path=item.get('Path',item.get('path'))
    expected=item.get('SHA256',item.get('sha256'))
    assert path and expected, item
    digest=hashlib.sha256(Path(path).read_bytes()).hexdigest()
    source_results.append(dict(Path=path,SHA256=digest,Matches=expected.lower()==digest))
export('source-pin-verification.csv',source_results)
capture=load(HERE/'snapshot-summary.json')
assert all(hashlib.sha256((HERE/'snapshot'/r['Snapshot']).read_bytes()).hexdigest()==r['SnapshotSHA256'] for r in capture['Copies'])
summary=dict(PreviousEntries=len(before),CurrentEntries=len(after),RawRemoved=(old-new).total(),RawAdded=(new-old).total(),ReviewedSourceLocationVariations=len(variations),ResolvedAfterReview=(old-new).total()-len(variations),NewDiagnosticsAfterReview=(new-old).total()-len(variations),ExpectedFixedGone=status['expected_fixed','absent'],ExpectedFixedStillPresent=status['expected_fixed','present'],ExceptionsPresent=status['exception','present'],ExceptionsAbsent=status['exception','absent'],DeferredPresent=status['deferred','present'],DeferredAbsent=status['deferred','absent'],OtherDiagnostics=len(remaining),LocalizationDuplicates=len(after)-len(remaining),PriorFixRegressions=regressions,SourcePinsChecked=len(source_results),SourcePinsChanged=sum(not r['Matches'] for r in source_results),ActiveMods=capture['ActiveMods'],VerifiedRuntimeFiles=capture['RuntimeFiles'],Started=capture['Started'],ExitLines=capture['ExitLines'],Categories=fine,ByMod=by_mod,InCampaignBehaviorChecked=False,VisualEquivalenceChecked=False)
save('comparison-summary.json',summary)
print(json.dumps({k:v for k,v in summary.items() if k not in ['Categories','ByMod']},ensure_ascii=False,indent=2))
