"""Reproducible, source-pinned patch for the approved AGOT submod fixes.

Writes only this mod and its adjacent descriptor. --check performs no writes.
Workshop and AGOT_PLUS_FIX are never changed. No integration branches removed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from ScriptBlocks import one, parse, edit, comment, walk
from CrownWithoutCreator import CROWN_SOURCE, LOTD_CROWNS, function_names, make_helpers

sys.stdout.reconfigure(encoding='utf-8')
MOD = Path(__file__).resolve().parents[1]
REPO = MOD.parents[1]
WS = Path('E:/SteamLibrary/steamapps/workshop/content/1158310')
GAME = Path('E:/SteamLibrary/steamapps/common/Crusader Kings III/game')
IDS = dict(agot='2962333032', core='3034473189', di='2996152542', lotd='3101422928',
           cow='2971198450', crowns='2995674648', vs='2962713441', bookmarked='3149692324',
           agot_ru='2962803371')
INPUTS, OUTPUTS, FIXES = {}, {}, []


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(owner, relative):
    return read_bytes(owner, relative).decode('utf-8-sig').replace('\r\n', '\n')


def read_bytes(owner, relative):
    root = REPO if owner == 'repo' else GAME if owner == 'game' else WS / IDS[owner]
    path = root / relative
    data = path.read_bytes()
    key = owner + '/' + relative
    INPUTS[key] = dict(owner=owner, relative=relative, path=path.as_posix(), sha256=digest(data),
                       bom=data.startswith(b'\xef\xbb\xbf'))
    return data


def output(relative, text, owner=None, source=None, reason=''):
    assert relative not in OUTPUTS, relative
    if relative.endswith(('.txt', '.asset')):
        parse(text)
    # CK3 requests UTF-8 BOM for new scripts, even when their text is ASCII.
    bom = INPUTS[owner + '/' + (source or relative)]['bom'] if owner else True
    if relative.endswith('.yml'):
        bom = True
    data = (b'\xef\xbb\xbf' if bom else b'') + text.encode('utf-8')
    OUTPUTS[relative] = data
    FIXES.append(dict(file=relative, source=owner + '/' + (source or relative) if owner else None, reason=reason))


def replace(text, old, new, count=1):
    assert text.count(old) == count, (old, text.count(old), count)
    return text.replace(old, new)


def simple(owner, path, pairs, reason):
    text = read(owner, path)
    for pair in pairs:
        text = replace(text, *pair)
    output(path, text, owner, reason=reason)


def build():
    simple('core', 'common/scripted_triggers/core_artifact_triggers.txt', [
        ('has_variable = blackfyre', 'has_artifact_modifier = vs_blackfyre_modifier'),
        ('has_variable = darksister', 'has_artifact_modifier = vs_dark_sister_modifier'),
        ('has_variable = seafoam', 'has_artifact_modifier = vs_seafoam_modifier')], 'Recognize current AGOT/LOTD sword modifiers; preserve optional integrations.')

    # Only AGOT compatibility files from DI, never the vanilla menu files.
    p = 'common/scripted_effects/DI_court_position_spawner_overrides.txt'
    t = read('di', p)
    old = '\n'.join('            learn_language = language_' + x for x in ['arabic','greek','latin','norse'])
    t = replace(t, old, '\n'.join('            # USF: replaced: learn_language = language_' + x for x in ['arabic','greek','latin','norse']) + '\n            usf_learn_four_available_languages_effect = yes', 2)
    output(p, t, 'di', reason='Preserve polyglot roles using existing cultures and distinct unknown languages.')
    output('common/scripted_effects/usf_language_effects.txt', '''# Current scope: the spawned character. No vanilla language IDs.
usf_learn_four_available_languages_effect = {
    save_scope_as = usf_language_student
    while = {
        count = 4
        random_culture_global = {
            limit = {
                scope:usf_language_student = {
                    NOT = { knows_language_of_culture = prev }
                }
            }
            save_scope_as = usf_language_culture
            scope:usf_language_student = {
                learn_language_of_culture = scope:usf_language_culture
            }
        }
    }
}
''', reason='At most four new languages; cultures sharing a language cannot duplicate it.')
    p = 'common/scripted_effects/DI_present_effects.txt'
    t = read('di', p)
    lines = t.splitlines(True)
    hits = [i for i,s in enumerate(lines) if re.search(r'\b(?:has_trait|add_trait|remove_trait) = (?:honorable|ruthless)\b',s)]
    assert len(hits) == 4
    for i in hits:
        lines[i] = '    # USF: trait absent in current AGOT; ' + lines[i].lstrip()
    output(p, ''.join(lines), 'di', reason='Comment four obsolete trait choices/checks; preserve all other personalities and weights.')
    simple('di', 'common/scripted_guis/DI_cultural_editor_pillars_sgui.txt', [
        ('set_culture_pillar = language_agot_lhazaar', 'set_culture_pillar = language_agot_lhazar')], 'Correct the existing AGOT language ID.')

    p = 'common/scripted_effects/00_agot_artifact_vs_sword_effects_override.txt'
    t = read('lotd', p)
    for name in ['blackfyre','dark_sister','seafoam','pincer']:
        t = replace(t, 'template = vs_' + name + '_template', 'template = valyrian_steel_template', 2)
    changes = []
    for n in walk(parse(t)):
        if n.key == 'set_variable' and isinstance(n.value,list):
            names = n.children('name')
            if names and names[0].value in ['blackfyre_artifact','seafoam_artifact','pincer_artifact']:
                changes.append((n.start,n.end,comment(t[n.start:n.end], 'unused legacy marker; artifact modifier identifies the weapon')))
    assert len(changes) == 3
    output(p, edit(t,changes), 'lotd', reason='Use modern templates for Blackfyre, Dark Sister, Seafoam and Pincer; comment three unused markers without altering visuals, modifiers or history.')
    p = 'common/scripted_effects/00_lotd_artifact_creation_effects.txt'
    simple('lotd', p, [('modifier = artifact_personal_scheme_power_add_5_modifier',
                       '# USF: obsolete bonus; modifier = artifact_personal_scheme_power_add_5_modifier')], 'Keep remaining Subterfuge bonuses; do not duplicate its existing +5 bonus.')
    simple('lotd', 'events/decisions_events/buy_ruby_crown_events.txt', [
        ('remove_short_term_gold = -450', '# USF: decision already charges 450 gold; remove_short_term_gold = -450')], 'Prevent an invalid second AI charge; preserve decision cost.')
    simple('lotd', 'common/scripted_triggers/00_lotd_artifact_triggers.txt', [
        ('has_variable = crown_aegon_baelor_artifact', 'has_variable = crown_baelor_artifact')], 'Recognize the existing Baelor crown marker.')
    p = 'events/decisions_events/rediscover_events.txt'
    t = read('lotd', p)
    nodes = [n for n in walk(parse(t)) if n.key == '1' and isinstance(n.value,list)
             and any(x.key == 'set_variable' and 'flag:maekars_crown' in t[x.start:x.end] for x in n.value)]
    assert len(nodes) == 1
    n = nodes[0]
    old = t[n.start:n.end]
    new = '''1 = { # USF: search only when the crown is absent and not unavailable.
                        trigger = {
                            NOT = { any_artifact = { has_variable = crown_maekar_artifact } }
                            NOT = {
                                is_target_in_global_variable_list = {
                                    name = unavailable_artifacts
                                    target = flag:maekars_crown
                                }
                            }
                        }
                        set_variable = { name = artifact_choice value = flag:maekars_crown }
                    }'''
    t = edit(t, [(n.start,n.end,comment(old,'obsolete contradictory Maekar selection retained for reference')+'\n                    '+new)])
    for old, new in function_names(LOTD_CROWNS, 'usf').items():
        t = replace(t, old+' = { OWNER = this }', new+' = { OWNER = this }')
    output(p, t, 'lotd', reason='Restore Maekar search eligibility; five crown finds use current properties without an invented maker.')
    output('common/scripted_effects/usf_crowns_without_creator_effects.txt',
           make_helpers(read('agot', CROWN_SOURCE), LOTD_CROWNS, 'usf'),
           reason='Five separately named AGOT crown helpers; only the creator binding and creator field are omitted.')

    p = 'common/on_action/cowagot_province_on_actions.txt'
    t = read('cow', p)
    for pair in [('add_building = common_trade_03','add_building = common_tradeport_03'),
                 ('remove_building = ironwood_01','# USF: absent obsolete building; remove_building = ironwood_01'),
                 ('= bearisland_01','= agot_rodriks_gift_01',2)]:
        t = replace(t, *pair)
    branches = one(t, 'harlaw_building_check_on_actions').one('effect').children('if')
    obsolete = [n for n in branches if any(c.key == 'add_special_building_slot' and c.value == 'harlaw_mines_01' for c in n.value)]
    assert len(obsolete) == 1
    n = obsolete[0]
    t = edit(t, [(n.start, n.end, comment(t[n.start:n.end], 'unavailable legacy Harlaw mine; retain the existing Ten Towers branch'))])
    output(p, t, 'cow', reason='Known port/Bear Island IDs; comment obsolete removals and missing Harlaw mine branch; retain Ten Towers.')
    p = 'common/buildings/yy_agotcities_special_buildings_westeros.txt'
    t = read('cow', p)
    nodes = [n for n in walk(parse(t)) if n.key=='holding' and 'castle_05' in t[n.start:n.end]]
    assert len(nodes) == 1
    n = nodes[0]
    t = edit(t,[(n.start,n.end,comment(t[n.start:n.end],'already in province scope; preserve higher castle levels')+'\n                NOT = { has_building_or_higher = castle_05 }')])
    # Approved follow-up: keep the unavailable event calls as comments, not a stub event.
    changes = []
    for key in ['planky_town_special', 'agot_castamere_03', '24castamere_03']:
        complete = one(t, key).one('on_complete')
        holder = complete.one('barony.holder')
        call = holder.one('trigger_event')
        assert len(complete.value) == len(holder.value) == 1 and call.value == 'agot_cities.5000'
        changes.append((complete.start, complete.end,
                        comment(t[complete.start:complete.end],
                                'agot_cities.5000 has no definition in the installed mod set; original call retained for reference')))
    t = edit(t, changes)
    t = replace(t, 'rhoynish_religion_opinion', 'the_mother_religion_opinion', 2)
    output(p,t,'cow',reason='Repair scope and avoid downgrade; comment three unavailable agot_cities.5000 callbacks; use modern Mother religion opinion with original +10/+5.')
    p = 'common/scripted_triggers/cowagot_building_requirement_triggers.txt'
    old = read('cow',p)
    base = read('agot','common/scripted_triggers/00_building_requirement_triggers.txt')
    n = one(base,'building_quarries_requirement_terrain')
    rule = base[n.start:n.end]
    gate = one(rule,'building_quarries_requirement_terrain').one('OR')
    additions = '\n        # USF: preserve COW exceptions on Tarth.\n' + '\n'.join('        this.barony = title:b_' + x for x in ['castlestar','sundown','bright_tree','spur']) + '\n    '
    rule = edit(rule,[(gate.closing,gate.closing,additions)])
    output(p,comment(old,'replaced by current AGOT terrain requirement plus original Tarth exceptions')+'\n\n'+rule+'\n','cow',reason='Modern quarry terrain requirement, including Iron Islands restriction, with four COW Tarth exceptions.')
    simple('cow','common/scripted_guis/cow_custom_mapmodes_gui.txt',[
        ('exists = global_var:highlight_cow_provinces_map','exists = global_var:cow_custom_map_mode'),
        ('global_var:cow_custom_map_mode = flag:highlight_special_buildings_map','global_var:cow_custom_map_mode = flag:highlight_cow_provinces_map')], 'Match the actual map mode variable and its existing flag value.')

    # Crowns of Westeros is excluded from this patch. Its eight former outputs
    # and build fragment are retained under docs/disabled-crowns-2026-09-22.
    # AGOT crown helpers used by Legacy of the Dragon remain enabled above.

    p='common/scripted_effects/00_agot_scenario_clash_of_kings_effects.txt'
    base=read('agot',p)
    bm=read('bookmarked',p)
    assert any(n.key=='agot_8299_6_13_acok_scenario_setup' for n in parse(bm))
    assert not any(n.key=='agot_8299_4_1_acok_scenario_setup' for n in parse(bm))
    n=one(base,'agot_8299_4_1_acok_scenario_setup')
    output('common/scripted_effects/usf_bookmarked_april_scenario.txt',
           '# USF: restore current AGOT April setup alongside Bookmarked June setup.\n'+base[n.start:n.end]+'\n',
           'agot',p,'Copy exact AGOT April effect under a unique path; preserve Bookmarked June scenario.')
    simple('vs','common/scripted_triggers/00_valyrian_artifact_triggers.txt',[
        ('flag:blackDarkRed','flag:blackdarkred'),('flag:iceFire','flag:icefire')], 'Match current case-sensitive egg color values; no model or texture changes.')
    p='common/modifier_definition_formats/agot_scheme_definitions.txt'
    t=read('vs',p)
    changes=[]
    for key in ['bond_with_dragon_scheme_success_chance_add','bond_with_dragon_scheme_scheme_success_chance_add']:
        n=one(t,key)
        changes.append((n.start,n.end,comment(t[n.start:n.end],'obsolete display format; current phase-duration formats preserved')))
    output(p,edit(t,changes),'vs',reason='Comment two unavailable display formats only.')

    # Same-path copies avoid adding duplicate keys to localization/replace.
    p='localization/replace/russian/game_concepts_l_russian.yml'
    t=read('agot_ru',p)
    t=replace(t, ", чья религиозная концепция — [GetReligionFamily('rf_valyrian').GetName],", '')
    read('agot','localization/replace/english/game_concepts_l_english.yml')
    output(p,t,'agot_ru',reason='Match current AGOT English description, which has no obsolete family restriction.')
    p='localization/replace/russian/dlc/tgp/dlc_tgp_china_game_concepts_l_russian.yml'
    source='AGOT_Submods/AGOT_RUS_CORRECT/'+p
    t=read('repo',source)
    t=replace(t,"[GetDecision('tgp_minister_recruit_courtiers_decision').GetName|V]",'#V $tgp_minister_recruit_courtiers_decision$#!',2)
    output(p,t,'repo',source,'Use existing localized decision name without looking up an unavailable decision object.')

    from Resources import build_resources
    build_resources(sys.modules[__name__])


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--init-baseline',action='store_true')
    ap.add_argument('--check',action='store_true')
    args=ap.parse_args()
    build()
    baseline=MOD/'docs/source-baseline.json'
    if args.init_baseline:
        assert not args.check and not baseline.exists(), 'Baseline initialization is one-time only.'
    else:
        expected=json.loads(baseline.read_text(encoding='utf-8'))
        assert INPUTS==expected, 'Source content or paths changed; review before rebuilding.'
    manifest={p:dict(bytes=len(b),sha256=digest(b)) for p,b in OUTPUTS.items()}
    if args.check:
        for p,b in OUTPUTS.items():
            assert (MOD/p).read_bytes()==b, 'Generated file differs: '+p
        assert json.loads((MOD/'docs/source-manifest.json').read_text(encoding='utf-8'))==manifest
        for path, data in DESCRIPTORS.items():
            assert path.read_bytes() == data, 'Descriptor differs: '+str(path)
        assert json.loads((MOD/'docs/resource-build.json').read_text(encoding='utf-8')) == RESOURCE_AUDIT
        print('PASS: pinned sources and all',len(OUTPUTS),'generated files match.')
        return
    oldmanifest=MOD/'docs/source-manifest.json'
    previous=json.loads(oldmanifest.read_text(encoding='utf-8')) if oldmanifest.exists() else {}
    assert not (set(previous)-set(OUTPUTS)), 'Explicit migration required for removed generated files.'
    for p in OUTPUTS:
        target=MOD/p
        if target.exists():
            assert p in previous and digest(target.read_bytes())==previous[p]['sha256'], 'Refusing to overwrite local edits: '+p
    old_descriptor = (MOD/'docs/resources-before-descriptor.mod').read_bytes()
    for path, data in DESCRIPTORS.items():
        initial = old_descriptor if path == MOD/'descriptor.mod' else old_descriptor+('path="'+MOD.as_posix()+'"\n').encode('utf-8')
        assert path.read_bytes() in (initial, data), 'Refusing to overwrite local descriptor edits: '+str(path)
    for p,b in OUTPUTS.items():
        target=MOD/p
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists() or target.read_bytes()!=b:
            target.write_bytes(b)
    (MOD/'docs').mkdir(exist_ok=True)
    for path, data in DESCRIPTORS.items():
        if path.read_bytes() != data:
            path.write_bytes(data)
    for filename,data in [('source-baseline.json',INPUTS),('source-manifest.json',manifest),('fixes.json',FIXES),('resource-build.json',RESOURCE_AUDIT)]:
        (MOD/'docs'/filename).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('Built',len(OUTPUTS),'files; source hashes pinned; Workshop and AGOT+ untouched.')


if __name__=='__main__':
    main()
