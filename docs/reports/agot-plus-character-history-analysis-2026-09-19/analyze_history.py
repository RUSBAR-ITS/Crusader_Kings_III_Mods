"""Read-only audit of installed sources; writes evidence only beside this script."""
from pathlib import Path
from collections import Counter, defaultdict
from functools import lru_cache
import bisect
import csv
import difflib
import hashlib
import json
import re

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[2]
LOG = OUT.parent / 'ck3-agot-plus-fix-stage6-log-2026-09-19'
PROFILE = Path('C:/Users/RUSBAR/Documents/Paradox Interactive/Crusader Kings III')
GAME = Path('E:/SteamLibrary/steamapps/common/Crusader Kings III/game')

def read(path):
    return Path(path).read_text(encoding='utf-8-sig')

def table(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))

def write_csv(name, rows, fields=None):
    with (OUT / name).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def write_json(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def mask(text):
    # Preserve offsets and newlines; braces in comments/strings are not syntax.
    return re.sub(r'"(?:\\.|[^"\\])*"|#[^\r\n]*',
                  lambda m: re.sub(r'[^\r\n]', ' ', m[0]), text)

def line_at(text, position):
    return text.count('\n', 0, position) + 1

@lru_cache(maxsize=128)
def definitions(text):
    clean = mask(text)
    pairs, depths, stack = {}, {}, []
    for token in re.finditer('[{}]', clean):
        if token[0] == '{':
            depths[token.start()] = len(stack)
            stack.append(token.start())
        elif stack:
            pairs[stack.pop()] = token.end()
        # Stray closing braces are analyzed separately; do not make all
        # subsequent real root definitions disappear from this inventory.
    newlines = [m.start() for m in re.finditer('\n', text)]
    result = []
    for match in re.finditer(r'(?m)^[ \t]*([\w-]+)\s*=\s*\{', clean):
        start = clean.index('{', match.start(), match.end())
        if depths[start] != 0:
            continue
        end = pairs.get(start, len(text))
        result.append({'Id': match[1], 'Line': bisect.bisect_left(newlines, match.start()) + 1,
                       'Start': match.start(), 'End': end, 'Body': text[match.start():end]})
    return tuple(result)

mods = table(LOG / 'active-mods.csv')
current = json.loads(read(PROFILE / 'dlc_load.json'))
assert current['enabled_mods'] == [row['Descriptor'] for row in mods], 'Active set changed'
roots = [{'Name': 'CK3', 'Path': str(GAME), 'Descriptor': ''}] + mods
vfs = {}
replacements = []
for mod in roots:
    if mod['Descriptor']:
        desc = read(PROFILE / mod['Descriptor'])
        descriptor_path = re.search(r'(?m)^\s*path="([^"]+)"', desc)[1]
        assert Path(descriptor_path).resolve() == Path(mod['Path']).resolve()
        for prefix in re.findall(r'(?m)^\s*replace_path="([^"]+)"', desc):
            prefix = prefix.rstrip('/') + '/'
            replacements.append({'Mod': mod['Name'], 'Prefix': prefix})
            vfs = {rel: item for rel, item in vfs.items() if not rel.startswith(prefix)}
    root = Path(mod['Path'])
    for directory in ('common', 'history', 'events'):
        for path in (root / directory).rglob('*.txt'):
            vfs[path.relative_to(root).as_posix()] = {'Path': path, 'Mod': mod['Name']}

sources = {}
@lru_cache(maxsize=256)
def text_for(rel):
    item = vfs[rel]
    path = item['Path']
    data = path.read_bytes()
    sources[str(path)] = {'Path': str(path), 'Mod': item['Mod'], 'File': rel,
                          'SHA256': hashlib.sha256(data).hexdigest().upper()}
    return data.decode('utf-8-sig')

indexes = {}
for category, prefix in [('DNA', 'common/dna_data/'), ('Character', 'history/characters/'),
                         ('Trait', 'common/traits/'), ('Dynasty', 'common/dynasties/')]:
    index = defaultdict(list)
    for rel in sorted(vfs):
        if rel.startswith(prefix):
            text = text_for(rel)
            for definition in definitions(text):
                index[definition['Id']].append({**definition, 'File': rel, 'Mod': vfs[rel]['Mod']})
    indexes[category] = index

entries = table(LOG / 'agot-plus-without-portraits.csv')
history = [row for row in entries if row['IssueClass'] == 'Character_history']
assert len(history) == 103
diagnostics = []
dna_rows = []
for row in history:
    rel = row['Evidence']
    text = text_for(rel)
    location = re.search(r'(?:near line:|line:)\s*(\d+)', row['Message'])
    line = int(location[1])
    source_line = text.splitlines()[line - 1].strip()
    char_defs = list(definitions(text))
    char = next((d for d in char_defs if d['Line'] <= line <= line_at(text, d['End'])), None)
    id_ = char['Id'] if char else '(outside character definition)'
    name = re.search(r'(?m)^\s*name\s*=\s*([^\s#]+)', char['Body']) if char else None
    if source_line.startswith('dna ='):
        issue = 'Missing_DNA'
        key = re.search(r'^dna\s*=\s*(\S+)', source_line)[1]
        assert key not in indexes['DNA'], f'DNA found unexpectedly: {key}'
        dna_rows.append({'Character': id_, 'Name': name[1] if name else '', 'DNA': key,
                         'File': rel, 'Line': line, 'ActiveDNADefinitions': 0,
                         'CharacterDefinitionCount': len(indexes['Character'].get(id_, [])),
                         'SuggestedAction': 'Omit only unresolved dna assignment; appearance fallback, not restoration'})
    elif 6597 <= line <= 6608 and rel.endswith('asoiaf_char_dummies.txt'):
        issue = 'Partially_commented_anchor'
    elif source_line == 'dynasty = none':
        issue = 'Invalid_none_dynasty'
        assert 'none' not in indexes['Dynasty']
    elif source_line == 'add_trait = lifestyle_mystic_3_history':
        issue = 'Obsolete_mystic_trait'
        assert 'lifestyle_mystic_3_history' not in indexes['Trait']
        assert 'lifestyle_mystic' in indexes['Trait']
    else:
        raise AssertionError((rel, line, source_line))
    diagnostics.append({'LogLine': row['LogLine'], 'Kind': issue, 'Character': id_,
                        'File': rel, 'SourceLine': line, 'SourceText': source_line,
                        'Message': row['Message']})
write_csv('history-diagnostics.csv', diagnostics)
write_csv('missing-dna.csv', dna_rows)
assert len(dna_rows) == 98

# Audit all DNA assignments in the three implicated files, including those
# already valid. This avoids proposing blanket deletion of authored portraits.
assignments = []
for rel in sorted({row['Evidence'] for row in history}):
    text = text_for(rel)
    clean = mask(text)
    for match in re.finditer(r'(?m)^\s*dna\s*=\s*([\w-]+)', clean):
        key = match[1]
        assignments.append({'File': rel, 'Line': line_at(text, match.start(1)), 'DNA': key,
                            'DefinitionCount': len(indexes['DNA'].get(key, [])),
                            'DefinitionFiles': ' | '.join(d['File'] for d in indexes['DNA'].get(key, []))})
write_csv('all-dna-assignments.csv', assignments)

# Ownerless link errors form a separate population, not part of the 103.
all_entries = table(LOG / 'classified-entries.csv')
link_entries = [row for row in all_entries if not row['Owner'] and row['Component'] == 'history.cpp:644']
link_counts = Counter(re.search(r'character:([\w-]+)', row['Message'])[1] for row in link_entries)
refs = []
for rel, item in vfs.items():
    text = item['Path'].read_bytes().decode('utf-8-sig', errors='replace')
    if 'character:' not in text:
        continue
    clean = mask(text)
    for match in re.finditer(r'\bcharacter:([\w-]+)', clean):
        if match[1] in link_counts:
            line = line_at(text, match.start())
            refs.append({'Character': match[1], 'File': rel, 'Mod': item['Mod'], 'Line': line,
                         'SourceText': text.splitlines()[line - 1].strip()})
            if str(item['Path']) not in sources:
                text_for(rel)
write_csv('character-link-reference-sites.csv', refs)
links = []
for key, count in link_counts.items():
    matches = [r for r in refs if r['Character'] == key]
    links.append({'Character': key, 'LogMessages': count,
                  'ActiveCharacterDefinitions': len(indexes['Character'].get(key, [])),
                  'SameNamedDNA': len(indexes['DNA'].get(key, [])),
                  'ReferenceSites': len(matches),
                  'AppearanceDonorSites': sum('copy_inheritable_appearance_from' in r['SourceText'] for r in matches),
                  'Mods': ' | '.join(sorted({r['Mod'] for r in matches})),
                  'DefinitionFiles': ' | '.join(r['File'] for r in indexes['Character'].get(key, []))})
write_csv('character-links.csv', links)

# Save verbatim evidence snippets with stable line numbers.
snippets = []
for rel, begin, end in [
    ('history/characters/asoiaf_char_dummies.txt', 6588, 6663),
    ('history/characters/asoiaf_char_dummies.txt', 5188, 5207),
    ('history/characters/asoiaf_char_stormlands.txt', 109, 161),
    ('history/characters/00_agot_char_stormlands.txt', 2135, 2158),
    ('common/traits/00_traits.txt', 1998, 2075),
]:
    text = text_for(rel)
    lines = text.splitlines()
    snippets.append({'File': rel, 'Path': str(vfs[rel]['Path']), 'Mod': vfs[rel]['Mod'],
                     'StartLine': begin, 'Lines': [{'Line': n, 'Text': lines[n-1]} for n in range(begin, min(end, len(lines))+1)]})
write_json('source-excerpts.json', snippets)

# Concrete proposals remain inert report artifacts. No runtime file, manifest,
# launcher entry, Workshop source or save is written by this audit.
minimal_diff, dna_diff = [], []
proposal_checks = []
for rel in sorted({row['Evidence'] for row in history}):
    original = text_for(rel).replace('\r\n', '\n')
    minimal = original
    if rel.endswith('asoiaf_char_dummies.txt'):
        lines = minimal.splitlines(keepends=True)
        for number in (6597, 6606, 6607, 6608):
            assert not lines[number - 1].lstrip().startswith('#')
            lines[number - 1] = '# ' + lines[number - 1]
        minimal = ''.join(lines)
        assert minimal.count('\tdynasty = none') == 1
        minimal = minimal.replace('\tdynasty = none', '\t# dynasty = none # No dynasty: retain lowborn status')
    if rel.endswith('asoiaf_char_stormlands.txt'):
        before = '\t\t\tadd_trait = lifestyle_mystic_3_history'
        after = ('\t\t\tadd_trait = lifestyle_mystic\n'
                 '\t\t\tadd_trait_xp = {\n'
                 '\t\t\t\ttrait = lifestyle_mystic\n'
                 '\t\t\t\tvalue = trait_third_level\n'
                 '\t\t\t}')
        assert minimal.count(before) == 1
        minimal = minimal.replace(before, after)
    fallback = minimal
    for row in dna_rows:
        if row['File'] != rel:
            continue
        pattern = re.compile(r'(?m)^([ \t]*)dna[ \t]*=[ \t]*' + re.escape(row['DNA']) + r'[ \t]*$')
        fallback, count = pattern.subn(lambda m: m[1] + '# dna = ' + row['DNA'] + ' # Undefined template; use generated appearance', fallback)
        assert count == 1, (rel, row['DNA'], count)
    for variant, text in [('minimal', minimal), ('with_dna_fallback', fallback)]:
        level = 0
        for token in re.finditer('[{}]', mask(text)):
            level += 1 if token[0] == '{' else -1
            assert level >= 0, (rel, variant, 'stray closing brace')
        assert level == 0, (rel, variant, 'unclosed block')
        before_defs = {d['Id']: d for d in definitions(original) if d['Id'] != 'effect'}
        after_defs = {d['Id']: d for d in definitions(text)}
        assert before_defs.keys() == after_defs.keys(), (rel, variant, 'character IDs changed')
        # Preserve dates, parent/spouse/death fields, names, skills and traits
        # other than the exact deprecated mystic effect and invalid dynasty.
        fields = r'(?:name|female|father|mother|dynasty_house|add_spouse|remove_spouse|killer|death_reason|birth|death|martial|diplomacy|intrigue|stewardship|learning|prowess)'
        for key, body in before_defs.items():
            before_clean, after_clean = mask(body['Body']), mask(after_defs[key]['Body'])
            for pattern in (r'(?m)^\s*\d+\.\d+\.\d+\s*=\s*\{', r'(?m)^\s*' + fields + r'\s*=[^\r\n]*'):
                assert [s.strip() for s in re.findall(pattern, before_clean)] == [s.strip() for s in re.findall(pattern, after_clean)], (rel, variant, key, 'biography changed')
        if variant == 'with_dna_fallback':
            expected = [r['DNA'] for r in assignments if r['File'] == rel and r['DefinitionCount'] > 0]
            actual = re.findall(r'(?m)^\s*dna\s*=\s*([\w-]+)', mask(text))
            assert actual == expected, (rel, 'valid DNA changed')
        proposal_checks.append({'File': rel, 'Variant': variant, 'BalancedBraces': True,
                                'CharacterIdsAndBiographiesPreserved': True, 'Characters': len(after_defs)})
    minimal_diff.extend(difflib.unified_diff(original.splitlines(True), minimal.splitlines(True), fromfile='a/'+rel, tofile='b/'+rel))
    dna_diff.extend(difflib.unified_diff(minimal.splitlines(True), fallback.splitlines(True), fromfile='a/'+rel, tofile='b/'+rel))
(OUT / 'proposal-01-minimal.patch').write_text(''.join(minimal_diff), encoding='utf-8')
(OUT / 'proposal-02-dna-fallback.patch').write_text(''.join(dna_diff), encoding='utf-8')
write_json('proposal-checks.json', proposal_checks)
assert 'trait_third_level = 100' in text_for('common/script_values/00_trait_values.txt')
assert 'Forrester_1' in indexes['DNA'] and 'Forrester_1' in indexes['Character']
write_json('effective-replace-paths.json', replacements)
write_csv('source-hashes.csv', list(sources.values()))
summary = {
    'ReadOnlyAudit': True, 'RuntimePatchRevisionUnchanged': 6,
    'LogSHA256': hashlib.sha256((LOG / 'snapshot/error.log').read_bytes()).hexdigest().upper(),
    'ActiveMods': len(mods), 'EffectiveTextFiles': len(vfs),
    'DirectHistoryMessages': len(history), 'Classes': dict(Counter(r['Kind'] for r in diagnostics)),
    'MissingDNAByFile': dict(Counter(r['File'] for r in dna_rows)),
    'AllDNAAssignmentsInImplicatedFiles': len(assignments),
    'ValidDNAAssignmentsPreserved': sum(r['DefinitionCount'] > 0 for r in assignments),
    'RelatedPostValidateMessages': sum(row['IssueClass'] == 'Secondary_PostValidate' for row in entries),
    'MinimalProposalDiagnosticTargetsIncludingPostValidate': 6,
    'DNAFallbackProposalAdditionalTargets': 98,
    'ProposalsAppliedToRuntime': False,
    'SeparateCharacterLinkMessages': len(link_entries), 'SeparateCharacterLinkIds': len(links),
    'LinkIdsWithActiveCharacterDefinition': sum(row['ActiveCharacterDefinitions'] > 0 for row in links),
    'LinkIdsWithSameNamedDNA': sum(row['SameNamedDNA'] > 0 for row in links),
    'LinkIdsWithAppearanceDonorSites': sum(row['AppearanceDonorSites'] > 0 for row in links),
    'LinkIdsWithoutAppearanceDonorSites': [r['Character'] for r in links if r['AppearanceDonorSites'] == 0],
    'DefinitionIndexMethod': 'Effective same-path files after descriptor replace_path; root block IDs by brace depth, comments and strings masked. Stray closing brace recovery only for inventory; malformed anchor assessed separately.'
}
write_json('summary.json', summary)
print(json.dumps(summary, ensure_ascii=False, indent=2))
