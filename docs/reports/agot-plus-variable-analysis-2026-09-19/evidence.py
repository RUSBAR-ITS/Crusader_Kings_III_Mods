"""Additional read-only evidence for the variable analysis; no runtime writes."""
import importlib.util
import json
from pathlib import Path
import re
import subprocess

OUT=Path(__file__).resolve().parent
REPO=OUT.parents[2]
spec=importlib.util.spec_from_file_location('dna9',REPO/'AGOT_Submods/AGOT_PLUS_FIX/tools/DNA-Stage9.py')
d=importlib.util.module_from_spec(spec); spec.loader.exec_module(d)
mods=d.active_mods()
summary=d.load(OUT/'summary.json')
starks=[x['Symbol'].removesuffix('_cc') for x in summary if x['Symbol'].startswith('asoiaf_Stark_')]
founders=[x['Symbol'].removeprefix('asoiaf_canon_children_').removesuffix('_born_variable') for x in summary if x['Symbol'].endswith('_born_variable')]
queries=[
 'asoiafCanonChildrenCharacterDesc','ASOIAF_CANON_CHILDREN_CHARACTER_TOOLTIP',
 'asoiaf_targaryen_invasion_claimants_spawn_aegon_effect','asoiaf_targaryen_invasion_claimants_rule',
 'asoiaf_on_title_inheritance_robert_usurper_nickname','is_Stark_7','kingsguard_armor',
 'primary_color','primary_color_grading','dark_sister_artifact',
 'asoiaf_sword_krakenfall_visuals','asoiaf_needle_visuals','asoiaf_red_vipers_spear_visuals',
 'agot_create_artifact_vs_dark_sister_effect','asoiaf_canon_children_$','_born_variable$',
] + [s+'_trait' for s in starks] + ['asoiaf_canon_children_'+s+'_birth' for s in founders]
(OUT/'evidence-queries.txt').write_text('\n'.join(queries)+'\n',encoding='utf-8')
result=subprocess.run(['rg','--json','--no-ignore','-F','-f',str(OUT/'evidence-queries.txt'),'-g','*.txt','-g','*.gui','-g','*.yml']+[m['Path'] for m in mods],capture_output=True,encoding='utf-8')
assert result.returncode in (0,1),result.stderr
roots=sorted([(str(Path(m['Path']).resolve()).replace('\\','/'),m) for m in mods],key=lambda x:len(x[0]),reverse=True)
providers={}
def provider(rel):
 if rel not in providers:
  found=None
  for m in mods:
   if any(rel==rp or rel.startswith(rp.rstrip('/')+'/') for rp in m['Replace']):found=None
   p=Path(m['Path'])/rel
   if d.native(p).is_file():found=(m,p)
  providers[rel]=found
 return providers[rel]
rows=[]
for line in result.stdout.splitlines():
 x=json.loads(line)
 if x['type']!='match':continue
 x=x['data']; path=x['path']['text'].replace('\\','/')
 base,mod=next((p,m) for p,m in roots if path.lower().startswith(p.lower()+'/'))
 rel=path[len(base)+1:]
 if rel.split('/')[0] not in {'common','events','gfx','gui','history','localization','map_data'}:continue
 eff=provider(rel)
 if not eff or eff[0] is not mod:continue
 raw=x['lines']['text'].rstrip()
 code=re.sub(r'"(?:\\.|[^"\\])*"|#[^\r\n]*',lambda m:'' if m[0].startswith('#') else m[0],raw)
 for q in queries:
  if re.search(r'(?<!\w)'+re.escape(q)+r'(?!\w)',code):
   rows.append(dict(Query=q,Owner=mod['Name'],File=rel,Path=str(eff[1]),Line=x['line_number'],Text=raw.strip()))
(OUT/'supporting-references.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
pins=d.load(OUT/'source-pins.json')
for p in {r['Path'] for r in rows}:pins[p]=d.sha(p)
(OUT/'source-pins.json').write_text(json.dumps(pins,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assignment=d.read(d.MOD/'common/scripted_effects/asoiaf_assign_inactive_traits_effects.txt').splitlines()
refs=d.load(OUT/'references.json')
table=[]
for char in founders:
 r=next(r for r in refs if r['Symbol']=='asoiaf_canon_children_'+char+'_born_variable')
 context=next(line.strip() for line in reversed(assignment[:r['Line']]) if re.search(r'character:[\w_]+\s*\?*=',line))
 # Prefix check supplements the strict word-boundary lookup above.
 needle='asoiaf_canon_children_'+char+'_birth'
 exact=subprocess.run(['rg','-l','--no-ignore','-F',needle,str(d.MOD/'common'),str(d.PLUS/'common'),str(d.PLUS/'events')],capture_output=True,encoding='utf-8')
 assert exact.returncode in (0,1)
 table.append(dict(Character=char,MarkerLine=r['Line'],Assignment=context,BirthEffectFiles=exact.stdout.splitlines()))
(OUT/'born-marker-audit.json').write_text(json.dumps(table,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Supporting references:',len(rows),'source pins:',len(pins))
for q in queries[:17]:
 hits=[x for x in rows if x['Query']==q]
 print(q,len(hits))
for row in table:print(row['Character'],row['Assignment'],'birth files:',len(row['BirthEffectFiles']))
before=d.load(OUT/'runtime-before.json')
assert all(d.sha(d.MOD/p)==h for p,h in before.items())
