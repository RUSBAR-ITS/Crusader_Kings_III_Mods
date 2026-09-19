"""Analysis only: schema scope, asset ownership, and accessory candidates."""
import os, contextlib, json, re
from pathlib import Path
from collections import Counter
with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink):
    import analyze as a
d, OUT = a.d, a.OUT

all_presets = {}
for rel, (owner, path) in a.files.items():
    txt = d.read(path)
    for p in d.parse(txt).children:
        g = d.genes_of(p)
        if g:
            all_presets[(rel, p.key)] = d.state(g, txt)
human = {k:s for k,s in all_presets.items() if 'gene_bs_eye_size' in s}
scope = dict(AllExpandedPresets=len(all_presets), HumanLikePresets=len(human),
    HumanLikeCriterion='contains gene_bs_eye_size; excludes compact DNA and is not a species classifier',
    ExistingLegacy={g:sum(g in s for s in human.values()) for g in a.targets})
foldkeys = [(r['File'],r['DNA']) for r in a.output if r['Gene']=='gene_bs_eye_fold_2']
scope['FoldOtherGenes'] = {}
for gene in ('gene_bs_eye_fold_shape','gene_bs_eye_shape','gene_bs_eye_lower_lid_size'):
    scope['FoldOtherGenes'][gene] = dict(Counter(' | '.join(' '.join(v) for v in human[k].get(gene,[])) for k in foldkeys))
scope['AllLegacyPresent'] = {g:sum(g in s for s in all_presets.values()) for g in a.targets}

assets=[]
for sex in ('male','female'):
    rels = [f'gfx/models/portraits/{sex}_head/{sex}_head.{ext}' for ext in ('mesh','asset')]
    for rel in rels:
        owner=None
        for mod in a.mods:
            if any(rel==r or rel.startswith(r.rstrip('/')+'/') for r in mod['Replace']): owner=None
            p=Path(mod['Path'])/rel
            if p.is_file(): owner=(mod,p)
        assets.append(dict(File=rel,Owner=owner[0]['Name'] if owner else None,
            Path=str(owner[1]) if owner else None,SHA256=d.sha(owner[1]) if owner else None))
scope['EffectiveAssets']=assets
(OUT/'restoration-scope.json').write_text(json.dumps(scope,indent=2)+'\n',encoding='utf-8')

core=Path('E:/SteamLibrary/steamapps/workshop/content/1158310/3034473189')
txt=d.read(core/'common/genes/07_genes_special_accessories_misc.txt')
blocks={b.key:b for b in d.walk(d.parse(txt))}
groups={}
for name in ('agot_all_legwear','asoiaf_all_legwears','kingsguard_legwear_01'):
    block=blocks.get(name)
    if not block: continue
    male=block.child('male')
    groups[name]=re.findall(r'(?m)^\s*([\d.]+)\s*=\s*(\w+)',male.body(txt).split('{',1)[1])

mapping=[
 ('bookmark_277_barristan_selmy','kingsguard_war_01_legwear',255,'male_legwear_special_kingsguard_war_01','agot_all_legwear','same accessory ID'),
 ('bookmark_284_cressen','maester_legwear',62,'male_legwear_maester_skirt_01','agot_all_legwear','same accessory ID; first of four old equal-weight choices'),
 ('challenge_character_282_walder_frey','agot_trousers',0,'male_legwear_secular_agot_trousers_01','agot_all_legwear','same accessory ID; first of three old equal-weight choices'),
 ('bookmark_236_tion_lannister','asoiaf_lannister_war_legs',255,'male_legwear_asoiaf_lannister_legs_dynast','asoiaf_all_legwears','candidate replacement model; not a proven rename')]
out=[]
for dna, old, value, asset, new, confidence in mapping:
    weights=groups[new]
    total=sum(float(w) for w,_ in weights)
    before=0
    for i,(w,item) in enumerate(weights):
        w=float(w)
        if item==asset:
            candidate=round(255*(before+w/2)/total)
            assert before/total < candidate/255 < (before+w)/total
            out.append(dict(DNA=dna,OldTemplate=old,OldValue=value,SelectedAsset=asset,
                NewTemplate=new,CandidateValue=candidate,OneBasedIndex=i+1,GroupCount=len(weights),
                Confidence=confidence,SelectionAssumption='linear cumulative weight, value / 255; chosen away from boundaries'))
            break
        before+=w
    else: raise AssertionError(asset)
a.save_csv('legwear-mapping.csv',out)

references=[]
for r in d.rows(OUT/'closest-author-presets.csv'):
    if float(r['Ratio'])<.9: continue
    old=all_presets[(r['File'],r['DNA'])]
    new=all_presets[(r['DonorFile'],r['DonorDNA'])]
    checked=('gene_bs_eye_size','gene_bs_eye_upper_lid_size','gene_bs_eye_fold_shape')
    references.append(dict(**r,CheckedGenes=';'.join(checked),Unchanged=';'.join(g for g in checked if old.get(g)==new.get(g)),
        Interpretation='similarity candidate only; identity must be checked separately; absent old genes do not prove conversion'))
a.save_csv('author-reference-comparison.csv',references)
print(json.dumps({k:v for k,v in scope.items() if k!='FoldOtherGenes'},indent=2))
for r in out: print(r)
print('fold carriers', {g:len(v) for g,v in scope['FoldOtherGenes'].items()})
print('references',len(references),'all checked genes same',sum(len(r['Unchanged'].split(';'))==3 for r in references))
assert a.runtime=={r['File']:d.sha(a.MOD/r['File']) for r in a.manifest['Files']}
