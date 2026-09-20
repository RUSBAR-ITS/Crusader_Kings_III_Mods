"""Read the active mod stack and collect evidence; no runtime writes."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
spec = importlib.util.spec_from_file_location('d', REPO/'AGOT_Submods/AGOT_PLUS_FIX/tools/DNA-Stage9.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
mods = d.active_mods()
targets = [
    'Dormund_1', 'Dormand', 'Broome_rs_54', 'Broome_54', 'Hotah_rs_2', 'Hotah_1_B',
    'asoiaf_Targaryen_61_1', 'Targaryen_61_1', 'test_crush_desc',
    'ce_bottom_solid.dds', 're_block_02.dds', 'asoiaf_unicorn.dds',
    'north_wibberly.dds', 'vale_seldon_rayonne.dds',
    'asoiaf_oathkeeper_modifier', 'asoiaf_stark_throne_modifier', 'asoiaf_Karstark_4_modifier',
    'asoiaf_mega_war_events.0001', 'asoiaf_young_griff_landing_events.2',
    'asoiaf_hound_armour_visuals', 'male_cloaks_secular_shouldercape_01',
    'asoiaf_create_artifact_stark_throne_effect', 'asoiaf_greyjoy_cadets_decision',
    'asoiaf_baelish_cadets_decision', 'asoiaf_harlaw_cadets_decision',
    'asoiaf_jon_targ_cadet_branch_decision', 'asoiaf_aegon_II_greens_cadet_branch_decision',
]
pattern = re.compile('|'.join(map(re.escape,targets)))
files = {}
for mod in mods:
    for prefix in mod['Replace']:
        files = {k:v for k,v in files.items() if not(k==prefix or k.startswith(prefix.rstrip('/')+'/'))}
    root = Path(mod['Path'])
    for folder in ('common','events','history','localization','gfx','gui'):
        for path in (root/folder).rglob('*'):
            if path.is_file() and path.suffix in ('.txt','.yml','.asset','.gui','.gfx','.shader','.fxh'):
                files[path.relative_to(root).as_posix()] = (mod['Name'],path)
matches, pins = [], {}
for rel,(owner,path) in files.items():
    raw = path.read_bytes()
    text = raw.decode('utf-8-sig',errors='replace')
    if not pattern.search(text): continue
    pins[str(path)] = hashlib.sha256(raw).hexdigest().upper()
    lines=text.splitlines()
    for i,line in enumerate(lines):
        found=sorted(set(pattern.findall(line)))
        if not found: continue
        matches.append(dict(Owner=owner,File=rel,Path=str(path),Line=i+1,Targets=found,
                            CommentOnly=line.lstrip().startswith('#'),Text=line,
                            Context='\n'.join(f'{j+1}: {lines[j]}' for j in range(max(0,i-5),min(len(lines),i+7)))))
for name,data in [('matches.json',matches),('source-pins.json',pins),('active-mods.json',mods)]:
    (HERE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(EffectiveFiles=len(files),MatchedFiles=len(pins),MatchedLines=len(matches),
    Hits={s:sum(s in r['Targets'] for r in matches) for s in targets}),ensure_ascii=False,indent=2))
