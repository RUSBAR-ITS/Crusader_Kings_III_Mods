"""Read-only follow-up to Analyze.py. No game or mod files are written.

Optional Pillow is needed only for decoded DDS comparisons. Pass its import
directory with --pillow-dir when it is installed outside the active interpreter.
"""
from pathlib import Path
import argparse, collections, csv, gzip, hashlib, io, json, re, struct, sys
import Analyze as a

parser=argparse.ArgumentParser()
parser.add_argument('--pillow-dir')
args=parser.parse_args()
if args.pillow_dir:sys.path.insert(0,args.pillow_dir)
from PIL import Image, ImageChops

e=json.loads(gzip.decompress((a.HERE/'effective-files.json.gz').read_bytes()))
a.pins=json.loads((a.HERE/'source-evidence.json').read_text(encoding='utf-8'))
def readrel(rel):return a.read(e[rel]['Path'])

# Script references including commented author intentions, in the effective VFS.
pattern=re.compile(r'burge_sprawl|alicent_dress_0[34]|lucerys_gun|'
    r'artifact_monthly_piety_negative_1_modifier|artifact_monthly_martial_lifestyle_xp_1_negative_modifier|'
    r'feature_dragon_whip_(black|silver|bronze)|show_notifications_decision|'
    r'b_graced_castle|b_cheesemongers?_manse|Gardener_75|ethiopian_atlas_diffuse\.dds')
hits=[]
for rel,v in e.items():
    if not rel.endswith(('.txt','.asset','.yml')):continue
    if rel.startswith('localization/') and not any(x in rel for x in ('english','russian')):continue
    text=Path(v['Path']).read_text(encoding='utf-8-sig',errors='replace')
    if not pattern.search(text):continue
    a.raw(v['Path'])
    for n,line in enumerate(text.splitlines(),1):
        if pattern.search(line):hits.append(dict(File=v['Path'],Owner=v['Owner'],Line=n,Text=line,Comment=line.lstrip().startswith('#')))
a.save('reference-evidence.json',hits)
a.save('ethiopian-atlas-references.json',[h for h in hits if 'ethiopian_atlas_diffuse.dds' in h['Text']])
for rel in ('gfx/models/buildings/special/Karhold/karhold.asset','gfx/models/buildings/special/Karhold/karhold.mesh',
            'gfx/models/buildings/special/Runestone/runestone.asset','gfx/models/buildings/special/Runestone/runestone.mesh'):
    a.raw(e[rel]['Path'])

# Known animation state registrations, resolved through current load order.
states=[]
for rel in ('gfx/models/portraits/male_body/male_body.asset','gfx/models/portraits/male_body/boy_body.asset',
            'gfx/models/portraits/female_body/female_body.asset','gfx/models/portraits/female_body/girl_body.asset'):
    text=readrel(rel)
    states.append(dict(File=e[rel],State='throneRoom_twoHandedPassive1_entry',
                       Present='name = "throneRoom_twoHandedPassive1_entry"' in text,
                       ObsoleteFatPresent='name = "throneRoom_twoHandedPassiveFat1_entry"' in text,
                       ObsoleteFatDwarfPresent='name = "throneRoom_twoHandedPassiveFatDwarf1_entry"' in text))
assert all(x['Present'] and not x['ObsoleteFatPresent'] and not x['ObsoleteFatDwarfPresent'] for x in states)
a.save('animation-state-evidence.json',states)
for rel in ('gfx/portraits/portrait_animations/99_valyrian_invasion_weapons_animations.txt',
            'gfx/portraits/portrait_animations/animations.txt','common/genes/07_genes_special_accessories_misc.txt',
            'gfx/portraits/portrait_modifiers/00_custom_legwear.txt','gfx/portraits/portrait_modifiers/00_custom_clothes.txt',
            'common/bookmark_portraits/bookmark_299_asha_greyjoy.txt','common/bookmark_portraits/bookmark_99_aurion_varezys.txt',
            'common/artifacts/features/00_vs_artifact_features.txt',
            'common/opinion_modifiers/valyrian_opinion_modifiers.txt','gfx/FX/pdxmesh.shader'):
    readrel(rel)

