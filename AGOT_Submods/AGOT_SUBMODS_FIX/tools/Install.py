"""Register this local mod last in AGOT-RUSBAR. Preview unless --apply.

Requires CK3/launcher closed and agreement between launcher SQLite and dlc_load.
Backs up profile files, keeps every existing playset entry/order/enabled state.
"""
import argparse
import csv
from datetime import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time
import uuid
import Build as b

sys.stdout.reconfigure(encoding='utf-8')
REGISTRY='mod/AGOT_SUBMODS_FIX.mod'


def atomic(path,data):
    temporary=path.with_name(path.name+'.usf-'+uuid.uuid4().hex+'.tmp')
    try:
        temporary.write_bytes(data)
        os.replace(temporary,path)
    finally:
        if temporary.exists():temporary.unlink()


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--apply',action='store_true')
    ap.add_argument('--profile',type=Path,default=Path('C:/Users/RUSBAR/Documents/Paradox Interactive/Crusader Kings III'))
    args=ap.parse_args()
    profile=args.profile.resolve()
    database=profile/'launcher-v2.sqlite'
    loadpath=profile/'dlc_load.json'
    descriptor=b.MOD.parent/'AGOT_SUBMODS_FIX.mod'
    installed=profile/'mod/AGOT_SUBMODS_FIX.mod'
    desc=descriptor.read_bytes()
    internal=(b.MOD/'descriptor.mod').read_bytes()
    expected=internal+('path="'+b.MOD.as_posix()+'"\n').encode('utf-8')
    assert desc==expected,'Descriptor mismatch'
    name=re.search(r'^name="([^"]+)"',internal.decode('utf-8'),re.M)[1]
    dependency_block=re.search(r'\bdependencies\s*=\s*\{([^}]*)\}',internal.decode('utf-8'),re.S)
    assert dependency_block, 'Missing dependency block'
    dependencies=re.findall(r'"([^"]+)"',dependency_block[1])
    manifest=json.loads((b.MOD/'docs/source-manifest.json').read_text(encoding='utf-8'))
    for p,m in manifest.items():
        assert hashlib.sha256((b.MOD/p).read_bytes()).hexdigest()==m['sha256'],p
    for s in json.loads((b.MOD/'docs/source-baseline.json').read_text(encoding='utf-8')).values():
        assert hashlib.sha256(Path(s['path']).read_bytes()).hexdigest()==s['sha256'],s['path']
    before_load=loadpath.read_bytes()
    load=json.loads(before_load)
    c=sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)
    c.row_factory=sqlite3.Row
    active=c.execute('SELECT id,name FROM playsets WHERE isActive=1 AND isRemoved=0').fetchall()
    assert len(active)==1 and active[0]['name']=='AGOT-RUSBAR','Unexpected active playset'
    playset=active[0]['id']
    query='SELECT pm.modId,pm.position,pm.enabled,m.gameRegistryId,m.displayName FROM playsets_mods pm JOIN mods m ON pm.modId=m.id WHERE pm.playsetId=? ORDER BY pm.position'
    rows=[dict(x) for x in c.execute(query,(playset,))]
    assert [x['gameRegistryId'] for x in rows if x['enabled']]==load['enabled_mods'],'Launcher/dlc_load disagree'
    names={x['displayName'] for x in rows if x['enabled']}
    assert set(dependencies)<=names,('Dependencies disabled',set(dependencies)-names)
    existing=c.execute('SELECT id,source FROM mods WHERE gameRegistryId=?',(REGISTRY,)).fetchall()
    assert len(existing)<=1 and (not existing or existing[0]['source']=='local'),'Registry conflict'
    modid=existing[0]['id'] if existing else str(uuid.uuid4())
    other_playsets=[tuple(x) for x in c.execute('SELECT * FROM playsets_mods WHERE playsetId!=? ORDER BY playsetId,position',(playset,))]
    before_existing=[x for x in rows if x['gameRegistryId']!=REGISTRY]
    newenabled=[x['gameRegistryId'] for x in before_existing if x['enabled']]+[REGISTRY]
    result=dict(name=name,playset=active[0]['name'],path=b.MOD.as_posix(),position=len(newenabled),apply=args.apply)
    if not args.apply:
        c.close();print(json.dumps(result,ensure_ascii=False,indent=2));return
    processes=subprocess.run(['tasklist','/fo','csv','/nh'],capture_output=True,check=True,
                             creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)).stdout.decode('utf-8',errors='replace')
    blocked=[r[0] for r in csv.reader(io.StringIO(processes)) if r and (r[0].lower() in ['ck3.exe','dowser.exe'] or r[0].lower().startswith('paradox launcher'))]
    assert not blocked,('Close CK3/launcher first',blocked)
    for suffix in ['-wal','-journal']:
        f=Path(str(database)+suffix)
        assert not (f.exists() and f.stat().st_size),'Active SQLite journal'
    backup=profile/'mod_backups'/('AGOT_SUBMODS_FIX_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8])
    backup.mkdir(parents=True)
    with sqlite3.connect(backup/'launcher-v2.sqlite') as destination:c.backup(destination)
    c.close()
    (backup/'dlc_load.json').write_bytes(before_load)
    before_desc=installed.read_bytes() if installed.exists() else None
    if before_desc is not None:(backup/'AGOT_SUBMODS_FIX.mod').write_bytes(before_desc)
    c=sqlite3.connect(database,isolation_level=None)
    c.row_factory=sqlite3.Row
    committed=False
    try:
        c.execute('PRAGMA foreign_keys=ON')
        c.execute('BEGIN IMMEDIATE')
        assert loadpath.read_bytes()==before_load,'Profile changed since preview'
        assert [dict(x) for x in c.execute(query,(playset,))]==rows,'Playset changed since preview'
        stamp=int(time.time())
        if not existing:
            c.execute('INSERT INTO mods (id,gameRegistryId,displayName,version,requiredVersion,dirPath,status,source,tags,createdDate,timeUpdated,isNew) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                      (modid,REGISTRY,name,'0.1.0','1.19.0.6',str(b.MOD),'ready_to_play','local','["Fixes","Gameplay"]',stamp,stamp,0))
        else:
            c.execute('UPDATE mods SET displayName=?,version=?,requiredVersion=?,dirPath=?,status=?,timeUpdated=? WHERE id=?',
                      (name,'0.1.0','1.19.0.6',str(b.MOD),'ready_to_play',stamp,modid))
        position=max((x['position'] for x in before_existing),default=-1)+1
        count=c.execute('SELECT COUNT(*) FROM playsets_mods WHERE playsetId=? AND modId=?',(playset,modid)).fetchone()[0]
        assert count<=1,'Duplicate mod in playset'
        if count:c.execute('UPDATE playsets_mods SET enabled=1,position=? WHERE playsetId=? AND modId=?',(position,playset,modid))
        else:c.execute('INSERT INTO playsets_mods (playsetId,modId,enabled,position) VALUES (?,?,1,?)',(playset,modid,position))
        c.execute("UPDATE playsets SET loadOrder='custom',updatedOn=? WHERE id=?",(stamp*1000,playset))
        installed.parent.mkdir(exist_ok=True)
        atomic(installed,desc)
        load['enabled_mods']=newenabled
        atomic(loadpath,json.dumps(load,ensure_ascii=False,separators=(',',':')).encode('utf-8'))
        after=[dict(x) for x in c.execute(query,(playset,))]
        assert [x for x in after if x['gameRegistryId']!=REGISTRY]==before_existing,'Existing entries changed'
        assert [x['gameRegistryId'] for x in after if x['enabled']]==newenabled
        assert other_playsets==[tuple(x) for x in c.execute('SELECT * FROM playsets_mods WHERE playsetId!=? ORDER BY playsetId,position',(playset,))]
        assert c.execute('PRAGMA quick_check').fetchone()[0]=='ok'
        assert not c.execute('PRAGMA foreign_key_check').fetchall()
        c.execute('COMMIT');committed=True
    except Exception:
        if not committed:
            if c.in_transaction:c.execute('ROLLBACK')
            atomic(loadpath,before_load)
            if before_desc is None:
                if installed.exists():installed.unlink()
            else:atomic(installed,before_desc)
        raise
    finally:c.close()
    result.update(backup=backup.as_posix(),registry=REGISTRY,existing_entries_preserved=True,other_playsets_preserved=True)
    (b.MOD/'docs/install-state.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
