"""Classify the captured diagnostics; write report artifacts only.

Requires Inspect-Sources.py index first. Assertions check inventory coverage,
not CK3 runtime behavior. Manual conclusions are recorded in README.md.
"""
import collections
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('inspect_sources', HERE / 'Inspect-Sources.py')
src = importlib.util.module_from_spec(spec)
spec.loader.exec_module(src)


def write_csv(name, records):
    with (HERE / name).open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(records)


# Each script diagnostic is assigned to one causal group, including diagnostics
# whose reported path points to the callee rather than the incompatible caller.
RULES = [
    ('shared-crown-creator', 'AGOT+ / Legacy of the Dragon', 'missing arguments: CREATOR'),
    ('crowns-event-duplicate', 'Crowns of Westeros', 'Duplicated event ID'),
    ('cow-missing-event', 'COW-AGOT', r'agot_cities\.5000'),
    ('localization-religion-family', 'AGOT Russian localization', 'rf_valyrian'),
    ('localization-decision', 'AGOT_RUS_CORRECT / CK3 localization', 'tgp_minister_recruit_courtiers_decision'),
    ('core-optional-armor', 'AGOT Submod Core', r'01_cloaks_base|01_legwear_base|05_clothes_situational|05_headgear_situational'),
    ('core-house-scope', 'AGOT Submod Core', "event target link 'house_Blackfyre'"),
    ('core-optional-tgc', 'AGOT Submod Core', 'tgc_loaded_trigger'),
    ('bookmarked-april-scenario', 'AGOT Bookmarked', 'agot_8299_4_1_acok_scenario_setup'),
    ('lotd-ruby-gold', 'Legacy of the Dragon', 'Negative value in remove_short_term_gold'),
    ('lotd-sword-templates', 'Legacy of the Dragon', '00_agot_artifact_vs_sword_effects_override'),
    ('lotd-scheme-bonus', 'Legacy of the Dragon', '00_lotd_artifact_creation_effects'),
    ('vs-scheme-formats', 'Valyrian Steel', 'agot_scheme_definitions'),
    ('crowns-culture-opinion', 'Crowns of Westeros', 'ntc_artifact_modifiers'),
    ('crowns-shattered-rule', 'Crowns of Westeros', 'ntc_artifacts_startdate'),
    ('cow-religion-opinion', 'COW-AGOT', 'rhoynish_religion_opinion'),
    ('cow-holding-trigger', 'COW-AGOT', 'Unknown trigger: holding'),
    ('cow-building-ids', 'COW-AGOT', 'cowagot_province_on_actions'),
    ('cow-quarries', 'COW-AGOT', 'cowagot_building_requirement_triggers'),
    ('di-confucian-xp', 'Divine Intervention + AGOT compatibility', 'confucian_education_xp_gain_mult'),
    ('di-varangian', 'Divine Intervention + AGOT compatibility', "'varangian'"),
    ('di-succession-innovation', 'Divine Intervention + AGOT compatibility', 'DI_change_succession'),
    ('di-persian-marriage', 'Divine Intervention + AGOT compatibility', 'DI_arrange_marriage_interaction'),
    ('di-faith-families', 'Divine Intervention + AGOT compatibility', 'DI_char_spawner_resolve_origin_effect'),
    ('di-polyglot', 'Divine Intervention + AGOT compatibility', 'DI_court_position_post_spawn_effect'),
    ('di-personalities', 'Divine Intervention + AGOT compatibility', 'DI_present_effects'),
    ('di-lhazar-language', 'Divine Intervention + AGOT compatibility', 'DI_cultural_editor_pillars_sgui'),
]

# Type matters: flag:roland_crown, a character flag and a variable with this name
# are not interchangeable. GUI reads and parameter-built writers count as use.
DECISIONS = {}


def variable(kind, keys, owner, issue, action):
    for key in keys.split():
        DECISIONS[(kind, key)] = dict(owner=owner, issue=issue, action=action)


variable('Flag', 'monastery_holding ruin_holding unknown_holding settlement_holding pirate_den_holding wilderness_holding',
         'Divine Intervention + AGOT compatibility', 'di-gui-holdings', 'KEEP: GUI supplies MakeScopeFlag values')
variable('Flag', 'global DI_subtype_throne',
         'Divine Intervention + AGOT compatibility', 'di-gui-artifact-origin', 'KEEP: GUI reads or switch fallback uses the value')
variable('Variable', 'DI_artifact_subtype_display DI_artifact_quality_display DI_artifact_category_display',
         'Divine Intervention + AGOT compatibility', 'di-gui-display', 'KEEP: GUI/localization reads display variables')
