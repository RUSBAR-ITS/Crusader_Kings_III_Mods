"""Write the per-error recommendation and verify the analysis evidence."""
import os, contextlib, re, json
from collections import Counter
with open(os.devnull,'w') as sink, contextlib.redirect_stdout(sink):
    import analyze as a
d, OUT = a.d, a.OUT
plans = {
 'gene_eye_size': ('legacy_animation', 'Restore independent historical gene and validated eye_size animation; retain existing gene_bs_eye_size', 'historical definition exact; visual compatibility unverified'),
 'gene_eye_shut_top': ('legacy_animation', 'Restore independent historical gene and validated upper-lid animation; retain current upper-lid morph', 'historical definition exact; female historical activation differs'),
 'gene_eye_shut_bottom': ('legacy_animation', 'Restore independent historical gene and validated lower-lid animation', 'historical definition exact; female historical activation differs'),
 'gene_forehead_inner_brow_width': ('legacy_animation_and_morph', 'Restore historical three-attribute gene including brow animation; retain gene_eyebrow_inner_width', 'historical definition exact; rig/combination requires visual validation'),
 'gene_bs_eye_fold_2': ('independent_existing_morph', 'Restore independent 0..1 gene using existing bs_eye_fold_2; preserve both alleles and primary fold; audit neutral defaults globally', 'same attribute and historical range established; current visual identity not tested'),
 'legwear': ('accessory_mapping', 'Use legwear-mapping.csv; preserve recessive allele', 'three same accessory IDs; Tion is a justified model adaptation'),
 'gene_bs_ear_outward': ('bookmark_helmet_pose', 'Preserve evidence of base ear and added helmet correction; bake or reapply without duplicate persistent gene', 'helmet intent strongly supported; exact baking/composition needs render check'),
}
matrix=[]
for row in a.output:
    method, action, confidence=plans[row['Gene']]
    matrix.append(dict(**row,Method=method,Recommendation=action,Confidence=confidence,Status='analysis_only'))
assert len(matrix)==250
a.save_csv('repair-matrix.csv',matrix)

old=d.read(OUT/'historical/shogunate-2023-epe_genes_morph.txt')
cur=d.read(d.AGOT/'common/genes/epe_genes_morph.txt')
uncommented=re.sub(r'(?m)^(\s*)(?:#\s*)+',r'\1',cur)
oldb={b.key:b for b in d.walk(d.parse(old))}
curb={b.key:b for b in d.walk(d.parse(uncommented))}
tokens=lambda b,t:[m[0] for m in d.TOK.finditer(b.body(t)) if not m[0].startswith('#')]
identical={g:tokens(oldb[g],old)==tokens(curb[g],uncommented) for g in list(a.targets)[:4]}
assert all(identical.values())
source_paths=set(a.sources)
for path in (d.AGOT/'common/genes/01_genes_morph.txt',d.AGOT/'common/genes/epe_genes_morph.txt',
 d.GAME/'gfx/portraits/portrait_modifiers/_portrait_modifiers.info',
 d.PLUS/'gfx/portraits/portrait_modifiers/asoiaf_clothes_armor.txt',
 d.PLUS/'gfx/portraits/portrait_modifiers/asoiaf_clothes.txt',
 d.PLUS/'gfx/portraits/portrait_modifiers/asoiaf_headgear_armor.txt'):
    source_paths.add(str(path))
for mod in a.mods:
    if '3034473189' in mod['Path']:
        for rel in ('common/genes/05_genes_special_accessories_clothes.txt','common/genes/07_genes_special_accessories_misc.txt'):
            source_paths.add(str(a.Path(mod['Path'])/rel))
for r in d.rows(OUT/'author-reference-comparison.csv'):
    source_paths.add(str(a.files[r['DonorFile']][1]))
pins={p:d.sha(p) for p in sorted(source_paths)}
(OUT/'source-pins.json').write_text(json.dumps(pins,indent=2)+'\n',encoding='utf-8', newline='\n')
downloads=d.load(OUT/'historical/downloads.json')
for name,meta in downloads.items():
    assert d.sha(OUT/'historical'/name).lower()==meta['SHA256'].lower(),name
runtime={r['File']:d.sha(a.MOD/r['File']) for r in a.manifest['Files']}
assert runtime==a.runtime
assert all(runtime[r['File']]==r['PatchedSHA256'] for r in a.manifest['Files'])
result=dict(Messages=250,Presets=88,Methods=dict(Counter(r['Method'] for r in matrix)),
 HistoricalGenesIdenticalToUncommentedCurrent=identical,RuntimeFilesChecked=len(runtime),RuntimeUnchanged=True,
 SourcePins=len(pins),HistoricalDownloadsVerified=len(downloads),GameExecuted=False,
 Note='Static evidence validation, not engine or visual validation')
(OUT/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8', newline='\n')
print(json.dumps(result,indent=2))
