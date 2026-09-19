"""Verify report totals and that revision-8 runtime files remain unchanged."""
import csv,hashlib,json,re,sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest().upper()
def read(p):return Path(p).read_text(encoding='utf-8-sig')
def rows(p):return list(csv.DictReader(Path(p).open(encoding='utf-8-sig',newline='')))
def js(p):return json.loads(read(p))
manifest=REPO/'AGOT_Submods/AGOT_PLUS_FIX/docs/source-manifest.json'
expected='22921E90C8B0FF497FFD77482F5D14B9F4E2FB287907D7E23838BB71FDCD505C'
assert sha(manifest)==expected
m=js(manifest);patch=manifest.parents[1]
checks=[dict(File=r['File'],Expected=r['PatchedSHA256'],Actual=sha(patch/r['File'])) for r in m['Files']]
assert len(checks)==45 and all(r['Actual']==r['Expected'] for r in checks)
run=HERE.parent/'ck3-agot-plus-fix-stage8-log-2026-09-19'
mods=rows(run/'active-mods.csv');roots={r['Name']:Path(r['Path']) for r in mods}
roots['CK3']=Path('E:/SteamLibrary/steamapps/common/Crusader Kings III/game')
sources=rows(HERE/'source-hashes.csv')+rows(HERE/'agot-donor-source-hashes.csv')
for r in sources:assert sha(roots[r['Mod']]/r['File'])==r['SHA256'],r
previous_sources=rows(run/'source-hash-verification.csv')
catalog_roots={'AGOT':roots['A Game of Thrones'],'AGOT_PLUS':roots['AGOT+']}
for r in previous_sources:assert sha(catalog_roots[r['Catalog']]/r['File'])==r['SHA256'],r
assert len(previous_sources)==100
agot=roots['A Game of Thrones']
support=[];evidence=[]
for rel in ['gfx/models/portraits/male_head/male_head.asset','gfx/models/portraits/female_head/female_head.asset','gfx/FX/jomini/portrait.shader','gfx/FX/jomini/portrait_decals.fxh']:
    p=agot/rel
    providers=[r['Name'] for r in mods if (Path(r['Path'])/rel).is_file()]
    support.append(dict(File=rel,SHA256=sha(p),Providers=providers))
    for n,line in enumerate(read(p).splitlines(),1):
        if re.search(r'bs_eye_fold_2|bs_head_round_shape|eye_shut_top|eye_shut_bottom|inner_eyebrow_width|brow_inner_width|\bPS_dragon\b|AddDragonDecals',line):
            evidence.append(f'{rel}:{n}: {line.strip()}')
(HERE/'model-evidence.txt').write_text('\n'.join(evidence)+'\n',encoding='utf-8', newline='\n')
index=rows(HERE/'dna-log-index.csv');covered=rows(HERE/'proposed-covered-log.csv');deferred=rows(HERE/'proposed-deferred-log.csv')
assert len(index)==8368 and len(covered)==8118 and len(deferred)==250
assert sorted(r['LogLine'] for r in index)==sorted(r['LogLine'] for r in covered+deferred)
summary=js(HERE/'detail-summary.json')
assert summary['MissingValidated']==6238 and summary['UnknownLogEqualsParsed']
assert summary['UnloggedBookmarkGaps']==1316 and summary['UnloggedBookmarkPresets']==124
assert summary['HumanDonors']==5273 and summary['CompleteDonors']==5273
snapshot=run/'snapshot/error.log';live=Path('C:/Users/RUSBAR/Documents/Paradox Interactive/Crusader Kings III/logs/error.log')
assert sha(snapshot)=='66781C0707B4EF82A775FBA0C6B3A72360135D2B9982E1D0FB7136A7D8FEBB03'
out=dict(Revision=m['Revision'],RuntimeFilesVerified=len(checks),RuntimeHashesUnchanged=True,ManifestSHA256=sha(manifest),AnalysisSourcesVerified=len(sources),PreviousSourceHashesVerified=len(previous_sources),LogSHA256=sha(snapshot),LiveLogMatchesSnapshot=live.exists() and sha(live)==sha(snapshot),Covered=8118,Deferred=250,LogPartitionValidated=True,SupportingSources=support)
(HERE/'verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8', newline='\n')
print(json.dumps(out,ensure_ascii=False,indent=2))
