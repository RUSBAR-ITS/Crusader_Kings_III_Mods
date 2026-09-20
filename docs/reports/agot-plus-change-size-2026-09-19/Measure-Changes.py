"""Measure the revision-14 overlay against installed AGOT+; no game-file writes."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ORIGINAL = Path('E:/SteamLibrary/steamapps/workshop/content/1158310/2950245430')
FIX = REPO / 'AGOT_Submods/AGOT_PLUS_FIX'
TEXT = {'.txt', '.asset', '.yml', '.gui', '.shader'}


def read(path):
    return path.read_text(encoding='utf-8-sig')


def load(path):
    return json.loads(read(path))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def category(relative):
    if relative.startswith(('common/dna_data/', 'common/bookmark_portraits/')):
        return 'DNA and bookmark portraits'
    if relative.startswith('localization/'):
        return 'Localization'
    if relative.startswith(('gfx/', 'gui/')):
        return 'Graphics and interface definitions'
    if relative.startswith(('common/', 'events/', 'history/', 'map_data/')):
        return 'Gameplay scripts and history/data'
    return 'Metadata'


def line_counts(path):
    lines = read(path).splitlines()
    return len(lines), sum(bool(line.strip()) for line in lines)


def active_lines(path):
    # CK3 script comments start at # outside a quoted string. Keep quoted #
    # formatting codes and escaped quotes; shader // comments are handled too.
    result = []
    for line in read(path).splitlines():
        quoted = escaped = False
        for i,char in enumerate(line):
            if escaped:
                escaped = False
                continue
            if char == '\\' and quoted:
                escaped = True
            elif char == '"':
                quoted = not quoted
            elif not quoted and (char == '#' or (path.suffix == '.shader' and line[i:i+2] == '//')):
                line = line[:i]
                break
        if line.strip():
            result.append(line.rstrip())
    return result


def diff_counts(source, output):
    result = subprocess.run(['git','diff','--no-index','--numstat',
                             '--ignore-space-at-eol','--',str(source),str(output)],
                            capture_output=True, text=True, encoding='utf-8')
    assert result.returncode in (0,1), result.stderr
    values = result.stdout.split('\t', 2)
    return tuple(map(int, values[:2])) if result.stdout else (0,0)


manifest = load(FIX / 'docs/source-manifest.json')
assert manifest['Revision'] == 14
all_original = [p for p in ORIGINAL.rglob('*') if p.is_file()]
original = []
for path in all_original:
    if path.suffix.lower() not in TEXT:
        continue
    relative = path.relative_to(ORIGINAL).as_posix()
    lines, nonblank = line_counts(path)
    original.append(dict(File=relative, Category=category(relative), Lines=lines,
                         NonblankLines=nonblank, ActiveLines=len(active_lines(path)),
                         Bytes=path.stat().st_size, SHA256=sha(path)))

changes = []
for row in manifest['Files']:
    if row['Kind'] != 'Shadow' or row['Catalog'] != 'AGOT_PLUS':
        continue
    source, output = ORIGINAL / row['File'], FIX / row['File']
    assert sha(source) == row['SourceSHA256']
    assert sha(output) == row['PatchedSHA256']
    # Git compares normalized logical lines: CRLF/LF and trailing whitespace
    # differences do not count. No broad ignore-all-space (quoted text can matter).
    added, deleted = diff_counts(source, output)
    with tempfile.TemporaryDirectory(prefix='agot-change-measure-') as scratch:
        old_active, new_active = Path(scratch)/'original.txt', Path(scratch)/'patched.txt'
        old_active.write_text('\n'.join(active_lines(source))+'\n',encoding='utf-8',newline='\n')
        new_active.write_text('\n'.join(active_lines(output))+'\n',encoding='utf-8',newline='\n')
        active_added, active_deleted = diff_counts(old_active, new_active)
    old_lines = line_counts(source)[0]
    new_lines = line_counts(output)[0]
    # Whitespace-only hunks ignored by Git can include empty lines; do not use
    # total output length to reconstruct the unchanged line count.
    changes.append(dict(File=row['File'], Category=category(row['File']),
                        OriginalLines=old_lines, OutputLines=new_lines,
                        RemovedOrReplacedOriginalLines=deleted, InsertedOrReplacementLines=added,
                        RemovedOrReplacedActiveLines=active_deleted, InsertedOrReplacementActiveLines=active_added,
                        SourceSHA256=row['SourceSHA256'], OutputSHA256=row['PatchedSHA256']))

additions = []
for row in manifest['Files']:
    if row['Kind'] != 'Addition':
        continue
    path = FIX / row['File']
    assert sha(path) == row['PatchedSHA256']
    additions.append(dict(File=row['File'],Category=category(row['File']),
                          Lines=line_counts(path)[0],ActiveLines=len(active_lines(path)),SHA256=row['PatchedSHA256']))


def summarize(label, selected, changed, added_files):
    total = sum(r['Lines'] for r in selected)
    deleted = sum(r['RemovedOrReplacedOriginalLines'] for r in changed)
    inserted = sum(r['InsertedOrReplacementLines'] for r in changed)
    new = sum(r['Lines'] for r in added_files)
    active = sum(r['ActiveLines'] for r in selected)
    active_deleted = sum(r['RemovedOrReplacedActiveLines'] for r in changed)
    active_added = sum(r['InsertedOrReplacementActiveLines'] for r in changed)
    active_new = sum(r['ActiveLines'] for r in added_files)
    return dict(Category=label, OriginalFiles=len(selected), OriginalLines=total,
                ChangedFiles=len(changed), ChangedFilePercent=round(100*len(changed)/len(selected),4),
                RemovedOrReplacedOriginalLines=deleted,
                OriginalLineChangePercent=round(100*deleted/total,4),
                UnchangedOriginalLinePercent=round(100*(total-deleted)/total,4),
                InsertedOrReplacementLines=inserted, NewFiles=len(added_files), NewFileLines=new,
                AddedLinesRelativeToOriginalPercent=round(100*(inserted+new)/total,4),
                TotalDiffVolumePercent=round(100*(deleted+inserted+new)/total,4),
                OriginalActiveLines=active, RemovedOrReplacedActiveLines=active_deleted,
                ActiveLineChangePercent=round(100*active_deleted/active,4),
                InsertedOrReplacementActiveLines=active_added, NewFileActiveLines=active_new,
                ActiveTotalDiffVolumePercent=round(100*(active_deleted+active_added+active_new)/active,4))


categories = sorted({r['Category'] for r in original})
summaries = [summarize(c,[r for r in original if r['Category']==c],
                        [r for r in changes if r['Category']==c],
                        [r for r in additions if r['Category']==c]) for c in categories]
total = summarize('All original runtime text', original, changes, additions)
without_loc = summarize('Runtime text excluding localization',
                        [r for r in original if r['Category']!='Localization'],
                        [r for r in changes if r['Category']!='Localization'],
                        [r for r in additions if r['Category']!='Localization'])
binary = [r for r in manifest['Files'] if r['Kind']=='BinaryShadow' and r['Catalog']=='AGOT_PLUS']
assert len(changes)==77 and len(binary)==49
mesh_sources = [p for p in all_original if p.suffix.lower()=='.mesh']
binary_original_bytes = binary_result_bytes = 0
for row in binary:
    source,output = ORIGINAL/row['File'],FIX/row['File']
    assert sha(source)==row['SourceSHA256'] and sha(output)==row['PatchedSHA256']
    binary_original_bytes += source.stat().st_size
    binary_result_bytes += output.stat().st_size
plan = load(FIX / 'docs/stage14-plan.json')
excluded = [r for r in plan['CloakInventory'] if not r['Name'].endswith('.asset')]

summary = dict(OriginalRoot=ORIGINAL.as_posix(),Revision=manifest['Revision'],
    ManifestSHA256=sha(FIX / 'docs/source-manifest.json'),
    Method='git diff --no-index --numstat --ignore-space-at-eol; LF/CRLF and trailing whitespace ignored; full lines including comments and blanks; removed/replaced original lines divided by ALL original lines; insertion volume reported separately, not as a fraction of original lines modified.',
    OriginalAllFiles=len(all_original), OriginalAllBytes=sum(p.stat().st_size for p in all_original),
    Total=total, WithoutLocalization=without_loc, Categories=summaries,
    ChangedMeshes=len(binary), OriginalMeshes=len(mesh_sources),
    ChangedMeshPercent=round(100*len(binary)/len(mesh_sources),4),
    ChangedMeshOriginalBytes=binary_original_bytes, ChangedMeshResultBytes=binary_result_bytes,
    RemovedMeshBytes=binary_original_bytes-binary_result_bytes,
    ExcludedDuplicateMeshes=sum(r['Name'].endswith('.mesh') for r in excluded),
    ExcludedDuplicateTextures=sum(r['Name'].endswith('.dds') for r in excluded),
    OtherCatalogShadows=[r['File'] for r in manifest['Files'] if r['Kind']=='Shadow' and r['Catalog']!='AGOT_PLUS'],
    SeparateLocalizationOverlayIncluded=False,
    Note='Repository tests, docs, generators and archived sources are excluded. File coverage is not a fraction of rewritten code. Behavior/visual impact cannot be inferred directly from line counts.')
for name,records in [('original-text-files.csv',original),('changed-text-files.csv',changes),
                      ('added-files.csv',additions),('categories.csv',summaries)]:
    with (HERE/name).open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(records[0]),lineterminator='\n')
        writer.writeheader();writer.writerows(records)
(HERE/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(summary,indent=2))
