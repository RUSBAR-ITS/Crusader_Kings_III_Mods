"""Preserve exited-game evidence; read-only toward game, profile and mod files."""
from pathlib import Path
import csv
import datetime as dt
import hashlib
import json
import re
import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PROFILE = Path('C:/Users/RUSBAR/Documents/Paradox Interactive/Crusader Kings III')
SNAP = HERE / 'snapshot'
PREVIOUS = HERE.parent / 'ck3-agot-submods-fix-stage1-log-2026-09-20'

def read(p): return Path(p).read_text(encoding='utf-8-sig')
def load(p): return json.loads(read(p))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def stamp(p): return dt.datetime.fromtimestamp(Path(p).stat().st_mtime).astimezone().isoformat()
def save(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
def export(name, rows):
    with (HERE / name).open('w', encoding='utf-8-sig', newline='') as f:
        w=csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
        w.writeheader(); w.writerows(rows)

assert not (HERE / 'snapshot-summary.json').exists(), 'Completed snapshot must not be overwritten'
SNAP.mkdir(exist_ok=True)
copies=[]
def copy(source, name):
    before=sha(source)
    raw=Path(source).read_bytes().replace(b'\r\n',b'\n').replace(b'\r',b'\n')
    target=SNAP/name
    if target.exists(): assert target.read_bytes()==raw, ('Partial snapshot differs', name)
    else: target.write_bytes(raw)
    assert sha(source)==before, ('Source changed during capture', source)
    copies.append(dict(Source=str(source),Snapshot=name,SourceSHA256=before,SnapshotSHA256=sha(target)))

logs=[]
for name in ('error.log','game.log','system.log','debug.log','database_conflicts.log','code_revisions.log','gui_warnings.log'):
    source=PROFILE/'logs'/name
    logs.append(dict(File=name,Bytes=source.stat().st_size,LastWriteTime=stamp(source)))
    copy(source,name)
debug=read(SNAP/'debug.log')
assert 'Quit: Quit from inside game' in debug, 'Game has not exited normally'
start=re.search(r'^\[(\d\d:\d\d:\d\d)\].*Log system initialized\.',debug)[1]
launch=dt.datetime.fromisoformat(logs[0]['LastWriteTime']).replace(**dict(zip(('hour','minute','second'),map(int,start.split(':')))),microsecond=0)
copy(PROFILE/'dlc_load.json','dlc_load.json')
mods=[]
for i, registry in enumerate(load(SNAP/'dlc_load.json')['enabled_mods'],1):
    text=read(PROFILE/registry)
    name=re.search(r'^\s*name="([^"]+)"',text,re.M)[1]
    path=re.search(r'^\s*path="([^"]+)"',text,re.M)[1]
    assert Path(path).is_dir(),path
    copy(PROFILE/registry,f'descriptor-{i:02d}.mod')
    mods.append(dict(Order=i,Name=name,Path=path,Descriptor=registry,Exists=True,ReplacePaths='|'.join(re.findall(r'^\s*replace_path\s*=\s*"([^"]+)"',text,re.M))))
export('active-mods.csv',mods)
with (PREVIOUS/'active-mods.csv').open(encoding='utf-8-sig',newline='') as f: old=list(csv.DictReader(f))
assert [(str(m['Order']),m['Descriptor'],m['Path']) for m in mods]==[(m['Order'],m['Descriptor'],m['Path']) for m in old]
assert len(mods)==33 and mods[-1]['Descriptor']=='mod/AGOT_SUBMODS_FIX.mod'
database=PROFILE/'launcher-v2.sqlite'
with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as c:
    c.row_factory=sqlite3.Row
    active=c.execute('SELECT id,name FROM playsets WHERE isActive=1 AND isRemoved=0').fetchall()
    assert len(active)==1 and active[0]['name']=='AGOT-RUSBAR'
    registry_rows=[dict(r) for r in c.execute('SELECT pm.position,pm.enabled,m.gameRegistryId,m.displayName FROM playsets_mods pm JOIN mods m ON pm.modId=m.id WHERE pm.playsetId=? ORDER BY pm.position',(active[0]['id'],))]
assert [r['gameRegistryId'] for r in registry_rows if r['enabled']]==[m['Descriptor'] for m in mods]
save('launcher-registry.json',registry_rows)
runtime=[]
for name,prefix in [('AGOT_PLUS_FIX','plus'),('AGOT_PLUS_RUS_CORRECT','plus-rus'),('AGOT_More_Dragon_Eggs_RUS_CORRECT','mde'),('AGOT_SUBMODS_FIX','submods')]:
    root=REPO/'AGOT_Submods'/name
    manifest=load(root/'docs/source-manifest.json')
    copy(root/'docs/source-manifest.json',prefix+'-source-manifest.json')
    if prefix=='submods': files=[(p,r['sha256']) for p,r in manifest.items()]
    elif prefix=='mde': files=[(r['File'],r['SHA256']) for r in manifest['Outputs']]
    else:
        files=[(r['File'],r['PatchedSHA256']) for r in manifest['Files']]
        if prefix=='plus-rus': files += [(manifest['Overlay'],manifest['OverlaySHA256']),(manifest['RuntimeNames']['File'],manifest['RuntimeNames']['SHA256'])]
    for rel,digest in files:
        p=root/rel
        assert sha(p)==digest.lower(),('Output changed',p)
        providers=[]
        for m in mods:
            if any(rel.lower().startswith(q.lower().rstrip('/')+'/') for q in m['ReplacePaths'].split('|') if q):
                providers.clear()
            if (Path(m['Path'])/rel).is_file(): providers.append(Path(m['Path']))
        if rel!='descriptor.mod': assert providers[-1].resolve()==root.resolve(),('Later provider',p)
        assert dt.datetime.fromisoformat(stamp(p)) < launch,('File modified after launch',p)
        runtime.append(dict(Mod=name,File=rel,SHA256=sha(p),LastWriteTime=stamp(p)))
export('runtime-files.csv',runtime)
for name in ['expected-log.json','diagnostic-disposition.csv','source-baseline.json','validation.json','installed-validation.json','install-state.json','resource-build.json','resource-validation.json','resource-disposition.csv','resource-log-expectations.json']:
    copy(REPO/'AGOT_Submods/AGOT_SUBMODS_FIX/docs'/name,'submods-'+name)
mounts=[line for line in debug.splitlines() if 'Mounted Data:' in line and '/AGOT_SUBMODS_FIX' in line]
assert len(mounts)==1,'Expected one debug mount entry for new patch'
save('snapshot-summary.json',dict(CapturedAt=dt.datetime.now().astimezone().isoformat(),Started=launch.isoformat(),ExitLines=[l for l in debug.splitlines() if 'Quit: Quit from inside game' in l],Logs=logs,ActiveMods=len(mods),Previous33ModsUnchanged=True,LauncherAndDlcAgree=True,Mounts=mounts,RuntimeFiles=len(runtime),AllRuntimeHashesMatch=True,AllRuntimeFilesPrecedeLaunch=True,LastDeclaredProvidersMatch=True,EngineIndividualResourceLoadingProven=False,SnapshotNewlines='LF',Copies=copies))
print(json.dumps(dict(Started=launch.isoformat(),ActiveMods=len(mods),RuntimeFiles=len(runtime),Mounts=mounts),ensure_ascii=False))
