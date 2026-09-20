"""Register and verify the approved portrait/model repairs; no game execution.

prepare archives revision 10 and writes recipes. Build-AGOTPlusFix.ps1 remains
the only runtime writer. sources checks immutable inputs before every build.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import re

spec = importlib.util.spec_from_file_location('dna9', Path(__file__).with_name('DNA-Stage9.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
MOD, DOC = d.MOD, d.DOC
REPORT = d.REPO / 'docs/reports/agot-plus-portrait-graphics-analysis-2026-09-19'
GROUPS = dict(portrait_templates='F34', portrait_rules='F35', accessory_entity='F36',
              mesh_blendshape='F37', mesh_duplicates='F38')


def code(text):
    return re.sub(r'"(?:\\.|[^"\\])*"|#[^\r\n]*',
                  lambda m: '' if m[0].startswith('#') else '""', text)


def approved(raw):
    return raw.replace(b'AGOT_PLUS_FIX candidate:', b'AGOT_PLUS_FIX:')


def prepare():
    assert not (DOC / 'stage11-plan.json').exists(), 'Prepare once from revision 10.'
    manifest = d.load(DOC / 'source-manifest.json')
    assert manifest['Revision'] == 10 and len(manifest['Files']) == 69
    for row in manifest['Files']:
        assert d.sha(MOD / row['File']) == row['PatchedSHA256'], row['File']
    pins = d.load(REPORT / 'source-pins.json')
    for path, digest in pins.items():
        assert d.sha(path) == digest, ('Approved analysis input changed', path)
    selected = d.load(REPORT / 'candidate-files.json')
    for row in selected:
        assert d.sha(REPORT / row['Candidate']) == row['CandidateSHA256']
        assert d.sha(row['Source']) == row['SourceSHA256']
    fixes = d.load(DOC / 'fixes.json')
    assert len(fixes) == 702
    baseline = d.load(DOC / 'source-baseline.json')
    definitions = dict(d.load(DOC / 'stage10-plan.json')['ShadowDefinitions'])
    archives, fileplans = {}, []
    for name in ('source-manifest.json', 'fixes.json', 'source-baseline.json'):
        (DOC / ('stage11-before-' + name.removeprefix('source-'))).write_bytes((DOC / name).read_bytes())
    for i, row in enumerate(selected, 1):
        rel = row['File']
        before = MOD / rel
        existing = before.is_file()
        if existing:
            archived = DOC / f'stage11-before/{i:02d}-{Path(rel).name}'
            archived.parent.mkdir(parents=True, exist_ok=True)
            archived.write_bytes(before.read_bytes())
            archives[rel] = archived.relative_to(DOC).as_posix()
        preview = DOC / f'stage11-approved/{i:02d}-{Path(rel).name}'
        preview.parent.mkdir(parents=True, exist_ok=True)
        raw = (REPORT / row['Candidate']).read_bytes()
        preview.write_bytes(raw if rel.endswith('.mesh') else approved(raw))
        fileplans.append(dict(File=rel, ExistingShadow=existing, Preview=preview.relative_to(DOC).as_posix(),
                              OutputSHA256=d.sha(preview)))
        if not rel.endswith('.mesh'):
            text = d.read(preview)
            d.parse(text)
            definitions[rel] = re.findall(r'(?m)^([A-Za-z_0-9.]+)\s*=\s*\{', code(text))
        if not any(b['Catalog'] == 'AGOT_PLUS' and b['File'] == rel for b in baseline):
            baseline.append(dict(Catalog='AGOT_PLUS', File=rel, SHA256=d.sha(d.PLUS / rel)))
    actions = d.load(REPORT / 'actions.json')
    for i, action in enumerate(actions, 1):
        original = d.read(d.PLUS / action['File'])
        assert original.count(action['Before']) == action['Count'], action['Reason']
        fixes.append(dict(Id=f'portrait-stage11-{i:02d}', Group=GROUPS[action['Category']],
                          File=action['File'], Before=action['Before'],
                          After=action['After'].replace('AGOT_PLUS_FIX candidate:', 'AGOT_PLUS_FIX:'),
                          ExpectedCount=action['Count'], Reason=action['Reason'], Confidence=action['Confidence']))
    proof = d.load(REPORT / 'mesh-proof.json')
    binary = [dict(Id='lannister-armour-empty-mesh', Group='F37', Catalog='AGOT_PLUS',
                   File=proof['File'], SourceSHA256=proof['SourceSHA256'],
                   PatchedSHA256=proof['CandidateSHA256'], Offset=proof['Offset'],
                   RemoveHex=proof['RemovedHex'], FollowingHex=b'[[[skeleton\0'.hex(),
                   Reason='Remove only the empty third mesh; preserve both real meshes and all nine morphs.')]
    # Reconstruct every text candidate from upstream through ALL previous rules.
    for row in fileplans:
        if row['File'].endswith('.mesh'):
            continue
        text = d.read(d.PLUS / row['File'])
        for fix in fixes:
            if fix['File'] == row['File']:
                assert text.count(fix['Before']) == fix['ExpectedCount'], fix['Id']
                text = text.replace(fix['Before'], fix['After'])
        assert text == d.read(DOC / row['Preview']), row['File']
    # Replace pins on the two live input files and old manifest by immutable archives.
    pinned = {}
    for path, digest in pins.items():
        p = Path(path)
        if p.resolve() == (DOC / 'source-manifest.json').resolve():
            p = DOC / 'stage11-before-manifest.json'
        elif p.is_relative_to(MOD) and p.relative_to(MOD).as_posix() in archives:
            p = DOC / archives[p.relative_to(MOD).as_posix()]
        pinned[str(p)] = digest
    evidence = [dict(File=row['Preview'], SHA256=d.sha(DOC / row['Preview'])) for row in fileplans]
    for name in ('actions.json', 'mesh-proof.json', 'duplicate-pairs.json', 'effective-resources.json', 'candidate-text.patch'):
        target = DOC / ('stage11-' + name)
        target.write_bytes((REPORT / name).read_bytes())
        evidence.append(dict(File=target.relative_to(DOC).as_posix(), SHA256=d.sha(target)))
    for name in ('stage11-before-fixes.json', 'stage11-before-baseline.json', 'stage11-before-manifest.json'):
        evidence.append(dict(File=name, SHA256=d.sha(DOC / name)))
    plan = dict(Revision=11, Rules=len(fixes), Occurrences=sum(f['ExpectedCount'] for f in fixes),
                Shadows=70, TextShadows=69, BinaryShadows=1, Additions=12, FixGroups=38,
                Groups=list(GROUPS.values()), PreviousFiles=manifest['Files'], Archives=archives,
                Files=fileplans, ShadowDefinitions=definitions, Sources=pinned, Evidence=evidence,
                LogMessages=231, ExpectedResolved=227, PendingTextureWarnings=4)
    d.save('fixes.json', fixes)
    d.save('source-baseline.json', baseline)
    d.save('binary-fixes.json', binary)
    # Binary recipes themselves are also guarded by the approved plan.
    plan['Evidence'].append(dict(File='binary-fixes.json', SHA256=d.sha(DOC / 'binary-fixes.json')))
    d.save('stage11-plan.json', plan)
    print(f'Registered 43 text recipes / 206 occurrences and one 8-byte binary repair; {len(baseline)} upstream pins.')


def sources():
    plan = d.load(DOC / 'stage11-plan.json')
    mods = d.active_mods()
    later_archives = d.load(DOC / 'stage12-plan.json')['Archives'] if (DOC / 'stage12-plan.json').exists() else {}
    for path, digest in plan['Sources'].items():
        source = d.repository_path(path)
        if source.is_relative_to(MOD):
            rel = source.relative_to(MOD).as_posix()
            if rel in later_archives:
                source = DOC / later_archives[rel]
        assert d.sha(d.before_stage14_path(source)) == digest, ('Stage11 source changed', path)
    for row in plan['Evidence']:
        assert d.sha(DOC / row['File']) == row['SHA256'], ('Stage11 evidence changed', row['File'])
    print(f'PASS: {len(plan["Sources"])} stage-eleven sources and {len(plan["Evidence"])} evidence hashes.')
    return plan, mods


def check():
    plan, mods = sources()
    live_manifest = d.load(DOC / 'source-manifest.json')
    assert live_manifest['Revision'] in (11, 12, 13, 14, 15)
    manifest, archived = live_manifest, {}
    if live_manifest['Revision'] >= 12:
        # Stage 12 proves the delta from these pinned snapshots to live scripts.
        # Unchanged portraits, all DNA, models and texture repairs stay live.
        manifest = d.load(DOC / 'stage12-before-manifest.json')
        archived = {rel: DOC / path for rel, path in d.load(DOC / 'stage12-plan.json')['Archives'].items()}
    def prior_path(rel):
        return archived.get(rel, d.before_stage14_path(MOD / rel))
    assert manifest['Revision'] == 11 and len(manifest['Files']) == 82
    assert (manifest['ReplacementRules'], manifest['ReplacementOccurrences'], manifest['FixGroups']) == (745, 1595, 38)
    fixes = d.load(DOC / 'fixes.json')
    if live_manifest['Revision'] >= 12:
        previous_fixes = d.load(DOC / 'stage12-before-fixes.json')
        assert fixes[:len(previous_fixes)] == previous_fixes
        fixes = previous_fixes
    assert fixes[:702] == d.load(DOC / 'stage11-before-fixes.json')
    assert len(fixes[702:]) == 43 and sum(f['ExpectedCount'] for f in fixes[702:]) == 206
    for row in manifest['Files']:
        assert d.sha(prior_path(row['File'])) == row['PatchedSHA256'], row['File']
        provider = None
        for mod in mods:
            if any(row['File'] == rp or row['File'].startswith(rp.rstrip('/') + '/') for rp in mod['Replace']):
                provider = None
            if d.native(Path(mod['Path']) / row['File']).is_file():
                provider = Path(mod['Path']) / row['File']
        assert provider and provider.resolve() == (MOD / row['File']).resolve(), ('Shadowed patch', row['File'])
    for row in plan['Files']:
        assert d.native(prior_path(row['File'])).read_bytes() == (DOC / row['Preview']).read_bytes(), ('Approved output differs', row['File'])
    unchanged = [r for r in plan['PreviousFiles'] if r['File'] not in plan['Archives']]
    assert len(unchanged) == 67
    for row in unchanged:
        assert d.sha(prior_path(row['File'])) == row['PatchedSHA256'], row['File']
    binary = d.load(DOC / 'binary-fixes.json')[0]
    original = (d.PLUS / binary['File']).read_bytes()
    offset, token = binary['Offset'], bytes.fromhex(binary['RemoveHex'])
    assert token == b'[[[mesh\0' and original[offset:offset+8] == token
    actual = d.native(MOD / binary['File']).read_bytes()
    assert actual == original[:offset] + original[offset+8:] and len(original) - len(actual) == 8
    # Every selected modifier must resolve a current template and, where explicit,
    # an accessory in the correct sex-specific list. Current genes were hash-pinned.
    db = d.load(DOC / 'stage11-effective-resources.json')
    def scalar(text, key):
        match = re.search(r'\b'+key+r'\s*=\s*([^\s{}#]+)', text)
        return match[1] if match else None
    checked = 0
    for action in d.load(DOC / 'stage11-actions.json'):
        if action['Category'] != 'portrait_templates':
            continue
        text = action['After']
        gene, template = scalar(text, 'gene'), scalar(text, 'template')
        assert gene in db['Genes'] and template in db['Genes'][gene]['Templates'], (gene, template)
        accessory = scalar(text, 'accessory')
        if accessory:
            body = db['Genes'][gene]['Templates'][template]
            block = d.parse(body).children[0].child(scalar(text, 'type') or 'male')
            assert block and re.search(r'\b'+accessory+r'\b', re.sub(r'#[^\r\n]*', '', block.body(body)))
            assert accessory in db['Accessories']
        checked += action['Count']
    assert checked == 187
    result = dict(Revision=11, Status='PASS', RuntimeFiles=82, ChangedExistingFiles=2, NewShadows=13,
                  ValidatedRuntimeRevision=live_manifest['Revision'], ArchivedLaterFiles=len(archived),
                  PreviousFilesUnchanged=67, Previous702RecipesUnchanged=True, TextRecipes=43,
                  TextOccurrences=206, ModifierOccurrencesValidated=checked, BinaryRemovedBytes=8,
                  ApprovedOutputsMatch=True, FinalActiveProviderForAllFiles=True,
                  SourcePins=len(plan['Sources']), EvidenceHashes=len(plan['Evidence']),
                  ExpectedResolvedMessages=227, PendingTextureWarnings=4,
                  GameExecutionChecked=False, FreshLogChecked=False, VisualEquivalenceClaimed=False,
                  ManifestSHA256=d.sha(DOC / 'source-manifest.json'))
    d.save('stage11-validation.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=('prepare', 'sources', 'check'))
    args = p.parse_args()
    {'prepare': prepare, 'sources': sources, 'check': check}[args.mode]()
