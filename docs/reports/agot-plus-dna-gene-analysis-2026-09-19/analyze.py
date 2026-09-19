"""Read-only DNA/schema analysis; writes evidence only inside this report folder."""
import collections,csv,hashlib,json,re,sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
INV=HERE.parent/'agot-plus-remaining-inventory-2026-09-19'
RUN=HERE.parent/'ck3-agot-plus-fix-stage8-log-2026-09-19'
GAME=Path('E:/SteamLibrary/steamapps/common/Crusader Kings III/game')
PROFILE=Path('C:/Users/RUSBAR/Documents/Paradox Interactive/Crusader Kings III')
def read(p):return Path(p).read_text(encoding='utf-8-sig')
def rows(p):return list(csv.DictReader(Path(p).open(encoding='utf-8-sig',newline='')))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest().upper()
def export(name,data,fields=None):
    if fields is None:fields=list(data[0])
    with (HERE/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data)
def save(name,data):(HERE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

class Block:
    def __init__(self,key,line,start,parent=None):
        self.key=key;self.line=line;self.start=start;self.parent=parent;self.children=[];self.end=None
    def child(self,key):return next((c for c in self.children if c.key==key),None)
    def body(self,text):return text[self.start:self.end]

TOK=re.compile(r'#[^\r\n]*|"(?:\\.|[^"\\])*"|[{}=]|[^\s{}=<>!]+|[<>!]=?')
def parse(text):
    root=Block('',1,0);stack=[root];last=[];line=1;pos=0
    for match in TOK.finditer(text):
        token=match[0];line+=text.count('\n',pos,match.start());pos=match.start()
        if token.startswith('#'):continue
        if token=='{':
            key=last[-2][0].strip('"') if len(last)>1 and last[-1][0]=='=' else ''
            start=last[-2][1] if key else match.start()
            b=Block(key,line,start,stack[-1]);stack[-1].children.append(b);stack.append(b)
        elif token=='}':
            assert len(stack)>1,('extra closing brace',line)
            stack.pop().end=match.end()
        last.append((token,match.start()));last=last[-2:]
    assert len(stack)==1,('unclosed block',stack[-1].key)
    root.end=len(text);return root

def walk(block):
    yield block
    for child in block.children:yield from walk(child)

mods=rows(RUN/'active-mods.csv')
roots=[dict(Name='CK3',Path=str(GAME),Order='0',Replace=[])]+mods
for m in mods:m['Replace']=re.findall(r'(?m)^\s*replace_path\s*=\s*"([^"]+)"',read(PROFILE/m['Descriptor']))
plus=next(m for m in mods if m['Name']=='AGOT+')
fix=next(m for m in mods if m['Descriptor']=='mod/AGOT_PLUS_FIX.mod')
agot=next(m for m in mods if m['Descriptor']=='mod/ugc_2962333032.mod')
own={plus['Name'],fix['Name']}
def effective(folder):
    result={}
    for m in roots:
        for replaced in m['Replace']:
            result={k:v for k,v in result.items() if not(k==replaced or k.startswith(replaced.rstrip('/')+'/'))}
        base=Path(m['Path'])/folder
        if base.is_dir():
            for p in sorted(base.rglob('*.txt')):result[p.relative_to(m['Path']).as_posix()]=(m,p)
    return result

efgenes=effective('common/genes');efethnic=effective('common/ethnicities')
schema=collections.defaultdict(list);templates=collections.defaultdict(list);texts={};sources=[];overrides=[]
for rel,(m,p) in efgenes.items():
    text=read(p);texts[str(p)]=text;root=parse(text)
    sources.append(dict(Mod=m['Name'],File=rel,SHA256=sha(p)))
    for group in walk(root):
        if group.key not in ('morph_genes','color_genes','accessory_genes'):continue
        for gene in group.children:
            schema[gene.key].append((m,rel,gene,text))
            temp=[]
            for b in gene.children:
                if re.search(r'\bindex\s*=',b.body(text)) and (b.child('male') or re.search(r'\bmale\s*=',b.body(text))):
                    templates[(gene.key,b.key)].append((m,rel,b,text));temp.append(b.key)
    providers=[]
    for other in roots:
        f=Path(other['Path'])/rel
        if f.is_file():providers.append(other['Name'])
    overrides.append(dict(File=rel,EffectiveOwner=m['Name'],Providers=' | '.join(providers)))
export('effective-gene-files.csv',overrides)
gene_rows=[]
for key,defs in sorted(schema.items()):
    for m,rel,b,text in defs:
        gene_rows.append(dict(Gene=key,Kind=b.parent.key,Owner=m['Name'],File=rel,Line=b.line,
                             Templates=' | '.join(c.key for c in b.children if (key,c.key) in templates)))
export('gene-schema.csv',gene_rows)
template_rows=[]
for (gene,key),defs in sorted(templates.items()):
    for m,rel,b,text in defs:
        body=b.body(text);idx=re.search(r'\bindex\s*=\s*(\d+)',body)
        template_rows.append(dict(Gene=gene,Template=key,Index=idx[1] if idx else '',Owner=m['Name'],File=rel,Line=b.line,
                                 Attributes=' | '.join(dict.fromkeys(re.findall(r'\battribute\s*=\s*"([^"]+)"',body)))))
export('gene-templates.csv',template_rows)

log=rows(INV/'all-agot-plus-associated.csv');dna_log=[r for r in log if r['Category'].startswith('dna_')]
issues=[]
for r in dna_log:
    msg=r['Message'];cat=r['Category']
    if cat=='dna_missing_gene':gene=re.search(r'missing gene (\S+)!',msg)[1]
    elif cat=='dna_unknown_gene':gene=re.search(r'gene with key: (\S+)',msg)[1]
    elif cat in ('dna_template','dna_accessory'):gene=re.search(r'Unknown (\S+) gene',msg)[1]
    else:gene=re.search(r'read gene (\S+)',msg)[1]
    match=re.search(r'file: ([^\n]+?) line: (\d+) \(([^)]+)\)',msg);assert match,msg
    issues.append(dict(Category=cat,Gene=gene,File=match[1],Line=int(match[2]),DNA=match[3],LogLine=r['LogLine']))
export('dna-log-index.csv',issues)
targets={r['Gene'] for r in issues}
matrix=[]
for key in sorted(targets):
    counts=collections.Counter(r['Category'] for r in issues if r['Gene']==key)
    defs=schema.get(key,[])
    matrix.append(dict(Gene=key,MissingMessages=counts['dna_missing_gene'],UnknownMessages=counts['dna_unknown_gene'],
                       TemplateMessages=counts['dna_template'],AccessoryMessages=counts['dna_accessory'],DuplicateMessages=counts['dna_duplicate'],
                       DefinitionCount=len(defs),DefinitionSources=' | '.join(f"{m['Name']}: {rel}:{b.line}" for m,rel,b,_ in defs),
                       Templates=' | '.join(k[1] for k in templates if k[0]==key)))
export('gene-error-matrix.csv',matrix)

presets={};pres_rows=[];pairs=[];unknowns=[]
for folder in ('common/dna_data','common/bookmark_portraits'):
    for rel,(m,p) in effective(folder).items():
        if m['Name'] not in own:continue
        text=read(p);root=parse(text);sources.append(dict(Mod=m['Name'],File=rel,SHA256=sha(p)))
        for preset in root.children:
            info=preset.child('portrait_info') or preset
            genes=info.child('genes')
            if not genes:continue
            presets[(rel,preset.key)]=(m,p,preset,genes,text)
            vals={b.key:re.findall(r'"[^"\r\n]*"|[-\d.]+',b.body(text).split('{',1)[1].rsplit('}',1)[0]) for b in genes.children}
            errors=[r for r in issues if r['File']==rel and r['DNA']==preset.key]
            body=genes.body(text)
            pres_rows.append(dict(File=rel,DNA=preset.key,Line=preset.line,GeneCount=len(genes.children),
                                 HumanBody='human_body' in ' '.join(vals.get('gene_dragon',[])),DragonGene=' '.join(vals.get('gene_dragon',[])),
                                 LogMessages=len(errors),MissingGenes=sum(r['Category']=='dna_missing_gene' for r in errors),
                                 UnknownGenes=sum(r['Category']=='dna_unknown_gene' for r in errors)))
            for gene in genes.children:
                if gene.key in targets:
                    pairs.append(dict(File=rel,DNA=preset.key,Gene=gene.key,Line=gene.line,Value=gene.body(text).split('=',1)[1].strip()))
                if not schema.get(gene.key):
                    unknowns.append(dict(File=rel,DNA=preset.key,Gene=gene.key,Line=gene.line,Value=gene.body(text).split('=',1)[1].strip()))
export('presets.csv',pres_rows)
export('affected-gene-values.csv',pairs)
export('unknown-gene-occurrences.csv',unknowns)

def excerpts(name,items):
    out=[]
    for m,rel,b,text in items:
        out.extend([f"# SOURCE {m['Name']}: {rel}:{b.line}",b.body(text),''])
    (HERE/name).write_text('\n'.join(out),encoding='utf-8')
excerpts('affected-gene-definitions.txt',[d for k in sorted(targets) for d in schema.get(k,[])])
export('source-hashes.csv',sources)
save('summary.json',dict(LogMessages=len(dna_log),GenesMentioned=len(targets),Presets=len(pres_rows),
                        AffectedPresets=sum(r['LogMessages']>0 for r in pres_rows),
                        HumanBodyPresets=sum(r['HumanBody'] for r in pres_rows),
                        AllPresetsHuman=all(r['HumanBody'] for r in pres_rows),
                        EffectiveGeneFiles=len(efgenes),GeneIDs=len(schema),TemplateIDs=len(templates),
                        MultiDefinitionGenes={k:len(v) for k,v in schema.items() if len(v)>1},
                        MissingDefinitionGenes=[k for k in sorted(targets) if not schema.get(k)],
                        LogSHA256=sha(RUN/'snapshot/error.log'),ManifestSHA256=sha(REPO/'AGOT_Submods/AGOT_PLUS_FIX/docs/source-manifest.json')))
print(read(HERE/'summary.json'))
