"""In-memory feasibility check. Writes CSV/JSON evidence, never runnable mod files."""
import collections,json,re
import analyze as a

def val(g,text):return re.findall(r'"[^"\r\n]*"|[-\d.]+',g.body(text).split('{',1)[1].rsplit('}',1)[0])
def pair(t,n):return [f'"{t}"',str(n),f'"{t}"',str(n)]

donors=collections.defaultdict(list)
for r in a.rows(a.HERE/'agot-human-gene-distributions.csv'):
    if r['Gene'].startswith('gene_dragon_'):donors[r['Gene']].append(r)
dragon_defaults={}
for g,rs in donors.items():
    assert len(rs)==1 and int(rs[0]['Count'])==5273,(g,rs)
    dragon_defaults[g]=rs[0]['Value'].split()
assert len(dragon_defaults)==25
human_defaults={
 'gene_face_dacals':pair('no_face_dacal',0),
 'gene_bs_eye_lower_lid_size':pair('vanilla_eye_lower_lid_size',0),
 'gene_bs_eye_shape':pair('vanilla_eye_shape',0),
 'skin_color_saturation':pair('vanilla_skin_saturation',127),
 'eye_color_saturation':pair('vanilla_eye_saturation',127),
}
for g,v in human_defaults.items():
    for m,rel,b,t in a.templates[(g,v[0].strip('"'))]:
        assert not b.child('male').children and not re.search(r'\b(?:setting|decal)\s*=',b.body(t)),(g,rel)

states={};before={};actions=[];missing_by_preset=collections.defaultdict(set)
for i in a.issues:
    if i['Category']=='dna_missing_gene':missing_by_preset[(i['File'],i['DNA'])].add(i['Gene'])
for (rel,pid),(_,_,preset,genes,t) in a.presets.items():
    state=collections.defaultdict(list)
    for g in genes.children:state[g.key].append(val(g,t))
    before[(rel,pid)]={k:[v[:] for v in vs] for k,vs in state.items()}
    def change(old,new,v,reason):
        oldvs=state.pop(old,[]) if old else []
        if new:
            assert new not in state,(rel,pid,new)
            state[new]=[v]
        actions.append(dict(File=rel,DNA=pid,OldGene=old,NewGene=new,Before=' | '.join(' '.join(x) for x in oldvs),After=' '.join(v),Reason=reason))
    assert any('"human_body"' in v for v in state['gene_dragon'])
    for g in list(state):
        v=state[g][0]
        if g.startswith('gene_dragon_') and not a.schema.get(g):
            change(g,'',[],'remove_retired_dragon_key_in_human_DNA')
        elif g=='gene_bs_head_round_shape':
            change(g,'gene_bs_head_shape',v,'rename_head_gene_preserve_both_alleles')
        elif g=='gene_bs_eye_fold_2' and v[1]==v[3]=='0':
            change(g,'',[],'retired_eye_fold_zero_on_both_alleles')
        elif g=='gene_forehead_inner_brow_width' and v[0]==v[2]=='"vanilla_inner_brow_width"':
            change(g,'',[],'retired_brow_noop_template_on_both_alleles')
        elif g=='gene_dragon_main_horn_shape' and '"dragon_horns_none"' in v:
            change(g,g,dragon_defaults[g],'AGOT_uniform_human_no_horn_template')
        elif g=='gene_hair_type' and '"hair_afro_no_beard"' in v:
            change(g,g,[s.replace('hair_afro_no_beard','hair_afro') for s in v],'supported_afro_template_preserve_strength')
        elif g=='gene_no_portrait' and len(state[g])==2 and state[g][0]==state[g][1]:
            change(g,g,v,'remove_identical_duplicate')
    for g in missing_by_preset[(rel,pid)]:
        if g in state:continue
        if g in dragon_defaults:change('',g,dragon_defaults[g],'AGOT_uniform_human_dragon_default')
        elif g in human_defaults:change('',g,human_defaults[g],'explicit_existing_noop_human_template')
        else:raise AssertionError(('unclassified missing gene',rel,pid,g))
    states[(rel,pid)]=dict(state)

covered=[];remaining=[]
for r in a.issues:
    s=states[(r['File'],r['DNA'])];g=r['Gene'];vs=s.get(g,[]);c=r['Category']
    if c=='dna_missing_gene':resolved=bool(vs) and bool(a.schema.get(g))
    elif c=='dna_unknown_gene':resolved=not vs
    elif c in ['dna_template','dna_accessory']:
        resolved=all((g,v[j].strip('"')) in a.templates or v[j]=='""' for v in vs for j in [0,2])
    elif c=='dna_duplicate':resolved=len(vs)==1
    else:raise AssertionError(c)
    (covered if resolved else remaining).append(r)

# Every new nonempty template must resolve. Every unlisted gene remains verbatim.
for act in actions:
    if not act['NewGene']:continue
    g=act['NewGene'];v=states[(act['File'],act['DNA'])][g][0]
    assert a.schema.get(g),act
    assert all(x=='""' or (g,x.strip('"')) in a.templates for x in v[::2]),act
for key,s in states.items():
    changed={x for ac in actions if (ac['File'],ac['DNA'])==key for x in [ac['OldGene'],ac['NewGene']]}
    assert {g:vs for g,vs in s.items() if g not in changed}=={g:vs for g,vs in before[key].items() if g not in changed},key
assert len(covered)==8118 and len(remaining)==250,(len(covered),len(remaining))
a.export('proposed-actions.csv',actions)
a.export('proposed-covered-log.csv',covered)
a.export('proposed-deferred-log.csv',remaining)
a.export('proposed-human-dragon-defaults.csv',[dict(Gene=k,Value=' '.join(v),DonorCount=5273) for k,v in dragon_defaults.items()])
a.save('preflight-summary.json',dict(Mode='analysis_only_in_memory',RuntimeFilesWritten=0,Actions=len(actions),AffectedFiles=len({r['File'] for r in actions}),AffectedPresets=len({(r['File'],r['DNA']) for r in actions}),CoveredLogMessages=len(covered),DeferredLogMessages=len(remaining),CoveredPercentage=round(100*len(covered)/len(a.issues),3),WholeLogPercentage=round(100*len(covered)/10560,3),DeferredByGene=dict(collections.Counter(r['Gene'] for r in remaining)),ActionsByReason=dict(collections.Counter(r['Reason'] for r in actions)),AllNewTemplatesValidated=True,UnlistedGenesPreserved=True))
print(a.read(a.HERE/'preflight-summary.json'))
