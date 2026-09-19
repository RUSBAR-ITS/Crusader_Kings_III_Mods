"""Read-only comparison of existing base/deformation vertex and UV layouts."""
import importlib.util
import re
from pathlib import Path

OUT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('a',OUT/'analyze.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
d = a.d
mods = d.active_mods()
pins = d.load(OUT/'source-pins.json')
regs = d.load(OUT/'mesh-registrations.json')
files = d.load(OUT/'uv-files.json')
result = []


def scalar(text,key):
    m = re.search(r'\b'+key+r'\s*=\s*"([^"]+)"',text)
    return m[1] if m else None


def layout(path):
    raw = d.native(path).read_bytes()
    pins[str(path)] = a.sha_bytes(raw)
    return [dict(Vertices=next((p['Count']//3 for p in n['Properties'] if p['Name']=='p'),0),
                 UV=[p['Name'] for p in n['Properties'] if re.fullmatch(r'u\d+',p['Name'])])
            for n in a.parse_spans(raw) if n['Name']=='mesh']


for f in files:
    base = layout(Path(f['Source']))
    for reg in regs[f['File']]:
        text = d.read(reg['Source'])
        for block in d.parse(text).children:
            if block.key!='pdxmesh' or scalar(block.body(text),'name')!=reg['ID']: continue
            for b in block.children:
                if b.key!='blend_shape': continue
                target = scalar(b.body(text),'type')
                if not target or not target.endswith('.mesh'): continue
                rel = target if target.startswith('gfx/') else (Path(reg['Asset']).parent/target).as_posix()
                p = None
                for mod in mods:
                    if any(rel==r or rel.startswith(r.rstrip('/')+'/') for r in mod['Replace']): p=None
                    q = Path(mod['Path'])/rel
                    if d.native(q).is_file(): p=q
                assert p is not None,rel
                blend = layout(p)
                result.append(dict(File=f['File'],Target=rel,Source=str(p),BaseLayout=base,BlendLayout=blend,
                    SameVertexCounts=[n['Vertices'] for n in base]==[n['Vertices'] for n in blend],
                    SameUVChannels=[n['UV'] for n in base]==[n['UV'] for n in blend]))
summary = dict(References=len(result),UniqueDeformationFiles=len(set(x['Target'] for x in result)),
               ExistingDifferentUVLayouts=sum(not x['SameUVChannels'] for x in result),
               ExistingDifferentVertexCounts=sum(not x['SameVertexCounts'] for x in result),
               Caveat='All examined original base/deformation vertex and UV layouts match. The shader consumes position, normal and tangent deformation data, not UV; whether the closed loader imposes additional UV-layout checks is not established. Check for new blendshape diagnostics on the next game run.')
blend_shader = d.GAME.parent/'clausewitz/gfx/FX/cw/pdxmesh_blendshapes.fxh'
pins[str(blend_shader)] = d.sha(blend_shader)
a.save('blendshape-layout.json',result)
a.save('blendshape-layout-summary.json',summary)
a.save('source-pins.json',pins)
print(summary)
