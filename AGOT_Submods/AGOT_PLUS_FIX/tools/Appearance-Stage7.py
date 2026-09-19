"""Register/check reviewed appearance repairs. Never writes Workshop or profile files."""
import argparse
import bisect
import csv
import hashlib
import json
import re
from collections import defaultdict, Counter
from functools import lru_cache
from pathlib import Path

MOD = Path(__file__).resolve().parents[1]
DOC = MOD / 'docs'
REPO = MOD.parents[1]
REPORT = REPO / 'docs/reports/agot-plus-character-history-analysis-2026-09-19'
PROFILE = Path('C:/Users/RUSBAR/Documents/Paradox Interactive/Crusader Kings III')
GAME = Path('E:/SteamLibrary/steamapps/common/Crusader Kings III/game')
parser = argparse.ArgumentParser()
parser.add_argument('mode', choices=['register', 'check'])
parser.add_argument('--plus', default='E:/SteamLibrary/steamapps/workshop/content/1158310/2950245430')
parser.add_argument('--agot', default='E:/SteamLibrary/steamapps/workshop/content/1158310/2962333032')
args = parser.parse_args()
PLUS, AGOT = Path(args.plus), Path(args.agot)
CHILDREN = 'common/scripted_effects/asoiaf_canon_children_effects.txt'
DONORS = 'history/characters/agot_plus_fix_appearance_donors.txt'


def read(p):
    return Path(p).read_bytes().decode('utf-8-sig')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest().upper()


def load(p):
    return json.loads(read(p))


def save(p, value):
    Path(p).write_text(json.dumps(value, ensure_ascii=False, indent=4) + '\n', encoding='utf-8', newline='\n')


def csv_rows(p):
    with Path(p).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def mask(text):
    return re.sub(r'"(?:\\.|[^"\\])*"|#[^\r\n]*',
                  lambda m: re.sub(r'[^\r\n]', ' ', m[0]), text)


@lru_cache(maxsize=128)
def blocks(text):
    clean = mask(text)
    stack, pairs, depths = [], {}, {}
    for m in re.finditer('[{}]', clean):
        if m[0] == '{':
            depths[m.start()] = len(stack)
            stack.append(m.start())
        elif stack:
            pairs[stack.pop()] = m.end()
    lines = [m.start() for m in re.finditer('\n', text)]
    out = []
    for m in re.finditer(r'(?m)^[ \t]*([\w.]+)\s*=\s*\{', clean):
        opening = clean.index('{', m.start(), m.end())
        end = pairs.get(opening, len(text))
        out.append({'Id': m[1], 'Start': m.start(), 'End': end, 'Depth': depths[opening],
                    'Line': bisect.bisect_left(lines, m.start()) + 1, 'Body': text[m.start():end]})
    return tuple(out)


def field(text, key):
    clean = re.sub(r'#[^\r\n]*', '', text)
    m = re.search(r'(?m)^\s*' + re.escape(key) + r'\s*=\s*("[^"]*"|[^\s{}]+)', clean)
    return m[1].strip('"') if m else ''


def sex(text):
    return 'female' if field(text, 'female') == 'yes' else 'male'


def index_sources():
    active = load(PROFILE / 'dlc_load.json')['enabled_mods']
    vfs = {}
    for descriptor in [None] + active:
        if descriptor is None:
            root = GAME
        else:
            desc = read(PROFILE / descriptor)
            root = Path(re.search(r'(?m)^\s*path\s*=\s*"([^"]+)"', desc)[1])
            for prefix in re.findall(r'(?m)^\s*replace_path\s*=\s*"([^"]+)"', desc):
                vfs = {k: v for k, v in vfs.items() if not k.startswith(prefix.rstrip('/') + '/')}
        for category in ('history/characters', 'common/dna_data'):
            for p in (root / category).rglob('*.txt'):
                vfs[p.relative_to(root).as_posix()] = p
    indexes = {'Character': defaultdict(list), 'DNA': defaultdict(list)}
    for relative, path in sorted(vfs.items()):
        category = 'DNA' if relative.startswith('common/') else 'Character'
        for d in blocks(read(path)):
            if d['Depth'] == 0:
                indexes[category][d['Id']].append({**d, 'Path': path, 'File': relative})
    return active, indexes