variable('Flag', 'highlight_special_buildings_map highlight_cow_provinces_map',
         'COW-AGOT', 'cow-map-mode', 'FIX: compare actual cow_custom_map_mode value to highlight_cow_provinces_map')
variable('Variable', 'highlight_cow_provinces_map',
         'COW-AGOT', 'cow-map-mode', 'FIX: exists must test global_var:cow_custom_map_mode')
variable('Variable', 'COWAGOT_is_loaded',
         'COW-AGOT', 'cow-integration-marker', 'KEEP: public integration marker, absence of installed consumers is expected')
variable('Flag', 'blackDarkRed iceFire',
         'Valyrian Steel', 'vs-egg-colors', 'FIX: blackdarkred / icefire, as written by current egg creation')
variable('Flag', 'roland_crown',
         'Crowns of Westeros', 'crowns-roland-uniqueness', 'REWORK: real artifact existence and in-progress lifecycle; do not fake unavailable_artifacts writer')
variable('Variable', 'is_baratheon_6',
         'Crowns of Westeros', 'crowns-myrcella', 'FIX: is_Baratheon_6')
variable('Variable', 'is_Durrandon_51',
         'Crowns of Westeros', 'crowns-baldric', 'FIX CANDIDATE: guarded historical character:Durrandon_51 identity; no invented dynamic birth chain')
variable('Variable', 'maekars_crown',
         'Legacy of the Dragon', 'lotd-maekar-selection', 'REWORK: require no crown_maekar_artifact and not unavailable; remove contradictory existence requirements')
variable('Variable', 'crown_aegon_baelor_artifact',
         'Legacy of the Dragon', 'lotd-baelor-marker', 'FIX: crown_baelor_artifact')
variable('Variable', 'blackfyre_artifact seafoam_artifact pincer_artifact',
         'Legacy of the Dragon', 'lotd-unused-sword-markers', 'COMMENT obsolete assignments after Core recognition uses current artifact modifiers')
variable('Flag', 'all_found',
         'Legacy of the Dragon', 'lotd-empty-result', 'KEEP: overwrites artifact_choice with empty-result sentinel; fallback does nothing')
variable('Variable', 'blackfyre darksister seafoam',
         'AGOT Submod Core', 'core-sword-recognition', 'FIX: has_artifact_modifier vs_blackfyre_modifier / vs_dark_sister_modifier / vs_seafoam_modifier')
variable('Variable', 'Aotk_enabled tgc_enabled brightboar_enabled kingsguard_choice captains_sword swordman_armor_artifact',
         'AGOT Submod Core', 'core-optional-markers', 'KEEP optional integration checks, or remove whole absent integration branches in a profile-specific build')
variable('Variable', 'app_enabled',
         'AGOT Submod Core', 'core-obsolete-cloak-gate', 'REVIEW: obsolete extra gate to an absent asoiaf_kingsguard_cloaks template; do not just enable it')


