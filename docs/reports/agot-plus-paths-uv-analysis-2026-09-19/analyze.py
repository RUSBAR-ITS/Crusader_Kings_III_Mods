"""Read-only runtime investigation; writes evidence only inside this report.

No descriptors, registry, installed mods or launcher settings are changed.
UV candidate bytes exist only in memory; binary input is never re-exported.
"""
import collections
import csv
import ctypes
from ctypes import wintypes as wt
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import sys
import winreg

sys.stdout.reconfigure(encoding='utf-8')
OUT = Path(__file__).resolve().parent
REPO = OUT.parents[2]
spec = importlib.util.spec_from_file_location('dna9', REPO / 'AGOT_Submods/AGOT_PLUS_FIX/tools/DNA-Stage9.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
RUN = OUT.parent / 'ck3-agot-plus-fix-stage12-log-2026-09-19'
PINS = {}


def sha_bytes(raw):
    return hashlib.sha256(raw).hexdigest().upper()


def pin(path):
    PINS[str(path)] = d.sha(path)


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def load_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def check_runtime():
    manifest_path = d.MOD / 'docs/source-manifest.json'
    pin(manifest_path)
    manifest = d.load(manifest_path)
    assert manifest['Revision'] == 12
    for f in manifest['Files']:
        assert d.sha(d.MOD / f['File']) == f['PatchedSHA256'], f['File']
    return manifest


def paths(manifest):
    # Load CK3's PE as a data file: does not execute any application code.
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p, wt.DWORD, wt.DWORD, wt.HANDLE]
    k.CreateFileW.restype = wt.HANDLE
    k.GetFileAttributesW.argtypes = [wt.LPCWSTR]
    k.GetFileAttributesW.restype = wt.DWORD
    k.ReadFile.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD), ctypes.c_void_p]
    k.ReadFile.restype = wt.BOOL
    k.CloseHandle.argtypes = [wt.HANDLE]
    k.CloseHandle.restype = wt.BOOL

    def probe(path):
        result = {}
        for kind, name in [('ordinary', str(path)), ('extended', str(d.native(path)))]:
            ctypes.set_last_error(0)
            attrs = k.GetFileAttributesW(name)
            ae = ctypes.get_last_error() if attrs == 0xFFFFFFFF else 0
            ctypes.set_last_error(0)
            h = k.CreateFileW(name, 0x80000000, 7, None, 3, 0x80, None)
            error = ctypes.get_last_error() if h == ctypes.c_void_p(-1).value else 0
            ok, prefix = not error, None
            if ok:
                try:
                    buffer = ctypes.create_string_buffer(16)
                    count = wt.DWORD()
                    assert k.ReadFile(h, buffer, 16, ctypes.byref(count), None)
                    prefix = buffer.raw[:count.value].hex()
                    assert bytes.fromhex(prefix) == d.native(path).read_bytes()[:16]
                finally:
                    k.CloseHandle(h)
            result[kind] = dict(AttributesError=ae, OpenError=error, OpenOK=ok, FirstBytes=prefix)
        return result

    manifest_exe = d.GAME.parent / 'binaries/ck3.exe'
    pin(manifest_exe)
    k.LoadLibraryExW.argtypes = [wt.LPCWSTR, wt.HANDLE, wt.DWORD]
    k.LoadLibraryExW.restype = wt.HMODULE
    k.FindResourceW.argtypes = [wt.HMODULE, ctypes.c_void_p, ctypes.c_void_p]
    k.FindResourceW.restype = ctypes.c_void_p
    k.SizeofResource.argtypes = [wt.HMODULE, ctypes.c_void_p]
    k.SizeofResource.restype = wt.DWORD
    k.LoadResource.argtypes = [wt.HMODULE, ctypes.c_void_p]
    k.LoadResource.restype = ctypes.c_void_p
    k.LockResource.argtypes = [ctypes.c_void_p]
    k.LockResource.restype = ctypes.c_void_p
    k.FreeLibrary.argtypes = [wt.HMODULE]
    handle = k.LoadLibraryExW(str(manifest_exe), None, 2)
    assert handle
    manifests = []
    try:
        for resource_id in (1, 2, 3):
            res = k.FindResourceW(handle, ctypes.c_void_p(resource_id), ctypes.c_void_p(24))
            if not res:
                continue
            size = k.SizeofResource(handle, res)
            data = ctypes.string_at(k.LockResource(k.LoadResource(handle, res)), size)
            text = data.decode('utf-8-sig')
            (OUT / f'ck3-embedded-manifest-{resource_id}.xml').write_text(text, encoding='utf-8')
            manifests.append(dict(ResourceID=resource_id, LongPathAwareElement='longPathAware' in text, Text=text))
    finally:
        k.FreeLibrary(handle)
    pin(manifest_exe.with_suffix('.exe.manifest'))
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\FileSystem') as key:
        long_paths = winreg.QueryValueEx(key, 'LongPathsEnabled')[0]

    all_files = []
    for f in manifest['Files']:
        path = d.MOD / f['File']
        all_files.append(dict(File=f['File'], AbsolutePathLength=len(str(path)), Probe=probe(path)))
    targets = d.load(RUN / 'resource-path-investigation.json')['Files']
    for f in targets:
        f['FixProbe'] = probe(d.MOD / f['File'])
        f['WorkshopPathLength'] = len(str(d.PLUS / f['File']))
        f['WorkshopProbe'] = probe(d.PLUS / f['File'])
    result = dict(LongPathsEnabled=long_paths, CK3EmbeddedManifests=manifests,
                  ExternalManifestLongPathAware='longPathAware' in d.read(manifest_exe.with_suffix('.exe.manifest')),
                  Files=all_files, RepairTargets=targets,
                  RuntimeFileCount=len(all_files),
                  OrdinaryOpenFailures=[f['File'] for f in all_files if not f['Probe']['ordinary']['OpenOK']],
                  ExtendedOpenFailures=[f['File'] for f in all_files if not f['Probe']['extended']['OpenOK']],
                  Caveat='Win32 probes run in this Python process, not CK3. No engine file-open trace or short-path game run was performed.')
    save('path-probes.json', result)
    print('PATHS', json.dumps({k:v for k,v in result.items() if k in ('LongPathsEnabled','RuntimeFileCount','OrdinaryOpenFailures','ExtendedOpenFailures')}))


