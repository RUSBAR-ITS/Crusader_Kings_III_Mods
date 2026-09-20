"""Capture exited-game logs and exact runtime identity; report files only."""
import csv
import datetime as dt
import importlib.util
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PATCH = REPO / 'AGOT_Submods/AGOT_PLUS_FIX'
spec = importlib.util.spec_from_file_location('dna9', PATCH / 'tools/DNA-Stage9.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
SNAPSHOT = HERE / 'snapshot'
assert not (HERE / 'snapshot-summary.json').exists(), 'Do not overwrite completed historical evidence'
SNAPSHOT.mkdir(exist_ok=True)
SOURCE_COPIES = []


def copy(source, target):
    before = d.sha(source)
    raw = d.native(source).read_bytes()
    normalized = raw.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
    if target.exists():
        assert target.read_bytes() == normalized, ('Partial snapshot differs; do not overwrite', target)
    else:
        target.write_bytes(normalized)
    assert before == d.sha(source), ('File changed during capture', source)
    SOURCE_COPIES.append(dict(Source=str(source), Snapshot=target.name,
                              SourceSHA256=before, SnapshotSHA256=d.sha(target)))
    return d.sha(target)


def stamp(path):
    return dt.datetime.fromtimestamp(d.native(path).stat().st_mtime).astimezone().isoformat()


def export(name, rows):
    with (HERE / name).open('w', encoding='utf-8-sig', newline='') as out:
        writer = csv.DictWriter(out, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)


logs = []
for name in ('error.log', 'game.log', 'system.log', 'debug.log', 'database_conflicts.log', 'code_revisions.log'):
    source = d.PROFILE / 'logs' / name
    logs.append(dict(File=name, Length=d.native(source).stat().st_size,
                     LastWriteTime=stamp(source), SHA256=copy(source, SNAPSHOT / name)))
assert 'Quit: Quit from inside game' in d.read(SNAPSHOT / 'debug.log')
copy(d.PROFILE / 'dlc_load.json', SNAPSHOT / 'dlc_load.json')
mods = []
for i, descriptor in enumerate(d.load(SNAPSHOT / 'dlc_load.json')['enabled_mods'], 1):
    text = d.read(d.PROFILE / descriptor)
    name = re.search(r'^\s*name="([^"]+)"', text, re.M)[1]
    path = re.search(r'^\s*path="([^"]+)"', text, re.M)[1]
    assert d.native(path).is_dir()
    mods.append(dict(Order=i, Name=name, Path=path, Descriptor=descriptor, Exists=True))
export('active-mods.csv', mods)
runtime, manifests = [], {}
for name, prefix in (('AGOT_PLUS_FIX', 'patch'), ('AGOT_PLUS_RUS_CORRECT', 'localization'),
                     ('AGOT_More_Dragon_Eggs_RUS_CORRECT', 'mde')):
    root = REPO / 'AGOT_Submods' / name
    manifest = d.load(root / 'docs/source-manifest.json')
    manifests[prefix] = copy(root / 'docs/source-manifest.json', SNAPSHOT / (prefix+'-source-manifest.json'))
    files = ([(r['File'], r['SHA256']) for r in manifest['Outputs']] if prefix == 'mde' else
             [(r['File'], r['PatchedSHA256']) for r in manifest['Files']])
    if prefix == 'localization':
        files += [(manifest['Overlay'], manifest['OverlaySHA256']),
                  (manifest['RuntimeNames']['File'], manifest['RuntimeNames']['SHA256'])]
    for rel, digest in files:
        path = root / rel
        assert d.sha(path) == digest, ('Runtime differs', path)
        providers = [Path(m['Path']) for m in mods if d.native(Path(m['Path']) / rel).is_file()]
        if rel != 'descriptor.mod':  # Per-mod metadata is not an overlay resource.
            assert providers[-1].resolve() == root.resolve(), ('Later file provider', rel)
        runtime.append(dict(Mod=name, File=rel, LastWriteTime=stamp(path), SHA256=digest,
                            AbsolutePathLength=len(str(path))))
export('runtime-files.csv', runtime)
files = ['source-baseline.json']
for stage in (9, 10, 11, 12, 13):
    files += [f'stage{stage}-plan.json', f'stage{stage}-validation.json']
files += ['stage9-targeted-log-messages.csv', 'stage9-deferred-log-messages.csv',
          'stage10-targeted-log-messages.csv', 'stage12-decisions.json']
for name in files: copy(PATCH / 'docs' / name, SNAPSHOT / name)
import json
summary = dict(CapturedAt=dt.datetime.now().astimezone().isoformat(), ActiveMods=len(mods), Logs=logs,
               PatchManifestSHA256=manifests['patch'], LocalizationManifestSHA256=manifests['localization'],
               MDEManifestSHA256=manifests['mde'],
               RuntimeFiles=len(runtime), RuntimeMatchesManifest=True, LastDeclaredProvidersMatch=True,
               EngineIndividualResourceLoadingProven=False, Copies=SOURCE_COPIES, SnapshotNewlines="LF")
(HERE / 'snapshot-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
print(json.dumps(summary, ensure_ascii=False, indent=2))
