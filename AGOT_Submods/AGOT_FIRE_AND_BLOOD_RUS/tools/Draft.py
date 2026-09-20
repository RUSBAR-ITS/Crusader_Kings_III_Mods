"""Optional draft generator. Sends only public source localization to Google Translate.

Not used by Build.py. Cached outputs are drafts, never marked as manual review.
Workshop files and playset are never modified.
"""
from Localization import *
from DraftDisambiguation import clarify
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import urllib.parse
import urllib.request
import sys

sys.stdout.reconfigure(encoding='utf-8')
en,files=read_catalog(MAIN,'english')
old,oldfiles=read_catalog(OLD,'russian')
save(ROOT/'docs/source-manifest.json',dict(main=str(MAIN),main_version='1.1.2',translation_reference=str(OLD),translation_reference_version='1',english_files=files,reference_files=oldfiles))
save(ROOT/'docs/source-catalog.json',en)
save(ROOT/'docs/reference-catalog.json',old)
output=ROOT/'docs/translation-draft.json'
draft=json.loads(output.read_text(encoding='utf-8')) if output.exists() else {}
pending=[]
for key,row in en.items():
    if key in draft:continue
    value=row['text']
    previous=old.get(key,{}).get('text','')
    if previous and len(value)<250 and signature(previous)==signature(value) and len(previous)>len(value)*0.45:
        draft[key]=dict(text=previous,origin='previous_translation_candidate')
    elif value=='TO DO' or re.fullmatch(r'\$[^$]+\$',value):
        draft[key]=dict(text=value,origin='source_reference_or_placeholder')
    else:
        masked,protected=mask(value)
        masked=clarify(masked)
        pending.append(dict(key=key,text=masked,protected=protected))
save(output,draft)
batches=[];current=[];length=0
for row in pending:
    if current and length+len(row['text'])>3400:
        batches.append(current);current=[];length=0
    current.append(row);length+=len(row['text'])+32
if current:batches.append(current)
print(f'Seeded {len(draft)}; pending {len(pending)} in {len(batches)} batches',flush=True)


def translate(s):
    url='https://translate.googleapis.com/translate_a/single?'+urllib.parse.urlencode(dict(client='gtx',sl='en',tl='ru',dt='t',q=s))
    for attempt in range(4):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req,timeout=30) as response: obj=json.load(response)
            return ''.join(part[0] for part in obj[0] if part[0])
        except Exception:
            if attempt==3:raise
            time.sleep(2**attempt)


def work(batch):
    s='\n\n'.join(f'ZBND{n:05d}Z\n'+r['text'] for n,r in enumerate(batch))
    result=translate(s)
    matches=list(re.finditer(r'ZBND\s*(\d{5})\s*Z',result))
    if [int(m[1]) for m in matches]!=list(range(len(batch))):
        # Retry separately when batching boundaries are not preserved.
        return [work([r])[0] if len(batch)>1 else single(r) for r in batch]
    values=[]
    for n,r in enumerate(batch):
        text=result[matches[n].end():matches[n+1].start() if n+1<len(matches) else len(result)]
        try:value=unmask(text,r['protected'])
        except ValueError:
            values.append(single(r));continue
        values.append((r['key'],dict(text=value,origin='machine_draft')))
    time.sleep(0.15)
    return values


def single(r):
    text=translate(r['text'])
    return r['key'],dict(text=unmask(text,r['protected']),origin='machine_draft')


errors=[]
with ThreadPoolExecutor(max_workers=3) as pool:
    futures={pool.submit(work,b):b for b in batches}
    for n,f in enumerate(as_completed(futures),1):
        try:
            for k,v in f.result():draft[k]=v
        except Exception as exc:
            errors.append(dict(keys=[r['key'] for r in futures[f]],error=str(exc)))
        save(output,draft)
        if n%10==0 or n==len(batches):print(f'{n}/{len(batches)} batches; {len(draft)}/{len(en)} keys; errors={len(errors)}',flush=True)
save(ROOT/'docs/draft-errors.json',errors)
if errors:sys.exit(1)
