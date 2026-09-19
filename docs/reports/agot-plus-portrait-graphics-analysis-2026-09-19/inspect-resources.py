"""Read-only inventory of effective portrait genes, accessories and model definitions."""
import importlib.util
import json
from pathlib import Path
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
OUT = Path(__file__).resolve().parent
REPO = OUT.parents[2]
spec = importlib.util.spec_from_file_location('dna9', REPO / 'AGOT_Submods/AGOT_PLUS_FIX/tools/DNA-Stage9.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
mods = d.active_mods()

def effective(folder, pattern):
    result = {}
    for mod in mods:
        for replaced in mod['Replace']:
            result = {k: v for k, v in result.items() if not (k == replaced or k.startswith(replaced.rstrip('/') + '/'))}
        root = Path(mod['Path'])
        for p in sorted((root / folder).rglob(pattern)):
            result[p.relative_to(root).as_posix()] = (mod, p)
    return result

def scalar(text, key):
    code = re.sub(r'#[^\r\n]*', '', text)
    m = re.search(r'\b' + re.escape(key) + r'\s*=\s*("[^"]*"|[^\s{}]+)', code)
    return m[1].strip('"') if m else None

def main():
    genes = {}
    for rel, (mod, path) in effective('common/genes', '*.txt').items():
        text = d.read(path)
        for cat in d.walk(d.parse(text)):
            if cat.key not in ('morph_genes', 'accessory_genes', 'color_genes'): continue
            for g in cat.children:
                genes[g.key] = dict(File=rel, Path=str(path), Owner=mod['Name'], Kind=cat.key,
                                    Templates={b.key: b.body(text) for b in g.children})
    assets, parse_failures = {}, []
    for rel, (mod, path) in effective('gfx/models', '*.asset').items():
        text = d.read(path)
        try: blocks = d.parse(text).children
        except AssertionError as exc:
            parse_failures.append(dict(Path=str(path), Error=str(exc)))
            continue
        for block in blocks:
            if block.key not in ('pdxmesh', 'entity'): continue
            body = block.body(text)
            key = scalar(body, 'name')
            if key:
                assets.setdefault(key, []).append(dict(Kind=block.key, File=rel, Path=str(path),
                                                       Owner=mod['Name'], Body=body))
    accessories = {}
    for rel, (mod, path) in effective('gfx/portraits/accessories', '*.txt').items():
        text = d.read(path)
        for b in d.parse(text).children:
            accessories[b.key] = dict(File=rel, Path=str(path), Owner=mod['Name'], Body=b.body(text))
    # Keep the report small: record the complete accessory identity index but
    # retain full definitions only for the genes and duplicate meshes in scope.
    wanted_genes = {row['gene'] for row in d.load(OUT / 'portrait-template-contexts.json')}
    wanted_genes.add('secondary_headgears')
    missing_entities = ('female_cloak_asoiaf_stannis_cloak_1',
                        'female_clothes_asoiaf_stannis_clothes_1',
                        'female_jewellery_asoiaf_septon_necklace_1')
    # Two unrelated base-game files defeat the strict brace parser. Include
    # a text fallback so their omission cannot conceal any requested entity.
    missing_proof = {}
    for name in missing_entities:
        fallback = [failure['Path'] for failure in parse_failures
                    if re.search(r'\b' + re.escape(name) + r'\b', d.read(failure['Path']))]
        assert name not in assets and not fallback, (name, fallback)
        missing_proof[name] = dict(ParsedDefinitionCount=0, UnparsedFileTextHits=fallback)
    data = dict(Genes={k:v for k,v in genes.items() if k in wanted_genes},
                Assets={k:v for k,v in assets.items() if k in ('female_cloaks_secular_shouldercape_01_mesh', 'male_cloaks_secular_shouldercape_01_mesh')},
                Accessories={k:{f:v[f] for f in ('File','Path','Owner')} for k,v in accessories.items()},
                InventoryCounts=dict(Genes=len(genes), AssetIDs=len(assets), Accessories=len(accessories)),
                AssetParseFailures=parse_failures,
                MissingEntityProof=missing_proof)
    (OUT / 'effective-resources.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Inventoried', len(genes), 'genes,', len(assets), 'asset IDs,', len(accessories), 'accessories.')
    for key in assets:
        if ('female' in key and ('stannis' in key or 'septon' in key)) or 'shouldercape_01_mesh' in key:
            print(key, [(a['Owner'], a['File']) for a in assets[key]])
    for gene in ('hairstyles', 'legwear'):
        for name, body in genes[gene]['Templates'].items():
            if ('male_hair_fp1_09' in body or 'stormlands_war_04' in body or 'high_valyrian_war' in body):
                print(gene, name, '\n', body if gene == 'legwear' else 'contains male_hair_fp1_09')

if __name__ == '__main__':
    main()
