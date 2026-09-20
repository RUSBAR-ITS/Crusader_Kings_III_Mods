"""Read-only inspection. Writes evidence exclusively beside this script."""
from pathlib import Path
from collections import Counter, defaultdict
import csv, gzip, hashlib, importlib.util, json, math, re, struct, subprocess, sys

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
LOG=HERE.parent/'ck3-agot-submods-fix-stage1-log-2026-09-20'
sys.path.insert(0,str(REPO/'AGOT_Submods/AGOT_SUBMODS_FIX/tools'))
from ScriptBlocks import parse, walk, one, semantic
sys.stdout.reconfigure(encoding='utf-8')

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
d=module('resource_paths',REPO/'AGOT_Submods/AGOT_PLUS_FIX/tools/DNA-Stage9.py')
a=module('resource_mesh',HERE.parent/'agot-plus-paths-uv-analysis-2026-09-19/analyze.py')
pins={}
def raw(p):
    p=Path(p);b=p.read_bytes();pins[str(p)]=dict(SHA256=hashlib.sha256(b).hexdigest(),Bytes=len(b));return b
def read(p):return raw(p).decode('utf-8-sig')
def save(name,value):
    (HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def rows(cat):return list(csv.DictReader((LOG/f'remaining-{cat}.csv').open(encoding='utf-8-sig')))
def value(n,k,default=None):
    found=n.children(k)
    return found[0].value.strip('"') if found and isinstance(found[0].value,str) else default
def prop_values(b,p):
    if p['Kind']=='s':
        length=struct.unpack_from('<i',b,p['DataStart'])[0]
        return b[p['DataStart']+4:p['DataStart']+4+length].rstrip(b'\0').decode('latin-1')
    return struct.unpack_from('<'+p['Kind']*p['Count'],b,p['DataStart'])

def index():
    mods=d.active_mods();effective={}
    for mod in mods:
        for prefix in mod['Replace']:
            effective={k:v for k,v in effective.items() if not (k==prefix or k.startswith(prefix.rstrip('/')+'/'))}
        root=Path(mod['Path'])
        paths=subprocess.run(['rg','--files','--hidden',str(root)],capture_output=True,check=True).stdout.decode('utf-8').splitlines()
        for path in map(Path,paths):
            rel=path.relative_to(root).as_posix()
            if rel.split('/')[0] in ('gfx','common','events','history','localization','gui'):
                effective[rel]=dict(Path=str(path),Owner=mod['Name'],Relative=rel)
    save('active-mods.json',mods)
    (HERE/'effective-files.json.gz').write_bytes(gzip.compress(json.dumps(effective,ensure_ascii=False).encode('utf-8'),mtime=0))
    return effective

def meshes(effective):
    wanted={}
    for row in rows('mesh_uv')+rows('mesh_settings'):
        match=re.search(r"(?:file '([^']+)'|file: (.+?)(?:\s*$)|Asset \"([^\"]+)\")",row['Message'])
        if match:
            rel=next(x for x in match.groups() if x);wanted.setdefault(rel,[]).append(row)
    registrations=defaultdict(list)
    for rel,item in effective.items():
        if not rel.endswith('.asset') or not rel.startswith('gfx/models/buildings/'):continue
        text=read(item['Path'])
        for n in parse(text):
            if n.key!='pdxmesh':continue
            file=value(n,'file','')
            resolved=file if file.startswith('gfx/') else (Path(rel).parent/file).as_posix()
            if resolved not in wanted:continue
            settings=[]
            for child in n.children('meshsettings'):
                settings.append(dict(Name=value(child,'name'),Index=value(child,'index'),Shader=value(child,'shader'),
                                     Body=text[child.start:child.end]))
            registrations[resolved].append(dict(Path=item['Path'],Name=value(n,'name'),Settings=settings))
    output=[]
    for rel,messages in wanted.items():
        path=effective[rel]['Path'];b=raw(path);nodes=a.parse_spans(b);parts=[];named_counts=Counter()
        for i,n in enumerate(nodes):
            if n['Name']!='mesh':continue
            properties={p['Name']:p for p in n['Properties']}
            pos=prop_values(b,properties['p']) if 'p' in properties else []
            tri=prop_values(b,properties['tri']) if 'tri' in properties else []
            name=nodes[n['Parent']]['Name']
            named_index=named_counts[name];named_counts[name]+=1
            channels=[]
            for key,p in properties.items():
                if not re.fullmatch('u[0-9]+',key):continue
                uv=prop_values(b,p);finite=all(math.isfinite(x) for x in uv)
                areas=[]
                for j in range(0,len(tri),3):
                    x,y,z=[uv[2*v:2*v+2] for v in tri[j:j+3]]
                    areas.append(abs((y[0]-x[0])*(z[1]-x[1])-(y[1]-x[1])*(z[0]-x[0])))
                channels.append(dict(Name=key,Pairs=len(uv)//2,UniquePairs=len(set(zip(uv[::2],uv[1::2]))),
                                     Finite=finite,NonzeroTriangles=sum(x>0 for x in areas),
                                     MaxTwiceArea=max(areas,default=0),Start=p['Start'],End=p['End']))
            materials=[{p['Name']:prop_values(b,p) for p in c['Properties']}
                       for c in nodes if c['Parent']==i and c['Name']=='material']
            matching=[s for r in registrations[rel] for s in r['Settings'] if s['Name']==name and
                      (s['Index'] is None or int(s['Index'])==named_index)]
            parts.append(dict(Name=name,MeshIndex=len(parts),NamedIndex=named_index,Vertices=len(pos)//3,Triangles=len(tri)//3,
                              Channels=channels,Materials=materials,MatchingSettings=matching))
        output.append(dict(File=rel,Path=path,Parts=parts,Registrations=registrations[rel],
                           Diagnostics=[r['Message'] for r in messages]))
    save('mesh-evidence.json',output)
    settings=[]
    for r in rows('mesh_settings'):
        m=re.fullmatch(r'pdxmesh \[(.+?)\] is out of sync with its meshsettings. \[(.+?)\] is not in use in file: (.+)',r['Message'])
        name,unused,rel=m.groups();record=next(v for v in output if v['File']==rel)
        registrations_for_name=[v for v in record['Registrations'] if v['Name']==name]
        settings.append(dict(Line=r['Line'],File=rel,Pdxmesh=name,Setting=unused,
                             PresentInGeometry=unused in [v['Name'] for v in record['Parts']],
                             MatchingRegistrations=registrations_for_name))
    save('meshsettings-evidence.json',settings)
    print('Meshes:',len(output),'settings diagnostics:',len(settings),'settings actually in geometry:',sum(v['PresentInGeometry'] for v in settings))
    print('UV diagnostic channels:',Counter(re.search(r'UV-Set: (\d+)',r['Message'])[1] for r in rows('mesh_uv') if 'UV-Set' in r['Message']))

def duplicates(effective):
    output=[]
    for r in rows('texture_duplicates'):
        match=re.search(r"current path '([^']+)', previous path '([^']+)'",r['Message'])
        current,previous=match.groups()
        b1,b2=raw(effective[current]['Path']),raw(effective[previous]['Path'])
        folder=Path(current).parent.as_posix()
        inventory=[v for k,v in effective.items() if k.startswith(folder+'/')]
        output.append(dict(Line=r['Line'],Duplicate=effective[current],Canonical=effective[previous],
                           Identical=b1==b2,FolderInventory=inventory))
    save('duplicate-evidence.json',output)
    print('Textures identical:',sum(r['Identical'] for r in output),'of',len(output))

if __name__=='__main__':
    effective=index()
    meshes(effective);duplicates(effective)
    save('source-evidence.json',pins)
