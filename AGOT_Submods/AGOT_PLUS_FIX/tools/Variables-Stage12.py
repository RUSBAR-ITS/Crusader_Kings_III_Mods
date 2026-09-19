"""Register/check approved variable repairs. Only the PowerShell builder writes runtime files."""
import argparse
import difflib
import importlib.util
from itertools import product
from pathlib import Path
import re

spec = importlib.util.spec_from_file_location('dna9', Path(__file__).with_name('DNA-Stage9.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
MOD, DOC = d.MOD, d.DOC
REPORT = d.REPO / 'docs/reports/agot-plus-variable-analysis-2026-09-19'


def code(text):
    return re.sub(r'"(?:\\.|[^"\\])*"|#[^\r\n]*', lambda m: '' if m[0].startswith('#') else m[0], text)


def tokens(text):
    return [m[0] for m in d.TOK.finditer(text) if not m[0].startswith('#')]


def comment(text, reason):
    nl = '\r\n' if '\r\n' in text else '\n'
    indent = re.match(r'[\t ]*', text)[0]
    result = indent + '# AGOT_PLUS_FIX stage12: ' + reason + nl
    for line in text.splitlines(keepends=True):
        prefix = re.match(r'[\t ]*', line)[0]
        result += prefix + '# ' + line[len(prefix):]
    return result


def full_block(text, key):
    found = [b for b in d.walk(d.parse(text)) if b.key == key]
    assert len(found) == 1, (key, len(found))
    b = found[0]
    start = text.rfind('\n', 0, b.start) + 1
    assert not text[start:b.start].strip()
    end = b.end
    if text[end:end+2] == '\r\n': end += 2
    elif text[end:end+1] == '\n': end += 1
    return text[start:end]


def modifier_matches(text, values):
    """Evaluate only the boolean subset used by the eight repaired modifiers.

    Values stand for engine predicates; this checks rule/identity logic, not
    rendering, weights from other modifiers or CK3 scope resolution.
    """
    stream = iter(tokens(text))
    def block():
        result = []
        for key in stream:
            if key == '}':
                return result
            assert next(stream) == '='
            value = next(stream)
            result.append((key, block() if value == '{' else value))
        return result
    tree = block()
    def evaluate(items, mode='AND'):
        flags = []
        for key, value in items:
            if key == 'add':
                continue
            if isinstance(value, list):
                assert key in ('modifier', 'AND', 'OR', 'NOT', 'culture', 'any_equipped_character_artifact'), key
                flags.append(evaluate(value, key))
            else:
                assert (key, value) in values, ('Unmodelled predicate', key, value)
                flags.append(values[key, value])
        if mode == 'OR': return any(flags)
        if mode == 'NOT':
            assert len(flags) == 1
            return not flags[0]
        return all(flags)
    return evaluate(tree)


def portrait_contracts(plan):
    count, jon_blocks, guard_blocks = 0, 0, 0
    for row in plan['Files']:
        if '/portrait_modifiers/' not in row['File']: continue
        text = d.read(MOD / row['File'])
        previous = d.read(DOC / plan['Archives'][row['File']]) if row['ExistingShadow'] else d.read(d.PLUS / row['File'])
        # Conditions may change, but every mesh/accessory/morph selection stays identical.
        payload = lambda t: [tokens(b.body(t)) for b in d.walk(d.parse(t)) if b.key == 'dna_modifiers']
        assert payload(text) == payload(previous), ('Portrait payload changed', row['File'])
        for b in d.walk(d.parse(text)):
            if b.key != 'modifier': continue
            body = code(b.body(text))
            if 'is_Stark_7' in body:
                jon_blocks += 1
                clothing = 'asoiaf_new_clothes_north_rule_on' in body
                lordly = 'has_title' in body
                for native, identity, historical, dna, canon, title, clothes, heritage in product((False, True), repeat=8):
                    values = {('has_character_flag', 'is_Stark_7'): native,
                              ('has_inactive_trait', 'asoiaf_Stark_7_trait'): identity,
                              ('this', 'character:Stark_7'): historical,
                              ('has_game_rule', 'asoiaf_new_dnas_north_rule_on'): dna,
                              ('asoiaf_canon_children_enabled_trigger', 'yes'): canon,
                              ('has_game_rule', 'asoiaf_new_clothes_north_rule_on'): clothes,
                              ('has_cultural_pillar', 'heritage_first_man'): heritage}
                    for key in ('c_winterfell', 'd_winterfell', 'e_the_north'):
                        values['has_title', 'title:'+key] = title
                    expected = ((native or identity) and dna) or (identity and not historical and canon and not dna)
                    if lordly: expected = expected and title
                    if clothing: expected = (native or identity) and clothes and heritage
                    assert modifier_matches(body, values) == expected, (row['File'], values)
                    count += 1
            elif 'kingsguard_armor' in body:
                guard_blocks += 1
                helmet_required = 'portrait_wear_helmet_trigger' in body
                for male, member, equipped, clothes, helmet, armor, military in product((False, True), repeat=7):
                    values = {('is_male', 'yes'): male, ('has_trait', 'kingsguard'): member,
                              ('has_variable', 'kingsguard_armor'): equipped,
                              ('has_game_rule', 'asoiaf_new_clothes_crownlands_rule_on'): clothes,
                              ('portrait_wear_helmet_trigger', 'yes'): helmet,
                              ('portrait_wear_armor_trigger', 'yes'): armor,
                              ('has_character_flag', 'need_military_outfit'): military}
                    expected = male and (member or equipped) and clothes
                    if helmet_required: expected = expected and (helmet or military) and (armor or military)
                    assert modifier_matches(body, values) == expected, (row['File'], values)
                    count += 1
    assert (jon_blocks, guard_blocks, count) == (5, 3, 1664)
    return count


def prepare():
    assert not (DOC / 'stage12-plan.json').exists(), 'Prepare once from verified revision 11.'
    manifest = d.load(DOC / 'source-manifest.json')
    assert manifest['Revision'] == 11 and len(manifest['Files']) == 82
    for row in manifest['Files']:
        assert d.sha(MOD / row['File']) == row['PatchedSHA256'], row['File']
    pins = d.load(REPORT / 'source-pins.json')
    for p, h in pins.items(): assert d.sha(p) == h, ('Analysis source changed', p)
    decisions = d.load(REPORT / 'decisions.json')
    assert len(decisions) == 65
    fixes = d.load(DOC / 'fixes.json')
    assert len(fixes) == 745
    baseline = d.load(DOC / 'source-baseline.json')
    definitions = dict(d.load(DOC / 'stage11-plan.json')['ShadowDefinitions'])
    original, before, outputs, actions = {}, {}, {}, []

    def get(rel):
        if rel not in outputs:
            original[rel] = d.read(d.PLUS / rel)
            before[rel] = d.read(MOD / rel) if (MOD / rel).is_file() else original[rel]
            outputs[rel] = before[rel]
        return outputs[rel]

    def edit(rel, old, new, group, count=1, source=None):
        assert old and old != new
        current = get(rel)
        assert current.count(old) == count, (rel, group, 'current', current.count(old), count, old[:100])
        guard = source if source is not None else old
        assert original[rel].count(guard) == count, (rel, group, 'source', original[rel].count(guard), count)
        row = dict(Id=f'variables-stage12-{len(actions)+1:02d}', Group=group, File=rel,
                   Before=old, After=new, ExpectedCount=count)
        if guard != old: row['SourceBefore'] = guard
        actions.append(row)
        outputs[rel] = current.replace(old, new)

    loc = 'common/customizable_localization/asoiaf_historical_character_loc.txt'
    for row in decisions:
        if row['Group'] == 'V01':
            edit(loc, 'has_variable = '+row['Symbol'], 'has_inactive_trait = '+row['Replacement'], 'F39')
    portrait = 'gfx/portraits/portrait_modifiers/'
    for file, count in [('asoiaf_character_custom_flags.txt', 2), ('asoiaf_hairs_custom_flags.txt', 2), ('asoiaf_beards_custom_flags.txt', 1)]:
        edit(portrait+file, 'has_character_flag = is_jon_snow', 'has_character_flag = is_Stark_7', 'F40', count)
    hair = portrait+'asoiaf_hairs_custom_flags.txt'
    nl = '\r\n' if '\r\n' in get(hair) else '\n'
    # Two previously unguarded branches: lordly hair AND and ordinary hair OR.
    line = '\t'*6+'has_character_flag = is_Stark_7'+nl
    edit(hair, line, line+'\t'*6+'has_game_rule = asoiaf_new_dnas_north_rule_on'+nl, 'F40',
         source=line.replace('is_Stark_7','is_jon_snow'))
    line = '\t'*5+'has_character_flag = is_Stark_7'+nl
    replacement = ('\t'*5+'AND = {'+nl+'\t'*6+'has_character_flag = is_Stark_7'+nl+
                   '\t'*6+'has_game_rule = asoiaf_new_dnas_north_rule_on'+nl+'\t'*5+'}'+nl)
    # Anchor the five-tab line to avoid matching the six-tab branch just edited.
    edit(hair, nl+line, nl+replacement, 'F40', source=nl+line.replace('is_Stark_7','is_jon_snow'))
    for file in ('asoiaf_legwear_armour.txt','asoiaf_headgear_situational.txt','asoiaf_clothes_situational.txt'):
        edit(portrait+file, 'has_variable = kingsguard_armour', 'has_variable = kingsguard_armor', 'F41')
    overwrite = 'common/scripted_effects/asoiaf_agot_overwrite_effects.txt'
    nl = '\r\n' if '\r\n' in get(overwrite) else '\n'
    for name in ('color','color_grading'):
        edit(overwrite, 'name = '+name+nl, 'name = primary_'+name+nl, 'F42', 7)
    assignment = 'common/scripted_effects/asoiaf_assign_inactive_traits_effects.txt'
    for row in decisions:
        if row['Group'] == 'V05':
            lines = [line for line in get(assignment).splitlines(keepends=True) if re.search(r'\bset_global_variable\s*=\s*'+re.escape(row['Symbol'])+r'\b',code(line))]
            assert len(lines) == 1
            old = lines[0]
            edit(assignment, old, comment(old, 'Unused historical birth marker; preserve identity and descendant chains.'), 'F43')
    old = full_block(get(overwrite), 'title:h_the_iron_throne')
    edit(overwrite, old, comment(old, 'Retired title metadata has no readers; keep baby_snow creation and duplicate-birth protection.'), 'F44')
    artifacts = 'common/scripted_effects/asoiaf_scripted_effects_artifacts.txt'
    for name in ('asoiaf_is_krakenfall','asoiaf_is_needle','asoiaf_is_red_vipers_spear'):
        lines = [line for line in get(artifacts).splitlines(keepends=True) if re.search(r'\bname\s*=\s*'+name+r'\b',code(line))]
        expected = 1 if name.endswith('spear') else 2
        assert len(lines) == expected and len(set(lines)) == 1
        edit(artifacts, lines[0], comment(lines[0], 'Unused artifact marker; keep creation, visuals, properties and history.'), 'F45', expected)
    text = get(artifacts)
    blocks = [b for b in d.walk(d.parse(text)) if b.key == 'set_variable' and re.search(r'\bname\s*=\s*dark_sister_artifact\b',code(b.body(text)))]
    assert len(blocks) == 1
    b = blocks[0]; start = text.rfind('\n',0,b.start)+1
    old = text[start:b.end]+'\r\n'
    edit(artifacts, old, comment(old, 'Unused variable only; retain the distinct Dark Sister accessory ID. LOTD is handled separately.'), 'F45')
    for rel, key, reason in [
        ('common/on_action/agot_on_actions/test_title_on_actions.txt','asoiaf_on_title_inheritance_robert_usurper_nickname',
         'Archive already unsubscribed on_action; restoring the Usurper scenario needs a separate design.'),
        ('common/scripted_effects/asoiaf_targaryen_invasion_claimants_effects.txt','asoiaf_targaryen_invasion_claimants_spawn_aegon_effect',
         'Archive uncalled incomplete multiple-claimant effect; no defined caller supplies its claimant scope.')]:
        old = full_block(get(rel), key)
        edit(rel, old, comment(old,reason), 'F46', source=full_block(original[rel],key))
    assert len(outputs) == 12 and len(actions) == 70
    # All candidates and upstream/intermediate guards are ready before registration.
    for name in ('source-manifest.json','fixes.json','source-baseline.json'):
        (DOC/('stage12-before-'+name.removeprefix('source-'))).write_bytes((DOC/name).read_bytes())
    archives, files, diff = {}, [], []
    for i, (rel, output) in enumerate(sorted(outputs.items()),1):
        existing = (MOD/rel).is_file()
        raw = (MOD/rel).read_bytes() if existing else (d.PLUS/rel).read_bytes()
        if existing:
            archive = DOC/f'stage12-before/{i:02d}-{Path(rel).name}'
            archive.parent.mkdir(parents=True,exist_ok=True); archive.write_bytes(raw)
            archives[rel] = archive.relative_to(DOC).as_posix()
        preview = DOC/f'stage12-approved/{i:02d}-{Path(rel).name}'
        preview.parent.mkdir(parents=True,exist_ok=True)
        preview.write_bytes((b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'')+output.encode('utf-8'))
        d.parse(output)
        definitions[rel] = re.findall(r'(?m)^([A-Za-z_0-9.]+)\s*=\s*\{',code(output))
        files.append(dict(File=rel,ExistingShadow=existing,Preview=preview.relative_to(DOC).as_posix(),OutputSHA256=d.sha(preview)))
        diff.extend(difflib.unified_diff(before[rel].splitlines(keepends=True),output.splitlines(keepends=True),fromfile='revision11/'+rel,tofile='revision12/'+rel))
        if not any(b['Catalog']=='AGOT_PLUS' and b['File']==rel for b in baseline):
            baseline.append(dict(Catalog='AGOT_PLUS',File=rel,SHA256=d.sha(d.PLUS/rel)))
    all_fixes = fixes+actions
    for rel, output in outputs.items():
        expected = original[rel]
        for fix in all_fixes:
            if fix['File']==rel:
                assert expected.count(fix['Before'])==fix['ExpectedCount'], fix['Id']
                expected=expected.replace(fix['Before'],fix['After'])
        assert expected==output, rel
    pinned = {}
    for path, digest in pins.items():
        p = Path(path)
        if p.is_relative_to(MOD) and p.relative_to(MOD).as_posix() in archives:
            p=DOC/archives[p.relative_to(MOD).as_posix()]
        pinned[str(p)]=digest
    # Preserve the already modified, unrelated user files as well.
    protected={str(p):d.sha(p) for p in [d.REPO/'DICM_RBE/common/modifiers/DICM_RBE_modifiers.txt',
        d.REPO/'DICM_RBE/localization/english/DICM_RBE_modifiers_l_english.yml',
        d.REPO/'DICM_RBE/localization/russian/DICM_RBE_modifiers_l_russian.yml']}
    for name in ('decisions.json','references.json','supporting-references.json','born-marker-audit.json'):
        (DOC/('stage12-'+name)).write_bytes((REPORT/name).read_bytes())
    (DOC/'stage12-variables.patch').write_bytes(''.join(diff).encode('utf-8'))
    evidence=[dict(File=f['Preview'],SHA256=d.sha(DOC/f['Preview'])) for f in files]
    for name in ['stage12-before-manifest.json','stage12-before-fixes.json','stage12-before-baseline.json',
                 'stage12-decisions.json','stage12-references.json','stage12-supporting-references.json',
                 'stage12-born-marker-audit.json','stage12-variables.patch']+list(archives.values()):
        evidence.append(dict(File=name,SHA256=d.sha(DOC/name)))
    plan=dict(Revision=12,Rules=len(all_fixes),Occurrences=sum(x['ExpectedCount'] for x in all_fixes),
              Shadows=72,TextShadows=71,BinaryShadows=1,Additions=12,FixGroups=46,Groups=[f'F{i}' for i in range(39,47)],
              PreviousFiles=manifest['Files'],Archives=archives,Files=files,ShadowDefinitions=definitions,
              Sources=pinned,Evidence=evidence,ProtectedFiles=protected,LogMessages=130,UniqueSymbols=65,
              SharedLOTDMessages=2,NewRules=len(actions),NewOccurrences=sum(x['ExpectedCount'] for x in actions))
    d.save('stage12-plan.json',plan);d.save('fixes.json',all_fixes);d.save('source-baseline.json',baseline)
    print(f'Registered {len(actions)} recipes; {plan["NewOccurrences"]} replacements; 12 files, two new shadows.')


def sources():
    plan=d.load(DOC/'stage12-plan.json');mods=d.active_mods()
    for p,h in plan['Sources'].items():assert d.sha(p)==h,('Stage12 source changed',p)
    for row in plan['Evidence']:assert d.sha(DOC/row['File'])==row['SHA256'],('Stage12 evidence changed',row['File'])
    print(f'PASS: {len(plan["Sources"])} stage-twelve source pins and {len(plan["Evidence"])} evidence hashes.')
    return plan,mods


def check():
    plan,mods=sources();manifest=d.load(DOC/'source-manifest.json')
    assert manifest['Revision']==12 and len(manifest['Files'])==84
    fixes=d.load(DOC/'fixes.json');prior=d.load(DOC/'stage12-before-fixes.json')
    assert fixes[:745]==prior and len(fixes)==plan['Rules']
    for row in manifest['Files']:
        assert d.sha(MOD/row['File'])==row['PatchedSHA256']
        provider=None
        for mod in mods:
            if any(row['File']==rp or row['File'].startswith(rp.rstrip('/')+'/') for rp in mod['Replace']):provider=None
            p=Path(mod['Path'])/row['File']
            if d.native(p).is_file():provider=p
        assert provider and provider.resolve()==(MOD/row['File']).resolve(),('Shadowed repair',row['File'])
    for row in plan['Files']:
        assert d.sha(MOD/row['File'])==row['OutputSHA256']
        d.parse(d.read(MOD/row['File']))
    untouched=[r for r in plan['PreviousFiles'] if r['File'] not in plan['Archives']]
    assert len(untouched)==72
    for row in untouched:assert d.sha(MOD/row['File'])==row['PatchedSHA256']
    for p,h in plan['ProtectedFiles'].items():assert d.sha(p)==h,('Unrelated user file changed',p)
    decisions=d.load(DOC/'stage12-decisions.json')
    for row in plan['Files']:
        text=code(d.read(MOD/row['File']))
        for decision in decisions:
            symbol=re.escape(decision['Symbol'])
            if decision['Group'] in ('V04', 'V08'):
                # `color = { gene = ... }` is a portrait operation; the Dark
                # Sister accessory ID is likewise distinct from a variable.
                pattern=r'\b(?:name|has_variable|set_variable|remove_variable)\s*=\s*'+symbol+r'\b|\bvar:'+symbol+r'\b'
            else:
                pattern=r'(?<!\w)'+symbol+r'(?!\w)'
            assert not re.search(pattern,text),(row['File'],decision['Symbol'])
    # Archival changes preserve every active token except the explicitly removed writes/definitions.
    def prior_text(rel):return d.read(DOC/plan['Archives'][rel])
    assignment='common/scripted_effects/asoiaf_assign_inactive_traits_effects.txt'
    expected=code(prior_text(assignment))
    for r in decisions:
        if r['Group']=='V05':expected=re.sub(r'\bset_global_variable\s*=\s*'+re.escape(r['Symbol'])+r'\b','',expected)
    assert tokens(expected)==tokens(d.read(MOD/assignment)), 'Birth/identity logic changed beyond unused writes'
    overwrite='common/scripted_effects/asoiaf_agot_overwrite_effects.txt'
    expected=prior_text(overwrite).replace(full_block(prior_text(overwrite),'title:h_the_iron_throne'),'')
    actual=d.read(MOD/overwrite).replace('name = primary_color_grading','name = color_grading').replace('name = primary_color','name = color')
    assert tokens(expected)==tokens(actual),'Dragon genes or Jon birth logic changed'
    artifacts='common/scripted_effects/asoiaf_scripted_effects_artifacts.txt'
    expected=prior_text(artifacts)
    for name in ('asoiaf_is_krakenfall','asoiaf_is_needle','asoiaf_is_red_vipers_spear','dark_sister_artifact'):
        expected=re.sub(r'set_variable\s*=\s*\{\s*name\s*=\s*'+name+r'\s+value\s*=\s*yes\s*\}','',expected)
    assert tokens(expected)==tokens(d.read(MOD/artifacts)), 'Artifact creation/visuals/history changed'
    support=d.load(DOC/'stage12-supporting-references.json')
    for row in decisions:
        if row['Group']=='V01':
            hits=[x for x in support if x['Query']==row['Replacement']]
            assert sum(bool(re.match(re.escape(row['Replacement'])+r'\s*=',x['Text'])) for x in hits)==1
            assert any('make_trait_inactive =' in x['Text'] for x in hits)
    for key in ('asoiaf_on_title_inheritance_robert_usurper_nickname','asoiaf_targaryen_invasion_claimants_spawn_aegon_effect'):
        hits=[x for x in support if x['Query']==key]
        assert len(hits)==1 and hits[0]['Text'].startswith(key+' = {')
    portrait_cases = portrait_contracts(plan)
    result=dict(Revision=12,Status='PASS',RuntimeFiles=84,ChangedExistingFiles=10,NewShadows=2,
                PreviousFilesUnchanged=72,Previous745RecipesUnchanged=True,Rules=plan['NewRules'],Occurrences=plan['NewOccurrences'],
                TargetedMessages=130,UniqueSymbols=65,SharedLOTDMessagesDeferred=2,LOTDSourceUnchanged=True,
                BirthIdentityAndDescendantLogicPreserved=True,DragonGenesAndJonCreationPreserved=True,ArtifactPayloadsPreserved=True,
                PortraitBooleanCases=portrait_cases,PortraitDNAPayloadsPreserved=True,
                GameExecutionChecked=False,FreshLogChecked=False,ManifestSHA256=d.sha(DOC/'source-manifest.json'))
    d.save('stage12-validation.json',result)
    print(result)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('prepare','sources','check'))
    mode=parser.parse_args().mode
    {'prepare':prepare,'sources':sources,'check':check}[mode]()
