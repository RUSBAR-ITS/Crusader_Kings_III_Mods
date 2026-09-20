"""Record the post-launch encoding correction separately from runtime evidence."""
from pathlib import Path
import hashlib
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
MOD=REPO/'AGOT_Submods/AGOT_SUBMODS_FIX'
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def digest(b):return hashlib.sha256(b).hexdigest()
def save(p,data):p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
relative='common/scripted_effects/usf_language_effects.txt'
old=load(HERE/'snapshot/submods-source-manifest.json')
new=load(MOD/'docs/source-manifest.json')
before=(HERE/'snapshot/usf_language_effects.before.txt').read_bytes()
after=(MOD/relative).read_bytes()
assert set(old)==set(new)
assert digest(before)==old[relative]['sha256']
assert digest(after)==new[relative]['sha256']
assert after==b'\xef\xbb\xbf'+before
assert before.decode('utf-8')==after.decode('utf-8-sig')
assert [p for p in old if old[p]!=new[p]]==[relative]
assert all(digest((MOD/p).read_bytes())==m['sha256'] for p,m in new.items())
capture=load(HERE/'snapshot-summary.json')
error=next(r for r in capture['Copies'] if r['Snapshot']=='error.log')
assert digest(Path(error['Source']).read_bytes())==error['SourceSHA256'],'Live log replaced after capture'
validation=load(MOD/'docs/validation.json')
assert validation['status']=='PASS'
record=dict(File=relative,Change='Prepend exactly EF BB BF; decoded script unchanged',BeforeSHA256=digest(before),AfterSHA256=digest(after),BeforeBytes=len(before),AfterBytes=len(after),Other25RuntimeFilesByteIdentical=True,BuildCheckPassed=True,StaticChecks=validation['checks'],LogWasNotModified=True,RuntimeRetestPending=True)
save(HERE/'post-launch-bom-fix.json',record)
save(HERE/'snapshot/submods-source-manifest.after-bom.json',new)
save(HERE/'snapshot/submods-validation.after-bom.json',validation)
summary=load(HERE/'comparison-summary.json')
save(MOD/'docs/runtime-validation.json',dict(Report='../../../docs/reports/ck3-agot-submods-fix-stage1-log-2026-09-20/README.md',Started=summary['Started'],ExitLines=summary['ExitLines'],CapturedManifestSHA256=digest((HERE/'snapshot/submods-source-manifest.json').read_bytes()),CurrentManifestSHA256=digest((MOD/'docs/source-manifest.json').read_bytes()),ExpectedFixedGone=summary['ExpectedFixedGone'],ExceptionsPresent=summary['ExceptionsPresent'],DeferredPresent=summary['DeferredPresent'],NewDiagnosticsAfterReview=summary['NewDiagnosticsAfterReview'],OriginalSourcePinsChecked=summary['SourcePinsChecked'],OriginalSourcePinsChanged=summary['SourcePinsChanged'],PostLaunchEncodingFix=record,InCampaignBehaviorChecked=False))
print(json.dumps(record,ensure_ascii=False,indent=2))
