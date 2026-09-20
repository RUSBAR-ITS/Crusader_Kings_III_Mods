"""Audit the approved COW/crown delta without overwriting historical evidence."""
from pathlib import Path
import difflib
import hashlib
import importlib.util
import json
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PLUS = REPO / 'AGOT_Submods/AGOT_PLUS_FIX'
USF = REPO / 'AGOT_Submods/AGOT_SUBMODS_FIX'
sys.path.insert(0, str(USF / 'tools'))
from CrownWithoutCreator import CROWN_SOURCE, PLUS_CROWNS, LOTD_CROWNS, function_names
from ScriptBlocks import parse, walk

spec = importlib.util.spec_from_file_location('applied_load_order', PLUS / 'tools/DNA-Stage9.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return path.read_text(encoding='utf-8-sig')


def save(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n',
                             encoding='utf-8', newline='\n')


def unified(before, after, old_name, new_name):
    for line in difflib.unified_diff(before, after, fromfile=old_name, tofile=new_name):
        yield line if line.endswith('\n') else line+'\n\\ No newline at end of file\n'


def main():
    mods = d.active_mods()
    effective = {**d.effective('common', mods), **d.effective('events', mods)}
    plus_names = function_names(PLUS_CROWNS, 'apf')
    lotd_names = function_names(LOTD_CROWNS, 'usf')
    original = set(plus_names) | set(lotd_names)
    helpers = set(plus_names.values()) | set(lotd_names.values())
    targets = original | helpers
    by_path = {str(p).casefold(): (rel, m, p) for rel, (m, p) in effective.items()}
    search = subprocess.run(['rg', '-l', '--hidden', '-g', '*.txt', '-e',
                             '|'.join(sorted(targets))] + [m['Path'] for m in mods],
                            capture_output=True, check=True)
    calls, definitions = [], []
    for match in search.stdout.decode('utf-8').splitlines():
        candidate = by_path.get(str(Path(match)).casefold())
        if not candidate:
            continue
        rel, mod, path = candidate
        text = read(path)
        for top in parse(text):
            for node in walk([top]):
                if node.key not in targets:
                    continue
                row = dict(path=str(path), relative=rel, function=node.key,
                           line=text.count('\n', 0, node.start)+1)
                if node is top:
                    definitions.append(row)
                else:
                    row['arguments'] = [n.key for n in node.value]
                    calls.append(row)
    old_calls = [r for r in calls if r['function'] in original]
    new_calls = [r for r in calls if r['function'] in helpers]
    assert len(old_calls) == 40 and len(new_calls) == 12
    assert all(set(r['arguments']) == {'OWNER', 'CREATOR'} for r in old_calls)
    assert all(r['arguments'] == ['OWNER'] for r in new_calls)
    assert {r['function'] for r in definitions} == targets
    assert len(definitions) == 20
    assert all(Path(r['path']) == d.AGOT / CROWN_SOURCE
               for r in definitions if r['function'] in original)
    historical = load(HERE / 'all-effective-crown-calls.json')
    key = lambda r: (r['path'], r['function'], tuple(r['arguments']))
    assert sorted(map(key, old_calls)) == sorted(key(r) for r in historical if not r['missing_creator'])

    before = load(USF / 'docs/stage2-before-manifest.json')
    after = load(USF / 'docs/source-manifest.json')
    changed = [rel for rel in before if before[rel]['sha256'] != after[rel]['sha256']]
    added = sorted(set(after) - set(before))
    assert set(before) <= set(after)
    assert set(changed) == {'common/on_action/cowagot_province_on_actions.txt',
                            'common/buildings/yy_agotcities_special_buildings_westeros.txt',
                            'events/decisions_events/rediscover_events.txt'}
    assert added == ['common/scripted_effects/usf_crowns_without_creator_effects.txt']
    assert len(before) == 26 and len(after) == 27
    for rel, row in after.items():
        assert sha(USF / rel) == row['sha256']
    rediscovery = 'events/decisions_events/rediscover_events.txt'
    restored = read(USF / rediscovery)
    for old, new in lotd_names.items():
        assert restored.count(new) == 1
        restored = restored.replace(new, old)
    assert restored == read(USF / 'docs/stage2-before' / rediscovery)

    evidence = load(HERE / 'source-evidence.json')
    external = {p: r for p, r in evidence.items() if not Path(p).is_relative_to(REPO)}
    for path, row in external.items():
        assert sha(Path(path)) == row['SHA256']
    stage15 = load(PLUS / 'docs/stage15-validation.json')
    assert stage15['Status'] == 'PASS' and stage15['Calls'] == 7
    usf_test = load(USF / 'docs/validation.json')
    suite_path = HERE / 'full-suite-console.txt'
    suite = read(suite_path)
    assert 'Static checks passed. CK3 execution was not performed;' in suite
    assert sha(PLUS / 'docs/source-manifest.json').upper() in suite
    assert 'Traceback' not in suite and 'AssertionError' not in suite

    diffs = []
    pairs = [(USF / 'docs/stage2-before' / rel, USF / rel) for rel in changed]
    pairs += [(PLUS / 'docs/stage15-before-title-on-actions.txt',
               PLUS / 'common/on_action/agot_on_actions/test_title_on_actions.txt')]
    for previous, current in pairs:
        diffs.extend(unified(read(previous).splitlines(True), read(current).splitlines(True),
                             previous.relative_to(REPO).as_posix(), current.relative_to(REPO).as_posix()))
    for current in [USF / added[0], PLUS / 'common/scripted_effects/apf_crowns_without_creator_effects.txt']:
        raw = current.read_bytes()
        assert raw.startswith(b'\xef\xbb\xbf') and b'\r' not in raw
        diffs.extend(unified([], read(current).splitlines(True), '/dev/null', current.relative_to(REPO).as_posix()))
    (HERE / 'remaining-applied.patch').write_text(''.join(diffs), encoding='utf-8', newline='\n')
    save('applied-effective-crown-calls.json', calls)
    save('applied-effective-crown-definitions.json', definitions)
    save('application-validation.json', dict(
        Status='PASS', Date='2026-09-20', FreshGameLogChecked=False,
        AGOTPlus=stage15,
        AGOTPlusFullSuite=dict(Status='PASS', Console=suite_path.name, ConsoleSHA256=sha(suite_path),
                              RuntimeManifestSHA256=sha(PLUS / 'docs/source-manifest.json')),
        UnifiedPatch=dict(RuntimeFiles=27, ChangedExistingFiles=changed, NewFiles=added,
                          UnchangedRuntimeFiles=23, StaticValidation=usf_test),
        EffectiveCrownCalls=dict(OriginalCompleteCallsPreserved=40, HelpersWithOwnerOnly=12,
                                MissingArguments=0, UniqueOriginalDefinitions=8, UniqueNewDefinitions=12),
        ExternalResearchSourcesUnchanged=len(external),
        ExpectedResolvedMessages=dict(CREATOR=8, HarlawMines=2, RhoynishOpinion=2, MissingEvent5000=6, Total=18),
        Event5000PreviousApplication='cow-5000-application.json',
        DeltaPatch='remaining-applied.patch',
        Limitations='Static source/structure/provider checks; no CK3 event execution or fresh log verification.'))
    print('PASS: 40 complete original calls preserved, 12 OWNER-only helper calls, 20 unique definitions.')
    print('PASS: USF 3 changed + 1 added / 23 unchanged; LOTD event is otherwise text-identical; external sources unchanged.')


if __name__ == '__main__':
    main()
