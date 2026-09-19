"""Static contracts and a small interpreter for the actual seven birth triggers.

This does not run the CK3 engine. Unsupported trigger syntax fails the test.
"""
import importlib.util
import itertools
import json
import re
from collections import Counter

spec = importlib.util.spec_from_file_location('stage8', __file__.replace('Test-Scripts-Stage8.py', 'Scripts-Stage8.py'))
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def parse(text):
    text = re.sub(r'#[^\r\n]*', '', text)
    tokens = re.findall(r'"[^"\n]*"|[{}=]|[^\s{}=]+', text)
    def block(i):
        result = []
        while i < len(tokens) and tokens[i] != '}':
            key = tokens[i]
            assert tokens[i+1] == '=', tokens[i:i+4]
            i += 2
            if tokens[i] == '{':
                value, i = block(i+1)
                assert tokens[i] == '}'
                i += 1
            else:
                value = tokens[i].strip('"'); i += 1
            result.append((key, value))
        return result, i
    result, end = block(0)
    assert end == len(tokens)
    return dict(result)


def main():
    manifest = s.load(s.DOC/'source-manifest.json')
    plan = s.load(s.DOC/'stage8-plan.json')
    assert manifest['Revision'] in (8, 9, 10, 11, 12)
    assert len(manifest['Files']) == {8: 45, 9: 64, 10: 69, 11: 82, 12: 84}[manifest['Revision']]
    for row in manifest['Files']:
        assert s.sha(s.MOD/row['File']) == row['PatchedSHA256']
    active, files = s.vfs()
    for row in manifest['Files']:
        if row['File'].startswith(('gfx/', 'localization/')):
            providers = [s.Path(m['Path'])/row['File'] for m in active if s.native(s.Path(m['Path'])/row['File']).exists()]
            assert providers[-1].resolve() == (s.MOD/row['File']).resolve()
        else:
            assert files[row['File']]['Path'].resolve() == (s.MOD/row['File']).resolve(), row['File']
    def text(rel): return s.read(files[rel]['Path'])
    def code(rel): return re.sub(r'#[^\r\n]*', '', text(rel))

    # Preserve the exact first seven packages outside the explicitly recorded repairs.
    fixes = s.load(s.DOC/'fixes.json')
    untouched = 0
    for prior in plan['PreviousFiles']:
        if not any(r['File'] == prior['File'] and int(r['Group'][1:]) >= 24 for r in fixes):
            assert s.sha(s.MOD/prior['File']) == prior['SHA256']
            untouched += 1

    triggers = {}
    existing_ids = (91, 134, 132, 92, 135, 94)
    for rel in (s.TRIG, s.NEW_TRIG):
        for b in s.blocks(text(rel)):
            if b['Depth'] == 0 and (b['Id'] in {f'asoiaf_canon_children_Targaryen_{n}_trigger' for n in (*existing_ids,*range(98,105))} or b['Id'].startswith('agot_plus_fix_')):
                assert b['Id'] not in triggers
                triggers.update(parse(b['Body']))

    def evaluate(nodes, state, who='root'):
        def pred(key, value):
            if key == 'OR': return any(pred(k,v) for k,v in value)
            if key == 'AND': return evaluate(value, state, who)
            if key == 'NOT': return not evaluate(value, state, who)
            if key == 'custom_description': return evaluate([(k,v) for k,v in value if k!='text'], state, who)
            if key in ('scope:mother', 'scope:real_father'):
                role = key.split(':')[1]
                return bool(state.get(role)) and evaluate(value, state, role)
            if key in triggers: return evaluate(triggers[key], state, who) == (value == 'yes')
            if key == 'asoiaf_canon_children_enabled_trigger': return state['enabled'] == (value == 'yes')
            if key == 'exists':
                if value.startswith('global_var:'):
                    return int(re.search(r'Targaryen_(\d+)_born', value)[1]) in state['born']
                if value == 'scope:mother.house': return bool(state.get('mother')) and state['mother'].get('has_house',False)
                if value.startswith('scope:'): return bool(state.get(value.split(':')[1]))
                if value == 'character:Lowborn_Kings_Landing_3': return state['historical_megette_exists']
                if value == 'character:Targaryen_13.house': return True
                if value == 'house': return state[who].get('has_house',False)
                raise AssertionError(value)
            if key == 'has_inactive_trait':
                if value=='asoiaf_Targaryen_83_trait': return state[who].get('daena',False)
                return state[who]['aegon']
            if key == 'has_character_flag':
                if value == 'is_Lowborn_Kings_Landing_3': return state[who]['megette_flag']
                return value in state['flags']
            if key == 'this': return state[who]['historical_megette']
            if key in ('house','scope:mother.house'):
                assert value == 'character:Targaryen_13.house'
                return state['mother' if key.startswith('scope:') else who].get('targaryen_house',False)
            if key == 'is_spouse_of_even_if_dead': return state['married_to_aegon']
            if key == 'culture': return state[who]['culture'] == value.split(':')[1]
            if key == 'is_alive': return state[who]['alive'] == (value == 'yes')
            if key == 'has_trait':
                assert value == 'pregnant'
                return state[who]['pregnant']
            raise AssertionError((key, value))
        return all(pred(k,v) for k,v in nodes)

    count = 0
    profiles = [(True,False,'riverman_main',False,False), (False,True,'riverman_main',False,False), (True,False,'braavosi',False,False),
                (False,False,'braavosi',False,False), (False,False,'jhalai',False,False), (False,False,'riverman_main',False,False),
                (False,False,'braavosi',True,False), (False,False,'braavosi',False,True)]
    for mask in range(128):
        born = {n for n in range(98,105) if mask & (1 << (n-98))}
        for hist, flag, culture, targaryen_house, daena in profiles:
            for enabled, pregnant, alive, aegon, exists_mother, exists_father in [(True,)*6, (False,True,True,True,True,True), (True,False,True,True,True,True), (True,True,False,True,True,True), (True,True,True,False,True,True), (True,True,True,True,False,True), (True,True,True,True,True,False)]:
                state = dict(born=born, enabled=enabled, historical_megette_exists=True, flags=set(),
                             mother=dict(historical_megette=hist, megette_flag=flag, culture=culture, alive=alive, pregnant=pregnant, targaryen_house=targaryen_house, has_house=targaryen_house, daena=daena) if exists_mother else None,
                             real_father=dict(aegon=aegon) if exists_father else None)
                selected = [n for n in range(98,105) if evaluate(triggers[f'asoiaf_canon_children_Targaryen_{n}_trigger'], state)]
                expected = []
                if all((enabled,pregnant,alive,aegon,exists_mother,exists_father)):
                    chain = list(range(98,102)) if (hist or flag) else list(range(102,105)) if culture=='braavosi' and not (targaryen_house or daena) else []
                    for n in chain:
                        if all(i in born for i in chain if i < n) and all(i not in born for i in chain if i >= n): expected.append(n)
                assert selected == expected and len(selected) <= 1, (state,selected,expected)
                count += 1
    # Lowborn mothers must not enter the pre-existing Targaryen/Daemon chains.
    # A Braavosi Targaryen remains in those original chains, not both systems.
    overlap_cases = 0
    for hist, flag, culture, targaryen_house, daena in profiles:
        for married in (False,True):
            for house_exists in (targaryen_house,True):
                state = dict(born=set(),enabled=True,historical_megette_exists=True,flags=set(),married_to_aegon=married,
                             mother=dict(historical_megette=hist,megette_flag=flag,culture=culture,alive=True,pregnant=True,
                                         targaryen_house=targaryen_house,has_house=house_exists,daena=daena),
                             real_father=dict(aegon=True))
                new = [n for n in range(98,105) if evaluate(triggers[f'asoiaf_canon_children_Targaryen_{n}_trigger'],state)]
                old = [n for n in existing_ids if evaluate(triggers[f'asoiaf_canon_children_Targaryen_{n}_trigger'],state)]
                assert not (new and old), (state,new,old)
                expected = [] if hist or flag else ([91] if targaryen_house and married else []) + ([94] if daena or (targaryen_house and not married) else [])
                assert old == expected, (state,old,expected)
                overlap_cases += 1
    # Heir restriction keeps both flags, including the misleadingly named positive call.
    for abducted, abductor in itertools.product((False,True), repeat=2):
        flags = {f for f,yes in [('yearly_1010_abducted',abducted),('yearly_1010_abductor',abductor)] if yes}
        assert evaluate(triggers['agot_plus_fix_heir_event_available_trigger'], dict(flags=flags)) == (not abducted and not abductor)

    effects = code(s.NEW_EFFECT)
    for n in range(98,105):
        b = s.one(effects,f'asoiaf_canon_children_Targaryen_{n}_birth_effect')
        assert b.count('create_character =') == 1
        assert b.index('create_character =') < b.index('asoiaf_canon_children_terminate_pregnancy_effect')
        assert 'limit = { exists = scope:child }' in b
        assert 'clear_saved_scope = child' in b
        assert f'asoiaf_canon_children_Targaryen_{n}_trigger = yes' in b
        assert f'copy_inheritable_appearance_from = character:Dummy_Targaryen_{n}' in b
        assert f'asoiaf_Targaryen_{n}_trait' in b and f'asoiaf_Targaryen_{n}_modifier' in b
        assert 'trigger_event = birth.0001' in b and 'trigger_event = birth.100' not in b
        # Verify actual identity/donor sex/name, including effective later mod overrides.
        history = 'history/characters/00_agot_char_'+('dragonstone' if n<102 else 'braavos')+'_ancestors.txt'
        historical = s.one(text(history),f'Targaryen_{n}')
        donor = s.one(text('history/characters/agot_canon_children_dummy_characters.txt'),f'Dummy_Targaryen_{n}')
        for char in (historical,donor):
            assert re.search(r'\bname\s*=\s*'+s.NAMES[n-98]+r'\b', char)
            assert bool(re.search(r'\bfemale\s*=\s*yes',char)) == (n!=104)
        assert f'dna = Targaryen_{n}' in donor
        # History init only touches a concrete existing identity, never a dummy or every character.
        init = s.one(effects,'agot_plus_fix_initialize_aegon_children_effect')
        assert f'character:Targaryen_{n} ?=' in init and f'Targaryen_{n}_born_variable' in init
    for suffix in ('0882','0883'):
        b = s.one(code(s.EVENT),'asoiaf_canon_children_targaryen_events.'+suffix)
        assert 'terminate_pregnancy' not in b
        assert b.index('agot_plus_fix_initialize_aegon_children_effect') < b.index('if =')
    # Existing pregnancy events and all nearby birth chains stay byte-identical.
    old_events = s.read(s.PLUS/s.EVENT)
    for b in s.blocks(old_events):
        if b['Depth']==0 and b['Id'] not in ('asoiaf_canon_children_targaryen_events.0882','asoiaf_canon_children_targaryen_events.0883'):
            expected = b['Body']
            for r in fixes:
                if r['File']==s.EVENT and int(r['Group'][1:])<24: expected=expected.replace(r['Before'],r['After'])
            assert s.one(text(s.EVENT),b['Id'])==expected, b['Id']

    choices = 0
    for b in s.blocks(code(s.DECISIONS)):
        if b['Depth'] != 0: continue
        old = s.one(s.read(s.PLUS/s.DECISIONS),b['Id'])
        values = re.findall(r'(?m)^\s*value\s*=\s*(\w+)',b['Body'])
        assert len(values) and values == re.findall(r'(?m)^\s*value\s*=\s*(\w+)',old)
        old_effect = next(x['Body'] for x in s.blocks(old) if x['Id']=='effect' and x['Depth']==1)
        actual = s.one(text(s.DECISIONS),b['Id'])
        new_effect = next(x['Body'] for x in s.blocks(actual) if x['Id']=='effect' and x['Depth']==1)
        assert old_effect == new_effect
        for value in values: assert re.search(r'scope:'+value+r'\s*=\s*yes',new_effect)
        choices += len(values)
    assert choices == 9
    assert not re.search(r'\b(decision_has_second_step|decision_custom_widget_container)\s*=',code(s.DECISIONS))

    native_id = 'agot_on_title_inheritance_lannister_baratheon_coa'
    definition_count = registration_count = 0
    for rel, entry in files.items():
        if rel.startswith('common/on_action/'):
            t = re.sub(r'#[^\r\n]*','',s.read(entry['Path']))
            definition_count += len(re.findall(r'(?m)^\s*'+native_id+r'\s*=\s*\{',t))
            registration_count += len(re.findall(r'(?m)^\s*'+native_id+r'\s*$',t))
    assert (definition_count,registration_count)==(1,1)
    disabled = s.one(code(s.NATIVE_TITLE),native_id)
    assert 'always = no' in disabled and 'add_gold' not in disabled
    old_native = s.read(s.AGOT/s.NATIVE_TITLE)
    assert text(s.NATIVE_TITLE).replace(s.one(text(s.NATIVE_TITLE),native_id),s.one(old_native,native_id))==old_native
    coa = s.one(code(s.TITLE),'asoiaf_on_title_inheritance_lannister_baratheon_coa')
    for check in ('is_diarch_valid_trigger = yes','basic_eligible_for_diarchy_trigger = yes','has_diarchy_type = regency','has_active_diarchy = yes','try_start_diarchy = regency','set_diarch = root.mother'):
        assert check in coa
    assert not re.search(r'\bstart_diarchy\s*=',coa)
    siege = code('common/on_action/asoiaf_army_on_actions.txt')
    for check in ('clear_saved_scope = asoiaf_war_claimant','exists = scope:asoiaf_war_claimant','primary_defender = root'):
        assert siege.count(check)==2
    assert 'scope:asoiaf_war_claimant ?=' not in siege and 'defender = { character = root }' not in siege
    assert 'asoiaf_destroy_crownlands_title_effect = yes' not in code(s.TITLE)
    assert 'asoiaf_mega_war_effect = yes' not in code('events/asoiaf_mega_war_events.txt')

    # Every new scripted reference must resolve in the actual effective set.
    new_code = '\n'.join(code(rel) for rel in (s.NEW_EFFECT,s.NEW_TRIG))
    needed = set(re.findall(r'\b((?:asoiaf|agot_plus_fix|agot)_[\w]+_(?:effect|trigger))\s*=',new_code))
    definitions = Counter()
    for rel, entry in files.items():
        if rel.startswith(('common/scripted_effects/','common/scripted_triggers/')):
            for key in re.findall(r'(?m)^\s*([A-Za-z_0-9]+)\s*=\s*\{',re.sub(r'#[^\r\n]*','',s.read(entry['Path']))):
                if key in needed: definitions[key]+=1
    assert all(definitions[k]==1 for k in needed), {k:definitions[k] for k in needed if definitions[k]!=1}
    s.save('stage8-validation.json',dict(Revision=8,ValidatedRuntimeRevision=manifest['Revision'],Status='PASS',GameExecutionChecked=False,FreshLogChecked=False,
           TriggerScenarioCases=count,ExistingChainOverlapCases=overlap_cases,HeirFlagCases=4,BirthFunctions=7,DecisionChoicesPreserved=choices,
           NativeCoADefinitions=definition_count,NativeCoARegistrations=registration_count,
           PreviousRuntimeFilesUnchanged=untouched,RuntimeFiles=len(manifest['Files']),
           UniqueNewScriptDependencies=len(needed),ManifestSHA256=s.sha(s.DOC/'source-manifest.json')))
    print(f'PASS: {count} birth-trigger cases and {overlap_cases} existing-chain cases; 7 guarded births; 4 heir states; 9 preserved choices; unique CoA handler; exact native file preservation.')


if __name__=='__main__': main()
