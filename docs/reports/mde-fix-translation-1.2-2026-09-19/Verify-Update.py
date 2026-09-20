"""Compare effective localization with the audited, committed 1.1 patch."""
import csv
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

REPORT = Path(__file__).resolve().parent
ROOT = REPORT.parents[2]
MOD_REL = Path('AGOT_Submods/AGOT_More_Dragon_Eggs_RUS_CORRECT')
MOD = ROOT / MOD_REL
BEFORE = '6568d4c69370bde7e39ddec8bff4e154fec5eb68'
TRANSLATION = Path('E:/SteamLibrary/steamapps/workshop/content/1158310/3736931686')


def committed(relative):
    return subprocess.check_output(
        ['git', 'show', f'{BEFORE}:{relative.as_posix()}'], cwd=ROOT
    ).decode('utf-8-sig')


def entries(text):
    result = {}
    for line in text.splitlines():
        match = re.match(r'^\s*([^\s#":]+):\s*\d*\s*"(.*)"\s*$', line)
        if match:
            key, value = match.groups()
            assert key not in result, key
            result[key] = value
    return result


def save_csv(name, rows, fields):
    with (REPORT / name).open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


old_manifest = json.loads(committed(MOD_REL / 'docs/source-manifest.json'))
manifest = json.loads((MOD / 'docs/source-manifest.json').read_text(encoding='utf-8-sig'))
old_patch = {}
for output in old_manifest['Outputs']:
    if output['File'].endswith('_l_russian.yml'):
        old_patch.update(entries(committed(MOD_REL / output['File'])))
assert len(old_patch) == 885

# Follow exact-file overrides before localization/replace priority.
external = {}
for source in sorted((TRANSLATION / 'localization').rglob('*_l_russian.yml')):
    shadow = MOD / source.relative_to(TRANSLATION)
    values = entries((shadow if shadow.exists() else source).read_text(encoding='utf-8-sig'))
    assert not external.keys() & values.keys(), source
    external.update(values)
assert len(external) == 1044 and 'nagga_desc' not in external
new_patch = {}
for source in sorted((MOD / 'localization').rglob('*_l_russian.yml'),
                     key=lambda p: ('replace' in p.relative_to(MOD).parts, p.as_posix())):
    new_patch.update(entries(source.read_text(encoding='utf-8-sig')))
effective = external | new_patch
assert old_patch.keys() <= effective.keys()
assert effective['MDE_nagga_desc'] == 'Нагга' and 'nagga_desc' not in effective

old_changes = {entry['Key']: entry for entry in old_manifest['RussianChanges']}
protected = [entry for entry in old_changes.values()
             if entry['Reason'] == 'Reviewed translation / compatibility label'
             or entry['Reason'].startswith('Reviewed probability')
             or entry['Reason'] == 'Reviewed hatching probability template']
assert len(protected) == 193
assert all(effective[entry['Key']] == entry['After'] for entry in protected)

current_changes = {entry['Key']: entry for entry in manifest['RussianChanges']}
changed = []
for key, before in sorted(old_patch.items()):
    if before == effective[key]:
        continue
    reason = old_changes.get(key, {}).get('Reason', 'External RU copied into builtin shadow')
    # Only borrowed upstream text may change; all handwritten and probability
    # corrections above are pinned to the previous output.
    assert reason in {'Preserve external RU over different builtin replace definition',
                      'Reviewed builtin Russian fallback',
                      'External RU copied into builtin shadow', 'MDE-06: gender-neutral wording'}, key
    if reason == 'MDE-06: gender-neutral wording':
        assert key == 'mde_dragon_eggs_events.0013.desc'
        assert current_changes[key]['Reason'] == reason
    changed.append({'Key': key, 'PreviousReason': reason, 'Before': before,
                    'After': effective[key]})
assert len(changed) == 60
save_csv('changed-effective-texts.csv', changed, ['Key', 'PreviousReason', 'Before', 'After'])

