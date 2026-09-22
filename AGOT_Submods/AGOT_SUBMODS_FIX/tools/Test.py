"""Static contracts and finite-state checks, not an emulator or a CK3 run."""
import collections
import csv
import hashlib
import itertools
import json
from pathlib import Path
import re
import subprocess
import sys
import Build as b
from CrownWithoutCreator import CROWN_SOURCE, LOTD_CROWNS, function_names
from ScriptBlocks import one, parse, semantic, walk

sys.stdout.reconfigure(encoding='utf-8')
checks=[]


def ok(name, condition=True):
    assert condition, name
    checks.append(name)


def patched(path):
    return (b.MOD/path).read_text(encoding='utf-8-sig')


def codes(text):
    return [semantic(n) for n in parse(text)]


def source(owner,path):
    return b.read(owner,path)


def evaluate(node,state):
    """Evaluate only the boolean subset used by the edited test conditions."""
    key=node.key
    if key in ('trigger','is_shown','limit','AND'):
        return all(evaluate(n,state) for n in node.value)
    if key=='NOT':
        return not all(evaluate(n,state) for n in node.value)
    if key=='NOR':
        return not any(evaluate(n,state) for n in node.value)
    if key=='OR':
        return any(evaluate(n,state) for n in node.value)
    if key=='any_artifact':
        return any(all(evaluate(n,dict(state,artifact=a)) for n in node.value) for a in state['artifacts'])
    if key=='any_living_character':
        return any(all(evaluate(n,dict(state,character=c)) for n in node.value) for c in state['characters'] if c['alive'])
    if key=='has_variable':
        return node.value in state['artifact']
    if key=='has_character_flag':
        return node.value in state['character']['flags']
    if key=='is_target_in_global_variable_list':
        return node.one('target').value in state.get(node.one('name').value,set())
    if key=='exists':
        return node.value in state
    if key.startswith('global_var:'):
        return state.get(key)==node.value
    raise AssertionError('Unsupported test condition: '+key)