dups=json.loads((a.HERE/'duplicate-evidence.json').read_text(encoding='utf-8'))
for x in dups:
    if x['Identical']:continue
    b,c=a.raw(x['Duplicate']['Path']),a.raw(x['Canonical']['Path'])
    i,j=Image.open(io.BytesIO(b)).convert('RGBA'),Image.open(io.BytesIO(c)).convert('RGBA')
    x['PixelComparison']=dict(EqualPixels=i.tobytes()==j.tobytes(),Size=i.size,
        DifferenceExtrema=ImageChops.difference(i,j).getextrema(),CurrentAlpha=i.getextrema()[3],
        CanonicalAlpha=j.getextrema()[3],CurrentFormat=b[84:88].decode('ascii'),CanonicalFormat=c[84:88].decode('ascii'))
a.save('duplicate-evidence.json',dups)

# Decode every mip of the constant AO map: UV relocation must be invariant under mip selection.
ao_rel='gfx/models/buildings/holdings/cow3_sprawl/building_x_AO_placeholder.dds'
b=a.raw(e[ao_rel]['Path']);height,width=struct.unpack_from('<II',b,12)
mips=struct.unpack_from('<I',b,28)[0] or 1
fourcc=b[84:88];assert fourcc in (b'DXT1',b'DXT3',b'DXT5')
blockbytes=8 if fourcc==b'DXT1' else 16;offset=128;ao=[]
for level in range(mips):
    length=((width+3)//4)*((height+3)//4)*blockbytes
    header=bytearray(b[:128]);struct.pack_into('<II',header,12,height,width);struct.pack_into('<I',header,28,1)
    im=Image.open(io.BytesIO(bytes(header)+b[offset:offset+length])).convert('RGBA')
    ao.append(dict(Level=level,Size=im.size,Extrema=im.getextrema()))
    offset+=length;width=max(1,width//2);height=max(1,height//2)
assert all(x['Extrema'][2]==(165,165) for x in ao)
a.save('ao-mip-evidence.json',dict(File=e[ao_rel],Mips=ao))

textures=[]
for rel in ('gfx/models/debug/no_normal.dds','gfx/models/debug/no_properties.dds',
            'gfx/models/debug/bronze_m_normal.dds','gfx/models/debug/bronze_m_gloss.dds','gfx/models/debug/bronze_m_diffuse.dds',
            'gfx/models/debug/iron_m_normal.dds','gfx/models/debug/iron_m_gloss.dds','gfx/models/debug/iron_m_diffuse.dds',ao_rel):
    b=a.raw(e[rel]['Path']);im=Image.open(io.BytesIO(b)).convert('RGBA')
    textures.append(dict(File=e[rel],Size=im.size,Extrema=im.getextrema(),SHA256=hashlib.sha256(b).hexdigest()))
a.save('material-texture-evidence.json',textures)

meshes=json.loads((a.HERE/'mesh-evidence.json').read_text(encoding='utf-8'))
uv_plan=[]
for m in meshes:
    for p in m['Parts']:
        bad=[c['Name'] for c in p['Channels'] if c['NonzeroTriangles']==0]
        if not bad:continue
        shaders=[s['Shader'] for s in p['MatchingSettings']] or [x['shader'] for x in p['Materials']]
        if 'u0' in bad:
            if set(shaders)<= {'standard_atlas','snap_to_terrain_atlas'}:
                assert all('building_x_AO_placeholder.dds' in s['Body'] for s in p['MatchingSettings'])
                action='copy_u1_to_u0_constant_ao';confidence='shader_invariant'
            else:
                assert shaders==['standard']
                action='copy_u1_to_u0_visible_metal';confidence='approved_visual_approximation'
            remove=[]
        else:
            assert set(shaders)<= {'standard','standard_winter','standard_atlas'}
            if set(shaders)=={'standard_atlas'}:
                assert bad==['u2'];remove=['u2']
            else:remove=[x['Name'] for x in p['Channels'] if x['Name']!='u0']
            action='remove_unused_tail';confidence='shader_unused'
        uv_plan.append(dict(File=m['File'],Part=p['Name'],NamedIndex=p['NamedIndex'],MeshIndex=p['MeshIndex'],
            BadChannels=bad,Shaders=shaders,Action=action,Confidence=confidence,Remove=remove))
a.save('uv-plan.json',uv_plan)

# One proposed remedy per original message; these statuses are NOT runtime validation.
owners={'animations':'Valyrian Steel','accessories':'AGOT Submod Core','mesh_settings':'COW-AGOT',
        'mesh_uv':'COW-AGOT','textures':'COW-AGOT','texture_duplicates':'COW-AGOT','dna':'AGOT Bookmarked'}
plans=[]
for category in ('animations','accessories','entities','mesh_settings','mesh_uv','textures','texture_duplicates','history','dna','localization','modifiers'):
    for r in a.rows(category):
        text=r['Message'];owner=owners.get(category);status='proposed';remedy=''
        if category=='animations':remedy='ANIM-01'
        elif category=='accessories':remedy='KEEP-INTEGRATIONS';status='retain'
        elif category=='entities':
            owner='AGOT Submod Core' if 'alicent' in text else 'COW-AGOT';remedy='ENTITY-ALICENT' if 'alicent' in text else 'ENTITY-WALLS'
        elif category=='mesh_settings':remedy='SETTINGS-01'
        elif category=='mesh_uv':
            remedy='UV-PLAN'
            if 'bronze_bell' in text or 'bellchain' in text:status='approximation';remedy='UV-METAL'
        elif category=='textures':
            if 'icon_' in text:remedy='ICONS-01'
            else:remedy='TEXTURE-NEUTRAL';status='approximation'
        elif category=='texture_duplicates':
            remedy='DEDUP-IDENTICAL'
            if 'ethiopian_atlas_diffuse.dds' in text:
                remedy='DEFER-REPLACER-CHECK';status='deferred'
        elif category=='history':
            if 'e_hre' in text:owner='Divine Intervention';remedy='KEEP-VANILLA-DI';status='retain'
            elif 'Gardener_75' in text:owner='Crowns of Westeros';remedy='HISTORY-GARDENER'
            elif 'graced_castle' in text:owner='COW-AGOT';remedy='HISTORY-GRACED'
            elif 'cheesemonger' in text:owner='COW-AGOT';remedy='HISTORY-PENTOS'
            else:raise AssertionError(text)
        elif category=='dna':remedy='DNA-PROP-CHOICE';status='approved_choice'
        elif category=='localization':owner='Clear Notifications' if 'show_notifications' in text else 'Valyrian Steel';remedy='LOC-01'
        elif category=='modifiers':
            if 'lucerys_gun' in text:owner='AGOT / Bookmarked';remedy='KEEP-LUCERYS';status='retain'
            elif 'asoiaf_stark' in text:owner='AGOT+';remedy='KEEP-AGOTPLUS';status='retain'
            else:owner='Valyrian Steel';remedy='OPINION-01' if 'monthly_change' in text else 'MODIFIER-DISABLED'
        assert owner and remedy
        plans.append(dict(Category=category,Line=r['Line'],Owner=owner,Remedy=remedy,Status=status,Message=text))
assert len(plans)==248
with (a.HERE/'solution-inventory.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(plans[0]),lineterminator='\n');w.writeheader();w.writerows(plans)
live=Path('C:/Users/RUSBAR/Documents/Paradox Interactive/Crusader Kings III/logs/error.log')
snapshot=a.LOG/'snapshot/error.log'
baseline=json.loads((a.HERE/'source-evidence.json').read_text(encoding='utf-8'))
changed=[p for p,v in baseline.items() if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=v['SHA256']]
assert not changed,changed
summary=dict(MessageCount=len(plans),ByCategory=dict(collections.Counter(x['Category'] for x in plans)),
    ByOwner=dict(collections.Counter(x['Owner'] for x in plans)),ByStatus=dict(collections.Counter(x['Status'] for x in plans)),
    UVParts=dict(collections.Counter(x['Action'] for x in uv_plan)),
    LiveLogSHA256=hashlib.sha256(a.raw(live)).hexdigest(),SnapshotSHA256=hashlib.sha256(a.raw(snapshot)).hexdigest(),
    PreviouslyPinnedSourcesChanged=changed,RuntimeModsWritten=False)
a.save('analysis-summary.json',summary);a.save('source-evidence.json',a.pins)
print(json.dumps(summary,ensure_ascii=False,indent=2))
