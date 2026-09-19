"""Prepare and verify isolated candidates for the five requested categories.

Only this report's candidate/ directory and evidence files are written.
The installed fix, Workshop files and launcher settings are never changed.
"""
import collections
import copy
import difflib
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import importlib.util
spec = importlib.util.spec_from_file_location('resources', Path(__file__).with_name('inspect-resources.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
d, OUT = r.d, r.OUT
db = d.load(OUT / 'effective-resources.json')
MOD = d.MOD
rows = d.load(OUT / 'portrait-template-contexts.json')
actions, sources, bodies = [], {}, {}
pins = {}


def pin(path):
    pins[str(Path(path).resolve())] = d.sha(path)


def source(rel):
    if rel not in bodies:
        p = MOD / rel
        if not p.exists(): p = d.PLUS / rel
        sources[rel] = p
        bodies[rel] = d.read(p)
        pin(p)
    return bodies[rel]


def change(rel, before, after, category, reason, confidence='exact_reference'):
    text = source(rel)
    count = text.count(before)
    assert count and before != after, (rel, reason, count)
    bodies[rel] = text.replace(before, after)
    actions.append(dict(File=rel, Category=category, Reason=reason, Confidence=confidence,
                        Count=count, Before=before, After=after))


def field(body, name, value):
    return re.sub(r'(\b'+name+r'\s*=\s*)[^\s{}#]+', lambda m: m[1]+value, body, count=1)


def code(text):
    return re.sub(r'#[^\r\n]*', '', text)


def validate_modifier(text):
    gene, template = r.scalar(text, 'gene'), r.scalar(text, 'template')
    assert gene in db['Genes'], gene
    g = db['Genes'][gene]
    pin(g['Path'])
    assert template in g['Templates'], (gene, template)
    tb = g['Templates'][template]
    acc = re.search(r'(?m)^\s*accessory\s*=\s*([^\s{}#]+)', text)
    if acc:
        sex = r.scalar(text, 'type') or 'male'
        parsed = d.parse(tb).children[0]
        block = parsed.child(sex)
        assert block and re.search(r'\b'+re.escape(acc[1])+r'\b', code(block.body(tb))), (gene, template, sex, acc[1])
        assert acc[1] in db['Accessories'], acc[1]
        pin(db['Accessories'][acc[1]]['Path'])


# 1. Templates and accessory membership; retain every parent weight/condition.
seen = set()
neutral = {f'cosmetics_{x}': f'{x}_none' for x in ('eyeliner', 'eyeshadow', 'lipcolor', 'blush', 'foundation')}
for row in rows:
    rel, old = row['Files'], row['Modifier']
    if (rel, old) in seen: continue
    seen.add((rel, old))
    g, t = row['gene'], row['template']
    new, why, confidence = old, '', 'exact_reference'
    if g == 'secondary_headgear':
        new, why = field(old, 'gene', 'secondary_headgears'), 'Correct singular/plural gene ID'
    elif g == 'additive_headgear' and t == 'no_headgear':
        new, why = field(old, 'template', 'no_additive'), 'Use the empty template of the additive layer'
    elif g in neutral and t == 'none':
        new, why = field(old, 'template', neutral[g]), 'Existing explicitly empty cosmetic template'
    elif g == 'gene_lovers_pox' and t == 'none':
        new, why = field(old, 'template', 'lovers_pox'), 'Existing decal at the original zero strength'
    elif t == 'one_eyed_gem_saphire':
        new, why = field(old, 'template', 'one_eyed_gem_light_blue'), 'Current AGOT blue-eye trait selects this gem template'
        confidence = 'modern_equivalent_color'
    elif t == 'complexion_beauty_2':
        new, why = field(old, 'template', 'complexion_beauty_1'), 'Current beauty complexion for Joffrey; not a proven exact historical texture match'
        confidence = 'approximation'
    elif t == 'body_hair_average':
        new, why = field(old, 'template', 'body_hair_avg'), 'Current average body-hair template'
    elif 'accesory =' in old:
        new, why = old.replace('accesory =', 'accessory ='), 'Renly cloak accessory-key typo (also one portrait_rules message)'
    elif t == 'asoiaf_fots_religious_clothes':
        new, why = field(old, 'template', 'asoiaf_religious_clothes'), 'Same septon robe accessory in current Core group'
    elif 'accessory = male_clothes_religious_catholic_high_1' in old:
        new, why = old.replace('male_clothes_religious_catholic_high_1', 'male_clothes_religious_catholic_high_01'), 'Correct item suffix; current group contains _01'
    elif 'accessory = male_legwear_asoiaf_hound_legs' in old:
        assert 'type = female' in old
        new, why = old.replace('male_legwear_asoiaf_hound_legs', 'female_legwear_asoiaf_hound_legs'), 'Female Hound legwear already exists in the female group'
    elif t == 'dragon_horns_small':
        # This is explicitly an approximation, not evidence of the old transfer curve.
        # Current drogon template applies bs_dragon_horns_small as 1-value.
        strength = {'0.7': '0.3', '1.0': '0.0'}[row['value']]
        new = field(field(old, 'template', 'dragon_horns_drogon'), 'value', strength)
        why = 'Interpret old small-horn strength as shrink intensity; current inverse curve gives 0.7/1.0 shrink'
        confidence = 'approximation_old_curve_unverified'
    elif 'accessory = male_hair_fp1_09' in old:
        new, why = field(old, 'template', 'fp1_hairstyles_straight'), 'Retain the exact hairstyle accessory in a group containing it'
    elif g == 'gene_head_top_width' and t == 'head_top_height_neg':
        new, why = field(old, 'template', 'head_top_width_neg'), 'Use width deformation for the already selected width gene'
    elif 'accessory = male_legwear_asoiaf_kingsguard_legs_' in old:
        for a, b in [('_legs_1', '_legs_default'), ('_legs_2', '_legs_boots')]: new = new.replace('male_legwear_asoiaf_kingsguard'+a, 'male_legwear_asoiaf_kingsguard'+b)
        why = 'Existing default armour / off-duty boots matching parent modifier purpose'
    elif t in ('high_valyrian_war_legwear', 'stormlands_war_04_legwear'):
        acc = 'male_legwear_secular_' + ('valyrian_war_04' if t == 'high_valyrian_war_legwear' else 'stormlands_war_04')
        new = field(old, 'template', 'agot_all_legwear')
        new = re.sub(r'\bvalue\s*=\s*1\b', 'accessory = '+acc, new)
        why = 'Use the exact accessory selected by current AGOT for the same Rhaegar/Robert armour'
    assert new != old, row
    validate_modifier(new)
    change(rel, old, new, 'portrait_templates', why, confidence)

# 2. Preserve script conditions and support both historical and dynamically born people.
custom = 'gfx/portraits/portrait_modifiers/asoiaf_character_custom_flags.txt'
change(custom, 'portrait_wear_lannister_armour_torso_courtiers = yes',
       'portrait_wear_lannister_armour_courtiers_trigger = yes', 'portrait_rules', 'Existing author trigger with the same courtier-armour purpose')
clothes = 'gfx/portraits/portrait_modifiers/asoiaf_clothes.txt'
change(clothes, 'liege.has_religion = religion:the_ways_religion',
       'liege = { has_religion = religion:the_ways_religion }', 'portrait_rules', 'Call has_religion inside existing guarded liege scope')
crowns = 'gfx/portraits/portrait_modifiers/asoiaf_headgear_crowns.txt'
for i in range(3, 8):
    change(crowns, f'is_character_baratheon_{i} = yes',
           f'OR = {{ this = character:Baratheon_{i} has_inactive_trait = asoiaf_Baratheon_{i}_trait }}',
           'portrait_rules', 'Recognize historical identity OR the already assigned canonical-child identity marker')

# 3. Inert unimplemented female definitions. Check all effective active text callers first.
unused = {
    'gfx/portraits/accessories/asoiaf_cloaks.txt': 'female_cloak_asoiaf_stormlands_stannis_cloak_1',
    'gfx/portraits/accessories/asoiaf_clothes.txt': 'female_clothes_asoiaf_stormlands_stannis_clothes_1',
    'gfx/portraits/accessories/asoiaf_jewellery.txt': 'female_jewellery_asoiaf_septon_necklace_1',
}
unused_hits = {key: [] for key in unused.values()}
for folder in ('common', 'gfx/portraits', 'events', 'history'):
    for rel, (mod, path) in d.effective(folder, r.mods).items():
        text = code(d.read(path))
        for key in unused_hits:
            count = len(re.findall(r'\b'+key+r'\b', text))
            if count: unused_hits[key].append(dict(File=rel, Count=count, Path=str(path)))
for rel, key in unused.items():
    assert len(unused_hits[key]) == 1 and unused_hits[key][0]['File'] == rel, unused_hits[key]
    text = source(rel)
    block = next(b for b in d.parse(text).children if b.key == key)
    old = block.body(text)
    new = '\r\n'.join('# AGOT_PLUS_FIX candidate: ' + ln for ln in old.splitlines())
    change(rel, old, new, 'accessory_entity', 'Comment unimplemented female accessory; no active selectors/callers in the current set')

# 4. Wrong reference to a neighbouring legwear set.
iron = 'gfx/models/portraits/m_legwear/asoiaf/asoiaf_iron_isles/asoiaf_ironborn_legs_coa/asoiaf_ironborn_legs_coa.asset'
change(iron, 'type = "asoiaf_greyjoy_legs_bs_no_left_leg.mesh"',
       'type = "asoiaf_ironborn_legs_coa_bs_no_left_leg.mesh"', 'mesh_blendshape', 'Matching missing-left-leg file already exists beside the model')
pin(d.PLUS / Path(iron).parent / 'asoiaf_ironborn_legs_coa_bs_no_left_leg.mesh')

# 5. Shared geometry is byte-identical; retain AGOT+ entities and variation blocks.
duplicate_pairs = []
for sex in ('male', 'female'):
    key = sex+'_cloaks_secular_shouldercape_01_mesh'
    entries = db['Assets'][key]
    assert len(entries) == 2
    base = next(a for a in entries if a['Owner'] == 'A Game of Thrones')
    plus = next(a for a in entries if a['Owner'] == 'AGOT+')
    assert re.sub(r'\s+', '', code(base['Body'])) == re.sub(r'\s+', '', code(plus['Body']))
    pin(base['Path'])
    for p in Path(plus['Path']).parent.iterdir():
        q = Path(base['Path']).parent / p.name
        if q.is_file() and p.suffix in ('.mesh', '.dds'):
            assert p.read_bytes() == q.read_bytes(), (p,q)
            pin(p); pin(q)
            duplicate_pairs.append(dict(Plus=str(p), AGOT=str(q), SHA256=d.sha(p)))
    change(plus['File'], plus['Body'], '# AGOT_PLUS_FIX candidate: use the identical AGOT pdxmesh; retain the unique AGOT+ entities below.',
           'mesh_duplicates', 'Remove redundant mesh registration, retaining entity IDs and variant settings')

diff, candidate_files = [], []
for number, (rel, text) in enumerate(bodies.items(), 1):
    if rel.endswith(('.txt', '.asset')): d.parse(text)
    raw = sources[rel].read_bytes()
    data = (b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'') + text.encode('utf-8')
    dst = OUT / 'candidate' / (f'{number:02d}-' + Path(rel).name)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)
    candidate_files.append(dict(File=rel, Candidate=dst.relative_to(OUT).as_posix(), Source=str(sources[rel]),
                               SourceSHA256=d.sha(sources[rel]), CandidateSHA256=d.sha(dst)))
    diff.extend(difflib.unified_diff(d.read(sources[rel]).splitlines(), text.splitlines(), fromfile='before/'+rel, tofile='candidate/'+rel, lineterm=''))

# Remove only the fully empty third mesh node: eight bytes, no re-export.
reader = OUT.parent / 'agot-plus-dna-remaining-analysis-2026-09-19/historical/pdx_data.py'
pin(reader)
ns = {'__name__': 'read_only_pdx'}
exec(compile(reader.read_text(encoding='utf-8').replace('from .external import six', ''), str(reader), 'exec'), ns)
meshrel = 'gfx/models/portraits/f_clothes/asoiaf/asoiaf_westerlands/asoiaf_lannister_armours/f_asoiaf_lannister_armour_high/f_asoiaf_lannister_armour_high.mesh'
p = d.PLUS / meshrel
pin(p)
raw = p.read_bytes()
root = ns['read_meshfile'](str(p))
obj = root.find('./object/*')
meshes = obj.findall('mesh')
assert len(meshes) == 3 and meshes[-1].attrib == {} and len(meshes[-1]) == 0
token = b'[[[mesh\x00'
offsets = [m.start() for m in re.finditer(re.escape(token), raw)]
assert len(offsets) == 3 and raw[offsets[-1]+len(token):].startswith(b'[[[skeleton\x00')
offset = offsets[-1]
candidate = raw[:offset] + raw[offset+len(token):]
dst = OUT / 'candidate/15-lannister-armour.mesh'
dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_bytes(candidate)
candidate_files.append(dict(File=meshrel, Candidate=dst.relative_to(OUT).as_posix(), Source=str(p),
                           SourceSHA256=d.sha(p), CandidateSHA256=d.sha(dst)))
newroot = ns['read_meshfile'](str(dst))
expected = copy.deepcopy(root)
eo = expected.find('./object/*'); eo.remove(eo.findall('mesh')[-1])
def tree(node):
    return node.tag, node.attrib, [tree(c) for c in node]
assert tree(newroot) == tree(expected)
def triangles(m):
    v = m.get('tri')
    return collections.Counter(tuple(sorted(v[i:i+3])) for i in range(0, len(v), 3))
deformations = []
for q in sorted(p.parent.glob('*_bs_*.mesh')):
    pin(q)
    qs = ns['read_meshfile'](str(q)).findall('./object/*/mesh')
    assert len(qs) == 2
    for a, b in zip(meshes[:2], qs):
        assert len(a.get('p')) == len(b.get('p')) and a.get('u0') == b.get('u0') and triangles(a) == triangles(b)
    deformations.append(q.name)
assert len(deformations) == 9
iron_dir = d.PLUS / Path(iron).parent
iron_base = iron_dir / 'asoiaf_ironborn_legs_coa.mesh'
iron_shape = iron_dir / 'asoiaf_ironborn_legs_coa_bs_no_left_leg.mesh'
pin(iron_base)
iron_base_meshes = ns['read_meshfile'](str(iron_base)).findall('./object/*/mesh')
iron_shape_meshes = ns['read_meshfile'](str(iron_shape)).findall('./object/*/mesh')
assert len(iron_base_meshes) == len(iron_shape_meshes) > 0
for a, b in zip(iron_base_meshes, iron_shape_meshes):
    assert len(a.get('p')) == len(b.get('p')) and a.get('u0') == b.get('u0') and triangles(a) == triangles(b)
meshproof = dict(File=meshrel, Offset=offset, RemovedBytes=len(token), RemovedHex=token.hex(),
                 SourceSHA256=d.sha(p), CandidateSHA256=d.sha(dst),
                 ExpectedTreeMatches=True, RealMeshVertexCounts=[len(m.get('p'))//3 for m in meshes[:2]],
                 Deformations=deformations, DeformationVertexCountsUVAndTriangleSetsMatch=True,
                 ExistingSkeletonMaterialsVerticesUnchanged=True,
                 IronbornReplacement=dict(File=str(iron_shape), Base=str(iron_base),
                    MeshCount=len(iron_base_meshes), VertexCountsUVAndTriangleSetsMatch=True))

# Pin the current runtime as a guard that preparation didn't install candidates.
manifest = d.load(MOD / 'docs/source-manifest.json')
assert manifest['Revision'] == 10
assert all(d.sha(MOD / f['File']) == f['PatchedSHA256'] for f in manifest['Files'])
pin(MOD / 'docs/source-manifest.json')
pin(OUT.parent / 'ck3-agot-plus-fix-stage10-log-2026-09-19/snapshot/error.log')
for rel in ('common/scripted_triggers/asoiaf_clothing_triggers.txt',
            'common/scripted_effects/asoiaf_assign_inactive_traits_effects.txt',
            'common/scripted_effects/asoiaf_canon_children_effects.txt'):
    pin(MOD / rel if (MOD / rel).exists() else d.PLUS / rel)
pin(d.AGOT / 'gfx/portraits/portrait_modifiers/04_clothes_armor.txt')
pin(d.AGOT / 'gfx/portraits/trait_portrait_modifiers/00_trait_modifiers.txt')
for failure in db['AssetParseFailures']:
    pin(failure['Path'])
for folder, rel in [('history/characters', 'history/characters/00_agot_char_stormlands.txt'),
                    ('common/traits', 'common/traits/asoiaf_canon_children_traits.txt')]:
    mod, path = d.effective(folder, r.mods)[rel]
    text = d.read(path)
    for i in range(3, 8):
        key = f'Baratheon_{i}' if folder.startswith('history') else f'asoiaf_Baratheon_{i}_trait'
        assert any(b.key == key for b in d.parse(text).children), (key, path)
    pin(path)
for key, value in [('actions.json', actions), ('source-pins.json', pins), ('mesh-proof.json', meshproof),
                   ('duplicate-pairs.json', duplicate_pairs), ('unused-accessory-references.json', unused_hits),
                   ('candidate-files.json', candidate_files)]:
    (OUT / key).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
(OUT / 'candidate-text.patch').write_text('\n'.join(diff)+'\n', encoding='utf-8', newline='\n')
result = dict(Status='CANDIDATES_VERIFIED_NOT_INSTALLED', BaselineRevision=10,
              Runtime69FilesUnchanged=True, CandidateTextFiles=len(bodies), CandidateBinaryFiles=1,
              ExactTextOccurrences=sum(a['Count'] for a in actions), Recipes=len(actions),
              OccurrencesByCategory=dict(collections.Counter({cat:sum(a['Count'] for a in actions if a['Category']==cat) for cat in {a['Category'] for a in actions}})),
              ApproximateActions=[dict(File=a['File'], Reason=a['Reason'], Confidence=a['Confidence'], Count=a['Count']) for a in actions if a['Confidence'] != 'exact_reference'],
              IdenticalResourcePairs=len(duplicate_pairs), BinaryBytesRemoved=8,
              SourcePins=len(pins), GameExecutionChecked=False, VisualEquivalenceClaimed=False,
              FourTextureWarningsRequireFreshLog=True)
(OUT / 'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n', encoding='utf-8', newline='\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
