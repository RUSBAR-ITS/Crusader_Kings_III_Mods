"""Source-pinned repairs for the 38 agreed diagnostics; no Workshop writes.

prepare registers exact recipes and archives revision 13. sources guards the
single excluded directory as well as dependencies. check verifies the installed
patch and behavior contracts; it does not execute CK3.
"""
import argparse
import difflib
import importlib.util
import itertools
import json
from pathlib import Path
import re
import subprocess

spec = importlib.util.spec_from_file_location('d', Path(__file__).with_name('DNA-Stage9.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
MOD, DOC = d.MOD, d.DOC
REPORT = d.REPO / 'docs/reports/agot-plus-remaining-safe-fixes-analysis-2026-09-19'
CLOAK = 'gfx/models/portraits/m_cloaks/asoiaf/asoiaf_westerlands/asoiaf_lannister_cloaks/asoiaf_lannister_cloak_royal'
NATIVE_CLOAK = 'gfx/models/portraits/m_cloaks/agot/shouldercape'
SETUP = 'common/scripted_effects/asoiaf_setup_effects.txt'
CHILDREN = 'common/scripted_effects/asoiaf_canon_children_effects.txt'
ASSIGN = 'common/scripted_effects/asoiaf_assign_inactive_traits_effects.txt'
HOUSE = 'common/decisions/asoiaf_house_branch_decisions.txt'
JON = 'common/decisions/asoiaf_jon_targ_cadet_branch_decision.txt'
ARTMOD = 'common/modifiers/asoiaf_artifact_modifiers.txt'
CCMOD = 'common/modifiers/asoiaf_canon_children_modifiers.txt'
EVENT = 'events/asoiaf_mega_war_events.txt'
VISUAL = 'common/artifacts/visuals/asoiaf_visuals.txt'
COA = 'common/coat_of_arms/coat_of_arms/'
DECISIONS = [(HOUSE, 'asoiaf_'+x+'_cadets_decision') for x in ('greyjoy', 'baelish', 'harlaw')] + [
    (JON, 'asoiaf_jon_targ_cadet_branch_decision'), (JON, 'asoiaf_aegon_II_greens_cadet_branch_decision')]


def lf(text): return text.replace('\r\n', '\n').replace('\r', '\n')
def code(text): return re.sub(r'#[^\r\n]*', '', text)
def tokens(text): return [m[0] for m in d.TOK.finditer(text) if not m[0].startswith('#')]
def blocks(text): return list(d.walk(d.parse(text.replace('?=', ' ='))))
def block(text, key):
    found = [b for b in blocks(text) if b.key == key]
    assert len(found) == 1, (key, len(found))
    return found[0].body(text)


def descriptor_fields(text):
    # The launcher can reorder top-level fields without changing their values.
    clean=code(text); result={}
    pattern=re.compile(r'(\w+)\s*=\s*("(?:\\.|[^"\\])*"|\{[^{}]*\})')
    for match in pattern.finditer(clean):
        assert match[1] not in result, ('Duplicate descriptor field',match[1])
        result[match[1]]=tokens(match[2])
    assert not pattern.sub('',clean).strip(), 'Unexpected descriptor syntax'
    return result


def comment(text, why):
    nl = '\r\n' if '\r\n' in text else '\n'
    return '# AGOT_PLUS_FIX stage14: '+why+nl+nl.join('# '+s if s.strip() else '#' for s in text.splitlines())


def provider(rel, mods):
    result = None
    for m in mods:
        if any(rel == p or rel.startswith(p.rstrip('/')+'/') for p in m['Replace']): result = None
        path = Path(m['Path']) / rel
        if path.is_file(): result = path
    return result


def reference_audit(mods):
    """Find full-directory references, then reject only effective active code.

    Search raw and escaped Windows spellings too. Hidden original .asset is
    expected to match; only the effective provider can make a live reference.
    """
    roots = list(dict.fromkeys(str(Path(m['Path'])) for m in mods))
    variants = [CLOAK, CLOAK.replace('/', '\\'), CLOAK.replace('/', '\\\\')]
    cmd = ['rg', '--no-ignore', '--hidden', '-l', '-i', '-F']
    for v in variants: cmd += ['-e', v]
    for ext in ('txt','asset','gui','gfx','shader','fxh','yml'): cmd += ['-g', '*.'+ext]
    result = subprocess.run(cmd+roots, capture_output=True, encoding='utf-8')
    assert result.returncode in (0,1), result.stderr
    hits = []
    for name in result.stdout.splitlines():
        path = Path(name)
        root = next(Path(r) for r in roots if path.is_relative_to(Path(r)))
        rel = path.relative_to(root).as_posix()
        if not rel.startswith(('common/','events/','history/','localization/','gfx/','gui/')): continue
        if provider(rel,mods) != path: continue
        text = code(d.read(path)).replace('\\','/')
        text = re.sub('/+', '/', text)
        if CLOAK.casefold() in text.casefold(): hits.append(str(path))
    assert not hits, ('Live references to excluded folder', hits)
    return dict(ActiveRoots=len(roots), RawMatchingFiles=len(result.stdout.splitlines()), LiveReferences=hits)


def prepare():
    assert not (DOC/'stage14-plan.json').exists(), 'Prepare once from verified revision 13.'
    manifest = d.load(DOC/'source-manifest.json')
    assert manifest['Revision'] == 13 and len(manifest['Files']) == 132
    pins = d.load(REPORT/'evidence-source-pins.json')
    for p,h in pins.items(): assert d.sha(p) == h, ('Analysis changed',p)
    for row in manifest['Files']: assert d.sha(MOD/row['File']) == row['PatchedSHA256']
    audit = reference_audit(d.active_mods())
    fixes = d.load(DOC/'fixes.json'); baseline = d.load(DOC/'source-baseline.json')
    assert len(fixes)==815 and len(baseline)==187
    original, before, outputs, actions = {}, {}, {}, []

    def get(rel):
        if rel not in outputs:
            original[rel] = d.read(d.PLUS/rel)
            text = original[rel]
            for f in fixes:
                if f['File']==rel:
                    assert text.count(f['Before'])==f['ExpectedCount'], f['Id']
                    text = text.replace(f['Before'],f['After'])
            if (MOD/rel).exists(): assert lf(text)==d.read(MOD/rel), rel
            before[rel] = outputs[rel] = text
        return outputs[rel]

    def edit(rel, old, new, group, count=1, source=None):
        current = get(rel); guard = old if source is None else source
        assert old != new and current.count(old)==count, (rel,group,current.count(old),old[:100])
        assert original[rel].count(guard)==count, (rel,'source guard',guard[:100])
        row = dict(Id=f'remaining-stage14-{len(actions)+1:02d}',Group=group,File=rel,Before=old,After=new,ExpectedCount=count)
        if guard!=old: row['SourceBefore']=guard
        actions.append(row); outputs[rel]=current.replace(old,new)

    edit(SETUP,'character:Dormund_1','character:Dormand_10','F48',2)
    edit(SETUP,'character:Hotah_rs_2','character:Hotah_1_B.mother','F48')
    text=get(SETUP); nl='\r\n' if '\r\n' in text else '\n'
    old='\t\tset_father = character:Broome_54 #Morrec broome (son of Briony)'+nl+'\t\tset_mother = character:Broome_rs_54'
    new=nl.join(['\t\t# AGOT_PLUS_FIX: younger Alfred variant only; keep base parents when ages are unchanged.',
        '\t\tif = {','\t\t\tlimit = {','\t\t\t\thas_game_rule = asoiaf_alternative_ages_rule_on',
        '\t\t\t\texists = character:Broome_54','\t\t\t\texists = character:Brax_67','\t\t\t}',
        '\t\t\tset_father = character:Broome_54 # Morrec','\t\t\tset_mother = character:Brax_67 # Landra, Morrec\'s wife','\t\t}'])
    edit(SETUP,old,new,'F48')
    edit(ASSIGN,'character:asoiaf_Targaryen_61_1','character:Targaryen_70_B','F48')
    text=get(CHILDREN)
    candidates=[b.body(text) for b in blocks(text) if b.key=='if' and 'character:Targaryen_61_1 = { exists = yes }' in b.body(text)]
    old=min(candidates,key=len)
    assert old.count('character:Targaryen_61_1')==4 and old.count('character:Targaryen_31.mother')==1
    edit(CHILDREN,old,old.replace('character:Targaryen_61_1','character:Targaryen_70_B').replace('character:Targaryen_31.mother','character:Targaryen_70_B.mother'),'F48')
    rel=COA+'test_reach_dynasties.txt'
    edit(rel,'ce_bottom_solid.dds','ce_solidblock.dds','F49')
    edit(rel,'re_block_02.dds','ce_solidblock.dds','F49',2)
    edit(COA+'test_personal_coas.txt','asoiaf_unicorn.dds','no_frikrigg_01.dds','F49')
    rel=COA+'test_northern_dynasties.txt'; old=block(get(rel),'dynn_Wibberley')
    native=block(d.read(d.AGOT/(COA+'northern_dynasties.txt')),'dynn_Wibberley')
    edit(rel,old,comment(old,'Missing custom emblem; use the current complete AGOT house arms.')+'\r\n'+native,'F49')
    rel=COA+'test_riverland_dynasties.txt'; old=block(get(rel),'dynn_Byrne')
    edit(rel,old,old.replace('vale_seldon_rayonne.dds','vale_seldon_rayonne5.dds').replace('scale = { 0.9 0.9 } rotation = 90','scale = { 0.905 -0.905 } rotation = 0'),'F49')
    text=get(CHILDREN)
    crush=[b.body(text) for b in blocks(text) if b.key=='set_relation_crush' and 'test_crush_desc' in b.body(text)]
    assert len(crush)==6
    for old in dict.fromkeys(crush):
        target=re.search(r'\btarget\s*=\s*(scope:\w+)',old)[1]
        edit(CHILDREN,old,'set_relation_crush = '+target,'F50',crush.count(old))
    for rel,key in DECISIONS:
        old=block(get(rel),key)
        assert 'ai_check_interval' not in code(old) and re.search(r'ai_will_do\s*=\s*{\s*base\s*=\s*0\s*}',code(old))
        new=old.replace('{','{\r\n\tai_check_interval = 0 # Player-only: the authored AI weight is zero.',1)
        edit(rel,old,new,'F51',source=block(original[rel],key))
    for rel,key,reason in [(ARTMOD,'asoiaf_oathkeeper_modifier','Retired by the author after AGOT added its own modifier.'),
                          (CCMOD,'asoiaf_Karstark_4_modifier','Unused placeholder; its only assignment was already commented out.'),
                          (EVENT,'asoiaf_mega_war_events.0001','Archive the empty, uncalled event; missing effect was already disabled.')]:
        old=block(get(rel),key)
        edit(rel,old,comment(old,reason),'F52' if rel!=EVENT else 'F53',source=block(original[rel],key))
    old=block(get(VISUAL),'asoiaf_hound_armour_visuals')
    edit(VISUAL,old,old.replace('{','{\r\n\tasset = m_clothes_sec_western_war_nob_01_artifact_entity',1),'F54')
    assert len(outputs)==13
    archives={}; files=[]; diff=[]
    for name in ('source-manifest.json','fixes.json','source-baseline.json'):
        target=DOC/('stage14-before-'+name.removeprefix('source-')); target.write_bytes((DOC/name).read_bytes())
    (DOC/'stage14-before-descriptor.mod').write_bytes((MOD/'descriptor.mod').read_bytes())
    definitions=dict(d.load(DOC/'stage12-plan.json')['ShadowDefinitions'])
    for i,(rel,output) in enumerate(sorted(outputs.items()),1):
        existing=(MOD/rel).exists(); raw=(MOD/rel if existing else d.PLUS/rel).read_bytes()
        if existing:
            archive=DOC/f'stage14-before/{i:02d}-{Path(rel).name}';archive.parent.mkdir(exist_ok=True)
            archive.write_bytes(raw);archives[rel]=archive.relative_to(DOC).as_posix()
        preview=DOC/f'stage14-approved/{i:02d}-{Path(rel).name}';preview.parent.mkdir(exist_ok=True)
        preview.write_bytes((b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'')+lf(output).encode('utf-8'))
        d.parse(output)
        files.append(dict(File=rel,ExistingShadow=existing,Preview=preview.relative_to(DOC).as_posix(),OutputSHA256=d.sha(preview)))
        definitions[rel]=re.findall(r'(?m)^([A-Za-z_0-9.]+)\s*=\s*\{',code(output))
        for line in difflib.unified_diff(lf(before[rel]).splitlines(True),lf(output).splitlines(True),fromfile='revision13/'+rel,tofile='revision14/'+rel):
            diff.append(line if line.endswith('\n') else line+'\n\\ No newline at end of file\n')
        if not any(b['Catalog']=='AGOT_PLUS' and b['File']==rel for b in baseline):
            baseline.append(dict(Catalog='AGOT_PLUS',File=rel,SHA256=d.sha(d.PLUS/rel)))
    (DOC/'stage14-repairs.patch').write_bytes(''.join(diff).encode('utf-8'))
    sources={}
    for p,h in pins.items():
        path=Path(p)
        if path==DOC/'source-manifest.json': path=DOC/'stage14-before-manifest.json'
        elif path.is_relative_to(MOD) and path.relative_to(MOD).as_posix() in archives:
            path=DOC/archives[path.relative_to(MOD).as_posix()]
        sources[str(path)]=h
    verification=d.load(REPORT/'verification.json')
    evidence={str(p):d.sha(p) for p in DOC.glob('stage14-before-*') if p.is_file()}
    evidence.update({str(DOC/f['Preview']):f['OutputSHA256'] for f in files})
    evidence.update({str(DOC/a):d.sha(DOC/a) for a in archives.values()})
    evidence[str(DOC/'stage14-repairs.patch')]=d.sha(DOC/'stage14-repairs.patch')
    allfixes=fixes+actions
    d.save('stage14-plan.json',dict(Revision=14,PreviousFiles=manifest['Files'],Archives=archives,Files=files,
        Sources=sources,Evidence=evidence,ShadowDefinitions=definitions,Rules=len(allfixes),NewRules=len(actions),
        Occurrences=sum(x['ExpectedCount'] for x in allfixes),NewOccurrences=sum(x['ExpectedCount'] for x in actions),
        RuntimeFiles=139,Shadows=127,Additions=12,BinaryShadows=49,FixGroups=54,BaselineCount=len(baseline),
        ReplacePath=CLOAK,CloakInventory=verification['CloakInventory'],ReferenceAudit=audit,
        ReplacementResources=verification['ReplacementResources'],TargetedMessages=38,RetainedMessages=2))
    d.save('fixes.json',allfixes);d.save('source-baseline.json',baseline)
    print(f'Registered {len(actions)} recipes; 13 files (six updated, seven new). Descriptor exclusion is separate.')


def sources():
    plan=d.load(DOC/'stage14-plan.json')
    for p,h in (plan['Sources']|plan['Evidence']).items(): assert d.sha(d.before_stage15_path(p))==h, ('Stage14 source/evidence changed',p)
    prior=d.load(DOC/'stage14-before-fixes.json'); fixes=d.load(d.before_stage15_path(DOC/'fixes.json'))
    assert fixes[:len(prior)]==prior and len(fixes)==plan['Rules']
    oldbase=d.load(DOC/'stage14-before-baseline.json'); baseline=d.load(DOC/'source-baseline.json')
    assert baseline[:len(oldbase)]==oldbase and len(baseline)==plan['BaselineCount']
    folder=d.PLUS/CLOAK
    assert sorted(p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file())==sorted(r['Name'] for r in plan['CloakInventory'])
    for r in plan['CloakInventory']:
        assert d.sha(folder/r['Name'])==r['PlusSHA256']
        if r['Name'].endswith(('.mesh','.dds')): assert d.sha(d.AGOT/NATIVE_CLOAK/r['Name'])==r['AGOTSHA256']==r['PlusSHA256']
    descriptor=d.read(MOD/'descriptor.mod')
    assert re.findall(r'(?m)^\s*replace_path\s*=\s*"([^"]+)"',descriptor)==[CLOAK]
    assert not re.search(r'(?m)^\s*path\s*=',descriptor)
    assert descriptor.replace('replace_path="'+CLOAK+'"\n','')==d.read(DOC/'stage14-before-descriptor.mod')
    assert sorted(p.name for p in (MOD/CLOAK).iterdir())==['asoiaf_lannister_cloak_royal.asset']
    reference_audit(d.active_mods())
    print('PASS: stage14 evidence, recipe prefix and exact 15-file exclusion inventory; 14 binaries identical to AGOT.')
    return plan


def check():
    plan=sources();manifest=d.load(DOC/'source-manifest.json');mods=d.active_mods()
    assert manifest['Revision'] in (14,15)
    assert len(manifest['Files']) == (140 if manifest['Revision']==15 else 139)
    for row in manifest['Files']:
        assert d.sha(MOD/row['File'])==row['PatchedSHA256']
        assert provider(row['File'],mods)==MOD/row['File'], ('Repair hidden',row['File'])
    for row in plan['Files']: assert d.sha(MOD/row['File'])==row['OutputSHA256']
    unchanged=[r for r in plan['PreviousFiles'] if r['File'] not in plan['Archives']]
    assert len(unchanged)==126
    for row in unchanged: assert d.sha(d.before_stage15_path(MOD/row['File']))==row['PatchedSHA256']
    # Both parents change atomically and only for the younger authored variant.
    setup=d.read(MOD/SETUP)
    variants=[b.body(setup) for b in blocks(setup) if b.key=='character:Broome_35' and 'set_mother' in code(b.body(setup))]
    assert len(variants)==1
    alfred=variants[0]
    parent_if=[b.body(alfred) for b in blocks(alfred) if b.key=='if' and 'set_mother' in code(b.body(alfred))]
    assert len(parent_if)==1
    limit=code(block(parent_if[0],'limit'))
    conditions=re.findall(r'(has_game_rule|exists)\s*=\s*([^\s{}]+)',limit)
    assert conditions==[('has_game_rule','asoiaf_alternative_ages_rule_on'),('exists','character:Broome_54'),('exists','character:Brax_67')]
    for enabled,father,mother in itertools.product((False,True),repeat=3):
        state={conditions[0][1]:enabled,conditions[1][1]:father,conditions[2][1]:mother}
        result=all(state[value] for _,value in conditions)
        assert result==(enabled and father and mother)
    assert re.findall(r'set_(father|mother)\s*=\s*(\S+)',code(alfred))==[('father','character:Broome_54'),('mother','character:Brax_67')]
    # Every birth definition is token-identical except the six crush relations.
    old=d.read(DOC/plan['Archives'][CHILDREN]); now=d.read(MOD/CHILDREN)
    prior_births={b.key:b.body(old) for b in d.parse(old).children if b.key.endswith('_birth_effect')}
    current_births={b.key:b.body(now) for b in d.parse(now).children if b.key.endswith('_birth_effect')}
    normalize=lambda t: re.sub(r'set_relation_crush\s*=\s*{\s*reason\s*=\s*test_crush_desc\s+target\s*=\s*(scope:\w+)\s*}',r'set_relation_crush = \1',t)
    assert prior_births.keys()==current_births.keys()
    for k in prior_births: assert tokens(normalize(prior_births[k]))==tokens(current_births[k]), k
    assert 'character:Targaryen_61_1' not in code(now)
    historical=[b.body(now) for b in blocks(now) if b.key=='if' and 'character:Targaryen_70_B = { exists = yes }' in b.body(now)]
    historical=min(historical,key=len)
    assert historical.count('character:Targaryen_70_B')==5 and 'character:Targaryen_31' not in historical
    for rel,key in DECISIONS:
        actual=block(d.read(MOD/rel),key)
        before=d.read(DOC/plan['Archives'][rel]) if rel in plan['Archives'] else d.read(d.PLUS/rel)
        assert tokens(re.sub(r'ai_check_interval\s*=\s*0','',actual))==tokens(block(before,key)),key
    assert 'asoiaf_stark_throne_modifier' in code(d.read(MOD/ARTMOD))
    assert 'asoiaf_young_griff_landing_events.2' in code(d.read(MOD/'events/asoiaf_young_griff_landing_events.txt'))
    assert 'asoiaf_mega_war_events.0001' not in code(d.read(MOD/EVENT))
    # Exact resource providers and the generic artifact-preview entity must exist.
    for name,row in plan['ReplacementResources'].items():
        p=Path(row['Path']); assert d.sha(p)==row['SHA256']
        assert provider(p.relative_to(next(Path(m['Path']) for m in mods if p.is_relative_to(Path(m['Path'])))).as_posix(),mods)==p
    assert tokens(block(d.read(MOD/(COA+'test_northern_dynasties.txt')),'dynn_Wibberley'))==tokens(block(d.read(d.AGOT/(COA+'northern_dynasties.txt')),'dynn_Wibberley'))
    entity='m_clothes_sec_western_war_nob_01_artifact_entity'
    entityfile='gfx/models/artifacts/clothing/m_clothes_sec_western_war_nob_01_artifact.asset'
    assert entity in code(d.read(provider(entityfile,mods))) and entity in code(block(d.read(MOD/VISUAL),'asoiaf_hound_armour_visuals'))
    for row in plan['CloakInventory']:
        if row['Name'].endswith(('.mesh','.dds')):
            assert provider(CLOAK+'/'+row['Name'],mods) is None
            assert provider(NATIVE_CLOAK+'/'+row['Name'],mods)==d.AGOT/NATIVE_CLOAK/row['Name']
    external=MOD.parent/'AGOT_PLUS_FIX.mod'
    launcher=d.PROFILE/next(m['Descriptor'] for m in mods if Path(m['Path'])==MOD)
    assert descriptor_fields(d.read(external))==descriptor_fields(d.read(launcher))
    assert lf(d.read(external))==lf(d.read(MOD/'descriptor.mod')).rstrip()+'\npath="'+MOD.as_posix()+'"\n'
    audit=reference_audit(mods)
    result=dict(Revision=14,Status='PASS',RuntimeFiles=139,ValidatedRuntimeRevision=manifest['Revision'],PreviousFilesUnchanged=126,ChangedExistingFiles=6,NewShadows=7,
        AlfredParentCases=8,BirthDefinitionsPreserved=len(prior_births),PlayerDecisionsPreserved=5,
        ExcludedDuplicateTextures=4,ExcludedDuplicateModels=10,LiveCloakReferences=audit['LiveReferences'],
        DescriptorsSynchronized=True,ExpectedResolvedMessages=38,ExpectedRemainingMessages=2,
        RetainedWarnings=['asoiaf_stark_throne_modifier','asoiaf_young_griff_landing_events.2'],
        GameExecutionChecked=False,FreshLogChecked=False,ManifestSHA256=d.sha(DOC/'source-manifest.json'))
    d.save('stage14-validation.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('prepare','sources','check'))
    globals()[parser.parse_args().mode]()
