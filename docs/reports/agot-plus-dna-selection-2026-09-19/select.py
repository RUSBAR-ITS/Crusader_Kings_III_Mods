"""Prepare an unapplied DNA migration using only the current schema.

All writes stay under this report directory. No build recipes, installed mods,
launcher settings, saves, or runtime files are modified.
"""
from pathlib import Path
from collections import Counter, defaultdict
import csv, difflib, importlib.util, json, re, sys

sys.stdout.reconfigure(encoding='utf-8')
OUT = Path(__file__).resolve().parent
REPO = OUT.parents[2]
MOD = REPO / 'AGOT_Submods/AGOT_PLUS_FIX'
HISTORY = OUT.parent / 'agot-plus-dna-remaining-analysis-2026-09-19'
spec = importlib.util.spec_from_file_location('stage9_read_helpers', MOD / 'tools/DNA-Stage9.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)

def write(name, data):
    path = (OUT / name).resolve()
    assert path.is_relative_to(OUT)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes): path.write_bytes(data)
    else: path.write_text(data, encoding='utf-8', newline='')

def save(name, data):
    write(name, json.dumps(data, ensure_ascii=False, indent=2) + '\n')

def csvout(name, data):
    import io
    buf=io.StringIO(newline='')
    writer=csv.DictWriter(buf, fieldnames=list(data[0]))
    writer.writeheader(); writer.writerows(data)
    write(name, b'\xef\xbb\xbf' + buf.getvalue().encode('utf-8'))

def fmt(value): return ' '.join(value)
def both(state, gene): return ' | '.join(fmt(v) for v in state.get(gene, []))
def delta(value): return max(-16, min(16, round((2 * value - 255) / 4)))

TARGETS = {
    'gene_eye_size': 'gene_bs_eye_size',
    'gene_eye_shut_top': 'gene_bs_eye_upper_lid_size',
    'gene_eye_shut_bottom': 'gene_bs_eye_lower_lid_size',
    'gene_forehead_inner_brow_width': 'gene_eyebrow_inner_width',
    'gene_bs_eye_fold_2': 'gene_bs_eye_fold_shape',
}
PAIRS = {
    'gene_eye_size': ('eye_size_neg', 'eye_size_pos'),
    'gene_eye_shut_top': ('eye_upper_lid_size_neg', 'eye_upper_lid_size_pos'),
    'gene_forehead_inner_brow_width': ('eyebrow_inner_width_min', 'eyebrow_inner_width_max'),
}

manifest=d.load(MOD/'docs/source-manifest.json')
assert manifest['Revision']==9 and len(manifest['Files'])==64
runtime_before={r['File']:d.sha(MOD/r['File']) for r in manifest['Files']}
assert all(runtime_before[r['File']]==r['PatchedSHA256'] for r in manifest['Files'])
historical=d.load(HISTORY/'summary.json')
assert historical['RuntimeSHA256']==runtime_before
for p,h in d.load(HISTORY/'source-pins.json').items(): assert d.sha(p)==h,p

mods=d.active_mods()
files=d.effective('common/dna_data',mods) | d.effective('common/bookmark_portraits',mods)
genefiles=d.effective('common/genes',mods)
schema=defaultdict(list); template_defs=defaultdict(list)
sourcepins={str(MOD/'docs/source-manifest.json'):d.sha(MOD/'docs/source-manifest.json')}
for evidence in (HISTORY/'summary.json',HISTORY/'source-pins.json',HISTORY/'remaining-values.csv',
                 HISTORY/'legwear-mapping.csv',OUT.parent/'ck3-agot-plus-fix-stage9-log-2026-09-19/remaining-dna.csv'):
    sourcepins[str(evidence)]=d.sha(evidence)
for rel,(owner,path) in genefiles.items():
    txt=d.read(path); sourcepins[str(path)]=d.sha(path)
    for group in d.walk(d.parse(txt)):
        if group.key not in ('morph_genes','color_genes','accessory_genes'):continue
        for g in group.children:
            schema[g.key].append((path,g,txt))
            for b in g.children:
                if re.search(r'\bindex\s*=',b.body(txt)) and (b.child('male') or re.search(r'\bmale\s*=',b.body(txt))):
                    template_defs[(g.key,b.key)].append((path,b,txt))
assert not any(g in schema for g in TARGETS), 'Historical genes reappeared; reassess migration.'
for g in set(TARGETS.values()) | {'legwear','gene_bs_ear_outward'}:
    assert len(schema[g])==1,(g,len(schema[g]))

