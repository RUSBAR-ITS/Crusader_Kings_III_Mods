"""Prepare exact, hash-pinned stage-eight repairs. No Workshop/profile writes."""
import argparse
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

MOD = Path(__file__).resolve().parents[1]
DOC = MOD / 'docs'
REPO = MOD.parents[1]
sys.path.insert(0, str(REPO / 'docs/reports/agot-plus-script-on-action-analysis-2026-09-19'))
from analyze_scripts import blocks, clean


def vfs():
    # Keep the historical audit unchanged; validate the same descriptors/order
    # through the shared resolver for the relocated repository.
    spec = importlib.util.spec_from_file_location('stage8_paths', Path(__file__).with_name('DNA-Stage9.py'))
    paths = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(paths)
    mods = paths.active_mods()
    files = {}
    for mod in mods:
        for prefix in mod['Replace']:
            files = {k: v for k, v in files.items() if not (k == prefix or k.startswith(prefix.rstrip('/') + '/'))}
        root = Path(mod['Path'])
        for category in ('common', 'events', 'history', 'gui', 'localization/english'):
            for p in (root / category).rglob('*'):
                if p.is_file() and p.suffix in ('.txt', '.gui', '.info', '.yml'):
                    files[p.relative_to(root).as_posix()] = {'Path': p, 'Mod': mod['Name']}
    return mods[1:], files

PLUS = Path('E:/SteamLibrary/steamapps/workshop/content/1158310/2950245430')
AGOT = Path('E:/SteamLibrary/steamapps/workshop/content/1158310/2962333032')
GAME = Path('E:/SteamLibrary/steamapps/common/Crusader Kings III/game')
TRIG = 'common/scripted_triggers/asoiaf_canon_children_triggers.txt'
EVENT = 'events/asoiaf_canon_children_events/asoiaf_canon_children_targaryen_events.txt'
HOOK = 'common/on_action/asoiaf_pregnancy_childbirth_on_actions.txt'
TITLE = 'common/on_action/agot_on_actions/test_title_on_actions.txt'
NATIVE_TITLE = 'common/on_action/agot_on_actions/agot_title_on_actions.txt'
DECISIONS = 'common/decisions/asoiaf_house_branch_decisions.txt'
NEW_TRIG = 'common/scripted_triggers/zz_agot_plus_fix_stage8_triggers.txt'
NEW_EFFECT = 'common/scripted_effects/zz_agot_plus_fix_aegon_children_effects.txt'
NAMES = ['Alysanne', 'Lily', 'Willow', 'Rosey', 'Bellenora', 'Narha', 'Balerion']
RU_NAMES = ['Алисанна', 'Лили', 'Ива', 'Рози', 'Белленора', 'Нарха', 'Балерион']


def native(p):
    text = str(Path(p).absolute())
    if sys.platform == 'win32' and not text.startswith('\\\\?\\'):
        text = '\\\\?\\UNC\\' + text[2:] if text.startswith('\\\\') else '\\\\?\\' + text
    return Path(text)


def read(p):
    # Retain source newlines for exact PowerShell replacements.
    return native(p).read_bytes().decode('utf-8-sig')


def sha(p):
    return hashlib.sha256(native(p).read_bytes()).hexdigest().upper()


def load(p):
    return json.loads(read(p))


