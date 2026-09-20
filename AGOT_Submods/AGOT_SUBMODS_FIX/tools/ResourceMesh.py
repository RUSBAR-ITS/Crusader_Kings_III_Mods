"""Apply bounded PDX UV edits; preserve every other token and numeric byte.

The span reader is shared in design with the previously verified AGOT+ UV
investigation. This module has no dependency on AGOT+ or external packages.
"""
import math
import re
import struct


def parse_spans(raw):
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
            result.append(dict(Name=name, Depth=depth, Parent=stack[-1], Start=start, End=end+1, Properties=[]))
            stack.append(len(result)-1)
            pos = end+1
        else:
            assert raw[pos] == 33 and stack
            length = raw[pos+1]
            name = raw[pos+2:pos+2+length].decode('latin-1')
            pos += 2+length
            kind = chr(raw[pos])
            count = struct.unpack_from('<i', raw, pos+1)[0]
            assert count >= 0
            pos += 5
            data_start = pos
            if kind in ('i', 'f'):
                pos += count*4
            elif kind == 's':
                assert count == 1
                length = struct.unpack_from('<i', raw, pos)[0]
                assert length > 0
                pos += 4+length
            else:
                raise AssertionError((name, kind, pos))
            assert pos <= len(raw)
            result[stack[-1]]['Properties'].append(dict(Name=name, Kind=kind, Count=count, Start=start, DataStart=data_start, End=pos))
    assert pos == len(raw)
    return result


def has_area(raw, mesh, prop):
    triangles = next(p for p in mesh['Properties'] if p['Name'] == 'tri')
    tri = struct.unpack_from('<'+'i'*triangles['Count'], raw, triangles['DataStart'])
    assert prop['Kind'] == 'f' and prop['Count'] % 2 == 0 and len(tri) % 3 == 0
    uv = struct.unpack_from('<'+'f'*prop['Count'], raw, prop['DataStart'])
    assert all(math.isfinite(v) for v in uv)
    assert all(0 <= i < len(uv)//2 for i in tri)
    for i in range(0, len(tri), 3):
        x, y, z = [uv[2*j:2*j+2] for j in tri[i:i+3]]
        if (y[0]-x[0])*(z[1]-x[1]) != (y[1]-x[1])*(z[0]-x[0]):
            return True
    return False


def repair(raw, recipes):
    nodes = parse_spans(raw)
    meshes = [n for n in nodes if n['Name'] == 'mesh']
    changes, removed, replaced = [], set(), {}
    seen = set()
    for row in recipes:
        index = row['MeshIndex']
        assert index not in seen
        seen.add(index)
        mesh = meshes[index]
        part = nodes[mesh['Parent']]['Name']
        assert part == row['Part']
        assert sum(nodes[m['Parent']]['Name'] == part for m in meshes[:index]) == row['NamedIndex']
        props = {p['Name']:p for p in mesh['Properties']}
        if row['Action'] == 'remove_unused_tail':
            channels = sorted(int(k[1:]) for k in props if re.fullmatch(r'u\d+', k))
            first = min(int(k[1:]) for k in row['Remove'])
            assert row['Remove'] == [f'u{i}' for i in channels if i >= first]
            assert first >= (2 if 'standard_atlas' in row['Shaders'] else 1)
            assert set(row['Shaders']) <= {'standard', 'standard_winter', 'standard_atlas'}
            for channel in row['Remove']:
                p = props[channel]
                if channel in row['BadChannels'] and channel != 'u3':
                    assert not has_area(raw, mesh, p)
                removed.add(p['Start'])
                changes.append((p['Start'], p['End'], b''))
        else:
            assert row['Action'] in ('copy_u1_to_u0_constant_ao', 'copy_u1_to_u0_visible_metal')
            assert row['BadChannels'] == ['u0'] and not row['Remove']
            a, b = props['u0'], props['u1']
            assert a['Kind'] == b['Kind'] == 'f' and a['Count'] == b['Count']
            assert not has_area(raw, mesh, a) and has_area(raw, mesh, b)
            replacement = raw[b['DataStart']:b['End']]
            replaced[a['Start']] = raw[a['Start']:a['DataStart']]+replacement
            changes.append((a['DataStart'], a['End'], replacement))
    candidate, last = raw, len(raw)+1
    for start, end, data in sorted(changes, reverse=True):
        assert 0 <= start < end <= last
        candidate = candidate[:start]+data+candidate[end:]
        last = start
    after = parse_spans(candidate)
    assert len(nodes) == len(after)
    for before_node, after_node in zip(nodes, after):
        assert all(before_node[k] == after_node[k] for k in ('Name', 'Depth', 'Parent'))
        assert raw[before_node['Start']:before_node['End']] == candidate[after_node['Start']:after_node['End']]
        kept = [p for p in before_node['Properties'] if p['Start'] not in removed]
        assert len(kept) == len(after_node['Properties'])
        for old, new in zip(kept, after_node['Properties']):
            assert replaced.get(old['Start'], raw[old['Start']:old['End']]) == candidate[new['Start']:new['End']]
    for index in seen:
        mesh = [n for n in after if n['Name'] == 'mesh'][index]
        channels = [p for p in mesh['Properties'] if re.fullmatch(r'u\d+', p['Name'])]
        assert [p['Name'] for p in channels] == [f'u{i}' for i in range(len(channels))]
        assert 0 < len(channels) <= 3
        count = next(p['Count']//3 for p in mesh['Properties'] if p['Name'] == 'p')
        for p in channels:
            assert p['Count'] == 2*count and has_area(candidate, mesh, p)
    return candidate