removed_overrides = []
old_overlay = entries(committed(MOD_REL / 'localization/replace/russian/zzzz_mde_rus_correct_l_russian.yml'))
new_overlay = entries((MOD / 'localization/replace/russian/zzzz_mde_rus_correct_l_russian.yml').read_text(encoding='utf-8-sig'))
for key in sorted(old_overlay.keys() - new_overlay.keys()):
    assert key in external
    removed_overrides.append({'Key': key, 'SameEffectiveText': old_overlay[key] == effective[key],
                              'Before': old_overlay[key], 'After': effective[key]})
assert len(removed_overrides) == 79
save_csv('removed-redundant-overrides.csv', removed_overrides,
         ['Key', 'SameEffectiveText', 'Before', 'After'])

old_hashes = {entry['File']: entry['SHA256'] for entry in old_manifest['Outputs']}
runtime_changes = []
for entry in manifest['Outputs']:
    data = (MOD / entry['File']).read_bytes()
    assert hashlib.sha256(data).hexdigest().upper() == entry['SHA256'], entry['File']
    assert b'\r' not in data and data.startswith(b'\xef\xbb\xbf'), entry['File']
    if old_hashes.get(entry['File']) != entry['SHA256']:
        runtime_changes.append(entry['File'])
assert len(runtime_changes) == 4
assert all(file.startswith('localization/') for file in runtime_changes)

profile = Path('C:/Users/RUSBAR/Documents/Paradox Interactive/Crusader Kings III')
enabled = json.loads((profile / 'dlc_load.json').read_text(encoding='utf-8-sig'))['enabled_mods']
patch_descriptor = 'mod/AGOT_More_Dragon_Eggs_RUS_CORRECT.mod'
assert enabled.index(patch_descriptor) > max(enabled.index('mod/ugc_3388366564.mod'),
                                           enabled.index('mod/ugc_3736931686.mod'))
descriptor = (profile / patch_descriptor).read_text(encoding='utf-8-sig')
assert f'path="{MOD.as_posix()}"' in descriptor
active_roots = []
for name in enabled:
    text = (profile / name).read_text(encoding='utf-8-sig')
    match = re.search(r'(?m)^\s*path\s*=\s*"([^"]+)"', text)
    assert match, name
    path = Path(match[1])
    active_roots.append((path if path.is_absolute() else profile / path).resolve())
for entry in manifest['Outputs']:
    if entry['File'] == 'descriptor.mod':
        continue
    providers = [path for path in active_roots if (path / entry['File']).is_file()]
    assert providers and providers[-1] == MOD.resolve(), entry['File']

summary = {
    'ComparedWithCommit': BEFORE, 'TranslationVersion': manifest['TranslationVersion'],
    'SourcePins': manifest['SourceHashesChecked'], 'RuntimeOutputs': len(manifest['Outputs']),
    'ChangedRuntimeFiles': runtime_changes, 'OtherPreviousRuntimeFilesByteIdentical': 16,
    'PreviousRussianPatchKeysStillAvailable': len(old_patch), 'CurrentRussianPatchKeys': len(new_patch),
    'HandwrittenAndProbabilityCorrectionsUnchanged': len(protected),
    'EffectiveTextsUpdatedFromTranslation': len(changed),
    'UpdatedTextOrigins': dict(Counter(entry['PreviousReason'] for entry in changed)),
    'RedundantOverlayEntriesRemoved': len(removed_overrides),
    'RemovedOverlayEntriesWithIdenticalEffectiveText': sum(entry['SameEffectiveText'] for entry in removed_overrides),
    'CommentedDuplicateDefinitions': 140, 'CommentedConflictingNaggaDefinition': 1,
    'ExternalRussianDuplicatesAfterOverrides': 0, 'GameProfileUsesCurrentRepository': True,
    'RuntimePathsWithPatchAsLastProvider': 19,
    'GameLaunchedAfterUpdate': False,
}
(REPORT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
print(json.dumps(summary, ensure_ascii=True))