# Resolve the attributes against the effective current heads; commented-out
# attributes must not be treated as available just because their names occur.
head_attributes={}
for sex in ('male','female'):
    rel=f'gfx/models/portraits/{sex}_head/{sex}_head.asset'
    provider=None
    for mod in mods:
        if any(rel==rp or rel.startswith(rp.rstrip('/')+'/') for rp in mod['Replace']):provider=None
        candidate=Path(mod['Path'])/rel
        if candidate.is_file():provider=candidate
    assert provider
    sourcepins[str(provider)]=d.sha(provider)
    txt=d.read(provider)
    head_attributes[sex]=set()
    for b in d.walk(d.parse(txt)):
        if b.key=='attribute':
            name=re.search(r'\bname\s*=\s*"([^"]+)"',b.body(txt))
            if name:head_attributes[sex].add(name[1])

rows=d.rows(HISTORY/'remaining-values.csv')
errors=d.rows(OUT.parent/'ck3-agot-plus-fix-stage9-log-2026-09-19/remaining-dna.csv')
assert len(rows)==len(errors)==250
byfile=defaultdict(list)
for r in rows:byfile[r['File']].append(r)
legwear={r['DNA']:r for r in d.rows(HISTORY/'legwear-mapping.csv')}
proposals=[]; actions=[]; allele_rows=[]; all_diffs=[]; preview_states={}; fileplans=[]
untouched_presets=0