def save(name, obj):
    (DOC / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def one(text, key):
    found = [b for b in blocks(text) if b['Depth'] == 0 and b['Id'] == key]
    assert len(found) == 1, (key, len(found))
    return found[0]['Body']


def trigger(n):
    chain = list(range(98, 102)) if n < 102 else list(range(102, 105))
    out = f'asoiaf_canon_children_Targaryen_{n}_trigger = {{ # {NAMES[n-98]}\n'
    out += '\tasoiaf_canon_children_enabled_trigger = yes\n'
    out += '\texists = scope:real_father\n\texists = scope:mother\n'
    out += '\tscope:real_father = { has_inactive_trait = asoiaf_Targaryen_88_trait }\n'
    out += '\tscope:mother = {\n\t\tis_alive = yes\n\t\thas_trait = pregnant\n'
    out += '\t\tagot_plus_fix_megette_trigger = yes\n' if n < 102 else '\t\tculture = culture:braavosi\n\t\tagot_plus_fix_megette_trigger = no\n\t\tagot_plus_fix_aegon_targaryen_mother_trigger = no\n'
    out += '\t}\n'
    for i in chain:
        field = f'exists = global_var:asoiaf_canon_children_Targaryen_{i}_born_variable'
        out += '\t' + (field if i < n else 'NOT = { ' + field + ' }') + '\n'
    return out + '}\n'


def birth(n):
    traits = ''
    hair = ['neutral_silver_hair', 'cool_silver_hair', 'cool_neutral_silver_hair', 'silver_blonde_hair']
    eyes = ['purple_eyes_9', 'purple_eyes_13', 'purple_eyes_13', 'purple_eyes_2']
    if n < 102:
        traits = f'''\t\t\t\tmake_trait_inactive = {hair[n-98]}
\t\t\t\tmake_trait_inactive = {eyes[n-98]}
\t\t\t\tif = {{
\t\t\t\t\tlimit = {{ has_game_rule = asoiaf_canon_children_rule_on_traits }}
\t\t\t\t\tadd_trait = education_learning_1
\t\t\t\t}}
'''
    elif n in (102, 104):
        traits = f'\t\t\t\tadd_trait = beauty_good_{3 if n == 102 else 1}\n'
    finish = ''
    if n in (101, 104):
        finish = '''
\t\t\tif = {
\t\t\t\tlimit = {
\t\t\t\t\thas_game_rule = asoiaf_canon_children_pregnancy_negation_rule_on
\t\t\t\t\tscope:mother = {
\t\t\t\t\t\tOR = {
\t\t\t\t\t\t\tis_married = no
\t\t\t\t\t\t\tis_spouse_of_even_if_dead = scope:real_father
\t\t\t\t\t\t}
\t\t\t\t\t}
\t\t\t\t}
\t\t\t\tscope:mother = { add_character_modifier = asoiaf_canon_children_pregnancy_negation_modifier }
\t\t\t}
'''
    return f'''asoiaf_canon_children_Targaryen_{n}_birth_effect = {{
\tif = {{
\t\tlimit = {{ asoiaf_canon_children_Targaryen_{n}_trigger = yes }}
\t\tclear_saved_scope = child
\t\tclear_saved_scope = child_2
\t\tclear_saved_scope = child_3
\t\tcreate_character = {{
\t\t\tage = 0
\t\t\tname = "{NAMES[n-98]}"
\t\t\tgender = {'male' if n == 104 else 'female'}
\t\t\tmother = scope:mother
\t\t\treal_father = scope:real_father
\t\t\tfaith = scope:mother.faith
\t\t\tculture = scope:mother.culture
\t\t\tlocation = scope:mother.location
\t\t\trandom_traits = no
\t\t\tsave_scope_as = child
\t\t\tafter_creation = {{
\t\t\t\tagot_plus_fix_place_newborn_effect = yes
\t\t\t\tagot_plus_fix_aegon_child_parentage_effect = yes
\t\t\t\tasoiaf_canon_children_join_travel_plan_effect = yes
\t\t\t\tset_global_variable = asoiaf_canon_children_Targaryen_{n}_born_variable
\t\t\t\tmake_trait_inactive = asoiaf_Targaryen_{n}_trait
\t\t\t\tadd_character_modifier = asoiaf_Targaryen_{n}_modifier
\t\t\t\tcopy_inheritable_appearance_from = character:Dummy_Targaryen_{n}
\t\t\t\tadd_character_flag = has_scripted_appearance
\t\t\t\tadd_character_flag = canon_status_canon
{traits}\t\t\t}}
\t\t}}
\t\t# End the pregnancy only after a child was actually created.
\t\tif = {{
\t\t\tlimit = {{ exists = scope:child }}
\t\t\tscope:mother = {{
\t\t\t\tasoiaf_canon_children_terminate_pregnancy_effect = yes
\t\t\t\tasoiaf_clear_bad_pregnancy_flags_effect = yes
\t\t\t\t# Native dispatcher handles one notification path, secrets and cleanup.
\t\t\t\ttrigger_event = birth.0001
\t\t\t}}
{finish}\t\t}}
\t}}
}}

'''


def prepare():
    manifest = load(DOC / 'source-manifest.json')
    assert manifest['Revision'] in (7, 8)
    for item in manifest['Files']:
        assert sha(MOD / item['File']) == item['PatchedSHA256']
    fixes, additions, baseline = [load(DOC / f'{name}.json') for name in ('fixes', 'additions', 'source-baseline')]
    if manifest['Revision'] == 8:
        manifest = load(DOC / 'stage8-before-manifest.json')
        fixes = [r for r in fixes if int(r['Group'][1:]) < 24]
        additions = [r for r in additions if int(r['Group'][1:]) < 24]
    assert len(fixes) == 284
    before_inventory = [dict(File=i['File'], SHA256=i['PatchedSHA256']) for i in manifest['Files']]
    def pin(rel, catalog='AGOT_PLUS'):
        path = {'AGOT_PLUS': PLUS, 'AGOT': AGOT}[catalog] / rel
        found = [b for b in baseline if b['Catalog'] == catalog and b['File'] == rel]
        if found:
            assert found[0]['SHA256'] == sha(path)
        else:
            baseline.append(dict(Catalog=catalog, File=rel, SHA256=sha(path)))
        return read(path)
    def repair(id, group, rel, before, after, count=1, catalog='AGOT_PLUS', reason=''):
        source = pin(rel, catalog)
        # Match the upstream newline convention, without rewriting the rest of the file.
        if '\r\n' in source:
            before = before.replace('\r\n', '\n').replace('\n', '\r\n')
            after = after.replace('\r\n', '\n').replace('\n', '\r\n')
        assert before != after and source.count(before) == count, id
        row = dict(Id=id, Group=group, File=rel, Before=before, After=after, ExpectedCount=count, Reason=reason)
        if catalog != 'AGOT_PLUS': row['Catalog'] = catalog
        fixes.append(row)
    def addition(rel, text, group='F24'):
        assert not any(a['File'] == rel for a in additions)
        additions.append(dict(File=rel, Text=text.replace('\r\n', '\n').replace('\n', '\r\n'), UTF8BOM=True,
                              Group=group, Reason='Stage-eight implementation; see docs/stage8-analysis.md.'))

    src = pin(TRIG)
    # The two malformed IDs are disambiguated by their existing child comments.
    starts = [m.start() for m in re.finditer(r'(?m)^asoiaf_canon_children_Targaryen_(?:98|99|100)_trigger = \{', src)]
    assert len(starts) == 4
    for n, start in zip(range(98, 102), starts):
        b = next(b for b in blocks(src) if b['Start'] == start)
        repair(f'aegon-child-{n}-trigger', 'F24', TRIG, b['Body'], trigger(n).rstrip())

    # A missing lowborn house must not satisfy the optional house comparison in
    # the existing legitimate/Daemon paths. Preserve those paths for Targaryens.
    for n in (91, 134, 132, 92, 135, 94):
        old = one(src, f'asoiaf_canon_children_Targaryen_{n}_trigger')
        new = re.sub(r'(?m)^(\s*)scope:mother.house \?= character:Targaryen_13.house',
                     r'\1exists = scope:mother.house\n\1scope:mother.house = character:Targaryen_13.house', old)
        new = new.replace('asoiaf_canon_children_enabled_trigger = yes',
                          'asoiaf_canon_children_enabled_trigger = yes\n\tscope:mother = { agot_plus_fix_megette_trigger = no }', 1)
        repair(f'aegon-existing-{n}-require-house', 'F24', TRIG, old, new,
               reason='Require a real Targaryen house; do not classify lowborn Megette or a Braavosi mother without a house as Targaryen.')

    new_triggers = '''# Megette only, including the native AGOT identity flag for dynamic identities.
agot_plus_fix_megette_trigger = {
\tOR = {
\t\tAND = {
\t\t\texists = character:Lowborn_Kings_Landing_3
\t\t\tthis = character:Lowborn_Kings_Landing_3
\t\t}
\t\thas_character_flag = is_Lowborn_Kings_Landing_3
\t}
}

agot_plus_fix_aegon_targaryen_mother_trigger = {
\tOR = {
\t\thas_inactive_trait = asoiaf_Targaryen_83_trait
\t\tAND = {
\t\t\texists = house
\t\t\texists = character:Targaryen_13.house
\t\t\thouse = character:Targaryen_13.house
\t\t}
\t}
}

'''+ '\n'.join(trigger(n) for n in range(102, 105)) + '''
# Legacy semantics: success means neither story flag is present.
agot_plus_fix_heir_event_available_trigger = {
\tcustom_description = {
\t\ttext = "yearly_1010_abducted"
\t\tNOT = { has_character_flag = yearly_1010_abducted }
\t}
\tcustom_description = {
\t\ttext = "yearly_1010_abductor"
\t\tNOT = { has_character_flag = yearly_1010_abductor }
\t}
}
'''
    addition(NEW_TRIG, new_triggers)
    # Safe adaptation of the PLUS parentage helper; no null house/father references.
    effects = '''agot_plus_fix_aegon_child_parentage_effect = {
\tif = {
\t\tlimit = { exists = scope:mother.house }
\t\tset_house = scope:mother.house
\t}
\tif = {
\t\tlimit = { exists = scope:father }
\t\tset_father = scope:father
\t\tif = {
\t\t\tlimit = { scope:mother = { has_character_flag = asoiaf_patrilineal_parentage } }
\t\t\tif = {
\t\t\t\tlimit = { exists = scope:father.house }
\t\t\t\tset_house = scope:father.house
\t\t\t}
\t\t\tset_character_faith = scope:father.faith
\t\t\tset_culture = scope:father.culture
\t\t}
\t}
\tif = {
\t\tlimit = {
\t\t\tOR = {
\t\t\t\tNOT = { exists = scope:father }
\t\t\t\tscope:mother = { has_character_flag = pregnancy_real_father_of_bastard_is_known_flag }
\t\t\t}
\t\t\tNOT = { scope:real_father = { is_spouse_of_even_if_dead = scope:mother } }
\t\t}
\t\tif = {
\t\t\tlimit = { faith = { has_doctrine_parameter = bastards_none } }
\t\t\tadd_trait = wild_oat
\t\t}
\t\telse = { add_trait = bastard }
\t\tif = {
\t\t\tlimit = { scope:mother = { has_character_flag = pregnancy_real_father_of_bastard_is_known_flag } }
\t\t\tset_father = scope:real_father
\t\t\tif = {
\t\t\t\tlimit = {
\t\t\t\t\thas_trait = bastard
\t\t\t\t\texists = scope:real_father.house
\t\t\t\t}
\t\t\t\tset_house = scope:real_father.house
\t\t\t}
\t\t}
\t\tagot_add_custom_bastard_nickname_effect = yes
\t}
}

# Idempotent initialization for new games and existing saves reaching these births.
agot_plus_fix_initialize_aegon_children_effect = {
'''
    for n in range(98, 105):
        effects += f'''\tcharacter:Targaryen_{n} ?= {{
\t\tset_global_variable = asoiaf_canon_children_Targaryen_{n}_born_variable
\t\tmake_trait_inactive = asoiaf_Targaryen_{n}_trait
\t}}
'''
    effects += '}\n\n' + ''.join(birth(n) for n in range(98, 105))
    addition(NEW_EFFECT, effects)
    addition('common/on_action/zz_agot_plus_fix_aegon_children_on_actions.txt', '''on_game_start = {
\ton_actions = { agot_plus_fix_initialize_aegon_children }
}
agot_plus_fix_initialize_aegon_children = {
\teffect = { agot_plus_fix_initialize_aegon_children_effect = yes }
}
''')
    for id, label in [('0882', 'Megette'), ('0883', 'a Braavosi mother')]:
        src = pin(EVENT)
        old = one(src, 'asoiaf_canon_children_targaryen_events.'+id)
        new = old.replace('by his lowborn lover', 'by Megette').replace('by his Summer Islander lover', 'by a Braavosi mother')
        new = re.sub(r'(?m)^\s*scope:mother = \{ asoiaf_canon_children_terminate_pregnancy_effect = yes \}\r?\n', '', new)
        new = new.replace('immediate = {', 'immediate = {\n\t\tagot_plus_fix_initialize_aegon_children_effect = yes', 1)
        repair('aegon-event-'+id, 'F24', EVENT, old, new, reason='Birth effects create first and terminate only with a valid newborn scope.')
    repair('aegon-pregnancy-initialize', 'F24', HOOK, 'asoiaf_canon_children_pregnancy_detection = {\n\teffect = {',
           '''asoiaf_canon_children_pregnancy_detection = {
\teffect = {
\t\tif = {
\t\t\tlimit = { scope:real_father ?= { has_inactive_trait = asoiaf_Targaryen_88_trait } exists = scope:real_father }
\t\t\tagot_plus_fix_initialize_aegon_children_effect = yes
\t\t}''')
    for old, new in [('by his lowborn lover', 'by Megette'), ('by his Summer Islander lover', 'by a Braavosi mother')]:
        repair('aegon-scheduler-'+('megette' if 'lowborn' in old else 'braavosi'), 'F24', HOOK, '#children of Aegon IV Targaryen '+old, '#children of Aegon IV Targaryen '+new)
    mods = ''
    for n in range(98, 105):
        mods += f'''asoiaf_Targaryen_{n}_modifier = {{
\ticon = asoiaf_canon_children_modifier
\tnegate_health_penalty_add = 1.5
\tfertility = 0.3
\ttravel_danger = -15
\thide_effects = yes
}}
'''
    addition('common/modifiers/zz_agot_plus_fix_aegon_children_modifiers.txt', mods)
    for language, names in [('english', NAMES), ('russian', RU_NAMES)]:
        text = 'l_'+language+':\n'
        for n, name in zip(range(98, 105), names):
            desc = ('Canon child of Aegon IV. No further canon descendants are implemented in this chain.' if language == 'english' else
                    'Канонический ребёнок Эйгона IV. Продолжение линии этого персонажа в данной цепочке не предусмотрено.')
            text += f' asoiaf_Targaryen_{n}_modifier:0 "[asoiaf_canon_children_concept|E]: #bold {name}#!"\n'
            text += f' asoiaf_Targaryen_{n}_modifier_desc:0 "{desc}"\n'
        desc = ('Canon children of Aegon IV: his legitimate children with a Targaryen wife; Alysanne, Lily, Willow and Rosey with Megette; Bellenora, Narha and Balerion with a Braavosi mother; Daemon Blackfyre with Daena or another Targaryen woman outside marriage. Aegon must be the biological father. Other bastard chains are not implemented.' if language == 'english' else
                'Канонические дети Эйгона IV: законные дети от жены из дома Таргариенов; Алисанна, Лили, Ива и Рози от Мегетт; Белленора, Нарха и Балерион от женщины браавосской культуры; Деймон Блэкфайр от Дейны или другой женщины дома Таргариенов вне брака. Эйгон должен быть биологическим отцом. Остальные цепочки бастардов не реализованы.')
        text += f' asoiaf_Targaryen_88_modifier_desc:0 "{desc}"\n'
        addition(f'localization/replace/{language}/zz_agot_plus_fix_aegon_children_l_{language}.yml', text)
    for key, value in [('decision_has_second_step', 'yes'), ('decision_custom_widget_container', '"custom_widgets_container_step_two"')]:
        repair('branch-widget-'+key, 'F25', DECISIONS, key+' = '+value, '# AGOT_PLUS_FIX: retired '+key+' = '+value, 4)
    repair('heir-story-availability', 'F26', 'common/character_interactions/asoiaf_character_interactions.txt',
           'is_busy_in_events_localised = yes', 'agot_plus_fix_heir_event_available_trigger = yes')
    old = one(pin(TITLE), 'agot_on_title_inheritance_lannister_baratheon_coa')
    repair('remove-duplicate-coa-handler', 'F27', TITLE, old, '# AGOT_PLUS_FIX: native CoA handler disabled in its canonical AGOT file.')
    repair('remove-duplicate-coa-registration', 'F27', TITLE, '\t\tagot_on_title_inheritance_lannister_baratheon_coa\n', '')
    old = one(pin(NATIVE_TITLE, 'AGOT'), 'agot_on_title_inheritance_lannister_baratheon_coa')
    repair('disable-native-personal-coa', 'F27', NATIVE_TITLE, old,
           '''agot_on_title_inheritance_lannister_baratheon_coa = {
\t# AGOT+ uses its own cadet branch instead of the native personal CoA.
\ttrigger = { always = no }
\teffect = { }
}''', catalog='AGOT')
    old = '''\t\t\tdesignate_diarch = root.mother #Cersei
\t\t\tstart_diarchy = regency
\t\t\tset_diarch = root.mother #Cersei'''
    new = '''\t\t\tif = {
\t\t\t\tlimit = {
\t\t\t\t\troot.mother = { is_diarch_valid_trigger = yes }
\t\t\t\t\tOR = {
\t\t\t\t\t\tbasic_eligible_for_diarchy_trigger = yes
\t\t\t\t\t\thas_diarchy_type = regency
\t\t\t\t\t}
\t\t\t\t}
\t\t\t\tdesignate_diarch = root.mother
\t\t\t\tif = {
\t\t\t\t\tlimit = { basic_eligible_for_diarchy_trigger = yes }
\t\t\t\t\ttry_start_diarchy = regency
\t\t\t\t}
\t\t\t\tif = {
\t\t\t\t\tlimit = { has_active_diarchy = yes has_diarchy_type = regency }
\t\t\t\t\tset_diarch = root.mother
\t\t\t\t}
\t\t\t}'''
    repair('mother-regency-safe-start', 'F28', TITLE, old, new)
    army = 'common/on_action/asoiaf_army_on_actions.txt'
    repair('claimant-clear-saved-target', 'F29', army, '\t\tscope:war = {\n\t\t\tcasus_belli = {', '\t\tclear_saved_scope = asoiaf_war_claimant\n\t\tscope:war = {\n\t\t\tcasus_belli = {', 2)
    repair('claimant-require-target', 'F29', army, 'scope:asoiaf_war_claimant ?= {', 'exists = scope:asoiaf_war_claimant\n\t\t\t\t\tscope:asoiaf_war_claimant = {', 2)
    repair('claimant-war-defender', 'F29', army, 'defender = { character = root }', 'primary_defender = root', 2)
    repair('retired-crownlands-cleanup', 'F30', TITLE, 'asoiaf_destroy_crownlands_title_effect = yes', '# AGOT_PLUS_FIX: author retired automatic title destruction; asoiaf_destroy_crownlands_title_effect = yes')
    repair('orphan-megawar-cleanup', 'F31', 'events/asoiaf_mega_war_events.txt', 'asoiaf_mega_war_effect = yes', '# AGOT_PLUS_FIX: unavailable unfinished effect; retained inert event ID.')

    # Pin dependencies used for births, modern diarchy, identity and source assumptions.
    deps = ['history/characters/00_agot_char_dragonstone_ancestors.txt', 'history/characters/00_agot_char_braavos_ancestors.txt',
            'history/characters/agot_canon_children_dummy_characters.txt', 'common/culture/cultures/00_agot_cul_freecities.txt',
            'common/scripted_triggers/00_diarchy_scripted_triggers.txt', 'common/scripted_effects/agot_character_initializiation_effects.txt',
            'events/birth_events.txt', 'common/scripted_effects/00_pregnancy_effects.txt',
            'common/scripted_effects/00_bastard_effects.txt', 'common/scripted_effects/00_agot_bastard_effects.txt']
    for rel in deps:
        pin(rel, 'AGOT')
    for rel in ['common/traits/asoiaf_canon_children_traits.txt', 'common/modifiers/asoiaf_modifiers.txt']:
        if (PLUS/rel).exists(): pin(rel)
    # Ensure every planned replacement remains exact after earlier repairs.
    outputs = {}
    for row in fixes:
        key = (row.get('Catalog', 'AGOT_PLUS'), row['File'])
        if key not in outputs: outputs[key] = read((PLUS if key[0] == 'AGOT_PLUS' else AGOT)/key[1])
        assert outputs[key].count(row['Before']) == row['ExpectedCount'], row['Id']
        outputs[key] = outputs[key].replace(row['Before'], row['After'])
    save('stage8-before-manifest.json', manifest)
    save('stage8-plan.json', dict(Revision=8, PreviousFiles=before_inventory,
         Groups=[f'F{n}' for n in range(24,32)], Rules=len(fixes),
         Occurrences=sum(r['ExpectedCount'] for r in fixes), Shadows=len(outputs), Additions=len(additions),
         ShadowDefinitions={rel: [b['Id'] for b in blocks(text) if b['Depth']==0] for (_,rel),text in outputs.items()},
         MotherPolicy='Megette by historical ID/native identity flag; Braavosi culture for the Otherys chain, excluding Megette.',
         GameExecutionChecked=False))
    save('fixes.json', fixes); save('additions.json', additions); save('source-baseline.json', baseline)
    print(f'Prepared {len(fixes)-284} rules; {len(outputs)} shadows / {len(additions)} additions; runtime files not yet built.')


if __name__ == '__main__':
    prepare()