active, indexes = index_sources()


def one(category, key):
    found = indexes[category].get(key, [])
    assert len(found) == 1, (category, key, len(found))
    return found[0]


def assert_native(row):
    """Verify fixed preset, identity, sex, and the current effective provider."""
    effective = one('Character', row['NativeId'])
    source = AGOT / effective['File']
    candidates = [b for b in blocks(read(source)) if b['Depth'] == 0 and b['Id'] == row['NativeId']]
    assert len(candidates) == 1, row['NativeId']
    native = {**candidates[0], 'Path': source, 'File': effective['File']}
    for character in (native, effective):
        assert field(character['Body'], 'name') == row['Name']
        assert sex(character['Body']) == row['Sex']
        assert field(character['Body'], 'dna') == row['DNA']
    if args.mode == 'register':
        row['EffectiveHistoryPath'] = str(effective['Path'])
        row['EffectiveHistorySHA256'] = sha(effective['Path'])
    else:
        assert str(effective['Path']) == row['EffectiveHistoryPath']
        assert sha(effective['Path']) == row['EffectiveHistorySHA256']
    dna = one('DNA', row['DNA'])
    assert dna['Path'].is_relative_to(AGOT), (row['DNA'], str(dna['Path']))
    return native, dna


if args.mode == 'register':
    fixes = load(DOC / 'fixes.json')
    additions = load(DOC / 'additions.json')
    baseline = load(DOC / 'source-baseline.json')
    old_manifest = load(DOC / 'source-manifest.json')
    assert old_manifest['Revision'] == 6 and len(fixes) == 103
    assert not any(r['Group'] in ('F21', 'F22', 'F23') for r in fixes)
    for row in baseline:
        assert sha((PLUS if row['Catalog'] == 'AGOT_PLUS' else AGOT) / row['File']) == row['SHA256']
    for row in old_manifest['Files']:
        assert sha(MOD / row['File']) == row['PatchedSHA256']
    new, deps = [], set()

    def dependency(path):
        for catalog, root in [('AGOT_PLUS', PLUS), ('AGOT', AGOT)]:
            if path.is_relative_to(root):
                deps.add((catalog, path.relative_to(root).as_posix()))
                return
        raise AssertionError(path)

    def repair(key, group, file, before, after, reason):
        assert before != after and read(PLUS / file).count(before) == 1, key
        new.append({'Id': key, 'Group': group, 'File': file, 'Before': before,
                    'After': after, 'ExpectedCount': 1, 'Reason': reason})
        dependency(PLUS / file)

    missing = csv_rows(REPORT / 'missing-dna.csv')
    history_actions = []
    for row in missing:
        cid = row['Character']
        assert not indexes['DNA'].get(row['DNA'])
        char = one('Character', cid)
        assert field(char['Body'], 'dna') == row['DNA']
        text = read(PLUS / row['File'])
        m = re.search(r'(?m)^[ \t]*dna = ' + re.escape(row['DNA']) + r'\r?$', text)
        assert m
        before = m[0]
        prefix = re.match(r'[ \t]*', before)[0]
        after = prefix + '# ' + before.strip() + ' # AGOT_PLUS_FIX: unavailable AGOT+ DNA.'
        action = 'CommentUnavailableDNA'
        if cid == 'Forrester_asoiaf_1':
            native = one('Character', 'Forrester_1')
            dna = one('DNA', 'Forrester_1')
            assert field(native['Body'], 'name') == row['Name'] == 'Thorren'
            assert field(native['Body'], 'dna') == 'Forrester_1'
            dependency(native['Path']); dependency(dna['Path'])
            after += '\r\n' + prefix + 'dna = Forrester_1 # AGOT_PLUS_FIX: same character, base AGOT appearance.'
            action = 'UseBaseAGOTDNA'
        # The match includes CR on CRLF input; restore one original line ending.
        after += '\r' if before.endswith('\r') else ''
        repair('appearance-history-' + cid, 'F22' if action == 'UseBaseAGOTDNA' else 'F21',
               row['File'], before, after, 'Keep the character and biography; ' + action)
        history_actions.append({**row, 'Action': action})

    children = read(PLUS / CHILDREN)
    creations = [b for b in blocks(children) if b['Id'] == 'create_character']
    donor_rows = csv_rows(REPORT / 'missing-appearance-donors.csv')
    actions, extra_donors = [], []
    for item in donor_rows:
        cid = item['Character']
        assert not indexes['Character'].get(cid)
        m = re.search(r'(?m)^([ \t]*)copy_inheritable_appearance_from = character:' + re.escape(cid) + r'\r?$', children)
        assert m, cid
        creation = [b for b in creations if b['Start'] <= m.start() < b['End']]
        assert len(creation) == 1, cid
        birth = creation[0]['Body']
        native_id = cid.replace('_asoiaf_', '_')
        assert 'asoiaf_' + native_id + '_modifier' in birth, cid
        row = {'MissingDonor': cid, 'NativeId': native_id, 'Name': field(birth, 'name'),
               'Sex': field(birth, 'gender'), 'Function': item['BirthEffect'],
               'AuthorLabel': item['AuthorLabel'], 'Action': 'CommentUnavailableDonor', 'Reason': ''}
        candidates = indexes['Character'].get(native_id, [])
        if len(candidates) != 1:
            row['Reason'] = 'No unique native historical character'
        else:
            native = candidates[0]
            dna_id = field(native['Body'], 'dna')
            row['NativeName'] = field(native['Body'], 'name')
            row['NativeSex'] = sex(native['Body'])
            if row['NativeName'] != row['Name'] or row['NativeSex'] != row['Sex']:
                row['Reason'] = 'Name or sex differs; do not guess identity or change biography'
            elif not dna_id or len(indexes['DNA'].get(dna_id, [])) != 1:
                row['Reason'] = 'Native character has no uniquely resolved fixed DNA'
            else:
                row['DNA'] = dna_id
                native, dna = assert_native(row)
                dependency(native['Path']); dependency(dna['Path'])
                row['HistoryFile'], row['HistoryLine'] = native['File'], native['Line']
                row['DNAFile'], row['DNALine'] = dna['File'], dna['Line']
                donor_id = 'Dummy_' + native_id
                donors = indexes['Character'].get(donor_id, [])
                if len(donors) == 1:
                    donor = donors[0]
                    assert field(donor['Body'], 'dna') == dna_id
                    assert field(donor['Body'], 'name') == row['Name'] and sex(donor['Body']) == row['Sex']
                    dependency(donor['Path'])
                    row['Action'] = 'UseBaseAGOTDonor'
                else:
                    assert not donors
                    donor_id = 'agot_plus_fix_donor_' + native_id
                    assert not indexes['Character'].get(donor_id)
                    model = one('Character', 'Dummy_Stark_87')
                    dependency(model['Path'])
                    body = model['Body'].replace('Dummy_Stark_87', donor_id)
                    body = body.replace('name = Bennard', 'name = ' + row['Name'])
                    body = body.replace('dna = Stark_87', 'dna = ' + dna_id)
                    if row['Sex'] == 'female':
                        body = body.replace('name = ' + row['Name'], 'name = ' + row['Name'] + '\r\n\tfemale = yes')
                    extra_donors.append(body)
                    row['Action'] = 'UseBaseDNAWithDedicatedDonor'
                row['Donor'] = donor_id
                row['Reason'] = 'Same native identity, exact name and sex, existing fixed DNA; base AGOT fallback'
        before = m[0]
        indent = m[1]
        comment = indent + '# ' + before.strip() + ' # AGOT_PLUS_FIX: unavailable AGOT+ donor.'
        if row['Action'] == 'CommentUnavailableDonor':
            flag = indent + 'add_character_flag = has_scripted_appearance'
            before += '\n' + flag
            assert children.count(before) == 1
            after = comment + '\r\n' + indent + '# add_character_flag = has_scripted_appearance # No fixed appearance assigned.'
            row['DNA'] = ''
        else:
            after = comment + '\r\n' + indent + 'copy_inheritable_appearance_from = character:' + row['Donor']
            after += '\r' if before.endswith('\r') else ''
        repair('appearance-birth-' + cid, 'F21' if row['Action'] == 'CommentUnavailableDonor' else 'F22',
               CHILDREN, before, after, row['Reason'])
        actions.append(row)
    assert Counter(r['Action'] for r in actions) == {
        'UseBaseAGOTDonor': 57, 'UseBaseDNAWithDedicatedDonor': 4, 'CommentUnavailableDonor': 19}
    assert len(missing) == 98
    addition = {'File': DONORS, 'Text': '# AGOT_PLUS_FIX: four dead appearance donors using existing base AGOT DNA.\r\n'
                '# Lifecycle follows Dummy_Stark_87; no family, titles or events are added.\r\n\r\n' + '\r\n\r\n'.join(extra_donors) + '\r\n',
                'UTF8BOM': True, 'Group': 'F22',
                'Reason': 'Fixed base DNA for Sara Snow, Baelon son of Aegon IV, Catelyn and Lysa Strong; independent of campaign birth dates.'}

    dummy = 'history/characters/asoiaf_char_dummies.txt'
    source = read(PLUS / dummy)
    start = source.index('# Dummy_asoiaf_1 = {')
    end = source.index('# }', start) + 3
    before = source[start:end]
    after = before
    for line in ['\ttrait = agot_dummy_trait', '\t\tbirth = yes',
                 '\t\teffect = { make_unprunable = yes }', '\t}']:
        assert ('\r\n' + line + '\r\n') in after
        after = after.replace('\r\n' + line + '\r\n', '\r\n# ' + line + '\r\n')
    repair('history-finish-disabled-anchor', 'F23', dummy, before, after,
           'Finish commenting the already disabled anchor; eliminate stray active birth/effect/closing brace.')
    before = 'asoiaf_Blackfyre_16_mother = {\r\n\tname = Melara\r\n\tdynasty = none'
    repair('history-melara-lowborn', 'F23', dummy, before,
           before.replace('\tdynasty = none', '\t# dynasty = none # No dynasty: retain lowborn status'),
           'none is not a dynasty ID; leave the existing lowborn character and biography intact.')
    mystic = '\t\t\tadd_trait = lifestyle_mystic_3_history'
    repair('history-melisandre-mystic', 'F23', 'history/characters/asoiaf_char_stormlands.txt', mystic,
           '\t\t\tadd_trait = lifestyle_mystic\r\n\t\t\tadd_trait_xp = {\r\n\t\t\t\ttrait = lifestyle_mystic\r\n\t\t\t\tvalue = trait_third_level\r\n\t\t\t}',
           'Use the same modern mystic trait and third-level XP as the native Melisandre history.')
    for rel in ['history/characters/00_agot_char_stormlands.txt', 'common/traits/00_traits.txt',
                'common/scripted_effects/00_agot_canon_children_effects.txt']:
        dependency(AGOT / rel)
    xp_files = [p for p in (AGOT / 'common/script_values').rglob('*.txt')
                if re.search(r'(?m)^trait_third_level\s*=', read(p))]
    if not xp_files:
        xp_files = [p for p in (GAME / 'common/script_values').rglob('*.txt')
                    if re.search(r'(?m)^trait_third_level\s*=', read(p))]
    assert len(xp_files) == 1
    # The native engine value is checked separately when supplied by the base game.
    xp = {'Path': str(xp_files[0]), 'SHA256': sha(xp_files[0])}
    if xp_files[0].is_relative_to(AGOT): dependency(xp_files[0])
    combined = fixes + new
    for file in {r['File'] for r in combined}:
        original = read(PLUS / file); current = original
        for r in [r for r in combined if r['File'] == file]:
            assert original.count(r['Before']) == current.count(r['Before']) == r['ExpectedCount'], r['Id']
            current = current.replace(r['Before'], r['After'])
    assert len(new) == 181
    for catalog, file in sorted(deps):
        if not any(r['Catalog'] == catalog and r['File'] == file for r in baseline):
            baseline.append({'Catalog': catalog, 'File': file, 'SHA256': sha((PLUS if catalog == 'AGOT_PLUS' else AGOT) / file)})
    save(DOC / 'stage7-before-manifest.json', old_manifest)
    save(DOC / 'stage7-appearance-plan.json', {'ActiveMods': active, 'History': history_actions,
         'Births': actions, 'MysticValueSource': xp, 'NewRules': 181, 'RuntimeRevision': 7})
    save(DOC / 'fixes.json', combined)
    save(DOC / 'additions.json', additions + [addition])
    save(DOC / 'source-baseline.json', baseline)
    print('Registered: 97 unavailable DNA comments, Thorren base DNA, 61 birth restorations, 19 birth fallbacks, 3 history repairs.')
