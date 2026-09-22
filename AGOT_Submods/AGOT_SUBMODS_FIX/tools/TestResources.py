"""Resource preservation contracts and effective file checks; no CK3 emulation."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
import Build as b
from ScriptBlocks import parse, one, walk, semantic
from ResourceMesh import parse_spans, has_area
from Resources import REPORT, REPLACE_PATHS


def validate(candidate=False):
    b.build()
    checks = []
    def ok(name, condition):
        assert condition, name
        checks.append(name)
    def source(owner, rel):
        return (b.WS/b.IDS[owner]/rel).read_text(encoding='utf-8-sig').replace('\r\n','\n')
    def new(rel):
        return b.OUTPUTS[rel].decode('utf-8-sig')
    def code(t):
        return [semantic(n) for n in parse(t)]
    def report(name):
        return json.loads((b.REPO/REPORT/name).read_text(encoding='utf-8'))

    before = json.loads((b.MOD/'docs/resources-before-source-manifest.json').read_text(encoding='utf-8'))
    excluded = json.loads((b.MOD/'docs/disabled-crowns-2026-09-22/manifest.json').read_text(encoding='utf-8'))['files']
    ok('Only archived Crowns files removed since resource baseline',
       set(before)-set(b.OUTPUTS) == set(excluded))
    before = {p:v for p,v in before.items() if p not in excluded}
    changed = {p for p,v in before.items() if b.digest(b.OUTPUTS[p]) != v['sha256']}
    ok('Exactly two earlier COW files extended', changed == {
        'common/on_action/cowagot_province_on_actions.txt',
        'common/buildings/yy_agotcities_special_buildings_westeros.txt'})
    for rel in set(before)-changed:
        ok('Prior runtime bytes retained: '+rel, b.digest(b.OUTPUTS[rel]) == before[rel]['sha256'])
    for rel in changed:
        original = (b.MOD/'docs/resources-before'/rel).read_text(encoding='utf-8-sig')
        nodes = parse(original)
        if '/buildings/' in rel:
            translations = {'"icon_building_ten_towers.dds"':'"icon_structure_ten_towers.dds"',
                            '"icon_riverrun.dds"':'"icon_structure_riverrun.dds"'}
            for n in walk(nodes):
                if n.key == 'type_icon' and n.value in translations:n.value = translations[n.value]
        else:
            for n in list(walk(nodes)):
                if isinstance(n.value, list):
                    n.value[:] = [c for c in n.value if c.key != 'title:b_graced_castle.title_province']
                if n.key == 'title:b_cheesemonger_manse.title_province':n.key = 'title:b_cheesemongers_manse.title_province'
        ok('Earlier COW logic unchanged except approved resources: '+rel,
           [semantic(n) for n in nodes] == code(new(rel)))

    rel = 'gfx/portraits/portrait_animations/99_valyrian_invasion_weapons_animations.txt'
    nodes = parse(source('vs',rel)); count = 0
    for n in walk(nodes):
        if n.key == 'torso' and n.value in ('"throneRoom_twoHandedPassiveFat1_entry"','"throneRoom_twoHandedPassiveFatDwarf1_entry"'):
            n.value = '"throneRoom_twoHandedPassive1_entry"';count += 1
    ok('Twelve torso replacements only; all selectors, heads and weapons preserved',
       count == 12 and [semantic(n) for n in nodes] == code(new(rel)))

    for key in ['bookmark_299_asha_greyjoy','bookmark_99_aurion_varezys']:
        rel = 'common/bookmark_portraits/'+key+'.txt'
        nodes = parse(source('bookmarked',rel))
        genes = nodes[0].one('genes'); props = genes.children('props_right')
        genes.value.remove(props[0])
        ok('Only earlier prop removed; face, clothing and anonymous tag blocks preserved: '+key,
           [semantic(n) for n in nodes] == code(new(rel)))
        ok('Exactly one weapon field: '+key,len(one(new(rel),key).one('genes').children('props_right')) == 1)

    rel = 'gfx/portraits/accessories/smc_clothing.txt'
    expected = [semantic(n) for n in parse(source('core',rel)) if n.key not in ('female_clothes_smc_alicent_dress_03','female_clothes_smc_alicent_dress_04')]
    ok('Only two unavailable dress registrations disabled',expected == code(new(rel)))
    rel = 'common/opinion_modifiers/valyrian_opinion_modifiers.txt'
    nodes = parse(source('vs',rel))
    for n in nodes:
        if n.key in ('funded_my_expedition','sent_relative_to_valyria'):
            n.value[:] = [c for c in n.value if c.key != 'monthly_change']
    ok('Opinion amounts, durations and decaying unchanged',[semantic(n) for n in nodes] == code(new(rel)))
    rel = 'common/modifiers/00_custom_artifact_modifiers.txt'
    disabled = {'artifact_monthly_piety_negative_1_modifier','artifact_monthly_martial_lifestyle_xp_1_negative_modifier'}
    ok('Only two obsolete penalties disabled',
       [semantic(n) for n in parse(source('vs',rel)) if n.key not in disabled] == code(new(rel)))

    # Independently compare every PDX property, including all unedited geometry.
    uv = report('uv-plan.json')
    for row in b.RESOURCE_AUDIT['uv_models']:
        rel = row['file']; raw = (b.WS/b.IDS['cow']/rel).read_bytes(); after = b.OUTPUTS[rel]
        recipes = {r['MeshIndex']:r for r in uv if r['File'] == rel}
        oldnodes, newnodes = parse_spans(raw), parse_spans(after)
        ok('PDX node count: '+rel,len(oldnodes) == len(newnodes))
        meshindex = -1
        for old,n in zip(oldnodes,newnodes):
            if old['Name'] == 'mesh':meshindex += 1
            recipe = recipes.get(meshindex) if old['Name'] == 'mesh' else None
            assert all(old[k] == n[k] for k in ('Name','Depth','Parent'))
            expected = []
            for p in old['Properties']:
                if recipe and p['Name'] in recipe['Remove']:continue
                data = raw[p['Start']:p['End']]
                if recipe and p['Name'] == 'u0' and recipe['Action'].startswith('copy_'):
                    u1 = next(c for c in old['Properties'] if c['Name'] == 'u1')
                    data = raw[p['Start']:p['DataStart']]+raw[u1['DataStart']:u1['End']]
                expected.append(data)
            assert expected == [after[p['Start']:p['End']] for p in n['Properties']]
            if recipe:
                channels = [p for p in n['Properties'] if re.fullmatch(r'u\d+',p['Name'])]
                assert [p['Name'] for p in channels] == [f'u{i}' for i in range(len(channels))]
                assert len(channels) <= 3 and all(has_area(after,n,p) for p in channels)
        ok('All non-target UV and geometry/material bytes preserved: '+rel,True)

    # Whole asset comparison: settings removal, neutral material maps and exact texture links only.
    duplicates = report('duplicate-evidence.json')
    settings = report('meshsettings-evidence.json')
    for rel in [r for r in b.OUTPUTS if r.endswith('.asset')]:
        nodes = parse(source('cow',rel))
        expected_removals = {(r['Pdxmesh'],r['Setting']) for r in settings
                             if Path(r['MatchingRegistrations'][0]['Path']).relative_to(b.WS/b.IDS['cow']).as_posix() == rel}
        for node in nodes:
            if node.key == 'pdxmesh':
                name = node.one('name').value.strip('"')
                node.value[:] = [n for n in node.value if not (n.key == 'meshsettings' and (name,n.one('name').value.strip('"')) in expected_removals)]
        if rel.endswith('cow3_sprawl_main_assets.asset'):
            nodes = [n for n in nodes if not (n.key == 'entity' and n.children('attach'))]
            ok('Farm entities and pdxmeshes retained',Counter(n.key for n in nodes) == {'pdxmesh':2,'entity':2})
        for n in walk(nodes):
            if not isinstance(n.value,str):continue
            if '/castamere/' in rel and n.value in ('"building_backup_atlas_normal.dds"','"building_backup_atlas_properties.dds"'):
                n.value = '"usf_castamere_neutral_'+('normal.dds' if n.key == 'texture_normal' else 'properties.dds')+'"'
            for duplicate in duplicates:
                original = duplicate['Duplicate']['Relative']
                if duplicate['Identical'] and Path(rel).parent == Path(original).parent:
                    if n.value.strip('"') in (original,Path(original).name):n.value = '"'+Path(duplicate['Canonical']['Relative']).name+'"'
        ok('Only approved asset changes: '+rel,[semantic(n) for n in nodes] == code(new(rel)))

    for r in b.RESOURCE_AUDIT['retained_diffuse']:
        ok('Distinct Ethiopian map preserved byte-for-byte: '+r['file'],b.digest(b.OUTPUTS[r['file']]) == r['sha256'])
    for folder in REPLACE_PATHS:
        entries = next(r['FolderInventory'] for r in duplicates if Path(r['Duplicate']['Relative']).parent.as_posix() == folder)
        expected = {x['Relative'] for x in entries}-set(b.RESOURCE_AUDIT['omitted_textures'])
        ok('Complete narrow replacement folder: '+folder,{p for p in b.OUTPUTS if p.startswith(folder+'/')} == expected)
    for rel,data in b.OUTPUTS.items():
        if rel.endswith(('.mesh','.dds')) and rel not in {x['file'] for x in b.RESOURCE_AUDIT['uv_models']}:
            neutral = {r['file']:r['source'] for r in b.RESOURCE_AUDIT['neutral_map_copies']}
            original = b.GAME/neutral[rel] if rel in neutral else b.WS/b.IDS['cow']/rel
            ok('Copied binary unchanged: '+rel,data == original.read_bytes())
        if not candidate:
            ok('Installed candidate bytes: '+rel,(b.MOD/rel).read_bytes() == data)

    # Resolve patched files through the actual playset, including descriptor replace_path.
    profile = Path('C:/Users/RUSBAR/Documents/Paradox Interactive/Crusader Kings III')
    enabled = json.loads((profile/'dlc_load.json').read_text(encoding='utf-8-sig'))['enabled_mods']
    # Inspect the current playset read-only; it can differ from the historical
    # resource audit and can contain later mods that do not override these files.
    mods = [dict(Path=str(b.GAME),Replace=[])]
    for descriptor in enabled:
        text = (profile/descriptor).read_text(encoding='utf-8-sig')
        path = re.search(r'(?m)^\s*path\s*=\s*"([^"]+)"',text)[1]
        ok('Current mod root exists: '+descriptor,Path(path).is_dir())
        mods.append(dict(Path=path,Replace=re.findall(r'(?m)^\s*replace_path\s*=\s*"([^"]+)"',text)))
    ok('Unified patch enabled',any(Path(mod['Path']).resolve() == b.MOD.resolve() for mod in mods))
    def provider(rel):
        found = None
        for mod in mods:
            replace = REPLACE_PATHS if Path(mod['Path']).resolve() == b.MOD.resolve() and candidate else mod['Replace']
            if any(rel == p or rel.startswith(p.rstrip('/')+'/') for p in replace):found = None
            path = Path(mod['Path'])/rel
            if Path(mod['Path']).resolve() == b.MOD.resolve() and candidate:
                if rel in b.OUTPUTS:found = b.MOD/rel
            elif path.is_file():found = path
        return found
    for rel in b.OUTPUTS:
        ok('Effective file resolves to unified patch: '+rel,provider(rel) == b.MOD/rel)
    for r in duplicates:
        rel = r['Duplicate']['Relative']
        if r['Identical']:
            ok('Exact duplicate path suppressed: '+rel,provider(rel) is None)
            ok('Canonical texture stays available: '+rel,provider(r['Canonical']['Relative']) is not None)
    # Regression contract: existence of the target VFS file alone does not make
    # a root-relative string a valid registered model texture name. Check the
    # authored field and its effective name registration separately, including
    # extra files from the actual playset rather than only the research index.
    texture_targets = {Path(r['Canonical']['Relative']).name:r['Canonical']['Relative']
                       for r in duplicates if r['Identical']}
    texture_targets.update({Path(r['file']).name:r['file'] for r in b.RESOURCE_AUDIT['neutral_map_copies']})
    registrations = {name:set() for name in texture_targets}
    for mod in mods:
        for p in (Path(mod['Path'])/'gfx/models').rglob('*.dds'):
            if p.name in registrations:
                rel = p.relative_to(mod['Path']).as_posix()
                if provider(rel) is not None:registrations[p.name].add(rel)
    if candidate:
        for rel in b.OUTPUTS:
            if Path(rel).name in registrations:registrations[Path(rel).name].add(rel)
    for name,target in texture_targets.items():
        ok('Unique effective model texture registration: '+name,registrations[name] == {target})
    references = 0
    for rel in [p for p in b.OUTPUTS if p.endswith('.asset')]:
        for n in walk(parse(new(rel))):
            if isinstance(n.value,str) and Path(n.value.strip('"')).name in texture_targets:
                name = n.value.strip('"')
                ok('Texture field uses registered basename: '+rel+':'+n.key,name in texture_targets)
                ok('Referenced model texture has an effective provider: '+name,provider(texture_targets[name]) is not None)
                references += 1
    ok('Exactly twenty repaired material references checked',references == 20)
    for rel in ['common/genes/07_genes_special_accessories_misc.txt','common/character_interactions/DI_character_interaction.txt',
                'common/scripted_guis/DI_char_editor_present_sgui.txt']:
        ok('Optional integrations / vanilla DI remain external: '+rel,provider(rel) is not None and not provider(rel).is_relative_to(b.MOD))
    # Revalidate source hashes after all checks, so externally updated files cannot slip through.
    for item in b.INPUTS.values():
        assert b.digest(Path(item['path']).read_bytes()) == item['sha256'],item['path']
    result = dict(status='PASS', checks=len(checks), runtime_files=len(b.OUTPUTS), candidate_only=candidate,
                  checks_passed=checks, runtime_verified=False,
                  limitation='Static binary/AST/VFS validation. Rendering and new log still require a game launch.')
    return result


if __name__ == '__main__':
    ap = argparse.ArgumentParser();ap.add_argument('--candidate',action='store_true');args = ap.parse_args()
    result = validate(args.candidate)
    (b.MOD/'docs/resource-validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS:',result['checks'],'resource contracts; candidate only:',args.candidate)
