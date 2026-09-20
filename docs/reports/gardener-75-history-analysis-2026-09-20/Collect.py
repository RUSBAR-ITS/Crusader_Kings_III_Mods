"""Read-only research: pin local sources and public historical file excerpts."""
from pathlib import Path
import concurrent.futures
import hashlib
import json
import sys
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'AGOT_Submods/AGOT_SUBMODS_FIX/tools'))
from ScriptBlocks import parse

WORKSHOP = Path('E:/SteamLibrary/steamapps/workshop/content/1158310')
sources = []


def record(label, data, locator, needles, context=4):
    text = data.decode('utf-8-sig').replace('\r\n', '\n')
    lines = text.splitlines()
    indices = set()
    for i, line in enumerate(lines):
        if any(n in line for n in needles):
            indices.update(range(max(0, i-context), min(len(lines), i+context+1)))
    return dict(Label=label, Source=locator, SHA256=hashlib.sha256(data).hexdigest(),
                Bytes=len(data), Excerpts=[dict(Line=i+1, Text=lines[i]) for i in sorted(indices)]), text


local = [
    ('crowns_effects', '2995674648/common/scripted_effects/00_ntc_scripted_effects_crowns.txt', ['Gardener_75'], 9),
    ('crowns_localization', '2995674648/localization/replace/english/ntc_artifacts_l_english.yml', ['garthgoldhand_crown_description:', 'gardener_war_crown_description:', 'gardener_peace_crown_description:'], 0),
    ('crowns_start', '2995674648/common/scripted_effects/00_ntc_startdate_crown_spawn.txt', ['create_artifact_gardener_'], 8),
    ('crowns_decisions', '2995674648/common/decisions/agot_decisions/00_ntc_artifact_decisions.txt', ['create_artifact_gardener_'], 4),
    ('core_portraits', '3034473189/gfx/portraits/portrait_modifiers/01_headgear_base.txt', ['Gardener_75'], 3),
    ('agot_characters', '2962333032/history/characters/00_agot_char_reach_ancestors.txt', ['Gardener_73 =', 'Gardener_28 =', 'Gardener_77 ='], 12),
    ('agot_titles', '2962333032/history/titles/agot_e_the_reach.txt', ['holder = Gardener_73', 'holder = Gardener_61', 'holder = Gardener_63', 'holder = Gardener_77'], 3),
    ('agot_province', '2962333032/common/landed_titles/01_agot_landed_titles.txt', ['province = 3237'], 4),
]
texts = {}
for label, relative, needles, context in local:
    path = WORKSHOP / relative
    source, text = record(label, path.read_bytes(), path.as_posix(), needles, context)
    sources.append(source)
    texts[label] = text

inventory = Path('E:/SteamLibrary/steamapps/common/Crusader Kings III/game/localization/english/inventory/inventory_l_english.yml')
source, _ = record('ck3_history_localization', inventory.read_bytes(), inventory.as_posix(),
                   ['artifact_history_created_desc:', 'artifact_history_created_before_history_desc:'], 0)
sources.append(source)

public = [
    ('crowns_2024_06_29', 'Nerdman3000/AGOT-Crowns-of-Westeros_Public-Release', 'a81dd0c7b8435ea31bd0756984420affa7b9abf4', 'common/scripted_effects/00_ntc_scripted_effects_crowns.txt', ['Gardener_75'], 5),
    ('core_2024_03_21', 'JediNick/AGOT_Submod_Core', 'df354b86c52bb257e37b6db020c844aa5147bc9d', 'gfx/portraits/portrait_modifiers/01_headgear_base.txt', ['Gardener_75'], 3),
    ('core_2026_02_20', 'JediNick/AGOT_Submod_Core', '40d536e21c3f9f0eae8860e89b6779f77c7528ad', 'gfx/portraits/portrait_modifiers/01_headgear_base.txt', ['Gardener_75'], 3),
    ('core_2026_03_07', 'JediNick/AGOT_Submod_Core', '5426feff61524ca0d2815c386016345d0f4b7abd', 'gfx/portraits/portrait_modifiers/01_headgear_base.txt', ['Gardener_75'], 3),
    ('bookmarked_2024_06_14', 'Troofax/AGOT_Bookmarked', 'fcf75c70baf2544cef1d3ba4f238cfafd86b28c1', 'history/titles/agot_empire_tier_titles.txt', ['Gardener_75'], 10),
]


def fetch(args):
    label, repo, sha, path, needles, context = args
    url = f'https://raw.githubusercontent.com/{repo}/{sha}/{path}'
    req = urllib.request.Request(url, headers={'User-Agent': 'CK3-mod-research'})
    data = urllib.request.urlopen(req, timeout=40).read()
    result, _ = record(label, data, url, needles, context)
    result['Commit'] = sha
    result['BrowseURL'] = f'https://github.com/{repo}/blob/{sha}/{path}'
    return result


with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
    sources.extend(pool.map(fetch, public))

characters = []
for n in parse(texts['agot_characters']):
    if n.key.startswith('Gardener_'):
        name = n.children('name')[0].value
        characters.append(dict(ID=n.key, Name=name, Line=texts['agot_characters'].count('\n', 0, n.start)+1,
                               Body=texts['agot_characters'][n.start:n.end]))

summary = dict(RuntimeFilesChanged=False, GardenerDefinitions=len(characters),
               MissingIDPresent=any(c['ID'] == 'Gardener_75' for c in characters),
               MerynCandidates=[c['ID'] for c in characters if c['Name'] == 'Meryn'],
               JohnIIICurrentID='Gardener_73', CurrentChildOfJohnIII='Gardener_61',
               CurrentGapAggregateID='Gardener_28', ProvenModernReplacement=None,
               Caveat='Old Bookmarked title comment calls Gardener_75 Merlon; Crowns and Core call him Meryn IV. No original character definition recovered.')

effects = []
for n in parse(texts['crowns_effects']):
    if n.key in ['create_artifact_gardener_war_crown_effect', 'create_artifact_gardener_peace_crown_effect']:
        effects.append(dict(ID=n.key, Line=texts['crowns_effects'].count('\n', 0, n.start)+1,
                            Body=texts['crowns_effects'][n.start:n.end]))
assert len(effects) == 2

for filename, data in [('source-evidence.json', sources), ('current-gardeners.json', characters), ('effects.json', effects), ('summary.json', summary)]:
    (HERE / filename).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
print(json.dumps(summary, ensure_ascii=False, indent=2))
