"""Read PDX binary records. Format cross-checked with ross-g/io_pdx_mesh.

Only records evidence. Does not convert, write or install models/animations.
"""
from pathlib import Path
import struct, json, hashlib
OUT=Path(__file__).resolve().parent
def read_pdx(path):
    data=path.read_bytes()
    assert data[:4]==b'@@b@', path
    pos=4
    root={'name':'root','props':{},'children':[]}
    stack=[root]
    while pos<len(data):
        if data[pos]==ord('['):
            depth=0
            while data[pos]==ord('['):depth+=1;pos+=1
            end=data.index(0,pos)
            node={'name':data[pos:end].decode('latin1'),'props':{},'children':[]}
            assert depth<=len(stack)
            stack=stack[:depth]
            stack[-1]['children'].append(node)
            stack.append(node);pos=end+1
        else:
            assert data[pos]==ord('!'),(path,pos)
            n=data[pos+1];pos+=2
            key=data[pos:pos+n].decode('latin1');pos+=n
            typ=chr(data[pos]);pos+=1
            n=struct.unpack_from('<i',data,pos)[0];pos+=4
            if typ in 'if':
                val=list(struct.unpack_from('<'+str(n)+typ,data,pos));pos+=4*n
            else:
                assert typ=='s' and n==1
                size=struct.unpack_from('<i',data,pos)[0];pos+=4
                val=[data[pos:pos+size].rstrip(b'\0').decode('latin1')];pos+=size
            stack[-1]['props'][key]=val
    return root
def nodes(n):
    yield n
    for c in n['children']:yield from nodes(c)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
report=[]
for sex in ('male','female'):
    current=Path('E:/SteamLibrary/steamapps/common/Crusader Kings III/game/gfx/models/portraits')/f'{sex}_head/{sex}_head.mesh'
    mesh=read_pdx(current)
    bones={n['name']:n['props'] for n in nodes(mesh) if n['name'].startswith('bn_h_') or n['name']=='head_root'}
    for anim in sorted((OUT/'historical').glob('shogunate-2023-'+sex+'*.anim')):
        parsed=read_pdx(anim)
        old={n['name']:n['props'] for n in nodes(parsed) if n['name'].startswith('bn_h_') or n['name']=='head_root'}
        animated={k:v for k,v in old.items() if v.get('sa') not in (None,[''])}
        report.append(dict(File=anim.name,SHA256=sha(anim),CurrentMesh=str(current),MeshSHA256=sha(current),
            Info=next(n['props'] for n in nodes(parsed) if n['name']=='info'),
            BoneCount=len(old),MissingBones=sorted(set(old)-set(bones)),
            AnimationBoneProperties=old,SampleArrays={k:len(v) for n in nodes(parsed) if n['name']=='samples' for k,v in n['props'].items()}))
        print(anim.name,'bones',len(old),'missing',len(set(old)-set(bones)), 'info',report[-1]['Info'])
(OUT/'animation-structure.json').write_text(json.dumps(report,indent=2)+'\n', newline='\n')
