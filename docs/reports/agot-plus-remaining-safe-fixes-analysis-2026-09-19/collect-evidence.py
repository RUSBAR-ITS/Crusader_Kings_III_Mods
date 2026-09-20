"""Collect focused, read-only evidence for proposed fixes; write reports only."""
from pathlib import Path
import hashlib
import json
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
FIX = REPO / 'AGOT_Submods/AGOT_PLUS_FIX'
PLUS = Path('E:/SteamLibrary/steamapps/workshop/content/1158310/2950245430')
AGOT = Path('E:/SteamLibrary/steamapps/workshop/content/1158310/2962333032')
GAME = Path('E:/SteamLibrary/steamapps/common/Crusader Kings III/game')
mods = json.loads((HERE/'active-mods.json').read_text(encoding='utf-8'))
pins = json.loads((HERE/'source-pins.json').read_text(encoding='utf-8'))
evidence = []

def read(path):
    raw = path.read_bytes()
    pins[str(path)] = hashlib.sha256(raw).hexdigest().upper()
    return raw.decode('utf-8-sig')

def pin_binary(path):
    pins[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest().upper()
    return pins[str(path)]

def effective(rel):
    found = None
    for mod in mods:
        if any(rel == p or rel.startswith(p.rstrip('/')+'/') for p in mod['Replace']):
            found = None
        candidate = Path(mod['Path'])/rel
        if candidate.is_file():
            found = candidate
    assert found is not None, rel
    return found

def block(path, symbol):
    text = read(path)
    match = re.search(r'(?m)^'+re.escape(symbol)+r'\s*=\s*\{', text)
    assert match, (path, symbol)
    # Sources selected below use a column-zero closing brace at top level.
    end = re.search(r'(?m)^\}', text[match.end():])
    assert end, (path, symbol)
    body = text[match.start():match.end()+end.end()]
    evidence.append(dict(Path=str(path), Symbol=symbol,
                         Line=text[:match.start()].count('\n')+1, Text=body))
    return body

def lines(path, first, last):
    text = read(path).splitlines()
    evidence.append(dict(Path=str(path), Line=first,
                         Text='\n'.join(text[first-1:last])))

for filename, symbols in {
    '00_agot_char_north_ancestors.txt': ['Dormand_10', 'Dormand_12'],
    '00_agot_char_westerlands_ancestors.txt': ['Broome_35','Broome_54','Brax_67'],
    '00_agot_char_norvos.txt': ['Hotah_1_B'],
    '00_agot_char_norvos_ancestors.txt': ['Hotah_rs_98'],
    '00_agot_char_dragonstone_ancestors.txt': ['Targaryen_70_B'],
}.items():
    path = effective('history/characters/'+filename)
    for symbol in symbols:
        block(path, symbol)

for first,last in [(2658,2667),(4809,4827),(5749,5767),(6253,6261),
                   (11255,11257),(12163,12179),(1179,1189)]:
    lines(FIX/'common/scripted_effects/asoiaf_setup_effects.txt',first,last)
lines(FIX/'common/on_action/asoiaf_setup.txt',1,19)
block(FIX/'common/on_action/asoiaf_setup.txt','asoiaf_setup_alternative_ages')
lines(FIX/'common/scripted_effects/asoiaf_assign_inactive_traits_effects.txt',522,532)
block(FIX/'common/scripted_effects/asoiaf_canon_children_effects.txt',
      'asoiaf_canon_children_Targaryen_61_1_birth_effect')
lines(FIX/'common/scripted_effects/asoiaf_canon_children_effects.txt',13930,13937)

coa = 'common/coat_of_arms/coat_of_arms/'
for file, symbols in {
    'reach_dynasties.txt':['dynn_Thornton','dynn_Bridges','dynn_Yelshire'],
    'riverland_dynasties.txt':['dynn_Byrne'],
    'northern_dynasties.txt':['dynn_Wibberley'],
    'westerland_dynasties.txt':['dynn_Brax'],
}.items():
    for symbol in symbols:
        block(AGOT/coa/file,symbol)
for file,symbols in {
    'test_reach_dynasties.txt':['dynn_Thornton','dynn_Bridges','dynn_Yelshire'],
    'test_riverland_dynasties.txt':['dynn_Byrne'],
    'test_northern_dynasties.txt':['dynn_Wibberley'],
    'test_personal_coas.txt':['Brax_rhllor_personal_coa'],
    'zzz_westerland_dynasties.txt':['dynn_Brax'],
}.items():
    for symbol in symbols:
        block(PLUS/coa/file,symbol)

decision_names = ['asoiaf_greyjoy_cadets_decision','asoiaf_baelish_cadets_decision',
                  'asoiaf_harlaw_cadets_decision','asoiaf_jon_targ_cadet_branch_decision',
                  'asoiaf_aegon_II_greens_cadet_branch_decision']
for name in decision_names:
    file = 'asoiaf_house_branch_decisions.txt' if name in decision_names[:3] else 'asoiaf_jon_targ_cadet_branch_decision.txt'
    body = block(effective('common/decisions/'+file),name)
    active = re.sub(r'#[^\n]*','',body)
    assert re.search(r'ai_will_do\s*=\s*\{\s*base\s*=\s*0\s*\}',active)
    assert 'ai_check_interval' not in active
lines(GAME/'common/decisions/_decisions.info',99,115)

for symbol in ['asoiaf_oathkeeper_modifier','asoiaf_stark_throne_modifier']:
    block(FIX/'common/modifiers/asoiaf_artifact_modifiers.txt',symbol)
block(PLUS/'common/modifiers/asoiaf_canon_children_modifiers.txt','asoiaf_Karstark_4_modifier')
block(FIX/'common/scripted_effects/asoiaf_scripted_effects_artifacts.txt','create_artifact_stark_throne_effect')
block(FIX/'events/asoiaf_mega_war_events.txt','asoiaf_mega_war_events.0001')
block(FIX/'events/asoiaf_young_griff_landing_events.txt','asoiaf_young_griff_landing_events.2')
block(PLUS/'common/artifacts/visuals/asoiaf_visuals.txt','asoiaf_hound_armour_visuals')
block(GAME/'common/artifacts/visuals/00_personal_misc.txt','armor')
lines(GAME/'gfx/models/artifacts/clothing/m_clothes_sec_western_war_nob_01_artifact.asset',1,40)
block(AGOT/'common/scripted_effects/00_agot_character_history_effects.txt','agot_safe_crush_history_effect')

royal = 'gfx/models/portraits/m_cloaks/asoiaf/asoiaf_westerlands/asoiaf_lannister_cloaks/asoiaf_lannister_cloak_royal'
native = 'gfx/models/portraits/m_cloaks/agot/shouldercape'
inventory = []
for path in sorted((PLUS/royal).iterdir()):
    if not path.is_file():
        continue
    h = pin_binary(path)
    corresponding = AGOT/native/path.name
    row = dict(Name=path.name, PlusSHA256=h)
    if corresponding.exists():
        row['AGOTSHA256'] = pin_binary(corresponding)
        row['Identical'] = h == row['AGOTSHA256']
    inventory.append(row)
assert len(inventory) == 15
duplicates = [r for r in inventory if r['Name'].endswith('.dds')]
assert len(duplicates) == 4 and all(r['Identical'] for r in duplicates)
royal_asset = FIX/royal/'asoiaf_lannister_cloak_royal.asset'
read(royal_asset)
assert len(list((FIX/royal).iterdir())) == 1

resources = {}
for name in ['ce_solidblock.dds','no_frikrigg_01.dds','vale_seldon_rayonne5.dds','ce_circle.dds','pattern_solid.dds']:
    folder = 'patterns' if name.startswith('pattern') else 'colored_emblems'
    path = effective('gfx/coat_of_arms/'+folder+'/'+name)
    resources[name] = dict(Path=str(path), SHA256=pin_binary(path))

manifest_path = FIX/'docs/source-manifest.json'
manifest = json.loads(read(manifest_path))
assert manifest['Revision'] == 13
for row in manifest['Files']:
    path = FIX/row['File']
    assert pin_binary(path) == row['PatchedSHA256'], row['File']

summary = dict(RuntimeFilesUnchanged=len(manifest['Files']), Revision=13,
               DisabledAIDecisionsChecked=len(decision_names),
               CloakFolder=royal, CloakInventory=inventory,
               ReplacementResources=resources, EvidenceExcerpts=len(evidence),
               Scope='Analysis only; no candidate game patch has been applied or run.')
for name,data in [('focused-evidence.json',evidence),('verification.json',summary),
                  ('evidence-source-pins.json',pins)]:
    (HERE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(RuntimeFilesUnchanged=summary['RuntimeFilesUnchanged'],
                     EvidenceExcerpts=len(evidence), PinnedFiles=len(pins),
                     IdenticalDDS=len(duplicates)),ensure_ascii=False))
