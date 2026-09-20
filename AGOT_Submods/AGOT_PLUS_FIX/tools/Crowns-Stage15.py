"""Register and verify seven OWNER-only crown grants; no Workshop writes."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

MOD = Path(__file__).resolve().parents[1]
DOC = MOD/'docs'
REPO = MOD.parents[1]
sys.path.insert(0, str(REPO/'AGOT_Submods/AGOT_SUBMODS_FIX/tools'))
from ScriptBlocks import parse, one, semantic, walk
from CrownWithoutCreator import CROWN_SOURCE, PLUS_CROWNS, make_helpers, function_names

AGOT = Path('E:/SteamLibrary/steamapps/workshop/content/1158310/2962333032')
PLUS = AGOT.parent/'2950245430'
TITLE = 'common/on_action/agot_on_actions/test_title_on_actions.txt'
HELPERS = 'common/scripted_effects/apf_crowns_without_creator_effects.txt'
TEMPLATES = 'common/artifacts/templates/00_agot_historical_artifacts_crowns.txt'


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()
def read(path): return Path(path).read_text(encoding='utf-8-sig')
def load(path): return json.loads(read(path))
def save(name, data): (DOC/name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


def prepare():
    assert not (DOC/'stage15-plan.json').exists(), 'Prepare once from revision 14.'
    manifest = load(DOC/'source-manifest.json')
    assert manifest['Revision'] == 14 and len(manifest['Files']) == 139
    for row in manifest['Files']: assert sha(MOD/row['File']) == row['PatchedSHA256']
    fixes = load(DOC/'fixes.json'); additions = load(DOC/'additions.json')
    plan14 = load(DOC/'stage14-plan.json')
    assert len(fixes) == plan14['Rules'] and len(additions) == 12
    old = read(MOD/TITLE); current = old; upstream = read(PLUS/TITLE)
    actions = []
    for original, replacement in function_names(PLUS_CROWNS, 'apf').items():
        before = original+' = { OWNER = this }'
        after = replacement+' = { OWNER = this }'
        assert current.count(before) == upstream.count(before) == 1
        actions.append(dict(Id='crowns-stage15-'+original, Group='F55', File=TITLE,
                            Before=before, After=after, ExpectedCount=1))
        current = current.replace(before, after)
    helpers = make_helpers(read(AGOT/CROWN_SOURCE), PLUS_CROWNS, 'apf')
    assert not (MOD/HELPERS).exists() and not (PLUS/HELPERS).exists() and not (AGOT/HELPERS).exists()
    for name in ['source-manifest.json', 'fixes.json', 'additions.json']:
        (DOC/('stage15-before-'+name.removeprefix('source-'))).write_bytes((DOC/name).read_bytes())
    archive = 'stage15-before-title-on-actions.txt'
    (DOC/archive).write_bytes((MOD/TITLE).read_bytes())
    bom = (MOD/TITLE).read_bytes().startswith(b'\xef\xbb\xbf')
    expected = (b'\xef\xbb\xbf' if bom else b'')+current.encode('utf-8')
    added = dict(File=HELPERS, Text=helpers, UTF8BOM=True, Reason='Seven current AGOT crowns without an invented maker; OWNER and all other fields retained.', Group='F55')
    sources = {str(p):sha(p) for p in [AGOT/CROWN_SOURCE, AGOT/TEMPLATES, PLUS/TITLE,
               REPO/'AGOT_Submods/AGOT_SUBMODS_FIX/tools/CrownWithoutCreator.py',
               REPO/'AGOT_Submods/AGOT_SUBMODS_FIX/tools/ScriptBlocks.py']}
    evidence = {str(DOC/name):sha(DOC/name) for name in ['stage15-before-manifest.json', 'stage15-before-fixes.json', 'stage15-before-additions.json', archive]}
    save('stage15-plan.json', dict(Revision=15, RuntimeFiles=140, Shadows=127, Additions=13,
         FixGroups=55, Rules=len(fixes)+7, Occurrences=plan14['Occurrences']+7,
         ShadowDefinitions=plan14['ShadowDefinitions'], Sources=sources, Evidence=evidence,
         TitleFile=TITLE, TitleArchive=archive, TitleBeforeSHA256=sha(MOD/TITLE),
         TitleAfterSHA256=hashlib.sha256(expected).hexdigest().upper(), HelperFile=HELPERS,
         HelperSHA256=hashlib.sha256(b'\xef\xbb\xbf'+helpers.encode('utf-8')).hexdigest().upper(),
         Actions=actions, Addition=added, PreviousFiles=[dict(File=r['File'],SHA256=r['PatchedSHA256']) for r in manifest['Files']]))
    save('fixes.json', fixes+actions); save('additions.json', additions+[added])
    print('Registered stage15: seven exact call replacements and one independent helper file.')


def sources():
    plan = load(DOC/'stage15-plan.json')
    for p,h in (plan['Sources']|plan['Evidence']).items(): assert sha(p) == h, ('Changed source/evidence',p)
    assert load(DOC/'fixes.json') == load(DOC/'stage15-before-fixes.json')+plan['Actions']
    assert load(DOC/'additions.json') == load(DOC/'stage15-before-additions.json')+[plan['Addition']]
    assert plan['Addition']['Text'] == make_helpers(read(AGOT/CROWN_SOURCE), PLUS_CROWNS, 'apf')
    for name in PLUS_CROWNS:
        template = one(read(AGOT/TEMPLATES), name+'_template')
        assert 'creator' not in repr(semantic(template))
    print('PASS: stage15 pinned crown sources, templates and exact recipe extension.')
    return plan


def check():
    plan = sources(); manifest = load(DOC/'source-manifest.json')
    assert manifest['Revision'] == 15 and len(manifest['Files']) == 140
    assert sha(MOD/TITLE) == plan['TitleAfterSHA256']
    assert sha(MOD/HELPERS) == plan['HelperSHA256']
    for row in plan['PreviousFiles']:
        if row['File'] != TITLE: assert sha(MOD/row['File']) == row['SHA256'], row['File']
    old = read(DOC/plan['TitleArchive']); current = read(MOD/TITLE)
    reverse = current
    helpers = read(MOD/HELPERS); base = read(AGOT/CROWN_SOURCE)
    mapping = function_names(PLUS_CROWNS, 'apf')
    assert len(parse(helpers)) == 7
    for original,replacement in mapping.items():
        assert sum(n.key == replacement for n in walk(parse(current))) == 1
        call = next(n for n in walk(parse(current)) if n.key == replacement)
        assert [semantic(n) for n in call.value] == [('OWNER', '=', 'this')]
        reverse = reverse.replace(replacement, original)
        source_node = one(base, original); candidate = one(helpers, replacement)
        expected = [semantic(n) for n in source_node.value if n.key != '$CREATOR$']
        creation = next(n for n in expected if n[0] == 'create_artifact')
        creation[2][:] = [n for n in creation[2] if n[0] != 'creator']
        assert expected == [semantic(n) for n in candidate.value]
        assert set(re.findall(r'\$([A-Z_]+)\$', helpers[candidate.start:candidate.end])) == {'OWNER'}
    assert reverse == old, 'Inheritance conditions, OWNER or equip callbacks changed.'
    assert not any(n.key in mapping for n in walk(parse(current)))
    result = dict(Revision=15, Status='PASS', RuntimeFiles=140, UnchangedRuntimeFiles=138,
                  ChangedExistingFiles=1, NewHelperFiles=1, Calls=7, Helpers=7,
                  OwnerConditionsEquipDelaysAndAllArtifactPropertiesPreserved=True,
                  CommonAGOTFunctionsUnchanged=True, InGameValidation=False)
    save('stage15-validation.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','sources','check'])
    globals()[parser.parse_args().mode]()
