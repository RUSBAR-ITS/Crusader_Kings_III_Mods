"""Additional read-only comparisons; no game/mod output is generated."""
import collections,re
import analyze as a

def values(g,t):
    return re.findall(r'"[^"\r\n]*"|[-\d.]+',g.body(t).split('{',1)[1].rsplit('}',1)[0])
def neutral(v):return len(v)==4 and v[1]==v[3]=='0'

mapping={
 'gene_bs_head_round_shape':'gene_bs_head_shape',
 'gene_bs_eye_fold_2':'gene_bs_eye_fold_shape',
 'gene_eye_size':'gene_bs_eye_size',
 'gene_eye_shut_top':'gene_bs_eye_upper_lid_size',
 'gene_eye_shut_bottom':'gene_bs_eye_lower_lid_size',
 'gene_forehead_inner_brow_width':'gene_eyebrow_inner_width',
 'gene_dragon_scales_effect':'gene_dragon_metallic_scales_strength',
}
for old,new in [('skin','primary_color'),('highlight','secondary'),('eye','eye_color'),('horn','horn_color')]:
    for suffix in ['hue','value']:mapping[f'gene_dragon_{old}_{suffix}']=f'gene_dragon_{new}_{suffix}'

collisions=[];stats=collections.defaultdict(collections.Counter);dupes=[]
for (rel,pid),(m,p,preset,genes,text) in a.presets.items():
    bykey=collections.defaultdict(list)
    for g in genes.children:bykey[g.key].append(g)
    for key,gs in bykey.items():
        if len(gs)>1:
            dupes.append(dict(File=rel,DNA=pid,Gene=key,Values=' | '.join(' '.join(values(g,text)) for g in gs),Lines=' | '.join(str(g.line) for g in gs),Identical=len({tuple(values(g,text)) for g in gs})==1))
    for old,new in mapping.items():
        if old not in bykey:continue
        ov=values(bykey[old][0],text);nv=values(bykey[new][0],text) if new in bykey else []
        stats[old]['Count']+=1;stats[old]['OldZeroPair']+=neutral(ov);stats[old]['TargetPresent']+=bool(nv)
        stats[old]['BothNonZero']+=bool(nv) and not neutral(ov) and not neutral(nv)
        stats[old]['OldNonZeroTargetZero']+=bool(nv) and not neutral(ov) and neutral(nv)
        collisions.append(dict(File=rel,DNA=pid,OldGene=old,OldValue=' '.join(ov),TargetCandidate=new,TargetValue=' '.join(nv),OldZero=neutral(ov),TargetZero=neutral(nv),CandidateOnly=old not in ('gene_bs_head_round_shape',)))
a.export('migration-collisions.csv',collisions)
a.export('duplicate-gene-values.csv',dupes)
a.export('migration-statistics.csv',[dict(OldGene=k,**{f:v[f] for f in ['Count','OldZeroPair','TargetPresent','BothNonZero','OldNonZeroTargetZero']}) for k,v in stats.items()])

# Compare complete current AGOT human presets, not arbitrary values or random DNA.
donors=[];freq=collections.defaultdict(collections.Counter);examples={};donor_sources=[]
missing={r['Gene'] for r in a.issues if r['Category']=='dna_missing_gene'}
horn='gene_dragon_main_horn_shape';missing.add(horn)
for rel,(m,p) in a.effective('common/dna_data').items():
    if m['Name']!=a.agot['Name']:continue
    text=a.read(p)
    donor_sources.append(dict(Mod=m['Name'],File=rel,SHA256=a.sha(p)))
    for preset in a.parse(text).children:
        info=preset.child('portrait_info') or preset;genes=info.child('genes')
        if not genes:continue
        bykey={g.key:g for g in genes.children}
        if 'gene_dragon' not in bykey or 'human_body' not in bykey['gene_dragon'].body(text):continue
        has=[k for k in missing if k in bykey]
        donors.append(dict(File=rel,DNA=preset.key,Coverage=len(has),Genes=len(genes.children)))
        for k in has:
            val=' '.join(values(bykey[k],text));freq[k][val]+=1;examples.setdefault((k,val),f'{rel}:{bykey[k].line} ({preset.key})')
a.export('agot-human-donors.csv',donors)
a.export('agot-donor-source-hashes.csv',donor_sources)
a.export('agot-human-gene-distributions.csv',[dict(Gene=k,Value=val,Count=n,Example=examples[(k,val)]) for k in sorted(freq) for val,n in freq[k].most_common()])

# Precisely match all unknown log messages to parsed declarations and all missing
# messages to absent, known genes. This audits the parser against actual CK3 output.
unknown_log=collections.Counter((r['File'],r['DNA'],r['Gene']) for r in a.issues if r['Category']=='dna_unknown_gene')
unknown_parsed=collections.Counter((r['File'],r['DNA'],r['Gene']) for r in a.unknowns)
missing_ok=[]
for r in a.issues:
    if r['Category']!='dna_missing_gene':continue
    p=a.presets[(r['File'],r['DNA'])]
    assert r['Gene'] in a.schema and not p[3].child(r['Gene']),r
    missing_ok.append(r)
assert unknown_log==unknown_parsed,(unknown_log-unknown_parsed,unknown_parsed-unknown_log)
logged_missing={(r['File'],r['DNA'],r['Gene']) for r in missing_ok}
unlogged_gaps=[]
for (rel,pid),(_,_,preset,genes,t) in a.presets.items():
    for k in sorted(missing-{horn}):
        if not genes.child(k) and (rel,pid,k) not in logged_missing:
            unlogged_gaps.append(dict(File=rel,DNA=pid,Gene=k))
a.export('unlogged-schema-gaps.csv',unlogged_gaps)
a.save('detail-summary.json',dict(UnknownLogEqualsParsed=True,MissingValidated=len(missing_ok),HumanDonors=len(donors),CompleteDonors=sum(r['Coverage']==len(missing) for r in donors),UnloggedBookmarkGaps=len(unlogged_gaps),UnloggedBookmarkPresets=len({r['DNA'] for r in unlogged_gaps}),Duplicates=dupes,Statistics={k:dict(v) for k,v in stats.items()}))
print(a.read(a.HERE/'detail-summary.json'))
