"""Additional read-only source comparisons and candidate accounting."""
import analyze as a
from collections import Counter
from pathlib import Path
import json, re
d, OUT = a.d, a.OUT
rows = d.rows(OUT / 'remaining-values.csv')
for gene in a.targets:
    group = [r for r in rows if r['Gene'] == gene]
    values = [int(v) for r in group for v in (r['Value'].split()[1], r['Value'].split()[3])]
    print(gene, 'n', len(group), 'range', min(values),max(values), 'most',Counter(values).most_common(8))
fold = [r for r in rows if r['Gene'] == 'gene_bs_eye_fold_2']
print('FOLD EXISTING TEMPLATES', Counter(r['CandidateValue'].split()[0] for r in fold))

# Closest other AGOT+ author presets, comparing facial genes only (not hair/clothes).
own = {}
for rel,(owner,path) in a.files.items():
    if Path(owner['Path']) not in (d.PLUS,d.MOD): continue
    txt=d.read(path)
    for p in d.parse(txt).children:
        g=d.genes_of(p)
        if g: own[(rel,p.key)]=d.state(g,txt)
donors=[]
for key,(state,txt,genes) in a.presets.items():
    if not any(g in state for g in a.targets): continue
    candidates=[]
    for other, st in own.items():
        if other==key or 'gene_eye_size' in st: continue
        common=[g for g in state.keys() & st.keys() if g.startswith('gene_') and g not in a.targets and not any(x in g for x in ('dragon','hair','bald','age','portrait'))]
        if len(common)<70:continue
        same=sum(state[g]==st[g] for g in common)
        candidates.append((same/len(common),same,len(common),other))
    if candidates:
        ratio,same,n,other=max(candidates)
        donors.append(dict(File=key[0],DNA=key[1],DonorFile=other[0],DonorDNA=other[1],ExactGenes=same,ComparedGenes=n,Ratio=round(ratio,4)))
a.save_csv('closest-author-presets.csv',donors)
print('CLOSEST PRESETS',sorted(donors,key=lambda r:-r['Ratio'])[:8])

# Extract exact historical/current blocks for human review, with file/line/hash.
sources=[(OUT/'historical/shogunate-2023-epe_genes_morph.txt',set(a.targets)),
 (d.AGOT/'common/genes/01_genes_morph.txt',{'gene_bs_eye_fold_shape','gene_bs_ear_outward'}),
 (d.AGOT/'common/genes/epe_genes_morph.txt',{'gene_eyebrow_inner_width'}),
 (Path('E:/SteamLibrary/steamapps/workshop/content/1158310/3034473189/common/genes/07_genes_special_accessories_misc.txt'),{'agot_all_legwear','asoiaf_all_legwears','kingsguard_legwear_01'}),
 (OUT/'historical/core-263ed44c09fd-misc.txt',{'kingsguard_war_01_legwear','maester_legwear','agot_trousers'}),
 (OUT/'historical/core-7e2334d3928e-misc.txt',{'asoiaf_lannister_war_legs'})]
pieces=[]
for path,keys in sources:
    txt=d.read(path)
    for b in d.walk(d.parse(txt)):
        if b.key in keys:
            line=txt.count('\n',0,b.start)+1
            pieces.append(f'FILE {path}\nSHA256 {d.sha(path)}\nLINE {line}\n{b.body(txt)}\n')
(OUT/'definition-evidence.txt').write_text('\n'.join(pieces),encoding='utf-8')
print('evidence blocks',len(pieces))
