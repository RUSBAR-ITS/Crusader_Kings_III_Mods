"""Inspect the second UV diagnostic: collapsed texture-streaming coordinates."""
import collections
import importlib.util
import json
from pathlib import Path
import re
import struct

OUT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('analysis', OUT / 'analyze.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
d = a.d
mods = d.active_mods()
pins = d.load(OUT / 'source-pins.json')


def pin(path):
    pins[str(path)] = d.sha(path)


def scalar(text, key, default=None):
    text = re.sub(r'#[^\r\n]*', '', text)
    m = re.search(r'\b' + re.escape(key) + r'\s*=\s*("[^"]*"|[^\s{}]+)', text)
    return m[1].strip('"') if m else default


def effective(rel):
    # Shader files may originate in the engine's virtual roots as well as game/.
    found = None
    for root in (d.GAME.parent / 'clausewitz', d.GAME.parent / 'jomini', d.GAME):
        if (root / rel).is_file(): found = root / rel
    for mod in mods:
        if any(rel == x or rel.startswith(x.rstrip('/') + '/') for x in mod['Replace']): found = None
        p = Path(mod['Path']) / rel
        if d.native(p).is_file(): found = p
    assert found, rel
    return found


rows = a.load_csv(a.RUN / 'remaining-mesh_uv.csv')
files = d.load(OUT / 'uv-files.json')
flat_rows = [r for r in rows if 'texture streaming factor' in r['Message']]
flat_files = {r['Files'] for r in flat_rows}
wanted = {f['File'] for f in files}
names = {Path(f).name for f in wanted}
assets = {}
for mod in mods:
    for replace in mod['Replace']:
        assets = {k:v for k,v in assets.items() if not (k == replace or k.startswith(replace.rstrip('/') + '/'))}
    root = d.native(mod['Path'])
    for p in (root / 'gfx/models').rglob('*.asset'):
        assets[p.relative_to(root).as_posix()] = (mod, p)

registrations = collections.defaultdict(list)
for asset_rel, (mod, p) in assets.items():
    text = d.read(p)
    if not any(n in text for n in names): continue
    for b in d.parse(text).children:
        if b.key != 'pdxmesh': continue
        body = b.body(text)
        filename = scalar(body, 'file')
        if not filename or Path(filename).name not in names: continue
        mesh_rel = filename if filename.startswith('gfx/') else (Path(asset_rel).parent / filename).as_posix()
        if mesh_rel not in wanted: continue
        pin(p)
        registrations[mesh_rel].append(dict(Asset=asset_rel, Source=str(p), Owner=mod['Name'], ID=scalar(body,'name'),
            Settings=[dict(Name=scalar(c.body(text),'name'), Index=int(scalar(c.body(text),'index','0')),
                           Shader=scalar(c.body(text),'shader'), ShaderFile=scalar(c.body(text),'shader_file'),
                           Body=c.body(text)) for c in b.children if c.key == 'meshsettings']))

flat = []
for f in files:
    raw = d.native(f['Source']).read_bytes()
    nodes = a.parse_spans(raw)
    object_indices = collections.Counter()
    for mesh_index, n in enumerate(n for n in nodes if n['Name'] == 'mesh'):
        object_name = nodes[n['Parent']]['Name']
        index = object_indices[n['Parent']]
        object_indices[n['Parent']] += 1
        props = {p['Name']:p for p in n['Properties']}
        def values(p): return struct.unpack('<' + p['Kind'] * p['Count'], raw[p['DataStart']:p['End']])
        if 'tri' not in props: continue
        tri = values(props['tri'])
        uv = {k:values(p) for k,p in props.items() if re.fullmatch(r'u\d+',k)}
        for key, coords in uv.items():
            pairs = list(zip(coords[::2], coords[1::2]))
            areas = []
            for j in range(0,len(tri),3):
                x,y,z = [pairs[t] for t in tri[j:j+3]]
                areas.append(abs((y[0]-x[0])*(z[1]-x[1])-(y[1]-x[1])*(z[0]-x[0])))
            if any(areas): continue
            selected = []
            for registration in registrations[f['File']]:
                for setting in registration['Settings']:
                    if setting['Name'] == object_name and setting['Index'] == index:
                        selected.append(dict(ID=registration['ID'], Asset=registration['Asset'], **setting))
            assert selected, (f['File'],object_name,index)
            flat.append(dict(File=f['File'], GlobalMeshIndex=mesh_index, Object=object_name, ObjectMeshIndex=index,
                             Channel=key, VertexCount=len(pairs), UniqueUVPairs=len(set(pairs)),
                             ConstantUV=pairs[0] if len(set(pairs))==1 else None,
                             TriangleCount=len(tri)//3, MaxUVTriangleDoubleArea=max(areas),
                             ChannelNames=list(uv), Settings=selected, Start=props[key]['Start'], End=props[key]['End']))

expected = collections.Counter()
for f in flat:
    expected[(f['File'], f['Object'], int(f['Channel'][1:]))] += len(f['Settings'])
actual = collections.Counter()
for row in flat_rows:
    match = re.search(r"UV-Set: (\d+) in mesh '([^']+)'", row['Message'])
    actual[(row['Files'], match[2], int(match[1]))] += 1
assert not (actual - expected), actual - expected
assert collections.Counter({k:v for k,v in expected.items() if k in actual}) == actual
for item in flat:
    item['AlreadyLogged'] = (item['File'],item['Object'],int(item['Channel'][1:])) in actual

shader_files = {}
for f in flat:
    for s in f['Settings']:
        rel = s['ShaderFile']
        if rel not in shader_files:
            path = effective(rel)
            pin(path)
            shader_files[rel] = dict(Source=str(path), SHA256=d.sha(path), Effects=[])
        if s['Shader'] not in shader_files[rel]['Effects']:
            shader_files[rel]['Effects'].append(s['Shader'])

summary = dict(LoggedExcessUV=sum('more than 3' in r['Message'] for r in rows), LoggedCollapsedUV=len(flat_rows),
               LoggedCollapsedFiles=len(flat_files), LoggedCollapsedUniqueChannels=sum(x['AlreadyLogged'] for x in flat),
               TotalCollapsedFiles=len(set(x['File'] for x in flat)), TotalCollapsedUniqueChannels=len(flat),
               AdditionalUnloggedCollapsedChannels=sum(not x['AlreadyLogged'] for x in flat),
               CollapsedMessagesExplainedByMeshsettingsRegistrationCount=not bool(actual-expected),
               AllLoggedCollapsedChannelsConstantPoints=all(x['UniqueUVPairs']==1 for x in flat if x['AlreadyLogged']), Materials=shader_files,
               CollapsedByFile=dict(collections.Counter(f['File'] for f in flat)))
a.save('mesh-registrations.json',registrations)
a.save('collapsed-uv.json',flat)
a.save('collapsed-summary.json',summary)
a.save('source-pins.json',pins)
print(json.dumps(summary, indent=2))