def parse_spans(raw):
    """Index PDX tokens without modifying numeric representations or property order."""
    assert raw[:4] == b'@@b@'
    pos, stack = 4, [0]
    result = [dict(Name='File', Depth=0, Parent=None, Start=0, End=4, Properties=[])]
    while pos < len(raw):
        start = pos
        if raw[pos] == 91:
            depth = 0
            while raw[pos] == 91:
                depth += 1
                pos += 1
            end = raw.index(b'\0', pos)
            name = raw[pos:end].decode('latin-1')
            assert 1 <= depth <= len(stack)
            stack = stack[:depth]
            parent = stack[-1]
            node = dict(Name=name, Depth=depth, Parent=parent, Start=start, End=end + 1, Properties=[])
            result.append(node)
            stack.append(len(result) - 1)
            pos = end + 1
        else:
            assert raw[pos] == 33 and stack, (pos, raw[pos:pos+20])
            length = raw[pos+1]
            name = raw[pos+2:pos+2+length].decode('latin-1')
            pos += 2 + length
            kind = chr(raw[pos])
            count = struct.unpack_from('<i', raw, pos+1)[0]
            assert count >= 0
            pos += 5
            data_start = pos
            if kind in ('i', 'f'):
                pos += count * 4
            elif kind == 's':
                assert count == 1
                length = struct.unpack_from('<i', raw, pos)[0]
                assert length > 0
                pos += 4 + length
            else:
                raise AssertionError((name, kind, pos))
            assert pos <= len(raw)
            result[stack[-1]]['Properties'].append(dict(Name=name, Kind=kind, Count=count, Start=start, DataStart=data_start, End=pos))
    assert pos == len(raw)
    return result