def main():
    scripts = src.rows(src.LOG / 'remaining-scripts.csv')
    inventory, variables = [], []
    for row in scripts:
        hits = [x for x in RULES if re.search(x[2], row['Message'])]
        assert hits, row
        # Only the first (most specific) rule owns a diagnostic.
        issue, owner, _ = hits[0]
        inventory.append(dict(category='scripts', log_line=int(row['Line']), owner=owner,
                              issue=issue, original_owner=row['Owner'], message=row['Message']))
    refs = json.loads(src.read(HERE / 'variable-references.json'))
    assert len(refs) == 36
    for row in refs:
        d = DECISIONS[(row['kind'], row['key'])]
        variables.append(dict(category=row['category'], kind=row['kind'], key=row['key'],
                              owner=d['owner'], issue=d['issue'], messages=len(row['log_lines']),
                              action=d['action'], log_lines=';'.join(map(str,row['log_lines']))))
        for ln in row['log_lines']:
            inventory.append(dict(category=row['category'], log_line=ln, owner=d['owner'],
                                  issue=d['issue'], original_owner='', message=row['kind'] + ' ' + row['key']))
    assert len(inventory) == 264
    assert len(set(r['log_line'] for r in inventory)) == 264
    assert collections.Counter(r['category'] for r in inventory) == dict(scripts=192, read_not_set=50, set_not_read=22)
    write_csv('diagnostic-inventory.csv', sorted(inventory, key=lambda r:r['log_line']))
    write_csv('variable-decisions.csv', variables)
    totals = []
    for owner in dict.fromkeys(r['owner'] for r in inventory):
        counts = collections.Counter(r['category'] for r in inventory if r['owner'] == owner)
        totals.append(dict(owner=owner, scripts=counts['scripts'], read_not_set=counts['read_not_set'],
                           set_not_read=counts['set_not_read'], total=sum(counts.values())))
    write_csv('totals-by-mod.csv', sorted(totals, key=lambda x:-x['total']))
    write_csv('issue-counts.csv', [dict(issue=k, messages=v) for k,v in sorted(collections.Counter(r['issue'] for r in inventory).items())])

    functions = set(re.findall(r'Compiling source for (\w+) failed', '\n'.join(r['Message'] for r in scripts)))
    pattern = r'\b(' + '|'.join(sorted(functions)) + r')\s*=\s*\{([^{}]*)\}'
    calls = []
    for item in src.candidates('|'.join(sorted(functions)), 'common') + src.candidates('|'.join(sorted(functions)), 'events'):
        code = '\n'.join(src.uncomment(x) for x in src.read(item['path']).splitlines())
        for m in re.finditer(pattern, code):
            if re.search(r'\bOWNER\s*=', m[2]) and not re.search(r'\bCREATOR\s*=', m[2]):
                calls.append(dict(owner=item['owner'], path=item['path'], line=code.count('\n',0,m.start())+1,
                                  function=m[1], arguments=m[2].strip()))
    assert len(calls) == 12, calls
    assert len(set(c['function'] for c in calls)) == 8
    src.save('missing-creator-call-sites.json', calls)

    index = src.loadindex()
    byrel = {x['relative']:x for x in index}
    evidence_paths = {x['path'] for row in refs for x in row['references']}
    evidence_paths.update(c['path'] for c in calls)
    for row in scripts:
        for rel in re.findall(r'(?:common|events|gfx|gui)/[\w./-]+\.txt', row['Message']):
            if rel in byrel:
                evidence_paths.add(byrel[rel]['path'])
    extras = [
        ('2962333032','common/scripted_effects/00_agot_scenario_clash_of_kings_effects.txt'),
        ('3149692324','common/scripted_effects/00_agot_scenario_clash_of_kings_effects.txt'),
        ('2995674648','events/activities/agot_coronation_activity/agot_activity_events_crown_commission.txt'),
        ('2962333032','common/artifacts/templates/00_agot_historical_artifacts_equipment.txt'),
        ('2962333032','common/religion/religion_types/00_agot_the_mother.txt'),
        ('2962333032','common/scripted_triggers/00_building_requirement_triggers.txt'),
        ('3101422928','common/decisions/10_lotd_decisions.txt'),
        ('2962333032','common/scripted_effects/00_agot_artifact_effects.txt'),
        ('3388366564','common/scripted_effects/00_agot_dragon_eggs_effects.txt'),
        ('2996152542','gui/DI_title_manager_templates/DI_title_manager_holding_type_list_template.gui'),
        ('2986538297','gui/DI_artifact_creator.gui'),
        ('2986538297','gui/DI_char_spawner.gui'),
        ('2962803371','localization/replace/russian/game_concepts_l_russian.yml'),
    ]
    workshop = Path('E:/SteamLibrary/steamapps/workshop/content/1158310')
    for mod, rel in extras:
        p = workshop / mod / rel
        assert p.exists(), p
        evidence_paths.add(str(p))
    evidence_paths.add(str(HERE.parents[2] / 'AGOT_Submods/AGOT_RUS_CORRECT/localization/replace/russian/dlc/tgp/dlc_tgp_china_game_concepts_l_russian.yml'))
    manifest = []
    for p in sorted(set(str(Path(p)) for p in evidence_paths)):
        data = Path(p).read_bytes()
        manifest.append(dict(path=p, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    src.save('source-evidence-manifest.json', manifest)
    log = src.LOG / 'snapshot/error.log'
    src.save('validation.json', dict(
        log=str(log), log_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),
        active_mods=len(src.rows(src.LOG/'active-mods.csv')), effective_files=len(index),
        diagnostics=len(inventory), categories=dict(collections.Counter(r['category'] for r in inventory)),
        unique_variable_diagnostics=len(refs), missing_creator_calls=len(calls),
        missing_creator_functions=len(functions), evidence_files=len(manifest),
        scope='Static analysis only. No runtime mod edits or CK3 run performed.'))
    print(json.dumps(totals, ensure_ascii=False, indent=2))
    print('PASS: 264 diagnostics assigned once; 36 variable decisions; 12 missing-CREATOR calls; source hashes captured.')


if __name__ == '__main__':
    main()