def main():
    subprocess.run([sys.executable,str(b.MOD/'tools/Build.py'),'--check'],check=True)
    outputs=json.loads((b.MOD/'docs/source-manifest.json').read_text(encoding='utf-8'))
    runtime=[p.relative_to(b.MOD).as_posix() for root in ['common','events','localization','gfx'] for p in (b.MOD/root).rglob('*') if p.is_file()]
    ok('Runtime file set matches manifest',set(outputs)==set(runtime))
    ok('Generated language script has CK3-required UTF-8 BOM',
       (b.MOD/'common/scripted_effects/usf_language_effects.txt').read_bytes().startswith(b'\xef\xbb\xbf'))
    for p in runtime:
        data=(b.MOD/p).read_bytes()
        if p.endswith(('.mesh','.dds')):
            continue
        ok('LF and strict UTF-8: '+p,b'\r' not in data)
        text=data.decode('utf-8-sig')
        if p.endswith(('.txt','.asset')):
            parse(text)
        if p.endswith('.yml'):
            ok('Localization BOM: '+p,data.startswith(b'\xef\xbb\xbf'))
    ok('Optional integration files and vanilla DI not overridden', not any(p in outputs for p in [
        'common/scripted_triggers/tgc_loaded_trigger.txt','gfx/portraits/portrait_modifiers/00_custom_cloaks.txt',
        'gfx/portraits/portrait_modifiers/01_cloaks_base.txt','common/character_interactions/DI_character_interaction.txt',
        'common/modifiers/DI_modifiers.txt','common/scripted_effects/DI_char_spawner_effects.txt']))

    # Preserve every artifact property other than the approved template replacement.
    p='common/scripted_effects/00_agot_artifact_vs_sword_effects_override.txt'
    old=source('lotd',p);new=patched(p)
    original_creates=[n for n in walk(parse(old)) if n.key=='create_artifact']
    new_creates=[n for n in walk(parse(new)) if n.key=='create_artifact']
    ok('Same number of LOTD artifact creations',len(original_creates)==len(new_creates))
    for a,c in zip(original_creates,new_creates):
        ok('Artifact properties/history preserved at '+str(a.start),
           [semantic(n) for n in a.value if n.key!='template']==[semantic(n) for n in c.value if n.key!='template'])
    t=source('agot','common/artifacts/templates/00_agot_historical_artifacts_equipment.txt')
    one(t,'valyrian_steel_template')
    ok('Replacement valyrian steel template exists')

    # Read the actual modified Maekar trigger and exhaust absence/presence/list cases.
    p='events/decisions_events/rediscover_events.txt'
    t=patched(p)
    branches=[n for n in walk(parse(t)) if n.key=='1' and isinstance(n.value,list)
              and any(x.key=='set_variable' and 'flag:maekars_crown' in t[x.start:x.end] for x in n.value)]
    ok('One Maekar selection branch',len(branches)==1)
    gate=branches[0].one('trigger')
    for count,blocked,other in itertools.product(range(3),[False,True],[False,True]):
        state=dict(artifacts=[{'crown_maekar_artifact'}]*count+([{'unrelated_artifact'}] if other else []),
                   unavailable_artifacts={'flag:maekars_crown'} if blocked else {'flag:some_other_crown'})
        ok(f'Maekar state count={count} unavailable={blocked} other={other}',evaluate(gate,state)==(count==0 and not blocked))
    old=source('lotd',p)
    func=re.compile(r'agot_create_artifact_\w+_effect\s*=\s*\{[^{}]*\}')
    original_names = t
    for original, replacement in function_names(LOTD_CROWNS, 'usf').items():
        original_names = original_names.replace(replacement, original)
    ok('LOTD crown arguments and historical calls preserved',func.findall(old)==func.findall(original_names))
    helpers = patched('common/scripted_effects/usf_crowns_without_creator_effects.txt')
    for original, replacement in function_names(LOTD_CROWNS, 'usf').items():
        base = one(source('agot', CROWN_SOURCE), original)
        actual = one(helpers, replacement)
        expected = [semantic(n) for n in base.value if n.key != '$CREATOR$']
        creation = next(n for n in expected if n[0] == 'create_artifact')
        creation[2][:] = [n for n in creation[2] if n[0] != 'creator']
        ok('Crown properties and markers preserved without maker: '+replacement,
           expected == [semantic(n) for n in actual.value])
        ok('Exactly one OWNER-only LOTD call: '+replacement,
           sum(n.key == replacement and [semantic(c) for c in n.value] == [('OWNER', '=', 'this')] for n in walk(parse(t))) == 1)
    ok('Empty-result sentinel preserved','value = flag:all_found' in t)

    p='common/decisions/10_lotd_decisions.txt'
    cost=one(source('lotd',p),'buy_ruby_crown').one('cost').one('gold').value
    event=one(patched('events/decisions_events/buy_ruby_crown_events.txt'),'buy_ruby_crown.0999')
    ok('Ruby crown costs exactly the decision fee',cost=='450' and not any(n.key=='remove_short_term_gold' for n in walk(event.value)))

    # Excluding Crowns must remove its base-event override as well as its own files.
    archive = b.MOD/'docs/disabled-crowns-2026-09-22'
    excluded = json.loads((archive/'manifest.json').read_text(encoding='utf-8'))['files']
    ok('Exactly eight Crowns outputs archived', len(excluded) == 8)
    for rel, record in excluded.items():
        ok('Crowns output absent from runtime: '+rel, rel not in outputs and not (b.MOD/rel).exists())
        ok('Archived Crowns bytes preserved: '+rel,
           b.digest((archive/'runtime'/rel).read_bytes()) == record['sha256'])
    ok('Crowns sources no longer required by build', not any(k.startswith('crowns/') for k in b.INPUTS))
    for descriptor in [b.MOD/'descriptor.mod', b.MOD.parent/'AGOT_SUBMODS_FIX.mod']:
        ok('Crowns dependency removed: '+descriptor.name,
           '"AGOT - Crowns of Westeros"' not in descriptor.read_text(encoding='utf-8'))

    p='common/scripted_guis/cow_custom_mapmodes_gui.txt'
    gate=one(patched(p),'highlight_cow_provinces_map').one('is_shown')
    for val in [None,'flag:other_map','flag:highlight_cow_provinces_map']:
        state={} if val is None else {'global_var:cow_custom_map_mode':val}
        ok('COW selected mode '+str(val),evaluate(gate,state)==(val=='flag:highlight_cow_provinces_map'))
    p='common/buildings/yy_agotcities_special_buildings_westeros.txt'
    a=source('cow',p);c=patched(p)
    watched = ['trigger_event']
    ok('Other COW events preserved',
       [semantic(n) for n in walk(parse(a)) if n.key in watched and n.value != 'agot_cities.5000'] ==
       [semantic(n) for n in walk(parse(c)) if n.key in watched])
    base_buildings = source('agot', 'common/buildings/00_agot_special_buildings_westeros.txt')
    for field in ['character_modifier', 'county_holder_character_modifier']:
        ok('COW Planky Town bonuses equal current AGOT: '+field,
           semantic(one(c, 'agot_plankytown_01').one(field)) == semantic(one(base_buildings, 'agot_plankytown_01').one(field)))
    ok('No active old Rhoynish bonus',not any(n.key == 'rhoynish_religion_opinion' for n in walk(parse(c))))
    actions = patched('common/on_action/cowagot_province_on_actions.txt')
    original_actions = source('cow', 'common/on_action/cowagot_province_on_actions.txt')
    original_effect = one(original_actions, 'harlaw_building_check_on_actions').one('effect')
    current_effect = one(actions, 'harlaw_building_check_on_actions').one('effect')
    expected_effect = [semantic(n) for n in original_effect.value
                       if not any(c.key == 'add_special_building_slot' and c.value == 'harlaw_mines_01' for c in n.value)]
    ok('Harlaw Ten Towers branch and holder fallback preserved',
       expected_effect == [semantic(n) for n in current_effect.value])
    ok('No active unavailable Harlaw mine',not any(n.value == 'harlaw_mines_01' for n in walk(parse(actions))))
    for key in ['planky_town_special', 'agot_castamere_03', '24castamere_03']:
        original = one(a, key); current = one(c, key)
        ok('COW building preserved except unavailable callback: '+key,
           [semantic(n) for n in original.value if n.key != 'on_complete'] ==
           [semantic(n) for n in current.value])
    ok('Three unavailable COW calls retained as comments',
       len(re.findall(r'^\s*#\s*trigger_event\s*=\s*agot_cities\.5000\s*$', c, re.M)) == 3)
    ok('COW castle upgrade cannot downgrade higher tiers',
       sum(n.key=='has_building_or_higher' and n.value=='castle_05' for n in walk(parse(c)))==1)
    gate=one(patched('common/scripted_triggers/cowagot_building_requirement_triggers.txt'),'building_quarries_requirement_terrain')
    ok('COW four Tarth exceptions preserved',len([n for n in gate.one('OR').value if n.key=='this.barony'])==4)
    ok('COW modern Iron Islands condition preserved',gate.one('NOT').one('geographical_region').value=='world_westeros_the_iron_islands')

    # Finite enumeration of the language helper's actual selection condition.
    helper=one(patched('common/scripted_effects/usf_language_effects.txt'),'usf_learn_four_available_languages_effect')
    loop=helper.one('while');selector=loop.one('random_culture_global')
    ok('Language helper loop bound',loop.one('count').value=='4')
    ok('Language condition uses candidate culture',selector.one('limit').one('scope:usf_language_student').one('NOT').one('knows_language_of_culture').value=='prev')
    ok('Language learned from selected culture',selector.one('scope:usf_language_student').one('learn_language_of_culture').value=='scope:usf_language_culture')
    cases=0
    for languages in [[],['common','common'],['common','common','valyrian'],['a','a','b','c','d','e','f']]:
        for initial in [set(),{'common'},{'a','b'}]:
            states={frozenset(initial)}
            for _ in range(int(loop.one('count').value)):
                next_states=set()
                for known in states:
                    candidates=[x for x in languages if x not in known]
                    if not candidates:next_states.add(known)
                    for x in candidates:next_states.add(known|{x})
                states=next_states
            expected=min(4,len(set(languages)-initial))
            ok('Distinct available languages '+repr((languages,initial)),all(len(s-initial)==expected and initial<=s for s in states))
            cases+=len(states)

    # Exact restored scenario, and unchanged Bookmarked June effect still present.
    p='common/scripted_effects/00_agot_scenario_clash_of_kings_effects.txt'
    key='agot_8299_4_1_acok_scenario_setup'
    ok('Bookmarked April scenario equals current AGOT',semantic(one(source('agot',p),key))==semantic(one(patched('common/scripted_effects/usf_bookmarked_april_scenario.txt'),key)))
    one(source('bookmarked',p),'agot_8299_6_13_acok_scenario_setup')
    ok('Bookmarked June scenario retained')
    for p in outputs:
        ok('No AGOT+ source files included: '+p,not p.startswith(('common/dna_data/','history/')))
    ok('Known dynamic crown calls deferred',not any('test_title_on_actions' in x for x in outputs))

    # Verify source owners not altered and protect all inspected sources from the analysis.
    evidence=json.loads((b.REPO/'docs/reports/scripts-variables-analysis-2026-09-19/source-evidence-manifest.json').read_text(encoding='utf-8'))
    changed=[x for x in evidence if hashlib.sha256(Path(x['path']).read_bytes()).hexdigest()!=x['sha256']]
    plus = b.REPO/'AGOT_Submods/AGOT_PLUS_FIX'
    for item in changed:
        plan=json.loads((plus/'docs/stage15-plan.json').read_text(encoding='utf-8'))
        ok('Only approved AGOT+ title grant delta in protected sources',
           Path(item['path']).resolve() == (plus/plan['TitleFile']).resolve() and
           hashlib.sha256((plus/'docs'/plan['TitleArchive']).read_bytes()).hexdigest() == item['sha256'] and
           hashlib.sha256(Path(item['path']).read_bytes()).hexdigest().upper() == plan['TitleAfterSHA256'])
    ok('Other inspected existing sources unchanged',len(changed) <= 1)
    result=dict(checks=len(checks),language_outcomes=cases,files=len(outputs),status='PASS',
                limitation='Static syntax/contract/finite-state checks only; CK3 has not been run with the new patch.',checks_passed=checks)
    (b.MOD/'docs/validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS:',len(checks),'checks;',len(outputs),'runtime files; protected original sources unchanged.')


if __name__=='__main__':
    main()
