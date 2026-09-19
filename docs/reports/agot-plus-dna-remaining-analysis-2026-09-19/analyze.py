"""Read-only runtime audit; writes evidence only inside this report directory."""
from pathlib import Path
from collections import Counter, defaultdict
import csv, json, importlib.util, hashlib, sys

sys.stdout.reconfigure(encoding='utf-8')
OUT = Path(__file__).resolve().parent
REPO = OUT.parents[2]
MOD = REPO / 'AGOT_Submods/AGOT_PLUS_FIX'
spec = importlib.util.spec_from_file_location('dna_stage9', MOD / 'tools/DNA-Stage9.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)

def save_csv(name, rows):
    with (OUT / name).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

manifest = d.load(MOD / 'docs/source-manifest.json')
runtime = {r['File']: d.sha(MOD / r['File']) for r in manifest['Files']}
assert all(runtime[r['File']] == r['PatchedSHA256'] for r in manifest['Files'])
errors = d.rows(OUT.parent / 'ck3-agot-plus-fix-stage9-log-2026-09-19/remaining-dna.csv')
mods = d.active_mods()
files = d.effective('common/dna_data', mods) | d.effective('common/bookmark_portraits', mods)
sources, presets = {}, {}
for rel in sorted({e['File'] for e in errors}):
    owner, path = files[rel]
    text = d.read(path)
    sources[str(path)] = d.sha(path)
    root = d.parse(text)
    for b in root.children:
        genes = d.genes_of(b)
        if genes:
            presets[(rel, b.key)] = (d.state(genes, text), text, genes)

targets = {'gene_eye_size': 'gene_bs_eye_size', 'gene_eye_shut_top': 'gene_bs_eye_upper_lid_size',
           'gene_eye_shut_bottom': 'gene_bs_eye_lower_lid_size',
           'gene_forehead_inner_brow_width': 'gene_eyebrow_inner_width',
           'gene_bs_eye_fold_2': 'gene_bs_eye_fold_shape'}
output, summary, contexts = [], defaultdict(Counter), []
for e in errors:
    state, text, genes = presets[(e['File'], e['DNA'])]
    vals = state[e['Gene']]
    target = targets.get(e['Gene'], '')
    v = vals[0]
    classification = 'other'
    if e['Gene'] in targets:
        classification = 'both_noop_templates' if all(v[i].strip('"').startswith('vanilla_') for i in (0,2)) else 'active_template'
    summary[e['Gene']][classification] += 1
    output.append(dict(File=e['File'], DNA=e['DNA'], Gene=e['Gene'],
        Value=' | '.join(' '.join(vv) for vv in vals), Classification=classification,
        CandidateGene=target, CandidateValue=' | '.join(' '.join(vv) for vv in state.get(target, [])),
        Line=next(text.count('\n', 0, b.start)+1 for b in genes.children if b.key == e['Gene'])))
    if e['Gene'] in ('legwear','gene_bs_ear_outward'):
        contexts.append(dict(File=e['File'], DNA=e['DNA'], State=state))
save_csv('remaining-values.csv', output)
(OUT / 'accessory-ear-context.json').write_text(json.dumps(contexts, indent=2)+'\n', encoding='utf-8', newline='\n')
(OUT / 'summary.json').write_text(json.dumps(dict(Messages=len(errors), Presets=len({(e['File'],e['DNA']) for e in errors}),
    Groups=summary, Sources=sources, RuntimeSHA256=runtime), indent=2)+'\n', encoding='utf-8', newline='\n')
print(json.dumps(summary, indent=2))
print('TEMPLATES')
for gene in targets:
    subset = [r for r in output if r['Gene'] == gene]
    print(gene, Counter((r['Value'].split()[0], r['Value'].split()[2]) for r in subset))
print('ACCESSORIES/EARS')
for row in output:
    if row['Gene'] not in targets: print(row)
assert runtime == {r['File']: d.sha(MOD / r['File']) for r in manifest['Files']}
