"""Read-only investigation; all output stays in this report directory."""
from pathlib import Path
import hashlib
import difflib
import importlib.util
import json
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
WS=Path('E:/SteamLibrary/steamapps/workshop/content/1158310')
AGOT=WS/'2962333032'
USF=REPO/'AGOT_Submods/AGOT_SUBMODS_FIX'
PLUS=REPO/'AGOT_Submods/AGOT_PLUS_FIX'
sys.path.insert(0,str(USF/'tools'))
from ScriptBlocks import parse,one,walk,semantic,edit,comment
spec=importlib.util.spec_from_file_location('prior_inspect',HERE.parent/'scripts-variables-analysis-2026-09-19/Inspect-Sources.py')
idx=importlib.util.module_from_spec(spec);spec.loader.exec_module(idx)
idx.HERE=HERE
idx.LOG=HERE.parent/'ck3-agot-submods-fix-stage1-log-2026-09-20'
pins={}
def read(p):
    p=Path(p);raw=p.read_bytes()
    pins[p.as_posix()]=dict(SHA256=hashlib.sha256(raw).hexdigest(),Bytes=len(raw))
    return raw.decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
def save(name,value):
    (HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def extract(text,n):return text[n.start:n.end]
def line(text,n):return text.count('\n',0,n.start)+1

def crowns():
    p=AGOT/'common/scripted_effects/00_agot_artifact_crowns_effects.txt';text=read(p)
    names=['aegon_i_crown','aenys_crown','jaehaerys_crown','aegon_iii_crown','baelors_crown','aegon_iv_crown','maekars_crown','visenya_circlet']
    result=[];excerpts=[];proposals=[]
    for name in names:
        key='agot_create_artifact_'+name+'_effect';n=one(text,key)
        historical=one(text,'agot_create_artifact_'+name+'_historical_effect')
        body=extract(text,n)
        for item in [n,historical]:excerpts.append(f'# SOURCE {p.as_posix()}:{line(text,item)}\n'+extract(text,item))
        binding=n.one('$CREATOR$');creation=n.one('create_artifact');field=creation.one('creator')
        assert binding.one('save_scope_as').value=='creator' and field.value=='scope:creator'
        removals=[(binding.start-n.start,binding.end-n.start),(field.start-n.start,field.end-n.start)]
        candidate=body
        for a,b in sorted(removals,reverse=True):candidate=candidate[:a]+candidate[b:]
        candidate=candidate.replace(key,'review_create_artifact_'+name+'_without_creator_effect',1)
        rebuilt=one(candidate,'review_create_artifact_'+name+'_without_creator_effect')
        original_filtered=[]
        for child in n.value:
            if child is binding:continue
            if child is creation:
                original_filtered.append((child.key,child.op,[semantic(c) for c in child.value if c is not field]))
            else:original_filtered.append(semantic(child))
        assert tuple(original_filtered)==tuple(semantic(c) for c in rebuilt.value)
        result.append(dict(Function=key,Line=line(text,n),RequiredParameters=sorted(set(re.findall(r'\$([A-Z_]+)\$',body))),CreationFields=[c.key for c in creation.value],Template=creation.one('template').value,HistoricalLine=line(text,historical),HistoricalFixedCharacters=sorted(set(re.findall(r'character:[A-Za-z_0-9]+',extract(text,historical)))),CandidateSemanticDifference='Only creator binding and creator field removed; function renamed',ResidualCreatorReferences='creator' in candidate.lower().replace('without_creator','')))
        proposals.append(candidate)
    (HERE/'crown-effect-excerpts.txt').write_text('\n\n'.join(excerpts)+'\n',encoding='utf-8',newline='\n')
    (HERE/'PROPOSAL-ONLY-crown-effects.txt').write_text('# Analysis only. Not installed, not loaded by CK3.\n\n'+'\n\n'.join(proposals)+'\n',encoding='utf-8-sig',newline='\n')
    save('crown-functions.json',result)
    calls=[]
    for p in [PLUS/'common/on_action/agot_on_actions/test_title_on_actions.txt',USF/'events/decisions_events/rediscover_events.txt']:
        t=read(p)
        for parent in parse(t):
            for n in walk([parent]):
                if n.key in [r['Function'] for r in result]:
                    calls.append(dict(File=p.as_posix(),Line=line(t,n),Container=parent.key,Function=n.key,Arguments=extract(t,n)))
    save('current-crown-call-sites.json',calls)
    print('Functions:',len(result),'missing-argument calls:',len(calls))

def cow():
    t=read(USF/'common/buildings/yy_agotcities_special_buildings_westeros.txt')
    base=read(AGOT/'common/buildings/00_agot_special_buildings_westeros.txt')
    n=one(t,'agot_plankytown_01');original=one(base,'agot_plankytown_01')
    results=[]
    for key in ['character_modifier','county_holder_character_modifier']:
        a=n.one(key);b=original.one(key)
        expected=tuple((c.key.replace('rhoynish_religion_opinion','the_mother_religion_opinion'),c.op,c.value) for c in a.value)
        actual=tuple((c.key,c.op,c.value) for c in b.value)
        assert expected==actual
        results.append(dict(Scope=key,COWLine=line(t,a),AGOTLine=line(base,b),ExactModernModifierBlockMatchAfterRename=True))
    save('plankytown-modern-equivalence.json',results)
    events=[]
    for n in parse(t):
        calls=[v for v in walk([n]) if v.key=='trigger_event' and v.value=='agot_cities.5000']
        if calls:events.append(dict(Building=n.key,Line=line(t,n),Calls=[line(t,c) for c in calls],Definition=extract(t,n)))
    save('cow-missing-event-calls.json',events)
    print('Plankytown: both bonus blocks exactly match current AGOT after rename. Event callers:',[r['Building'] for r in events])

def evidence():
    queries={
        'cow_symbols':(r'harlaw_mines_[0-9]+|agot_cities\.5000|agot_castamere_ruins\.1000',''),
        'ten_towers':(r'\b2819\b|b_ten_towers|agot_ten_towers_01','history/'),
        'rhoynish_current':(r'the_mother_religion_opinion|rhoynish_religion_opinion','common/'),
    }
    for key,(pattern,prefix) in queries.items():
        found=[]
        for item in idx.candidates(pattern,prefix):
            text=read(item['path'])
            for number,raw in enumerate(text.splitlines(),1):
                if re.search(pattern,idx.uncomment(raw)):
                    found.append(dict(**item,line=number,text=raw))
        save(key+'-references.json',found)
    crown_data=json.loads((HERE/'crown-functions.json').read_text(encoding='utf-8'))
    functions={r['Function'] for r in crown_data}
    pattern='|'.join(sorted(functions))
    all_calls=[];definitions=[]
    for item in idx.candidates(pattern):
        if not item['relative'].startswith(('common/','events/')):continue
        text=read(item['path'])
        for top in parse(text):
            for n in walk([top]):
                if n.key in functions:
                    if n is top:definitions.append(dict(**item,line=line(text,n),function=n.key))
                    else:
                        args=[v.key for v in n.value] if isinstance(n.value,list) else []
                        all_calls.append(dict(**item,line=line(text,n),function=n.key,arguments=args,missing_creator='CREATOR' not in args))
    save('all-effective-crown-calls.json',all_calls)
    save('effective-crown-definitions.json',definitions)
    assert len(definitions)==8 and all(x['owner']=='A Game of Thrones' for x in definitions)
    assert sum(x['missing_creator'] for x in all_calls)==12
    templates=read(AGOT/'common/artifacts/templates/00_agot_historical_artifacts_crowns.txt')
    for row in crown_data:
        t=extract(templates,one(templates,row['Template']))
        assert 'creator' not in t.lower(),row['Template']
    for p in [AGOT/'common/religion/religion_types/00_agot_the_mother.txt',
              AGOT/'common/scripted_effects/00_agot_artifact_effects.txt',
              USF/'common/scripted_effects/00_lotd_artifact_creation_effects.txt']:
        read(p)
    print('Effective crown calls:',len(all_calls),'missing CREATOR:',sum(x['missing_creator'] for x in all_calls),'definitions:',len(definitions))

def cow_proposal():
    relative='common/buildings/yy_agotcities_special_buildings_westeros.txt'
    original=read(USF/relative)
    changes=[];removed=[]
    for top in parse(original):
        for n in walk([top]):
            if n.key=='rhoynish_religion_opinion':
                changes.append((n.start,n.start+len(n.key),'the_mother_religion_opinion'))
            if n.key=='on_complete' and any(x.key=='trigger_event' and x.value=='agot_cities.5000' for x in walk([n])):
                changes.append((n.start,n.end,comment(extract(original,n),'PROPOSAL ONLY: event agot_cities.5000 is absent; preserve building and working ruin restoration.')))
                removed.append((top.key,n))
    assert len(changes)==5 and len(removed)==3
    candidate=edit(original,changes)
    for before,after in zip(parse(original),parse(candidate)):
        expected=[n for n in before.value if not any(before.key==key and n.start==omitted.start for key,omitted in removed)]
        # Recursive AST normalization applies only the approved religion rename.
        def canonical(n):
            return (n.key.replace('rhoynish_religion_opinion','the_mother_religion_opinion'),n.op,[canonical(x) for x in n.value] if isinstance(n.value,list) else n.value)
        assert [canonical(n) for n in expected]==[semantic(n) for n in after.value],before.key
    assert 'trigger_event = agot_castamere_ruins.1000' in candidate
    diffs=list(difflib.unified_diff(original.splitlines(True),candidate.splitlines(True),fromfile='a/'+relative,tofile='b/'+relative))
    rel='common/on_action/cowagot_province_on_actions.txt'
    t=read(USF/rel);action=one(t,'harlaw_building_check_on_actions');effect=action.one('effect')
    missing=[n for n in effect.value if isinstance(n.value,list) and any(x.key=='add_special_building_slot' and x.value=='harlaw_mines_01' for x in walk([n]))]
    assert len(missing)==1 and missing[0].key=='if'
    n=missing[0]
    fixed=edit(t,[(n.start,n.end,comment(extract(t,n),'PROPOSAL ONLY: unavailable legacy mine; retain the Harlaw/Ten Towers branch and province history.'))])
    assert [semantic(x) for x in effect.value if x is not n]==[semantic(x) for x in one(fixed,action.key).one('effect').value]
    assert [semantic(x) for x in parse(t) if x.key!=action.key]==[semantic(x) for x in parse(fixed) if x.key!=action.key]
    diffs.extend(difflib.unified_diff(t.splitlines(True),fixed.splitlines(True),fromfile='a/'+rel,tofile='b/'+rel))
    (HERE/'PROPOSAL-ONLY-cow.patch').write_text(''.join(diffs),encoding='utf-8',newline='\n')
    save('proposal-validation.json',dict(Installed=False,RuntimeFilesModified=False,CrownFunctionsCompared=8,CrownCallSitesScanned=52,IncompleteCalls=12,CrownChanges='Only creator binding and field removed; original OWNER, artifact fields and marker blocks retained',COWExactModernBonusBlocks=2,COWCommentedMissingEventBlocks=3,COWCommentedUnavailableMineBranch=1,WorkingCastamereRestorationPreserved=True,OtherCOWBuildingFieldsAndOnActionsSemanticallyIdentical=True,InGameValidation=False))
    print('COW proposal: 2 exact ID replacements, 3 event blocks and 1 mine branch commented. Not installed.')

if __name__=='__main__':
    if sys.argv[1]=='index':print('Effective files:',len(idx.index()))
    elif sys.argv[1]=='search':idx.search(sys.argv[2],context=int(sys.argv[3]) if len(sys.argv)>3 else 0,prefix=sys.argv[4] if len(sys.argv)>4 else '')
    elif sys.argv[1]=='contracts':
        crowns();cow();save('source-evidence.json',pins)
    elif sys.argv[1]=='evidence':
        pins.update(json.loads((HERE/'source-evidence.json').read_text(encoding='utf-8')))
        evidence();save('source-evidence.json',pins)
    elif sys.argv[1]=='proposal':
        pins.update(json.loads((HERE/'source-evidence.json').read_text(encoding='utf-8')))
        cow_proposal();save('source-evidence.json',pins)