for rel, issues in sorted(byfile.items()):
    owner,path=files[rel]
    assert Path(owner['Path']).resolve() in (MOD.resolve(),d.PLUS.resolve())
    sourcepins[str(path)]=d.sha(path)
    raw=path.read_bytes(); txt=d.read(path); tree=d.parse(txt)
    presets={p.key:p for p in tree.children}
    edits=[]; touched=defaultdict(set); changed_states={}

    def add_action(preset,gene,kind,after,reason,source):
        genes=d.genes_of(preset)
        blocks=[b for b in genes.children if b.key==gene]
        assert blocks
        before=' | '.join(fmt(d.value(b,txt)) for b in blocks)
        line=txt.count('\n',0,blocks[0].start)+1
        action=dict(File=rel,DNA=preset.key,Gene=gene,Kind=kind,Before=before,After=after,
                    Reason=reason,SourceLegacyGene=source,Line=line)
        actions.append(action); touched[preset.key].add(gene)
        if kind=='retire':
            assert len(blocks)==1
            b=blocks[0]
            old=b.body(txt)
            newline='\r\n' if '\r\n' in txt else '\n'
            comment='# AGOT_PLUS_FIX candidate: '+reason+'; '+old.replace(newline,newline+'# ')
            edits.append((b.start,b.end,comment))
        elif kind=='collapse_bookmark_pose':
            assert len(blocks)==2
            # Preserve the exported helmet correction as the single bookmark pose.
            # The inherited character DNA is not edited by this operation.
            first,last=blocks
            assert after==fmt(d.value(last,txt))
            comment='# AGOT_PLUS_FIX candidate: base ear before exported helmet pose; '+first.body(txt)
            edits.append((first.start,first.end,comment))
        else:
            assert kind=='replace' and len(blocks)==1
            b=blocks[0]
            edits.append((b.start,b.end,f'{gene} = {{ {after} }}'))

    for r in issues:
        preset=presets[r['DNA']]; genes=d.genes_of(preset)
        state=d.state(genes,txt)
        assert state['gene_dragon'] and all('"human_body"' in v for v in state['gene_dragon'])
        assert both(state,r['Gene'])==r['Value'],r
        oldgene=r['Gene']; target=TARGETS.get(oldgene,oldgene)
        target_before=both(state,target)
        final=None; details=[]; decision=''
        if oldgene in TARGETS:
            assert len(state[oldgene])==len(state[target])==1
            old=state[oldgene][0]; current=state[target][0]; final=current.copy()
            for ti,vi,allele in ((0,1,'dominant'),(2,3,'recessive')):
                template=current[ti].strip('"'); value=int(current[vi]); legacy=int(old[vi])
                change=delta(legacy); outcome=''; applied=0
                if oldgene=='gene_bs_eye_fold_2':
                    if value==0 and legacy>0:
                        final[ti]='"eye_fold_shape_neg_02"'; final[vi]=str(legacy)
                        outcome='same_attribute_in_free_slot_current_AGOT_range'
                    elif legacy==0:
                        outcome='no_legacy_fold_strength'
                    else:
                        outcome='preserve_existing_primary_fold'
                elif oldgene=='gene_eye_shut_bottom':
                    assert template=='vanilla_eye_lower_lid_size' and value==0
                    if change>0:
                        final[ti]='"eye_lower_lid_size"'; final[vi]=str(change)
                        applied=change; outcome='weak_positive_lower_lid_analogy'
                    else:
                        outcome='neutral_no_negative_lower_lid_analogue' if change<0 else 'neutral_near_midpoint'
                else:
                    neg,pos=PAIRS[oldgene]
                    assert template in (neg,pos)
                    sign=-1 if template==neg else 1
                    signed=value*sign
                    proposed=max(-255,min(255,signed+change))
                    # Only eye_size retains explicit min/max mirror metadata in AGOT.
                    # For other genes, do not cross an established nonzero branch.
                    if oldgene!='gene_eye_size' and value and proposed*sign<0:
                        proposed=0
                    if proposed!=signed:
                        final[vi]=str(abs(proposed))
                        final[ti]='"'+(neg if proposed<0 else pos if proposed>0 else template)+'"'
                        applied=proposed-signed
                        assert abs(applied)<=16
                        outcome='weak_signed_analogy'
                    else:
                        outcome='preserve_at_limit' if change else 'preserve_near_midpoint'
                allele_rows.append(dict(File=rel,DNA=preset.key,OldGene=oldgene,Allele=allele,
                    LegacyTemplate=old[ti].strip('"'),LegacyValue=legacy,TargetGene=target,
                    BeforeTemplate=template,BeforeValue=value,AfterTemplate=final[ti].strip('"'),AfterValue=int(final[vi]),
                    RequestedDelta=change if oldgene!='gene_bs_eye_fold_2' else '',AppliedSignedDelta=applied if oldgene!='gene_bs_eye_fold_2' else '',
                    Decision=outcome))
                details.append(allele+':'+outcome)
            changed=final!=current
            if oldgene=='gene_bs_eye_fold_2': decision='map_fold_in_free_slot' if changed else 'retire_preserve_primary_fold'
            elif changed:decision='approximate_current_gene'
            else:decision='retire_preserve_current_gene'
            add_action(preset,oldgene,'retire','',decision,oldgene)
            if changed:add_action(preset,target,'replace',fmt(final),decision,oldgene)
        elif oldgene=='legwear':
            row=legwear[preset.key]
            final=state[oldgene][0].copy()
            final[0]='"'+row['NewTemplate']+'"';final[1]=row['CandidateValue']
            assert final[2:]==state[oldgene][0][2:]
            decision='adapt_lannister_set' if 'tion_lannister' in preset.key else 'same_accessory_new_group'
            details=[row['SelectedAsset'],row['Confidence']]
            add_action(preset,oldgene,'replace',fmt(final),decision,oldgene)
        else:
            assert oldgene=='gene_bs_ear_outward' and rel.startswith('common/bookmark_portraits/')
            final=state[oldgene][-1].copy()
            assert final==['"ear_outward_neg"','255','"ear_outward_neg"','0']
            decision='retain_exported_helmet_pose'
            details=['approximate pose; preserve base entry in comment; character DNA unchanged']
            add_action(preset,oldgene,'collapse_bookmark_pose',fmt(final),decision,oldgene)

        assert final is not None
        assert target in schema
        assert len(final)==4 and all(0<=int(final[i])<=255 for i in (1,3))
        assert all(len(template_defs[(target,final[i].strip('"'))])==1 for i in (0,2)),(target,final)
        if target!='legwear':
            for i in (0,2):
                _,block,definition=template_defs[(target,final[i].strip('"'))][0]
                used=set(re.findall(r'\battribute\s*=\s*"([^"]+)"',block.body(definition)))
                for sex,available in head_attributes.items():
                    assert used<=available,(target,final[i],sex,used-available)
        proposals.append(dict(File=rel,DNA=preset.key,OldGene=oldgene,OldValue=r['Value'],TargetGene=target,
            TargetBefore=target_before,TargetAfter=fmt(final),Decision=decision,Detail='; '.join(details),
            VisualValidationRequired=False,Status='candidate_not_applied'))

    after=txt; previous=len(txt)
    for start,end,replacement in sorted(edits,reverse=True):
        assert end<=previous,'overlapping edits'
        after=after[:start]+replacement+after[end:];previous=start
    newtree=d.parse(after)
    assert [p.key for p in tree.children]==[p.key for p in newtree.children]
    for oldp,newp in zip(tree.children,newtree.children):
        if oldp.key not in touched:
            assert oldp.body(txt)==newp.body(after)
            untouched_presets+=1
            continue
        og,ng=d.genes_of(oldp),d.genes_of(newp)
        before_state=d.state(og,txt); after_state=d.state(ng,after)
        relevant=[act for act in actions if act['File']==rel and act['DNA']==oldp.key]
        expected={k:[v.copy() for v in vs] for k,vs in before_state.items()}
        for act in relevant:
            assert both(expected,act['Gene'])==act['Before']
            if act['Kind']=='retire':expected.pop(act['Gene'])
            else:expected[act['Gene']]=[re.findall(r'"[^"\r\n]*"|[-\d.]+',act['After'])]
        assert expected==after_state
        assert not any(g in after_state for g in TARGETS)
        assert all(len(vs)==1 for vs in after_state.values())
        assert [(b.key,b.body(txt)) for b in og.children if b.key not in touched[oldp.key]]==[(b.key,b.body(after)) for b in ng.children if b.key not in touched[oldp.key]]
        # Everything outside the genes block is preserved, including history ID, tags and entity.
        assert oldp.body(txt).replace(og.body(txt),'GENES',1)==newp.body(after).replace(ng.body(after),'GENES',1)
        preview_states[(rel,oldp.key)]=after_state
    assert txt!=after
    data=(b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'')+after.encode('utf-8')
    preview='preview/'+rel
    write(preview,data)
    fileplans.append(dict(File=rel,SourcePath=str(path),SourceOwner=owner['Name'],SourceSHA256=d.sha(path),
        Preview=preview,PreviewSHA256=d.sha(OUT/preview),AffectedPresets=len(touched),ExistingShadow=(MOD/rel).is_file()))
    all_diffs.append(''.join(difflib.unified_diff(txt.splitlines(keepends=True),after.splitlines(keepends=True),
        fromfile='current/'+rel,tofile='candidate/'+rel)))

