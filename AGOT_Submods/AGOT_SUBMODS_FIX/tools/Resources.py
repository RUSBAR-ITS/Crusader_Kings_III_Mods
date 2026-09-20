"""Approved resource repairs, preserving the two distinct Ethiopian diffuse maps.

Only generates candidate bytes in the builder. No source or profile writes.
"""
from collections import Counter, defaultdict
import csv
import gzip
import io
import json
from pathlib import Path
import re
from ScriptBlocks import one, parse, walk, edit, comment, semantic
from ResourceMesh import parse_spans, repair

REPORT = 'docs/reports/submods-resource-analysis-2026-09-20/'
REPLACE_PATHS = [
    'gfx/models/buildings/special/high_hermitage',
    'gfx/models/buildings/special/Karhold',
    'gfx/models/buildings/special/Runestone',
]


def build_resources(b):
    def evidence(name):
        return json.loads(b.read('repo', REPORT+name))

    pins = {str(Path(k).resolve()):v for k,v in evidence('source-evidence.json').items()}
    effective = json.loads(gzip.decompress(b.read_bytes('repo', REPORT+'effective-files.json.gz')))
    inventory = list(csv.DictReader(io.StringIO(b.read('repo', REPORT+'solution-inventory.csv'))))
    textfiles, reasons, uv_audit = {}, defaultdict(list), []

    def raw(owner, rel):
        data = b.read_bytes(owner, rel)
        path = str(Path(b.INPUTS[owner+'/'+rel]['path']).resolve())
        if path in pins:
            assert b.digest(data) == pins[path]['SHA256'], 'Research source changed: '+path
        return data

    def read_path(path):
        path = Path(path).resolve()
        if path.is_relative_to(b.GAME):
            return raw('game', path.relative_to(b.GAME).as_posix())
        if path.is_relative_to(b.REPO):
            return raw('repo', path.relative_to(b.REPO).as_posix())
        for owner, wsid in b.IDS.items():
            root = b.WS/wsid
            if path.is_relative_to(root):
                return raw(owner, path.relative_to(root).as_posix())
        raise AssertionError('Unknown source owner: '+str(path))

    def get(owner, rel):
        if rel not in textfiles:
            original = raw(owner, rel)
            textfiles[rel] = (owner, b.OUTPUTS.get(rel, original).decode('utf-8-sig').replace('\r\n', '\n'))
        assert textfiles[rel][0] == owner
        return textfiles[rel][1]

    def put(owner, rel, text, reason):
        textfiles[rel] = (owner, text)
        reasons[rel].append(reason)

    def binary(rel, data, reason, source=None):
        assert rel not in b.OUTPUTS
        b.OUTPUTS[rel] = data
        b.FIXES.append(dict(file=rel, source=source or 'cow/'+rel, reason=reason))

    def disable(text, nodes, reason):
        return edit(text, [(n.start, n.end, comment(text[n.start:n.end], reason)) for n in nodes])

    # Keep all pose conditions, heads and weapons; replace only unavailable torso states.
    p = 'gfx/portraits/portrait_animations/99_valyrian_invasion_weapons_animations.txt'
    t = get('vs', p)
    changes = []
    for n in walk(parse(t)):
        if n.key == 'torso' and n.value in ('"throneRoom_twoHandedPassiveFat1_entry"', '"throneRoom_twoHandedPassiveFatDwarf1_entry"'):
            changes.append((n.start, n.end, 'torso = "throneRoom_twoHandedPassive1_entry"'))
    assert len(changes) == 12  # Each shared animation is checked for four body types.
    for item in evidence('animation-state-evidence.json'):
        body = read_path(item['File']['Path']).decode('utf-8-sig')
        assert 'throneRoom_twoHandedPassive1_entry' in body
    put('vs', p, edit(t, changes), '12 torso states causing 48 messages use the existing AGOT two-handed pose; all selectors and weapons retained.')

    p = 'gfx/portraits/accessories/smc_clothing.txt'
    t = get('core', p)
    nodes = [one(t, 'female_clothes_smc_alicent_dress_0'+x) for x in ['3','4']]
    put('core', p, disable(t, nodes, 'unimplemented dress entity; author already disabled the matching model and gene choices'),
        'Comment two unimplemented Alicent accessories; retain dresses 01/02.')

    p = 'gfx/models/buildings/holdings/cow3_sprawl/cow3_sprawl_main_assets.asset'
    t = get('cow', p)
    missing = {re.search(r'"([^"]+)"', r['Message'])[1] for r in inventory if r['Remedy'] == 'ENTITY-WALLS'}
    nodes = [n for n in parse(t) if n.key == 'entity' and any(c.value in missing for c in walk(n.children('attach')) if isinstance(c.value, str))]
    assert len(nodes) == len(missing) == 24
    put('cow', p, disable(t, nodes, 'unused wrapper attaches unavailable walls; keep original definition for reference'),
        'Comment 24 unused wall wrappers; keep both farm models and their entities.')

    # Disable only meshsettings whose named geometry is absent, using the reviewed index.
    settings = evidence('meshsettings-evidence.json')
    meshes = {r['File']:r for r in evidence('mesh-evidence.json')}
    grouped = defaultdict(list)
    for row in settings:
        assert not row['PresentInGeometry'] and len(row['MatchingRegistrations']) == 1
        path = Path(row['MatchingRegistrations'][0]['Path'])
        rel = path.relative_to(b.WS/b.IDS['cow']).as_posix()
        grouped[rel].append(row)
    assert len(settings) == 40 and len(grouped) == 15
    for rel, rows in grouped.items():
        t = get('cow', rel)
        removed = []
        for row in rows:
            geometry = parse_spans(raw('cow', row['File']))
            assert row['Setting'] not in {geometry[n['Parent']]['Name'] for n in geometry if n['Name'] == 'mesh'}
            pdx = [n for n in parse(t) if n.key == 'pdxmesh' and n.one('name').value.strip('"') == row['Pdxmesh']]
            assert len(pdx) == 1
            hits = [n for n in pdx[0].children('meshsettings') if n.one('name').value.strip('"') == row['Setting']]
            assert len(hits) == 1
            removed.extend(hits)
        assert len({n.start for n in removed}) == len(removed)
        put('cow', rel, disable(t, removed, 'meshsettings name is absent from this model; unused original retained'),
            f'Comment {len(removed)} settings for absent geometry; all actual mesh settings retained.')

    # Seven Castamere material slots use neutral normal/properties, retain diffuse and AO.
    neutral = {'building_backup_atlas_normal.dds':'gfx/models/debug/no_normal.dds',
               'building_backup_atlas_properties.dds':'gfx/models/debug/no_properties.dds'}
    # Model texture fields use registered texture names, not root-relative VFS
    # paths. The 2026-09-20 run rejected the latter and appended the mesh folder.
    # Unique local copies also avoid the two different vanilla no_*.dds sets.
    neutral_local = {}
    for original, target in neutral.items():
        name = 'usf_castamere_neutral_'+('normal.dds' if original.endswith('_normal.dds') else 'properties.dds')
        rel = 'gfx/models/buildings/special/castamere/'+name
        binary(rel, raw('game', target), 'Byte-identical neutral game map under a unique local model texture name.', 'game/'+target)
        neutral_local[original] = name
    material_slots = 0
    castamere_assets = {Path(reg['Path']).relative_to(b.WS/b.IDS['cow']).as_posix()
                       for m in meshes.values() if '/castamere/' in m['File'] for reg in m['Registrations']}
    for rel in sorted(castamere_assets):
        t = get('cow', rel)
        changes = []
        for n in walk(parse(t)):
            if isinstance(n.value, str) and n.value.strip('"') in neutral:
                assert n.key in ('texture_normal', 'texture_specular')
                changes.append((n.start, n.end, n.key+' = "'+neutral_local[n.value.strip('"')]+'"'))
        material_slots += len(changes)
        if changes:
            put('cow', rel, edit(t, changes), 'Neutral maps replace unavailable Castamere normal/properties; preserve diffuse and AO.')
    assert material_slots == 14

    # UV recipes: raw spans only. Pin shader and AO evidence supporting the decisions.
    uv = evidence('uv-plan.json')
    ao = evidence('ao-mip-evidence.json')
    assert all(m['Extrema'][2] == [165,165] for m in ao['Mips'])
    read_path(ao['File']['Path'])
    raw('agot', 'gfx/FX/pdxmesh.shader')
    uv_groups = defaultdict(list)
    for row in uv:
        uv_groups[row['File']].append(row)
        part = meshes[row['File']]['Parts'][row['MeshIndex']]
        matching = part['MatchingSettings']
        shaders = {m['Shader'] for m in matching} if matching else {m['shader'] for m in part['Materials']}
        assert shaders and set(row['Shaders']) == shaders
        for reg in meshes[row['File']]['Registrations']:
            read_path(reg['Path'])
        if row['Action'] == 'copy_u1_to_u0_constant_ao':
            assert set(row['Shaders']) <= {'standard_atlas','snap_to_terrain_atlas'}
            assert matching and all('building_x_AO_placeholder.dds' in m['Body'] for m in matching)
        if row['Action'] == 'copy_u1_to_u0_visible_metal':
            assert row['Part'] in ('bronze_bell','bellchain') and row['Shaders'] == ['standard']
    assert len(uv) == 37
    for rel, recipes in sorted(uv_groups.items()):
        original = raw('cow', rel)
        candidate = repair(original, recipes)
        binary(rel, candidate, 'Approved UV channel edits only; geometry, topology, materials and all other PDX tokens preserved.')
        uv_audit.append(dict(file=rel, source_sha256=b.digest(original), output_sha256=b.digest(candidate),
                             parts=len(recipes), removed_channels=sum(len(r['Remove']) for r in recipes),
                             copied_uv0=sum(r['Action'].startswith('copy_') for r in recipes)))

    # Hide eight byte-identical copies with three exact folder replacements.
    duplicates = evidence('duplicate-evidence.json')
    omitted, retained, folders, canonical = set(), [], {}, {}
    for row in duplicates:
        rel = row['Duplicate']['Relative']
        first = read_path(row['Duplicate']['Path'])
        second = read_path(row['Canonical']['Path'])
        assert (first == second) == row['Identical']
        folder = Path(rel).parent.as_posix()
        expected = {f['Relative']:f for f in row['FolderInventory']}
        if folder in folders:
            assert folders[folder] == expected
        folders[folder] = expected
        if row['Identical']:
            omitted.add(rel)
            canonical[rel] = row['Canonical']['Relative']
        else:
            assert Path(rel).name == 'ethiopian_atlas_diffuse.dds'
            retained.append(dict(file=rel, sha256=b.digest(first)))
    assert len(omitted) == 8 and len(retained) == 2 and sorted(folders) == sorted(REPLACE_PATHS)
    for folder, entries in folders.items():
        current = {p.relative_to(b.WS/b.IDS['cow']).as_posix() for p in (b.WS/b.IDS['cow']/folder).rglob('*') if p.is_file()}
        assert current == set(entries), 'Folder contents changed: '+folder
        for rel, entry in entries.items():
            data = read_path(entry['Path'])
            if rel in omitted:
                continue
            if rel.endswith('.asset'):
                t = get('cow', rel)
                changes = []
                local_map = {k:v for k,v in canonical.items() if str(Path(k).parent).replace('\\','/') == folder}
                for n in walk(parse(t)):
                    if not isinstance(n.value, str):
                        continue
                    for original, target in local_map.items():
                        if n.value.strip('"') in (original, Path(original).name):
                            changes.append((n.start, n.end, n.key+' = "'+Path(target).name+'"'))
                put('cow', rel, edit(t, changes), 'Use canonical byte-identical textures; preserve distinct Ethiopian diffuse references.')
            elif rel not in b.OUTPUTS:
                binary(rel, data, 'Preserve full folder contents under narrow replace_path; bytes unchanged.')

    # Extend the already-patched COW files, preserving all prior COW/CREATOR fixes.
    p = 'common/buildings/yy_agotcities_special_buildings_westeros.txt'
    t = get('cow', p)
    for old, new, count in [('icon_building_ten_towers.dds','icon_structure_ten_towers.dds',1),
                            ('icon_riverrun.dds','icon_structure_riverrun.dds',3)]:
        matches = [item for rel,item in effective.items() if Path(rel).name == new]
        assert len(matches) == 1
        read_path(matches[0]['Path'])
        t = b.replace(t, '"'+old+'"', '"'+new+'"', count)
    put('cow', p, t, 'Four missing building icons use the corresponding existing structure icons.')
    p = 'common/on_action/cowagot_province_on_actions.txt'
    t = get('cow', p)
    missing = [n for n in walk(parse(t)) if n.key == 'title:b_graced_castle.title_province']
    assert len(missing) == 1 and [semantic(n) for n in missing[0].value] == [('add_building','=','castle_05')]
    t = disable(t, missing, 'unavailable b_graced_castle; no verified current title equivalent')
    t = b.replace(t, 'title:b_cheesemonger_manse.title_province', 'title:b_cheesemongers_manse.title_province')
    put('cow', p, t, 'Correct Cheesemonger title; comment only unavailable Graced Castle placement; retain prior repairs.')

    for key, chosen in [('bookmark_299_asha_greyjoy','marshal_swords'), ('bookmark_99_aurion_varezys','agot_artifact_weapon_dragonbane')]:
        p = 'common/bookmark_portraits/'+key+'.txt'
        t = get('bookmarked', p)
        props = one(t, key).one('genes').children('props_right')
        assert len(props) == 2 and chosen in t[props[1].start:props[1].end]
        put('bookmarked', p, disable(t, props[:1], 'retain the later authored weapon override; original export kept as comment'),
            'Keep later props_right only; all other DNA fields unchanged.')

    p = 'common/opinion_modifiers/valyrian_opinion_modifiers.txt'
    t = get('vs', p)
    nodes = [one(t, k).one('monthly_change') for k in ['funded_my_expedition','sent_relative_to_valyria']]
    put('vs', p, disable(t, nodes, 'retain the explicit duration and decaying mode; remove conflicting monthly rate'),
        'Keep original opinion values, 15/20-year durations and decaying; comment monthly rates.')
    p = 'common/modifiers/00_custom_artifact_modifiers.txt'
    t = get('vs', p)
    nodes = [one(t, k) for k in ['artifact_monthly_piety_negative_1_modifier','artifact_monthly_martial_lifestyle_xp_1_negative_modifier']]
    put('vs', p, disable(t, nodes, 'unused legacy modifier already disabled in current AGOT'),
        'Comment two unused legacy penalties; retain all other artifact modifiers.')

    for lang, values in [('english',['Black','Silver','Bronze','Show notifications again.']),
                         ('russian',['Чёрный','Серебристый','Бронзовый','Снова показывать уведомления.'])]:
        keys = ['feature_dragon_whip_black','feature_dragon_whip_silver','feature_dragon_whip_bronze','show_notifications_decision_tooltip']
        text = 'l_'+lang+':\n'+''.join(' '+k+':0 "'+v+'"\n' for k,v in zip(keys,values))
        b.output('localization/'+lang+'/usf_missing_resources_l_'+lang+'.yml', text,
                 reason='Four missing localization keys; no existing strings overridden.')

    for rel, (owner, text) in sorted(textfiles.items()):
        if not reasons[rel]:
            continue
        reason = ' '.join(reasons[rel])
        if rel in b.OUTPUTS:
            previous = next(f for f in b.FIXES if f['file'] == rel)
            reason = previous['reason']+' '+reason
            b.FIXES.remove(previous)
            del b.OUTPUTS[rel]
        b.output(rel, text, owner, reason=reason)

    # Descriptors are tracked separately from runtime files in the builder.
    template = b.read('repo', 'AGOT_Submods/AGOT_SUBMODS_FIX/docs/resources-before-descriptor.mod')
    assert 'replace_path' not in template
    internal = template+''.join('replace_path="'+p+'"\n' for p in REPLACE_PATHS)
    b.DESCRIPTORS = {
        b.MOD/'descriptor.mod':internal.encode('utf-8'),
        b.MOD.parent/'AGOT_SUBMODS_FIX.mod':(internal+'path="'+b.MOD.as_posix()+'"\n').encode('utf-8'),
    }
    b.RESOURCE_AUDIT = dict(uv_models=uv_audit, meshsettings_commented=40, wall_wrappers_commented=24,
                           alicent_accessories_commented=2, torso_states_replaced=12, animation_messages=48, neutral_material_maps=14,
                           omitted_textures=sorted(omitted), retained_diffuse=retained, replace_paths=REPLACE_PATHS,
                           texture_reference_mode='Registered DDS basenames; distinct local copies of game neutral maps for Castamere.',
                           neutral_map_copies=[dict(file='gfx/models/buildings/special/castamere/'+neutral_local[k], source=v,
                                                    sha256=b.digest(b.OUTPUTS['gfx/models/buildings/special/castamere/'+neutral_local[k]]))
                                               for k,v in neutral.items()],
                           original_runtime_preservation='Only two previously generated COW files extended.',
                           runtime_verified=False)
    for folder, entries in folders.items():
        actual = {p for p in b.OUTPUTS if p.startswith(folder+'/')}
        assert actual == set(entries)-omitted
    for row in retained:
        assert b.digest(b.OUTPUTS[row['file']]) == row['sha256']
