"""Verify the proposed UV edits in memory only, after manual shader review."""
import collections
import importlib.util
import re
import struct
from pathlib import Path

OUT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('analysis', OUT / 'analyze.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
d = a.d
baseline = a.check_runtime()
files = d.load(OUT / 'uv-files.json')
flat = d.load(OUT / 'collapsed-uv.json')
pins = d.load(OUT / 'source-pins.json')
allowed = {'court','court_alpha_to_coverage','portrait_attachment','portrait_attachment_alpha_to_coverage'}
for item in flat:
    assert int(item['Channel'][1:]) > 0
    for setting in item['Settings']:
        assert setting['Shader'] in allowed
        assert not re.search(r'\bdefines\s*=|\bUV[1-9]\b', setting['Body'], re.I)

# Record the effective sources and small, exact evidence excerpts. This is not a
# general shader compiler: the four relevant effect branches were read manually.
excerpt_specs = [
    (d.AGOT / 'gfx/FX/jomini/portrait.shader', [(153,180),(240,250),(789,817),(1485,1493),(1582,1591)]),
    (d.AGOT / 'gfx/FX/court_scene.shader', [(2014,2025),(2038,2048),(2058,2085),(2089,2115),(2719,2742)]),
    (d.GAME.parent / 'clausewitz/gfx/FX/cw/pdxmesh.fxh', [(12,43),(145,160)]),
    (d.GAME.parent / 'clausewitz/gfx/FX/cw/pdxmesh_buffers.fxh', [(1,20)]),
]
excerpts = []
for path, intervals in excerpt_specs:
    pins[str(path)] = d.sha(path)
    lines = d.read(path).splitlines()
    excerpts.append(f'FILE: {path}\nSHA256: {d.sha(path)}')
    for lo, hi in intervals:
        excerpts.extend(f'{i+1}: {lines[i]}' for i in range(lo-1,hi))
(OUT / 'shader-evidence.txt').write_text('\n'.join(excerpts)+'\n',encoding='utf-8', newline='\n')

proposal = []
for f in files:
    raw = d.native(f['Source']).read_bytes()
    assert a.sha_bytes(raw) == f['SHA256']
    nodes = a.parse_spans(raw)
    mesh_nodes = [n for n in nodes if n['Name'] == 'mesh']
    flat_by_mesh = collections.defaultdict(list)
    for item in flat:
        if item['File'] == f['File']: flat_by_mesh[item['GlobalMeshIndex']].append(item)
    removals = []
    for index, n in enumerate(mesh_nodes):
        items = flat_by_mesh[index]
        # Cut off only the trailing range from the first collapsed channel. This
        # also removes two unused u2 arrays on Night's Watch fur, avoiding gaps.
        threshold = min([int(x['Channel'][1:]) for x in items] or [3])
        for p in n['Properties']:
            if not re.fullmatch(r'u\d+',p['Name']) or int(p['Name'][1:]) < threshold: continue
            channel = int(p['Name'][1:])
            why = 'unsupported_fourth_channel' if channel >= 3 else (
                'collapsed_unused_channel' if any(x['Channel']==p['Name'] for x in items) else 'unused_tail_avoid_channel_gap')
            removals.append(dict(MeshIndex=index, Channel=p['Name'], Start=p['Start'], End=p['End'], Reason=why))
    assert removals, f['File']
    candidate = raw
    for p in sorted(removals,key=lambda p:p['Start'],reverse=True): candidate = candidate[:p['Start']] + candidate[p['End']:]
    after = a.parse_spans(candidate)
    removed_starts = {p['Start'] for p in removals}
    expected = [(n['Name'],n['Depth'],n['Parent'],[(p['Name'],a.sha_bytes(raw[p['Start']:p['End']]))
                 for p in n['Properties'] if p['Start'] not in removed_starts]) for n in nodes]
    assert expected == a.fingerprints(candidate,after)
    assert [raw[n['Start']:n['End']] for n in nodes] == [candidate[n['Start']:n['End']] for n in after]
    for n in after:
        if n['Name'] != 'mesh': continue
        props = {p['Name']:p for p in n['Properties']}
        channels = [p for p in n['Properties'] if re.fullmatch(r'u\d+',p['Name'])]
        assert [p['Name'] for p in channels] == ['u'+str(i) for i in range(len(channels))]
        assert len(channels) <= 3
        if not channels: continue
        p = props['tri']
        tri = struct.unpack('<'+'i'*p['Count'],candidate[p['DataStart']:p['End']])
        for p in channels:
            vals = struct.unpack('<'+'f'*p['Count'],candidate[p['DataStart']:p['End']])
            pairs = list(zip(vals[::2],vals[1::2]))
            valid = False
            for j in range(0,len(tri),3):
                x,y,z = [pairs[i] for i in tri[j:j+3]]
                if (y[0]-x[0])*(z[1]-x[1]) != (y[1]-x[1])*(z[0]-x[0]):
                    valid=True
                    break
            assert valid, (f['File'],n['Name'],p['Name'])
    proposal.append(dict(File=f['File'], SourceSHA256=f['SHA256'], CandidateSHA256=a.sha_bytes(candidate),
                         SourceBytes=len(raw), ProposedRemovedBytes=len(raw)-len(candidate), ProposedRemovalSpans=removals,
                         RemainingUVChannelsContiguous=True, AllRemainingUVChannelsHaveNonzeroTriangle=True,
                         AllOtherBytesUnchanged=True))
assert a.check_runtime() == baseline
summary = dict(Status='IN_MEMORY_PROPOSAL_VERIFIED_NOT_INSTALLED', Files=len(proposal),
               UVPropertiesToRemove=sum(len(f['ProposedRemovalSpans']) for f in proposal),
               ByReason=dict(collections.Counter(x['Reason'] for f in proposal for x in f['ProposedRemovalSpans'])),
               BytesToRemove=sum(f['ProposedRemovedBytes'] for f in proposal),
               SourceBytes=sum(f['SourceBytes'] for f in proposal),
               RuntimeFilesUnchanged=len(baseline['Files']), NoRuntimeWrites=True, NoEngineValidation=True)
a.save('uv-proposal.json', proposal)
a.save('proposal-validation.json', summary)
a.save('source-pins.json', pins)
print(summary)