def fingerprints(raw, nodes, omit_extras=False):
    return [(n['Name'], n['Depth'], n['Parent'],
             [(p['Name'], sha_bytes(raw[p['Start']:p['End']])) for p in n['Properties']
              if not (omit_extras and n['Name'] == 'mesh' and re.fullmatch(r'u\d+', p['Name']) and int(p['Name'][1:]) >= 3)]) for n in nodes]


def uv():
    rows_path = RUN / 'remaining-mesh_uv.csv'
    pin(rows_path)
    log_rows = load_csv(rows_path)
    messages = collections.Counter(row['Files'] for row in log_rows)
    excess_messages = collections.Counter(row['Files'] for row in log_rows if 'more than 3 UV channels' in row['Message'])
    mods = d.active_mods()
    reader = OUT.parent / 'agot-plus-dna-remaining-analysis-2026-09-19/historical/pdx_data.py'
    pin(reader)
    ns = {'__name__': 'pdx_read_only'}
    exec(compile(reader.read_text(encoding='utf-8').replace('from .external import six', ''), str(reader), 'exec'), ns)
    files, all_channels = [], []
    for number, (rel, count) in enumerate(sorted(messages.items()), 1):
        source = None
        for mod in mods:
            if any(rel == r or rel.startswith(r.rstrip('/') + '/') for r in mod['Replace']):
                source = None
            if d.native(Path(mod['Path']) / rel).is_file():
                source = (mod, Path(mod['Path']) / rel)
        assert source is not None, rel
        mod, path = source
        pin(path)
        raw = d.native(path).read_bytes()
        nodes = parse_spans(raw)
        vendor = ns['read_meshfile'](str(d.native(path)))
        mesh_nodes = [n for n in nodes if n['Name'] == 'mesh']
        vendor_meshes = list(vendor.iter('mesh'))
        assert len(mesh_nodes) == len(vendor_meshes)
        removed, mesh_info = [], []
        for index, (node, vm) in enumerate(zip(mesh_nodes, vendor_meshes)):
            props = {p['Name']: p for p in node['Properties']}
            channels = [p for p in node['Properties'] if re.fullmatch(r'u\d+', p['Name'])]
            assert len(channels) == len([key for key in vm.attrib if re.fullmatch(r'u\d+', key)])
            if len(channels) <= 3:
                continue
            vertices = props['p']['Count'] // 3
            assert [p['Name'] for p in channels[:3]] == ['u0','u1','u2']
            channel_info = []
            for p in channels:
                assert p['Kind'] == 'f' and p['Count'] == vertices * 2
                payload = raw[p['DataStart']:p['End']]
                assert tuple(vm.attrib[p['Name']]) == struct.unpack('<' + 'f' * p['Count'], payload)
                identical = [q['Name'] for q in channels if q is not p and raw[q['DataStart']:q['End']] == payload]
                values = vm.attrib[p['Name']]
                entry = dict(File=rel, MeshIndex=index, Channel=p['Name'], Vertices=vertices,
                             PayloadSHA256=sha_bytes(payload), IdenticalChannels=identical,
                             Min=min(values), Max=max(values), UniqueUVPairs=len(set(zip(values[::2], values[1::2]))),
                             Start=p['Start'], End=p['End'], RemoveProposed=int(p['Name'][1:]) >= 3)
                channel_info.append(entry)
                all_channels.append(entry)
                if entry['RemoveProposed']:
                    removed.append(p)
            mesh_info.append(dict(MeshIndex=index, Object=nodes[node['Parent']]['Name'], Vertices=vertices,
                                  UVChannels=len(channels), Channels=channel_info,
                                  Materials=[m.attrib for m in vm.findall('material')]))
        # Offline proof: every other token/property, including float bit patterns,
        # remains identical. No output model is written or installed.
        candidate = raw
        for p in sorted(removed, key=lambda p:p['Start'], reverse=True):
            candidate = candidate[:p['Start']] + candidate[p['End']:]
        after = parse_spans(candidate)
        assert fingerprints(raw, nodes, True) == fingerprints(candidate, after)
        assert all(len([p for p in n['Properties'] if re.fullmatch(r'u\d+', p['Name'])]) <= 3 for n in after if n['Name'] == 'mesh')
        files.append(dict(File=rel, Source=str(path), Owner=mod['Name'], SHA256=sha_bytes(raw), Bytes=len(raw),
                          LoggedMessages=count, LoggedExcessChannelMessages=excess_messages[rel],
                          MeshCount=len(mesh_nodes), OffendingMeshCount=len(mesh_info), Meshes=mesh_info,
                          ProposedRemovedChannels=len(removed), ProposedRemovedBytes=len(raw)-len(candidate),
                          InMemoryCandidateSHA256=sha_bytes(candidate), AllOtherPropertiesBitIdentical=True,
                          WorkshopPathLength=len(str(path)), CurrentFixPathLength=len(str(d.MOD / rel)),
                          ExampleShortFixPathLength=len(str(Path('D:/CK3Mods/AGOT_PLUS_FIX') / rel))))
        print(f'UV {number}/{len(messages)}: {len(mesh_info)} meshes; {len(removed)} extra channels; {Path(rel).name}', flush=True)
    extras = [c for c in all_channels if c['RemoveProposed']]
    summary = dict(Files=len(files), LoggedMessages=sum(messages.values()), ExcessChannelFiles=sum(f['OffendingMeshCount']>0 for f in files),
                   LoggedExcessChannelMessages=sum(excess_messages.values()),
                   OffendingMeshes=sum(f['OffendingMeshCount'] for f in files),
                   ExcessMessageCountEqualsOffendingMeshesPerFile=all(f['LoggedExcessChannelMessages'] == f['OffendingMeshCount'] for f in files),
                   TotalMeshElements=sum(f['MeshCount'] for f in files),
                   ExtraChannels=len(extras),
                   ExtraChannelsBitIdenticalToRetained=sum(any(int(k[1:]) < 3 for k in c['IdenticalChannels']) for c in extras),
                   ExtraChannelsAllZero=sum(c['Min'] == c['Max'] == 0 for c in extras),
                   ExtraChannelsDistinctFromRetained=sum(not any(int(k[1:]) < 3 for k in c['IdenticalChannels']) for c in extras),
                   ProposedRemovedBytes=sum(f['ProposedRemovedBytes'] for f in files),
                   OffendingMeshesByChannelCount=dict(collections.Counter(m['UVChannels'] for f in files for m in f['Meshes'])),
                   CurrentFixPathsAtLeast260=sum(f['CurrentFixPathLength'] >= 260 for f in files),
                   MaxCurrentFixPathLength=max(f['CurrentFixPathLength'] for f in files),
                   MaxExampleShortFixPathLength=max(f['ExampleShortFixPathLength'] for f in files),
                   SourcesByOwner=dict(collections.Counter(f['Owner'] for f in files)),
                   AllNonExtraUVPropertiesBitIdentical=True, BinaryCandidatesInstalled=False,
                   EngineCheckPerformed=False)
    save('uv-files.json', files)
    save('uv-summary.json', summary)
    with (OUT / 'uv-channels.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(all_channels[0]))
        writer.writeheader()
        writer.writerows(all_channels)
    print('UV SUMMARY', json.dumps(summary))


if __name__ == '__main__':
    baseline = check_runtime()
    paths(baseline)
    uv()
    assert check_runtime() == baseline
    save('source-pins.json', PINS)
    save('validation.json', dict(Status='RESEARCH_ONLY', RuntimeRevision=12, RuntimeFilesUnchanged=len(baseline['Files']),
                                 InstalledModelsModified=0, RegistryModified=False, DescriptorsModified=False))
