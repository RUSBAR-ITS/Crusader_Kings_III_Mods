"""Register and verify the approved UV-only binary edits; never write runtime.

The PowerShell builder applies byte-span recipes. Every surviving PDX token,
including UV0, geometry, materials and skeleton data, must remain bit-identical.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct

spec = importlib.util.spec_from_file_location('uv_paths', Path(__file__).with_name('DNA-Stage9.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
MOD, DOC, REPO = d.MOD, d.DOC, d.REPO
REPORT = REPO / 'docs/reports/agot-plus-paths-uv-analysis-2026-09-19'
spec = importlib.util.spec_from_file_location('uv_indexer', REPORT / 'analyze.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


def digest(data):
    return hashlib.sha256(data).hexdigest().upper()


def ordinary(path):
    return Path(str(d.repository_path(path)).removeprefix('\\\\?\\'))


def pin(path):
    path = ordinary(path)
    return dict(Path=path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else str(path),
                Repository=path.is_relative_to(REPO), SHA256=d.sha(path))


def pinned_path(row):
    return REPO / row['Path'] if row['Repository'] else Path(row['Path'])


def provider(rel, mods):
    result = None
    for mod in mods:
        if any(rel == p or rel.startswith(p.rstrip('/') + '/') for p in mod['Replace']):
            result = None
        path = Path(mod['Path']) / rel
        if path.is_file():
            result = path
    return result


def has_area(raw, node, prop):
    triangles = next(p for p in node['Properties'] if p['Name'] == 'tri')
    tri = struct.unpack_from('<' + 'i' * triangles['Count'], raw, triangles['DataStart'])
    assert len(tri) % 3 == 0
    uv = struct.unpack_from('<' + 'f' * prop['Count'], raw, prop['DataStart'])
    assert len(uv) % 2 == 0 and all(0 <= i < len(uv) // 2 for i in tri)
    for i in range(0, len(tri), 3):
        x, y, z = [uv[2 * index:2 * index + 2] for index in tri[i:i + 3]]
        if (y[0] - x[0]) * (z[1] - x[1]) != (y[1] - x[1]) * (z[0] - x[0]):
            return True
    return False


def verify_model(row, raw):
    assert digest(raw) == row['SourceSHA256'] and len(raw) == row['SourceBytes'], row['File']
    nodes = a.parse_spans(raw)
    meshes = [node for node in nodes if node['Name'] == 'mesh']
    spans = sorted(row['ProposedRemovalSpans'], key=lambda p: p['Start'])
    end = 0
    for span in spans:
        assert end <= span['Start'] < span['End'] <= len(raw)
        node = meshes[span['MeshIndex']]
        prop = next(p for p in node['Properties'] if p['Start'] == span['Start'])
        assert prop['End'] == span['End'] and prop['Name'] == span['Channel']
        assert prop['Name'] in ('u1', 'u2', 'u3') and prop['Kind'] == 'f'
        if span['Reason'] == 'unsupported_fourth_channel':
            assert prop['Name'] == 'u3'
        elif span['Reason'] == 'collapsed_unused_channel':
            assert not has_area(raw, node, prop)
        else:
            assert span['Reason'] == 'unused_tail_avoid_channel_gap' and prop['Name'] == 'u2'
            assert any(s['MeshIndex'] == span['MeshIndex'] and s['Channel'] == 'u1'
                       and s['Reason'] == 'collapsed_unused_channel' for s in spans)
        end = span['End']
    candidate = raw
    for span in reversed(spans):
        candidate = candidate[:span['Start']] + candidate[span['End']:]
    assert digest(candidate) == row['CandidateSHA256']
    assert len(raw) - len(candidate) == row['ProposedRemovedBytes']
    after = a.parse_spans(candidate)
    assert len(nodes) == len(after)
    removed = {s['Start'] for s in spans}
    for before_node, after_node in zip(nodes, after):
        assert all(before_node[k] == after_node[k] for k in ('Name', 'Depth', 'Parent'))
        assert raw[before_node['Start']:before_node['End']] == candidate[after_node['Start']:after_node['End']]
        kept = [p for p in before_node['Properties'] if p['Start'] not in removed]
        assert len(kept) == len(after_node['Properties'])
        for before_prop, after_prop in zip(kept, after_node['Properties']):
            assert raw[before_prop['Start']:before_prop['End']] == candidate[after_prop['Start']:after_prop['End']]
        if after_node['Name'] != 'mesh':
            continue
        channels = [p for p in after_node['Properties'] if re.fullmatch(r'u\d+', p['Name'])]
        assert len(channels) <= 3
        assert [p['Name'] for p in channels] == [f'u{i}' for i in range(len(channels))]
        if not channels:
            continue  # Preserve pre-existing empty/non-textured mesh nodes.
        vertices = next(p['Count'] // 3 for p in after_node['Properties'] if p['Name'] == 'p')
        for prop in channels:
            assert prop['Count'] == 2 * vertices and has_area(candidate, after_node, prop)
    return candidate


def prepare():
    assert not (DOC / 'stage13-plan.json').exists(), 'Prepare once from revision 12.'
    manifest = d.load(DOC / 'source-manifest.json')
    assert manifest['Revision'] == 12 and len(manifest['Files']) == 84
    previous = [dict(File=r['File'], SHA256=r['PatchedSHA256']) for r in manifest['Files']]
    for row in previous:
        assert d.sha(MOD / row['File']) == row['SHA256']
    proposal = d.load(REPORT / 'uv-proposal.json')
    assert len(proposal) == 48 and not ({r['File'] for r in previous} & {r['File'] for r in proposal})
    flat = d.load(REPORT / 'collapsed-uv.json')
    for row in flat:
        assert row['Channel'] in ('u1', 'u2') and row['Settings']
        for setting in row['Settings']:
            assert setting['Shader'] in {'court', 'court_alpha_to_coverage', 'portrait_attachment', 'portrait_attachment_alpha_to_coverage'}
            assert not re.search(r'\bdefines\s*=|\bUV[1-9]\b', setting['Body'], re.I)
    counts = Counter(s['Reason'] for r in proposal for s in r['ProposedRemovalSpans'])
    assert counts == dict(unsupported_fourth_channel=39, collapsed_unused_channel=41, unused_tail_avoid_channel_gap=8)
    # External evidence must match its original byte hashes. Only historical
    # repository text may use the explicitly recorded, already-approved LF migration.
    migration = {r['File']: r for r in d.load(REPO / 'docs/reports/repository-lf-migration-2026-09-19/original-file-hashes.json')}
    pins, migrated = [], []
    for name, expected in d.load(REPORT / 'source-pins.json').items():
        path = ordinary(name)
        if path == DOC / 'source-manifest.json':
            continue  # The current verified 84-file manifest is recorded above.
        actual = d.sha(path)
        if actual != expected:
            rel = path.relative_to(REPO).as_posix()
            assert migration[rel]['OriginalSHA256'] == expected and migration[rel]['LFOnlySHA256'] == actual, rel
            migrated.append(dict(File=rel, Before=expected, After=actual))
        pins.append(pin(path))
    mods = d.active_mods()
    providers = {}
    for file, registrations in d.load(REPORT / 'mesh-registrations.json').items():
        assert provider(file, mods) == d.PLUS / file
        for reg in registrations:
            path = ordinary(reg['Source'])
            assert provider(reg['Asset'], mods) == path
            providers[reg['Asset']] = pin(path)
    for rel in ('gfx/FX/jomini/portrait.shader', 'gfx/FX/court_scene.shader'):
        assert provider(rel, mods) == d.AGOT / rel
        providers[rel] = pin(d.AGOT / rel)
    for row in d.load(REPORT / 'blendshape-layout.json'):
        path = ordinary(row['Source'])
        assert provider(row['Target'], mods) == path
        providers[row['Target']] = pin(path)
    recipes = []
    baseline = d.load(DOC / 'source-baseline.json')
    assert len(baseline) == 139
    for number, row in enumerate(proposal, 1):
        raw = d.native(d.PLUS / row['File']).read_bytes()
        verify_model(row, raw)
        recipes.append(dict(Id=f'uv-stage13-{number:02d}', Group='F47', Catalog='AGOT_PLUS', File=row['File'],
                            SourceSHA256=row['SourceSHA256'], PatchedSHA256=row['CandidateSHA256'],
                            RemoveSpans=[dict(Offset=s['Start'], Length=s['End']-s['Start'],
                                              SHA256=digest(raw[s['Start']:s['End']]), MeshIndex=s['MeshIndex'],
                                              Channel=s['Channel'], Reason=s['Reason']) for s in row['ProposedRemovalSpans']]))
        assert not any(p['Catalog'] == 'AGOT_PLUS' and p['File'] == row['File'] for p in baseline)
        baseline.append(dict(Catalog='AGOT_PLUS', File=row['File'], SHA256=row['SourceSHA256']))
    evidence = [pin(REPORT / name) for name in ('uv-proposal.json', 'collapsed-uv.json', 'mesh-registrations.json',
                'shader-evidence.txt', 'blendshape-layout.json', 'source-pins.json', 'analyze.py')]
    evidence += [pin(REPO / 'docs/reports/repository-lf-migration-2026-09-19/original-file-hashes.json')]
    evidence += [pin(DOC / name) for name in ('fixes.json', 'additions.json', 'binary-fixes.json')]
    d.save('uv-fixes.json', recipes)
    evidence.append(pin(DOC / 'uv-fixes.json'))
    d.save('stage13-plan.json', dict(Revision=13, PreviousFiles=previous, PreviousManifestSHA256=d.sha(DOC / 'source-manifest.json'),
                                   PreviousBaseline=baseline[:139], Sources=pins, Evidence=evidence,
                                   Providers=providers, LFMigrationAccepted=migrated, UVFiles=48,
                                   UVPropertiesRemoved=88, UVBytesRemoved=3560448, RemovalReasons=dict(counts),
                                   RuntimeFiles=132, Shadows=120, Additions=12, BinaryShadows=49, FixGroups=47,
                                   ExistingRuntimeFilesUnchanged=84, OriginalLogMessages=75, DeformationFilesUnchanged=300))
    d.save('source-baseline.json', baseline)
    print('Prepared 48 UV model recipes / 88 property removals. Runtime not written.')


def sources():
    plan = d.load(DOC / 'stage13-plan.json')
    for row in plan['Sources'] + plan['Evidence']:
        assert d.sha(d.before_stage14_path(pinned_path(row))) == row['SHA256'], ('UV evidence changed', row['Path'])
    baseline = d.load(d.before_stage14_path(DOC / 'source-baseline.json'))
    assert baseline[:139] == plan['PreviousBaseline'] and len(baseline) == 187
    mods = d.active_mods()
    for rel, row in plan['Providers'].items():
        assert provider(rel, mods) == pinned_path(row), ('Model/shader/deformation provider changed', rel)
    proposal = d.load(REPORT / 'uv-proposal.json')
    recipes = d.load(DOC / 'uv-fixes.json')
    assert len(recipes) == len(proposal) == 48
    for row, recipe in zip(proposal, recipes):
        assert recipe['File'] == row['File'] and recipe['PatchedSHA256'] == row['CandidateSHA256']
        assert d.sha(d.PLUS / row['File']) == row['SourceSHA256'] == recipe['SourceSHA256']
        current = provider(row['File'], mods)
        assert current in (d.PLUS / row['File'], MOD / row['File']), ('Unexpected model override', row['File'])
    print(f'PASS: UV sources/evidence ({len(plan["Sources"])} + {len(plan["Evidence"])}), materials and 300 unchanged deformations.')
    return plan, proposal, mods


def check():
    plan, proposal, mods = sources()
    manifest = d.load(DOC / 'source-manifest.json')
    live_manifest = manifest
    assert manifest['Revision'] in (13, 14, 15)
    if manifest['Revision'] in (14, 15): manifest = d.load(DOC / 'stage14-before-manifest.json')
    assert manifest['Revision'] == 13 and len(manifest['Files']) == plan['RuntimeFiles']
    for row in plan['PreviousFiles']:
        assert d.sha(d.before_stage14_path(MOD / row['File'])) == row['SHA256'], ('Previous repair changed', row['File'])
    reader = REPO / 'docs/reports/agot-plus-dna-remaining-analysis-2026-09-19/historical/pdx_data.py'
    namespace = {'__name__': 'pdx_read_only'}
    exec(compile(reader.read_text(encoding='utf-8').replace('from .external import six', ''), str(reader), 'exec'), namespace)
    mesh_count = 0
    for row in proposal:
        raw = d.native(d.PLUS / row['File']).read_bytes()
        expected = verify_model(row, raw)
        target = MOD / row['File']
        assert target.read_bytes() == expected and provider(row['File'], mods) == target
        # Independent reader, on the actual installed file, confirms UV counts
        # and values. It does not re-export/re-encode any model data.
        vendor = namespace['read_meshfile'](str(target))
        indexed = [n for n in a.parse_spans(expected) if n['Name'] == 'mesh']
        meshes = list(vendor.iter('mesh'))
        assert len(meshes) == len(indexed)
        for node, mesh in zip(indexed, meshes):
            props = [p for p in node['Properties'] if re.fullmatch(r'u\d+', p['Name'])]
            assert len(props) == len([key for key in mesh.attrib if re.fullmatch(r'u\d+', key)])
            for prop in props:
                assert tuple(mesh.attrib[prop['Name']]) == struct.unpack_from('<' + 'f' * prop['Count'], expected, prop['DataStart'])
        mesh_count += len(meshes)
    result = dict(Revision=13, Status='PASS', RuntimeFiles=132, ValidatedRuntimeRevision=live_manifest['Revision'],
                  ArchivedStage14Delta=live_manifest['Revision'] in (14,15), PreviousRuntimeFilesUnchanged=84,
                  NewBinaryShadows=48, UVPropertiesRemoved=88, UVBytesRemoved=3560448, MeshPartsChecked=mesh_count,
                  AllSurvivingTokensBitIdentical=True, UV0GeometryMaterialsSkeletonUnchanged=True,
                  AllRemainingUVChannelsContiguous=True, AllRemainingUVChannelsHaveNonzeroTriangle=True,
                  IndependentReaderPassed=True, DeformationFilesUnchanged=300, FinalActiveProviderForAllUVFiles=True,
                  LongestNewModelPath=max(len(str(MOD / r['File'])) for r in proposal),
                  ExpectedResolvedLogMessages=75, ExpectedRemainingAGOTPlusMessages=40,
                  GameExecutionChecked=False, FreshLogChecked=False, VisualEquivalenceClaimed=False,
                  ManifestSHA256=d.sha(DOC / 'source-manifest.json'))
    d.save('stage13-validation.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('prepare', 'sources', 'check'))
    args = parser.parse_args()
    globals()[args.mode]()
