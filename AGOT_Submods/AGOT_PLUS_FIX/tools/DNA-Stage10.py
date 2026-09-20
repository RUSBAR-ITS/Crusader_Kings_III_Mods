"""Install the approved current-AGOT-only selection as guarded F33 recipes.

prepare archives revision 9 inputs and writes recipes, never runtime DNA.
check compares the installed result with the approved preview, replays the
allele changes, and checks all 8,368 historical DNA diagnostics. No CK3 run.
"""
import argparse
from collections import Counter, defaultdict
import difflib
import importlib.util
import json
from pathlib import Path
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
spec = importlib.util.spec_from_file_location('dna_stage9', Path(__file__).with_name('DNA-Stage9.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
MOD, DOC = d.MOD, d.DOC
SELECTION = d.REPO / 'docs/reports/agot-plus-dna-selection-2026-09-19'
LEGACY = {'gene_eye_size', 'gene_eye_shut_top', 'gene_eye_shut_bottom',
          'gene_forehead_inner_brow_width', 'gene_bs_eye_fold_2'}


def approved_bytes(path):
    return d.native(path).read_bytes().replace(b'# AGOT_PLUS_FIX candidate:', b'# AGOT_PLUS_FIX F33:')


def pin(path):
    return dict(Path=str(Path(path).resolve()), SHA256=d.sha(path))


def code(text):
    return ' '.join(m[0] for m in d.TOK.finditer(text) if not m[0].startswith('#'))


def prepare():
    selected = d.load(SELECTION / 'plan.json')
    manifest = d.load(DOC / 'source-manifest.json')
    assert manifest['Revision'] == selected['BaseRevision'] == 9
    assert len(manifest['Files']) == 64
    assert selected['RuntimeSHA256'] == {r['File']: d.sha(MOD / r['File']) for r in manifest['Files']}
    for path, digest in selected['SourcePins'].items():
        assert d.sha(path) == digest, path
    fixes = d.load(DOC / 'fixes.json')
    baseline = d.load(DOC / 'source-baseline.json')
    assert len(fixes) == 614 and len(baseline) == 119
    assert not (DOC / 'stage10-plan.json').exists(), 'Prepare only once from revision 9.'
    actions = d.rows(SELECTION / 'actions.csv')
    assert len(actions) == 372 and len({(a['File'], a['DNA']) for a in actions}) == 88
    definitions = dict(d.load(DOC / 'stage9-plan.json')['ShadowDefinitions'])
    archive_map = {}
    for name in ('source-manifest.json', 'fixes.json', 'source-baseline.json'):
        dest = DOC / ('stage10-before-' + name.removeprefix('source-'))
        dest.write_bytes((DOC / name).read_bytes())
        archive_map[(DOC / name).resolve()] = dest
    fileplans, diffs = [], []
    for row in selected['Files']:
        rel = row['File']
        assert rel.startswith(('common/dna_data/', 'common/bookmark_portraits/'))
        source = Path(row['SourcePath'])
        assert d.sha(source) == row['SourceSHA256']
        preview = SELECTION / row['Preview']
        assert d.sha(preview) == row['PreviewSHA256']
        before = d.read(source)
        after_bytes = approved_bytes(preview)
        after = after_bytes.decode('utf-8-sig')
        archive = DOC / 'stage10-before' / rel
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_bytes(source.read_bytes())
        archive_map[source.resolve()] = archive
        upstream_path = d.PLUS / rel
        upstream = d.read(upstream_path)
        original_presets = {p.key: p for p in d.parse(upstream).children}
        old = d.parse(before).children
        new = d.parse(after).children
        assert [p.key for p in old] == [p.key for p in new]
        expected_names = {a['DNA'] for a in actions if a['File'] == rel}
        changed = set()
        for src, dst in zip(old, new):
            original, replacement = src.body(before), dst.body(after)
            if original == replacement:
                continue
            changed.add(src.key)
            source_before = original_presets[src.key].body(upstream)
            assert upstream.count(source_before) == before.count(original) == 1
            fixes.append(dict(Id='dna-current-schema-' + src.key, Group='F33', File=rel,
                              SourceBefore=source_before, Before=original, After=replacement,
                              ExpectedCount=1,
                              Reason='Approved current-AGOT-only approximation; exact alleles in stage10-actions.csv.'))
        assert changed == expected_names and len(changed) == row['AffectedPresets']
        if not row['ExistingShadow']:
            assert not any(b['Catalog'] == 'AGOT_PLUS' and b['File'] == rel for b in baseline)
            baseline.append(dict(Catalog='AGOT_PLUS', File=rel, SHA256=d.sha(upstream_path)))
        definitions[rel] = [p.key for p in new]
        diffs.append(''.join(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
                                               fromfile='revision9/' + rel, tofile='revision10/' + rel)))
        fileplans.append(dict(File=rel, BeforeFile=str(archive.relative_to(DOC)), BeforeSHA256=d.sha(archive),
                              Preview=str(preview), PreviewSHA256=d.sha(preview),
                              ExistingShadow=row['ExistingShadow'], AffectedPresets=len(changed)))
    assert len(fixes) == 702 and len(baseline) == 124
    assert len({r['Id'] for r in fixes}) == len(fixes)
    evidence = []
    for source, dest in (('actions.csv', 'stage10-actions.csv'), ('selection.csv', 'stage10-selection.csv'),
                         ('alleles.csv', 'stage10-alleles.csv'), ('plan.json', 'stage10-approved-selection.json')):
        (DOC / dest).write_bytes((SELECTION / source).read_bytes())
        evidence.append(dict(File=dest, SHA256=d.sha(DOC / dest)))
    log_source = SELECTION.parent / 'ck3-agot-plus-fix-stage9-log-2026-09-19/remaining-dna.csv'
    log_dest = DOC / 'stage10-targeted-log-messages.csv'
    log_dest.write_bytes(log_source.read_bytes())
    evidence.append(dict(File=log_dest.name, SHA256=d.sha(log_dest)))
    sources = []
    for path, digest in selected['SourcePins'].items():
        archived = archive_map.get(Path(path).resolve())
        current = archived or Path(path)
        assert d.sha(current) == digest
        sources.append(dict(Path=str(current.resolve()), SHA256=digest, SelectionSource=path))
    sources.extend(pin(path) for path in archive_map.values())
    sources.extend(pin(SELECTION / f['Preview']) for f in selected['Files'])
    plan = dict(Revision=10, Groups=['F33'], Rules=len(fixes), Occurrences=sum(f['ExpectedCount'] for f in fixes),
                Shadows=57, Additions=12, FixGroups=33, PreviousFiles=manifest['Files'], Files=fileplans,
                Actions=372, Presets=88, TargetedLogMessages=250, ShadowDefinitions=definitions,
                Policy=selected['Policy'], Heuristic=selected['Heuristic'], Sources=sources, Evidence=evidence,
                EffectiveGeneFiles=selected['EffectiveGeneFiles'], GameExecutionChecked=False, FreshLogChecked=False)
    d.save('fixes.json', fixes)
    d.save('source-baseline.json', baseline)
    (DOC / 'stage10-dna.patch').write_bytes(''.join(diffs).encode('utf-8'))
    d.save('stage10-plan.json', plan)
    print('Prepared F33: 88 sequential preset rules, 17 DNA files, 5 new shadows; runtime unchanged.')


def sources():
    plan = d.load(DOC / 'stage10-plan.json')
    mods = d.verify_sources(plan)
    print(f'PASS: {len(plan["Sources"])} stage-ten source/archive/preview pins and {len(plan["Evidence"])} evidence files.')
    return plan, mods


def check():
    plan, mods = sources()
    live_manifest = d.load(DOC / 'source-manifest.json')
    assert live_manifest['Revision'] in (10, 11, 12, 13, 14, 15)
    archived = {}
    manifest = live_manifest
    if live_manifest['Revision'] >= 11:
        # Stage 11 changes two non-DNA portrait files. Validate their revision-ten
        # snapshots while all DNA and the 8,368 diagnostic checks remain live.
        manifest = d.load(DOC / 'stage11-before-manifest.json')
        archived = {rel: DOC / path for rel, path in d.load(DOC / 'stage11-plan.json')['Archives'].items()}
        assert all(rel.startswith('gfx/portraits/portrait_modifiers/') for rel in archived)
    if live_manifest['Revision'] >= 12:
        for rel, path in d.load(DOC / 'stage12-plan.json')['Archives'].items():
            archived.setdefault(rel, DOC / path)
    def prior_path(rel):
        return archived.get(rel, d.before_stage14_path(MOD / rel))
    assert manifest['Revision'] == 10 and len(manifest['Files']) == 69
    assert (manifest['ReplacementRules'], manifest['ReplacementOccurrences'], manifest['FixGroups']) == (702, 1389, 33)
    for row in manifest['Files']:
        assert d.sha(prior_path(row['File'])) == row['PatchedSHA256'], row['File']
    selected_files = {f['File'] for f in plan['Files']}
    unchanged_files = [r for r in plan['PreviousFiles'] if r['File'] not in selected_files]
    assert len(unchanged_files) == 52
    for row in unchanged_files:
        assert d.sha(prior_path(row['File'])) == row['PatchedSHA256'], row['File']
    # Recipes before this stage are unchanged, including all earlier Before/After text.
    fixes = d.load(DOC / 'fixes.json')
    if live_manifest['Revision'] >= 11:
        previous_fixes = d.load(DOC / 'stage11-before-fixes.json')
        assert fixes[:len(previous_fixes)] == previous_fixes
        fixes = previous_fixes
    assert fixes[:614] == d.load(DOC / 'stage10-before-fixes.json')
    assert all(r['Group'] == 'F33' and r['SourceBefore'] for r in fixes[614:])
    schema, templates = defaultdict(list), defaultdict(list)
    for _, path in d.effective('common/genes', mods).values():
        text = d.read(path)
        for group in d.walk(d.parse(text)):
            if group.key not in ('morph_genes', 'color_genes', 'accessory_genes'):
                continue
            for gene in group.children:
                schema[gene.key].append((path, gene, text))
                for block in gene.children:
                    # A named direct child with an index is a template. Female-
                    # only templates and empty accessory templates are valid too.
                    if re.search(r'\bindex\s*=', code(block.body(text))):
                        templates[(gene.key, block.key)].append((path, block, text))
    assert not LEGACY.intersection(schema)
    # Recheck the effective head providers, including active attributes only.
    heads = {}
    for sex in ('male', 'female'):
        rel = f'gfx/models/portraits/{sex}_head/{sex}_head.asset'
        provider = None
        for mod in mods:
            if any(rel == rp or rel.startswith(rp.rstrip('/') + '/') for rp in mod['Replace']):
                provider = None
            candidate = Path(mod['Path']) / rel
            if candidate.is_file():
                provider = candidate
        assert provider and any(Path(p['Path']).resolve() == provider.resolve() for p in plan['Sources'])
        text = d.read(provider)
        heads[sex] = set()
        for block in d.walk(d.parse(text)):
            if block.key == 'attribute':
                name = re.search(r'\bname\s*=\s*"([^"]+)"', code(block.body(text)))
                if name:
                    heads[sex].add(name[1])
    acts = defaultdict(list)
    for a in d.rows(DOC / 'stage10-actions.csv'):
        acts[(a['File'], a['DNA'])].append(a)
    assert len(acts) == 88
    states, originals, unchanged_presets, tested = {}, {}, 0, 0
    dna_files = d.effective('common/dna_data', mods) | d.effective('common/bookmark_portraits', mods)
    for row in plan['Files']:
        rel = row['File']
        assert dna_files[rel][1].resolve() == (MOD / rel).resolve(), ('Shadowed DNA', rel)
        assert d.sha(DOC / row['BeforeFile']) == row['BeforeSHA256']
        assert (MOD / rel).read_bytes() == approved_bytes(row['Preview']), ('Approved preview differs', rel)
        before, after = d.read(DOC / row['BeforeFile']), d.read(MOD / rel)
        old, new = d.parse(before).children, d.parse(after).children
        assert [p.key for p in old] == [p.key for p in new]
        for src, dst in zip(old, new):
            key = rel, src.key
            actions = acts.get(key, [])
            if not actions:
                assert src.body(before) == dst.body(after), key
                unchanged_presets += 1
                continue
            og, ng = d.genes_of(src), d.genes_of(dst)
            original, actual = d.state(og, before), d.state(ng, after)
            originals[key] = original
            expected = {g: [v.copy() for v in vs] for g, vs in original.items()}
            touched = set()
            for action in actions:
                gene = action['Gene']
                assert ' | '.join(' '.join(v) for v in expected[gene]) == action['Before'], action
                if action['Kind'] == 'retire':
                    expected.pop(gene)
                else:
                    expected[gene] = [re.findall(r'"[^"\r\n]*"|[-\d.]+', action['After'])]
                touched.add(gene)
                tested += 1
            assert expected == actual and not LEGACY.intersection(actual), key
            assert [(b.key, b.body(before)) for b in og.children if b.key not in touched] == [(b.key, b.body(after)) for b in ng.children if b.key not in touched], key
            assert src.body(before).replace(og.body(before), 'GENES', 1) == dst.body(after).replace(ng.body(after), 'GENES', 1), key
            # Check every active field in an affected preset, not just edited fields.
            for gene, values in actual.items():
                assert len(values) == 1 and gene in schema, (key, gene)
                value = values[0]
                assert len(value) in (4, 8) and all(0 <= int(v) <= 255 for v in value if not v.startswith('"')), (key, gene, value)
                for template in (v.strip('"') for v in value if v.startswith('"') and v != '""'):
                    assert (gene, template) in templates, (key, gene, template)
            for action in actions:
                if action['Kind'] == 'retire':
                    continue
                gene = action['Gene']
                assert len(schema[gene]) == 1
                for template in actual[gene][0][::2]:
                    definitions = templates[(gene, template.strip('"'))]
                    assert len(definitions) == 1
                    if gene != 'legwear':
                        _, block, text = definitions[0]
                        attributes = set(re.findall(r'\battribute\s*=\s*"([^"]+)"', code(block.body(text))))
                        assert all(attributes <= available for available in heads.values())
            states[key] = actual
    assert tested == 372 and unchanged_presets == 208
    # Check the independently recorded selection and both inherited alleles.
    selected = d.rows(DOC / 'stage10-selection.csv')
    assert len(selected) == 250
    for row in selected:
        key = row['File'], row['DNA']
        assert ' | '.join(' '.join(v) for v in originals[key][row['OldGene']]) == row['OldValue']
        assert ' '.join(states[key][row['TargetGene']][0]) == row['TargetAfter']
    for row in d.rows(DOC / 'stage10-alleles.csv'):
        i = 0 if row['Allele'] == 'dominant' else 2
        value = states[(row['File'], row['DNA'])][row['TargetGene']][0]
        assert value[i].strip('"') == row['AfterTemplate'] and value[i+1] == row['AfterValue']
    # Cover both the 250 residual diagnostics and all earlier 8,118 fixes.
    covered = {}
    for table, expected_count in (('stage9-original-dna-log.csv', 8368), ('stage10-targeted-log-messages.csv', 250)):
        issues = d.rows(DOC / table)
        assert len(issues) == expected_count
        for issue in issues:
            key = issue['File'], issue['DNA']
            if key not in states:
                text = d.read(dna_files[issue['File']][1])
                preset = next(p for p in d.parse(text).children if p.key == issue['DNA'])
                states[key] = d.state(d.genes_of(preset), text)
            gene, cat = issue['Gene'], issue['Category']
            vs = states[key].get(gene, [])
            if cat == 'dna_missing_gene':
                resolved = bool(vs) and gene in schema
            elif cat == 'dna_unknown_gene':
                resolved = not vs
            elif cat in ('dna_template', 'dna_accessory'):
                resolved = all(v[j] == '""' or (gene, v[j].strip('"')) in templates for v in vs for j in (0, 2))
            elif cat == 'dna_duplicate':
                resolved = len(vs) == 1
            else:
                raise AssertionError(cat)
            assert resolved, ('Unresolved old diagnostic', issue)
        covered[table] = len(issues)
    result = dict(Revision=10, Status='PASS', RuntimeFiles=69, PreviousRuntimeFilesUnchanged=52,
                  ValidatedRuntimeRevision=live_manifest['Revision'], ArchivedNonDNAFiles=len(archived),
                  ChangedFiles=17, NewShadows=5, AffectedPresets=88, UnchangedPresetsInChangedFiles=208,
                  GeneActions=tested, ActionsByKind=dict(Counter(a['Kind'] for actions in acts.values() for a in actions)),
                  ExactApprovedPreviewExceptCommentLabel=True, PreviousRecipesUnchanged=True,
                  AllSelectedMorphAttributesAvailableInBothHeads=True, UnlistedGeneTextPreserved=True,
                  GlobalSchemaUnchanged=True, HistoricalDiagnosticsStructurallyResolved=covered,
                  SourcePinsVerified=len(plan['Sources']), ActiveMods=len(mods)-1,
                  GameExecutionChecked=False, FreshLogChecked=False, VisualEquivalenceClaimed=False,
                  ManifestSHA256=d.sha(DOC / 'source-manifest.json'))
    d.save('stage10-validation.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('prepare', 'sources', 'check'))
    args = parser.parse_args()
    {'prepare': prepare, 'sources': sources, 'check': check}[args.mode]()