else:
    plan = load(DOC / 'stage7-appearance-plan.json')
    assert active == plan['ActiveMods'], 'Active mods changed; review appearance providers'
    xp = plan['MysticValueSource']
    assert sha(xp['Path']) == xp['SHA256']
    assert re.search(r'(?m)^trait_third_level\s*=\s*100\b', read(xp['Path']))
    dummy_code = re.sub(r'#[^\r\n]*', '', read(MOD / 'history/characters/asoiaf_char_dummies.txt'))
    assert not re.search(r'(?m)^\s*dynasty\s*=\s*none\b', dummy_code)
    assert not indexes['Character'].get('Dummy_asoiaf_1')
    melisandre = one('Character', 'asoiaf_Melisandre_1')['Body']
    assert 'lifestyle_mystic_3_history' not in melisandre
    assert re.search(r'add_trait = lifestyle_mystic\s+add_trait_xp\s*=\s*\{\s*trait = lifestyle_mystic\s+value = trait_third_level\s*\}', melisandre)
    assert len([b for b in blocks(read(MOD / DONORS)) if b['Depth'] == 0]) == 4
    children = read(MOD / CHILDREN)
    funcs = {b['Id']: b for b in blocks(children) if b['Depth'] == 0}
    for row in plan['History']:
        char = one('Character', row['Character'])
        expected = 'Forrester_1' if row['Action'] == 'UseBaseAGOTDNA' else ''
        assert field(char['Body'], 'dna') == expected
        assert not indexes['DNA'].get(row['DNA']), 'Missing DNA was added upstream; review fallback'
    for row in plan['Births']:
        assert not indexes['Character'].get(row['MissingDonor']), 'Original donor reappeared; review fallback'
        func = funcs[row['Function']]['Body']
        creates = [b for b in blocks(func) if b['Id'] == 'create_character']
        birth = [b['Body'] for b in creates if row['MissingDonor'] in b['Body']]
        assert len(birth) == 1
        birth = birth[0]
        assert field(birth, 'name') == row['Name'] and field(birth, 'gender') == row['Sex']
        code = re.sub(r'#[^\r\n]*', '', birth)
        assert row['MissingDonor'] not in code
        if row['Action'] == 'CommentUnavailableDonor':
            assert not re.search(r'\bcopy_inheritable_appearance_from\s*=|\badd_character_flag\s*=\s*has_scripted_appearance', code)
        else:
            native, dna = assert_native(row)
            donor = one('Character', row['Donor'])
            assert field(donor['Body'], 'name') == row['Name'] and sex(donor['Body']) == row['Sex']
            assert field(donor['Body'], 'dna') == row['DNA']
            assert '118.1.1 = { birth = yes }' in donor['Body'] and '118.1.2 = { death = yes }' in donor['Body']
            assert 'copy_inheritable_appearance_from = character:' + row['Donor'] in code
            assert 'add_character_flag = has_scripted_appearance' in code
    # Check all active DNA in the three shadow files, and preserve every biography
    # except the explicitly migrated mystic trait/XP and invalid dynasty token.
    biographies = valid_dna = 0
    for file in {r['File'] for r in plan['History']}:
        before = {b['Id']: b for b in blocks(read(PLUS / file)) if b['Depth'] == 0}
        after = {b['Id']: b for b in blocks(read(MOD / file)) if b['Depth'] == 0}
        if file == 'history/characters/asoiaf_char_dummies.txt':
            # F23 removes this orphaned effect outside the commented character.
            # It is the known malformed block, not a character biography.
            orphan = before.pop('effect')
            assert re.sub(r'\s+', '', orphan['Body']) == 'effect={make_unprunable=yes}'
        assert set(before) == set(after), (file, sorted(set(before) - set(after)), sorted(set(after) - set(before)))
        for cid, current in after.items():
            original = before[cid]['Body']
            def biography(t):
                t = re.sub(r'#[^\r\n]*', '', t)
                t = re.sub(r'(?m)^\s*dna\s*=\s*\w+\s*$', '', t)
                t = t.replace('dynasty = none', '')
                t = t.replace('add_trait = lifestyle_mystic_3_history', '')
                t = re.sub(r'add_trait = lifestyle_mystic\s+add_trait_xp\s*=\s*\{\s*trait = lifestyle_mystic\s*value = trait_third_level\s*\}', '', t)
                return re.sub(r'\s+', '', t)
            assert biography(original) == biography(current['Body']), cid
            old_dna, new_dna = field(original, 'dna'), field(current['Body'], 'dna')
            if old_dna and indexes['DNA'].get(old_dna):
                assert new_dna == old_dna; valid_dna += 1
            if new_dna: one('DNA', new_dna)
            biographies += 1
    assert biographies == 406 and valid_dna == 302
    # Birth logic remains identical in LF form after restoring only this
    # stage's appearance edits. Raw source hashes are checked separately.
    rules = load(DOC / 'fixes.json')
    before = read(PLUS / CHILDREN)
    for r in [r for r in rules if r['File'] == CHILDREN and r['Group'] not in ('F21', 'F22', 'F23')]:
        before = before.replace(r['Before'], r['After'])
    restored = children
    for r in reversed([r for r in rules if r['File'] == CHILDREN and r['Group'] in ('F21', 'F22')]):
        old = r['Before'].replace('\r\n', '\n').replace('\r', '\n')
        new = r['After'].replace('\r\n', '\n').replace('\r', '\n')
        assert restored.count(new) == 1
        restored = restored.replace(new, old)
    assert restored == before.replace('\r\n', '\n').replace('\r', '\n')
    save(DOC / 'stage7-validation.json', {'Revision': 7, 'Status': 'PASS',
         'GameExecutionChecked': False, 'FreshLogChecked': False, 'HistoryDNACommented': 97,
         'ThorrenBaseDNARestored': 1, 'BirthAppearancesRestored': 61, 'ExistingNativeDonors': 57,
         'NewFixedDNADonors': 4, 'BirthCopyAndFlagCommented': 19, 'BiographiesPreserved': biographies,
         'PreviouslyValidDNAPreserved': valid_dna, 'BirthLogicPreserved': True,
         'ManifestSHA256': sha(DOC / 'source-manifest.json')})
    print('PASS: 62 base AGOT appearance restorations; 116 unavailable references commented; 406 biographies and 302 valid DNA preserved.')
