"""Apply the reviewed DNA migration as exact, source-pinned F32 replacements.

prepare writes build recipes only; the existing PowerShell builder writes runtime
files. check validates actual generated DNA against the reviewed allele changes,
the effective gene schema and the old engine diagnostics. No CK3 execution.
"""
import argparse
from collections import Counter, defaultdict
import csv
import difflib
import hashlib
import json
from pathlib import Path
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
MOD = Path(__file__).resolve().parents[1]
DOC = MOD / 'docs'
REPO = MOD.parents[1]
REPORT = REPO / 'docs/reports/agot-plus-dna-gene-analysis-2026-09-19'
RUN = REPORT.parent / 'ck3-agot-plus-fix-stage8-log-2026-09-19'
PROFILE = Path('C:/Users/RUSBAR/Documents/Paradox Interactive/Crusader Kings III')
GAME = Path('E:/SteamLibrary/steamapps/common/Crusader Kings III/game')
PLUS = Path('E:/SteamLibrary/steamapps/workshop/content/1158310/2950245430')
AGOT = Path('E:/SteamLibrary/steamapps/workshop/content/1158310/2962333032')


def native(path):
    path = Path(path).absolute()
    text = str(path)
    if sys.platform == 'win32' and not text.startswith('\\\\?\\'):
        text = '\\\\?\\UNC\\' + text[2:] if text.startswith('\\\\') else '\\\\?\\' + text
    return Path(text)


def read(path):
    return native(path).read_bytes().decode('utf-8-sig')


def sha(path):
    return hashlib.sha256(native(path).read_bytes()).hexdigest().upper()


def load(path):
    return json.loads(read(path))


def rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def save(name, value):
    (DOC / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


class Block:
    def __init__(self, key, start):
        self.key, self.start, self.end, self.children = key, start, None, []

    def child(self, key):
        return next((b for b in self.children if b.key == key), None)

    def body(self, text):
        return text[self.start:self.end]


# Same token grammar as the reviewed analysis; comments/quoted braces are inert.
TOK = re.compile(r'#[^\r\n]*|"(?:\\.|[^"\\])*"|[{}=]|[^\s{}=<>!]+|[<>!]=?')


def parse(text):
    root = Block('', 0)
    stack, last = [root], []
    for match in TOK.finditer(text):
        token = match[0]
        if token.startswith('#'):
            continue
        if token == '{':
            key = last[-2][0].strip('"') if len(last) > 1 and last[-1][0] == '=' else ''
            block = Block(key, last[-2][1] if key else match.start())
            stack[-1].children.append(block)
            stack.append(block)
        elif token == '}':
            assert len(stack) > 1, ('extra closing brace', match.start())
            stack.pop().end = match.end()
        last = (last + [(token, match.start())])[-2:]
    assert len(stack) == 1, ('unclosed block', stack[-1].key)
    root.end = len(text)
    return root


def walk(block):
    yield block
    for child in block.children:
        yield from walk(child)


def genes_of(preset):
    return (preset.child('portrait_info') or preset).child('genes')


def value(block, text):
    return re.findall(r'"[^"\r\n]*"|[-\d.]+', block.body(text).split('{', 1)[1].rsplit('}', 1)[0])


def state(genes, text):
    result = defaultdict(list)
    for block in genes.children:
        result[block.key].append(value(block, text))
    return dict(result)


def active_mods():
    recorded = rows(RUN / 'active-mods.csv')
    enabled = load(PROFILE / 'dlc_load.json')['enabled_mods']
    assert enabled == [m['Descriptor'] for m in recorded], 'Active mod order changed; re-analyse providers.'
    result = [dict(Name='CK3', Path=str(GAME), Replace=[])]
    for mod in recorded:
        descriptor = read(PROFILE / mod['Descriptor'])
        path = re.search(r'(?m)^\s*path\s*=\s*"([^"]+)"', descriptor)
        assert path and Path(path[1]).resolve() == Path(mod['Path']).resolve(), mod['Descriptor']
        mod['Replace'] = re.findall(r'(?m)^\s*replace_path\s*=\s*"([^"]+)"', descriptor)
        result.append(mod)
    return result


def effective(folder, mods):
    result = {}
    for mod in mods:
        for replaced in mod['Replace']:
            result = {k: v for k, v in result.items() if not (k == replaced or k.startswith(replaced.rstrip('/') + '/'))}
        root = Path(mod['Path'])
        if (root / folder).is_dir():
            for path in sorted((root / folder).rglob('*.txt')):
                result[path.relative_to(root).as_posix()] = (mod, path)
    return result


def verify_sources(plan):
    mods = active_mods()
    for pin in plan['Sources']:
        assert sha(pin['Path']) == pin['SHA256'], ('DNA source changed', pin['Path'])
    for pin in plan['Evidence']:
        assert sha(DOC / pin['File']) == pin['SHA256'], ('Reviewed migration changed', pin['File'])
    owners = effective('common/genes', mods)
    actual = {rel: str(path.resolve()) for rel, (_, path) in owners.items()}
    assert actual == plan['EffectiveGeneFiles'], 'Effective gene schema changed.'
    return mods


def migrate_preset(preset, text, actions):
    genes = genes_of(preset)
    assert genes and all('"human_body"' in v for v in state(genes, text)['gene_dragon'])
    by_key = defaultdict(list)
    for block in genes.children:
        by_key[block.key].append(block)
    edits, appended = [], []
    newline = '\r\n' if '\r\n' in text else '\n'
    for action in actions:
        old, new = action['OldGene'], action['NewGene']
        blocks = by_key[old] if old else []
        assert ' | '.join(' '.join(value(b, text)) for b in blocks) == action['Before'], action
        if not old:
            assert new not in by_key, action
            appended.append(f'{new} = {{ {action["After"]} }}')
            continue
        if action['Reason'] == 'remove_identical_duplicate':
            assert len(blocks) == 2 and value(blocks[0], text) == value(blocks[1], text)
            blocks = blocks[1:]
            new = ''
        else:
            assert len(blocks) == 1, action
        for block in blocks:
            old_body = block.body(text)
            if not new:
                # Retain the author's old entry as a comment, outside the schema.
                replacement = '# AGOT_PLUS_FIX F32: ' + action['Reason'] + '; ' + old_body.replace(newline, newline + '# ')
            elif action['Reason'] == 'rename_head_gene_preserve_both_alleles':
                replacement = new + old_body[len(old):]
            elif action['Reason'] == 'supported_afro_template_preserve_strength':
                replacement = old_body.replace('"hair_afro_no_beard"', '"hair_afro"')
            else:
                replacement = f'{new} = {{ {action["After"]} }}'
            edits.append((block.start, block.end, replacement))
    if appended:
        insertion = text.rfind('\n', genes.start, genes.end - 1) + 1
        assert not text[insertion:genes.end - 1].strip(), 'Genes closing brace must be on its own line.'
        first = genes.children[0]
        indent = text[text.rfind('\n', genes.start, first.start) + 1:first.start]
        assert not indent.strip()
        extra = indent + '# AGOT_PLUS_FIX F32: current AGOT human defaults for missing fields.' + newline
        extra += ''.join(indent + line + newline for line in appended)
        edits.append((insertion, insertion, extra))
    output, previous = preset.body(text), preset.end
    for start, end, replacement in sorted(edits, reverse=True):
        assert genes.start <= start <= end < genes.end and end <= previous
        output = output[:start-preset.start] + replacement + output[end-preset.start:]
        previous = start
    return output


def prepare():
    manifest = load(DOC / 'source-manifest.json')
    assert manifest['Revision'] == 8 and len(manifest['Files']) == 45, 'Prepare once from verified revision 8.'
    for row in manifest['Files']:
        assert sha(MOD / row['File']) == row['PatchedSHA256'], row['File']
    summary = load(REPORT / 'preflight-summary.json')
    assert (summary['Actions'], summary['AffectedFiles'], summary['AffectedPresets']) == (7912, 19, 303)
    evidence = []
    for original, target in [
        ('proposed-actions.csv', 'stage9-actions.csv'),
        ('dna-log-index.csv', 'stage9-original-dna-log.csv'),
        ('proposed-covered-log.csv', 'stage9-targeted-log-messages.csv'),
        ('proposed-deferred-log.csv', 'stage9-deferred-log-messages.csv'),
        ('proposed-human-dragon-defaults.csv', 'stage9-human-dragon-defaults.csv'),
    ]:
        evidence.append(dict(File=target, SHA256=sha(REPORT / original), Original=original))
    mods = active_mods()
    roots = {m['Name']: Path(m['Path']) for m in mods}
    sources = []
    for row in rows(REPORT / 'source-hashes.csv') + rows(REPORT / 'agot-donor-source-hashes.csv'):
        path = roots[row['Mod']] / row['File']
        assert sha(path) == row['SHA256'], str(path)
        sources.append(dict(Path=str(path), SHA256=row['SHA256']))
    for row in load(REPORT / 'verification.json')['SupportingSources']:
        path = AGOT / row['File']
        assert sha(path) == row['SHA256']
        sources.append(dict(Path=str(path), SHA256=row['SHA256']))
    fixes, baseline = load(DOC / 'fixes.json'), load(DOC / 'source-baseline.json')
    assert len(fixes) == 311 and len(baseline) == 100
    by_preset = defaultdict(list)
    for action in rows(REPORT / 'proposed-actions.csv'):
        by_preset[(action['File'], action['DNA'])].append(action)
    files = sorted({rel for rel, _ in by_preset})
    assert len(files) == 19 and not set(files) & {r['File'] for r in manifest['Files']}
    definitions = dict(load(DOC / 'stage8-plan.json')['ShadowDefinitions'])
    diffs = []
    for rel in files:
        text = read(PLUS / rel)
        root, output = parse(text), text
        for preset in root.children:
            actions = by_preset.get((rel, preset.key))
            if not actions:
                continue
            before = preset.body(text)
            after = migrate_preset(preset, text, actions)
            assert before != after and text.count(before) == output.count(before) == 1, (rel, preset.key)
            fixes.append(dict(Id=f'dna-schema-{preset.key}', Group='F32', File=rel,
                              Before=before, After=after, ExpectedCount=1,
                              Reason='Reviewed conservative human DNA migration; allele-level changes recorded in stage9-actions.csv.'))
            output = output.replace(before, after)
        assert [b.key for b in root.children] == [b.key for b in parse(output).children]
        definitions[rel] = [b.key for b in root.children]
        assert not any(r['Catalog'] == 'AGOT_PLUS' and r['File'] == rel for r in baseline)
        baseline.append(dict(Catalog='AGOT_PLUS', File=rel, SHA256=sha(PLUS / rel)))
        diffs.extend(difflib.unified_diff(text.splitlines(True), output.splitlines(True), fromfile='AGOT+/' + rel, tofile='AGOT_PLUS_FIX/' + rel))
    assert len(fixes) == 614 and len({r['Id'] for r in fixes}) == len(fixes)
    plan = dict(Revision=9, Groups=['F32'], Rules=len(fixes), Occurrences=sum(r['ExpectedCount'] for r in fixes),
                Shadows=52, Additions=12, FixGroups=32, PreviousFiles=manifest['Files'],
                NewFiles=files, GeneActions=7912, Presets=303, PredictedCoveredLogMessages=8118,
                DeferredLogMessages=250, ShadowDefinitions=definitions, Sources=sources,
                Evidence=[{k:v for k,v in r.items() if k != 'Original'} for r in evidence],
                EffectiveGeneFiles={rel: str(path.resolve()) for rel, (_, path) in effective('common/genes', mods).items()},
                GameExecutionChecked=False, FreshLogChecked=False)
    # All source and inventory checks complete before build recipes are changed.
    (DOC / 'stage9-before-manifest.json').write_bytes((DOC / 'source-manifest.json').read_bytes())
    for entry in evidence:
        (DOC / entry['File']).write_bytes((REPORT / entry['Original']).read_bytes())
    (DOC / 'stage9-dna.patch').write_bytes(''.join(diffs).encode('utf-8'))
    save('stage9-plan.json', plan)
    save('fixes.json', fixes)
    save('source-baseline.json', baseline)
    print('Prepared F32: 303 exact preset replacements / 7912 gene actions / 19 new shadows. Runtime files not yet built.')


def check(before_stage10=False):
    plan = load(DOC / 'stage9-plan.json')
    mods = verify_sources(plan)
    # Revision 10 intentionally changes 12 of these files. Revalidate revision 9
    # from pinned archived inputs; the stage-ten check proves their exact delta
    # to the live output and covers all old engine diagnostics on the live DNA.
    manifest_path = DOC / ('stage10-before-manifest.json' if before_stage10 else 'source-manifest.json')
    manifest = load(manifest_path)
    archived = {row['File']: DOC / row['BeforeFile'] for row in load(DOC / 'stage10-plan.json')['Files'] if row['ExistingShadow']} if before_stage10 else {}
    if before_stage10 and load(DOC / 'source-manifest.json')['Revision'] >= 11:
        for rel, path in load(DOC / 'stage11-plan.json')['Archives'].items():
            # The older stage-ten archive takes precedence for any overlap.
            archived.setdefault(rel, DOC / path)
    if before_stage10 and load(DOC / 'source-manifest.json')['Revision'] == 12:
        for rel, path in load(DOC / 'stage12-plan.json')['Archives'].items():
            archived.setdefault(rel, DOC / path)
    def runtime_path(rel):
        return archived.get(rel, MOD / rel)
    assert manifest['Revision'] == 9 and len(manifest['Files']) == 64
    for row in plan['PreviousFiles']:
        assert sha(runtime_path(row['File'])) == row['PatchedSHA256'], ('Previous fix changed', row['File'])
    for row in manifest['Files']:
        assert sha(runtime_path(row['File'])) == row['PatchedSHA256']
    schema, templates = set(), set()
    for _, path in effective('common/genes', mods).values():
        text = read(path)
        for group in walk(parse(text)):
            if group.key in ('morph_genes', 'color_genes', 'accessory_genes'):
                for gene in group.children:
                    schema.add(gene.key)
                    for block in gene.children:
                        if re.search(r'\bindex\s*=', block.body(text)) and (block.child('male') or re.search(r'\bmale\s*=', block.body(text))):
                            templates.add((gene.key, block.key))
    by_preset = defaultdict(list)
    actions = rows(DOC / 'stage9-actions.csv')
    for action in actions:
        by_preset[(action['File'], action['DNA'])].append(action)
    states, original_states, unchanged, tested = {}, {}, 0, 0
    dna_files = {**effective('common/dna_data', mods), **effective('common/bookmark_portraits', mods)}
    for rel in plan['NewFiles']:
        assert dna_files[rel][1].resolve() == (MOD / rel).resolve(), ('Shadowed migration', rel)
        before, after = read(PLUS / rel), read(runtime_path(rel))
        old, new = parse(before), parse(after)
        assert [b.key for b in old.children] == [b.key for b in new.children]
        for src, dst in zip(old.children, new.children):
            key = rel, src.key
            acts = by_preset.get(key, [])
            if not acts:
                assert src.body(before) == dst.body(after), key
                unchanged += 1
            og, ng = genes_of(src), genes_of(dst)
            if og is None:
                assert ng is None
                continue
            expected, actual = state(og, before), state(ng, after)
            original_states[key] = state(og, before)
            touched = set()
            for act in acts:
                oldgene, newgene = act['OldGene'], act['NewGene']
                prior = expected.pop(oldgene, []) if oldgene else []
                assert ' | '.join(' '.join(v) for v in prior) == act['Before'], act
                if newgene:
                    assert newgene not in expected
                    v = re.findall(r'"[^"\r\n]*"|[-\d.]+', act['After'])
                    assert len(v) == 4 and newgene in schema
                    assert all(t == '""' or (newgene, t.strip('"')) in templates for t in v[::2]), act
                    expected[newgene] = [v]
                touched.update((oldgene, newgene))
                tested += 1
            assert expected == actual, key
            # Existing, untouched gene blocks (including distinct inherited alleles)
            # must retain their exact original text, not just numerical equivalence.
            assert [(b.key, b.body(before)) for b in og.children if b.key not in touched] == [(b.key, b.body(after)) for b in ng.children if b.key not in touched], key
            states[key] = actual
    assert tested == 7912 and len(by_preset) == 303
    diagnostics = rows(DOC / 'stage9-original-dna-log.csv')
    for issue in diagnostics:
        key = issue['File'], issue['DNA']
        if key not in states:
            path = dna_files[issue['File']][1]
            if before_stage10:
                # The five newly shadowed files still came directly from PLUS
                # in revision 9; all 17 original inputs have a pinned archive.
                archived_issue = DOC / 'stage10-before' / issue['File']
                if archived_issue.is_file():
                    path = archived_issue
            text = read(path)
            preset = next(b for b in parse(text).children if b.key == issue['DNA'])
            states[key] = state(genes_of(preset), text)
    covered, deferred = [], []
    for issue in diagnostics:
        g, category = issue['Gene'], issue['Category']
        vs = states[(issue['File'], issue['DNA'])].get(g, [])
        if category == 'dna_missing_gene':
            resolved = bool(vs) and g in schema
        elif category == 'dna_unknown_gene':
            resolved = not vs
        elif category in ('dna_template', 'dna_accessory'):
            resolved = all(v[j] == '""' or (g, v[j].strip('"')) in templates for v in vs for j in (0, 2))
        elif category == 'dna_duplicate':
            resolved = len(vs) == 1
        else:
            raise AssertionError(category)
        (covered if resolved else deferred).append(issue['LogLine'])
    assert covered == [r['LogLine'] for r in rows(DOC / 'stage9-targeted-log-messages.csv')]
    assert deferred == [r['LogLine'] for r in rows(DOC / 'stage9-deferred-log-messages.csv')]
    assert (len(covered), len(deferred)) == (8118, 250)
    # Every intentionally deferred value stays exactly as it was, even when its
    # neighbouring genes are migrated. Also prove the two unequal ear duplicates survive.
    for issue in rows(DOC / 'stage9-deferred-log-messages.csv'):
        key = issue['File'], issue['DNA']
        if key in original_states:
            assert states[key][issue['Gene']] == original_states[key][issue['Gene']], issue
    result = dict(Revision=9, Status='PASS', RuntimeFiles=64, PreviousRuntimeFilesUnchanged=45,
                  NewDNAFiles=19, MigratedPresets=303, GeneActions=tested, UnchangedPresetsInNewFiles=unchanged,
                  AllNewTemplatesResolve=True, UnlistedGeneTextPreserved=True, DeferredAllelesPreserved=True,
                  ActiveMods=len(mods)-1, ActiveGeneFiles=len(plan['EffectiveGeneFiles']),
                  SourcePinsVerified=len(plan['Sources']), PredictedCoveredLogMessages=len(covered),
                  DeferredLogMessages=len(deferred), ActionsByReason=dict(Counter(r['Reason'] for r in actions)),
                  GameExecutionChecked=False, FreshLogChecked=False, ManifestSHA256=sha(manifest_path))
    if before_stage10:
        result['ValidationTarget'] = 'Pinned revision-nine inputs before the approved stage-ten changes'
    save('stage10-prior-dna-validation.json' if before_stage10 else 'stage9-validation.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['prepare', 'sources', 'check'])
    parser.add_argument('--before-stage10', action='store_true', help='Validate archived revision-nine DNA inputs, not the current output.')
    args = parser.parse_args()
    if args.mode == 'prepare':
        prepare()
    elif args.mode == 'check':
        check(before_stage10=args.before_stage10)
    else:
        plan = load(DOC / 'stage9-plan.json')
        verify_sources(plan)
        print(f'PASS: {len(plan["Sources"])} DNA source pins and unchanged effective gene providers.')
