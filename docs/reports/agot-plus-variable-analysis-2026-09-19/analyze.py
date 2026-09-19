"""Read-only variable/flag/scope inventory over the effective active mod set."""
import collections
import csv
import importlib.util
import json
from pathlib import Path
import re
import subprocess

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[2]
spec = importlib.util.spec_from_file_location('dna9', REPO/'AGOT_Submods/AGOT_PLUS_FIX/tools/DNA-Stage9.py')
d = importlib.util.module_from_spec(spec); spec.loader.exec_module(d)
mods = d.active_mods()
manifest = d.load(d.DOC/'source-manifest.json')
assert manifest['Revision'] == 11
before = {row['File']:d.sha(d.MOD/row['File']) for row in manifest['Files']}
assert before == {row['File']:row['PatchedSHA256'] for row in manifest['Files']}
log = OUT.parent/'ck3-agot-plus-fix-stage10-log-2026-09-19/all-agot-plus-associated.csv'
targets = [r for r in d.rows(log) if r['Category'] in ('variable_not_set','variable_unused')]
symbols = sorted({r['Symbols'] for r in targets})
assert len(targets) == 130 and len(symbols) == 65
(OUT/'symbols.txt').write_text('\n'.join(symbols)+'\n',encoding='utf-8', newline='\n')
pattern = re.compile(r'(?<![\w])(?:'+'|'.join(map(re.escape,sorted(symbols,key=len,reverse=True)))+r')(?![\w])')

def code(s):
    return re.sub(r'"(?:\\.|[^"\\])*"|#[^\r\n]*',lambda m:'' if m[0].startswith('#') else m[0],s)

provider_cache = {}
def provider(rel):
    if rel not in provider_cache:
        result = None
        for mod in mods:
            if any(rel==rp or rel.startswith(rp.rstrip('/')+'/') for rp in mod['Replace']): result=None
            p = Path(mod['Path'])/rel
            if d.native(p).is_file(): result=(mod,p)
        provider_cache[rel] = result
    return provider_cache[rel]

command = ['rg','--json','--no-ignore','-F','-f',str(OUT/'symbols.txt'),'-g','*.txt','-g','*.gui','-g','*.yml'] + [m['Path'] for m in mods]
result = subprocess.run(command,capture_output=True,encoding='utf-8')
assert result.returncode in (0,1),result.stderr
roots = sorted([(str(Path(m['Path']).resolve()).replace('\\','/'),m) for m in mods],key=lambda p:len(p[0]),reverse=True)
references, texts, parsed, failures = [], {}, {}, {}
for line in result.stdout.splitlines():
    row=json.loads(line)
    if row['type']!='match': continue
    row=row['data']; path=row['path']['text'].replace('\\','/')
    base,mod=next((p,m) for p,m in roots if path.lower().startswith(p.lower()+'/'))
    rel=path[len(base)+1:]
    if rel.split('/')[0] not in {'common','events','gfx','gui','history','localization','map_data'}: continue
    effective = provider(rel)
    if effective is None or effective[0] is not mod: continue
    matched=code(row['lines']['text'])
    found=set(m[0] for m in pattern.finditer(matched))
    if not found: continue
    if rel not in texts: texts[rel]=d.read(path)
    text=texts[rel]; lines=text.splitlines(); n=row['line_number']
    context='\n'.join(lines[max(0,n-9):n+4])
    clean=code(context)
    for symbol in found:
        q=re.escape(symbol)
        relevant=(re.search(r'\b(?:var|global_var|local_var|scope):'+q+r'\b',matched)
                  or re.search(r'\b(?:has|set|add|remove|change|subtract|multiply|divide|clamp)_[\w]*(?:variable|flag)\s*(?:[?=!<>]+)?\s*"?'+q+r'\b',matched)
                  or re.search(r'\b(?:name|flag)\s*=\s*"?'+q+r'\b',matched) and re.search(r'\b\w*variable\s*=\s*\{[^}]*\b(?:name|flag)\s*=\s*"?'+q+r'\b',clean)
                  or re.search(r'\bsave_(?:temporary_)?scope_as\s*=\s*"?'+q+r'\b',matched)
                  or re.search(r'(?:Variable|Flag|MakeScope|Var|GlobalVar)\([^)]*[\'\"]'+q+r'[\'\"]',matched))
        if not relevant: continue
        if rel not in parsed and rel not in failures:
            try: parsed[rel]=list(d.walk(d.parse(text)))
            except AssertionError as exc: failures[rel]=str(exc)
        offset=row['absolute_offset']
        # ripgrep offsets are bytes, whereas parser offsets are Unicode characters.
        offset=len(d.native(path).read_bytes()[:offset].decode('utf-8-sig'))
        chain=[b.key for b in parsed.get(rel,[]) if b.start<=offset<b.end and b.key!='ROOT']
        role='read'
        if re.search(r'\b(?:remove_\w*(?:variable|flag))\b',matched):role='remove'
        elif re.search(r'\b(?:set|add|change)_\w*(?:variable|flag)\b|\bsave_(?:temporary_)?scope_as\b',matched) or any(k.startswith(('set_variable','set_global_variable','set_local_variable','add_character_flag')) for k in chain):role='write'
        references.append(dict(Symbol=symbol,Role=role,File=rel,Line=n,Owner=mod['Name'],Path=str(Path(path)),
                               Chain=' > '.join(chain),Text=lines[n-1].strip(),Context=context))
counts=collections.Counter((r['Symbol'],r['Role']) for r in references)
summary=[]
for symbol in symbols:
    rows=[r for r in references if r['Symbol']==symbol]
    summary.append(dict(Symbol=symbol,Category=next(t['Category'] for t in targets if t['Symbols']==symbol),
                        LogMessages=sum(t['Symbols']==symbol for t in targets),
                        Reads=counts[symbol,'read'],Writes=counts[symbol,'write'],Removals=counts[symbol,'remove'],
                        Files=sorted({r['File'] for r in rows})))
for name,data in [('targets.json',targets),('references.json',references),('summary.json',summary),('parse-failures.json',failures)]:
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8', newline='\n')
pins={str(provider(rel)[1]):d.sha(provider(rel)[1]) for rel in {r['File'] for r in references}}
pins[str(log)]=d.sha(log)
(OUT/'source-pins.json').write_text(json.dumps(pins,ensure_ascii=False,indent=2)+'\n',encoding='utf-8', newline='\n')
assert before == {row['File']:d.sha(d.MOD/row['File']) for row in manifest['Files']}
(OUT/'runtime-before.json').write_text(json.dumps(before,indent=2)+'\n',encoding='utf-8', newline='\n')
print(f'{len(targets)} log messages, {len(symbols)} IDs, {len(references)} variable/flag/scope references, {len(pins)} pinned inputs, {len(failures)} parse failures.')
for row in summary:
    print(row['Symbol'],row['Reads'],row['Writes'],row['Removals'],len(row['Files']))