assert len(preview_states)==88 and len(proposals)==250
assert len({(r['File'],r['DNA'],r['OldGene']) for r in proposals})==250
for issue in errors:
    state=preview_states[(issue['File'],issue['DNA'])]
    gene=issue['Gene']; cat=issue['Category']; values=state.get(gene,[])
    if cat=='dna_unknown_gene': assert not values
    elif cat in ('dna_template','dna_accessory'):
        assert values and all((gene,v[i].strip('"')) in template_defs for v in values for i in (0,2))
    elif cat=='dna_duplicate':assert len(values)==1
    else:raise AssertionError(cat)

assert runtime_before=={r['File']:d.sha(MOD/r['File']) for r in manifest['Files']}
for p,h in sourcepins.items():assert d.sha(p)==h
assert {rel:str(path) for rel,(_,path) in genefiles.items()}=={rel:str(path) for rel,(_,path) in d.effective('common/genes',d.active_mods()).items()}
assert not any('/common/genes/' in f['Preview'] or '/gfx/' in f['Preview'] for f in fileplans)

csvout('selection.csv',proposals);csvout('alleles.csv',allele_rows);csvout('actions.csv',actions)
write('candidate.patch',''.join(all_diffs))
save('plan.json',dict(Status='selection_only',BaseRevision=9,Policy='current_AGOT_only_no_new_genes_or_animations',
    Heuristic=dict(SignedDelta='clamp(round((2*v-255)/4),-16,16)',Nature='conservative approximation, not an engine conversion',
        EyeSizeMayCrossMirror=True,OtherNonzeroBranchesDoNotCross=True,LowerLidNegative='neutral',
        Fold='only zero-strength primary alleles; keep original byte and accept current AGOT ranges'),
    Files=fileplans,SourcePins=sourcepins,RuntimeSHA256=runtime_before,
    EffectiveGeneFiles={rel:str(path) for rel,(_,path) in genefiles.items()}))
stats=dict(Status='PASS_STATIC_PREVIEW',MessagesCovered=250,AffectedPresets=88,PreviewFiles=len(fileplans),
    NewShadowsIfApplied=sum(not f['ExistingShadow'] for f in fileplans),ExistingShadowsIfApplied=sum(f['ExistingShadow'] for f in fileplans),
    Actions=len(actions),ActionsByKind=dict(Counter(r['Kind'] for r in actions)),
    Decisions=dict(Counter(r['Decision'] for r in proposals)),
    ByLegacyGene={g:dict(Counter(r['Decision'] for r in proposals if r['OldGene']==g)) for g in TARGETS},
    ChangedFaceAlleles=sum((r['BeforeTemplate'],r['BeforeValue'])!=(r['AfterTemplate'],r['AfterValue']) for r in allele_rows),
    AlleleDecisions=dict(Counter(r['Decision'] for r in allele_rows)),
    UnchangedPresetsInPreviewFiles=untouched_presets,RuntimeFilesUnchanged=len(runtime_before),
    SourcePinsVerified=len(sourcepins),AllNewTemplatesResolve=True,UnlistedGeneTextPreserved=True,
    AllSelectedMorphAttributesAvailableInBothHeads=True,
    OriginalLegacyValuesRetainedInComments=True,GlobalSchemaUnchanged=True,Installed=False,GameExecuted=False,
    VisualEquivalenceClaimed=False)
save('validation.json',stats)
print(json.dumps(stats,ensure_ascii=False,indent=2))
