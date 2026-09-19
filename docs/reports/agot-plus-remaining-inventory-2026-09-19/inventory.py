"""Complete AGOT+ inventory of the captured error.log, with explicit attribution.

No game/runtime files are written. Unlocated diagnostics are searched in the
effective text sources of the base game and all active mods using ripgrep.
"""
import collections
import csv
import hashlib
import json
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
RUN=HERE.parent/'ck3-agot-plus-fix-stage8-log-2026-09-19'
GAME=Path('E:/SteamLibrary/steamapps/common/Crusader Kings III/game')

def read(p): return Path(p).read_text(encoding='utf-8-sig')
def rows(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def save(name,value): (HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8', newline='\n')
def export(name,data,fields):
    with (HERE/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest().upper()

data=rows(RUN/'classified-entries.csv')
mods=rows(RUN/'active-mods.csv')
plus=next(m for m in mods if m['Name']=='AGOT+')
fix=next(m for m in mods if m['Descriptor']=='mod/AGOT_PLUS_FIX.mod')
names={plus['Name'],fix['Name']}
roots=[dict(Name='CK3',Path=str(GAME),Replace=[])]+mods
profile=Path('C:/Users/RUSBAR/Documents/Paradox Interactive/Crusader Kings III')
for m in mods:
    m['Replace']=re.findall(r'(?m)^\s*replace_path\s*=\s*"([^"]+)"',read(profile/m['Descriptor']))

@lru_cache(None)
def provider(rel):
    for m in reversed(roots):
        if (Path(m['Path'])/rel).is_file():return m
        if any(rel==p or rel.startswith(p.rstrip('/')+'/') for p in m['Replace']):return None
    return None

def keys(row):
    msg=row['Message'];comp=row['Component']
    if comp.startswith('jomini_effect.'):
        m=re.match(r"(?:Variable|Event target) '([^']+)'",msg);return [m[1]] if m else []
    if comp=='history.cpp:644':return re.findall(r'character:(\w+)',msg)
    if comp.startswith('decision_type.'):return [msg.split()[0]]
    if comp.startswith('artifact_feature.'):
        loc=re.findall(r"'([^']+)'",msg)
        return loc+[s.removeprefix('feature_') for s in loc]
    if comp.startswith('virtualfilesystem.'):
        return re.findall(r'([^/\s]+\.dds)',msg)
    if comp.startswith('game_icons.'):
        return re.findall(r"referenced from building '([^']+)'",msg)
    if comp.startswith(('opinion_modifier.','static_modifier.','artifact_feature.','artifact_visual_type.','pdx_3dtypes.')):
        return re.findall(r"['\"]([^'\"]+)['\"]",msg)[:1]
    if comp.startswith('pdx_entity.cpp:585'):return re.findall(r'in entity "([^"]+)"',msg)
    if comp.startswith(('pdx_entity.','pdxassetutil.cpp:1053')):return re.findall(r"['\"]([^'\"]+)['\"]",msg)[:1]
    if comp.startswith('portraitanimations.'):return re.findall(r"portrait animation '([^']+)'",msg)
    if comp.startswith('portraitaccessories.'):return re.findall(r'group \[[^:]+:([^\]]+)\]',msg)
    if 'is orphaned' in msg:return [msg.split()[1]]
    if 'does not have a valid namespace' in msg:return re.findall(r"'([^']+)'",msg)
    if 'Key is missing localization:' in msg:return [msg.split(': ',1)[1]]
    if 'Unrecognized loc key ' in msg:return [msg.split()[3].rstrip('.')]
    if comp=='databases.h:36':return [msg.split()[1]]
    return []

unlocated=[r for r in data if not r['Key'] and (not r['Owner'] or r['Owner']=='Unresolved file')]
symbols=sorted({k for r in unlocated for k in keys(r)})
(HERE/'search-symbols.txt').write_text('\n'.join(symbols)+'\n',encoding='utf-8', newline='\n')
pattern=re.compile(r'(?<![\w.])(?:'+ '|'.join(re.escape(s) for s in sorted(symbols,key=len,reverse=True)) +r')(?![\w.])')
command=['rg','--json','--no-heading','--no-ignore','-F','-f',str(HERE/'search-symbols.txt'),'-g','*.txt','-g','*.asset','-g','*.gui','-g','*.yml']
command += [m['Path'] for m in roots]
result=subprocess.run(command,capture_output=True,encoding='utf-8')
assert result.returncode in (0,1),result.stderr
references=[]
by_symbol=collections.defaultdict(list)
root_paths=sorted([(str(Path(m['Path']).resolve()).replace('\\','/'),m) for m in roots],key=lambda x:len(x[0]),reverse=True)
for line in result.stdout.splitlines():
    item=json.loads(line)
    if item['type']!='match':continue
    row=item['data'];path=row['path']['text'].replace('\\','/')
    root,m=next((p,m) for p,m in root_paths if path.lower().startswith(p.lower()+'/'))
    rel=path[len(root)+1:]
    if provider(rel) is not m:continue
    source=row['lines']['text'].rstrip('\r\n')
    # Keep quoted strings intact, drop only actual line comments.
    code=re.sub(r'"(?:\\.|[^"\\])*"|#[^\r\n]*',lambda x:'' if x[0].startswith('#') else x[0],source)
    for symbol in set(match[0] for match in pattern.finditer(code)):
        ref=dict(Symbol=symbol,Mod=m['Name'],File=rel,Line=row['line_number'],SourceText=source)
        references.append(ref);by_symbol[symbol].append(ref)
export('symbol-reference-sites.csv',references,['Symbol','Mod','File','Line','SourceText'])

@lru_cache(None)
def source_lines(rel):
    owner=provider(rel)
    return read(Path(owner['Path'])/rel).splitlines() if owner else []

def relevant_reference(row,ref):
    # A translated label is not an independent definition of a decision/modifier.
    if ref['File'].startswith('localization/'):
        return row['Component'].startswith(('pdx_locstring.','jomini_dynamicdescription.','artifact_feature.'))
    if not row['Component'].startswith('jomini_effect.'):
        return True
    # Identical names in models, artifact visuals and variables are separate IDs.
    sym=re.escape(ref['Symbol']);text=ref['SourceText'].split('#',1)[0]
    if row['Message'].startswith('Variable '):
        if re.search(r'(?<![\w:])(?:var|global_var|local_var):'+sym+r'(?![\w.])',text):return True
        if re.search(r'\b(?:has|remove|set)_(?:global_|local_)?variable\s*=\s*"?'+sym+r'\b',text):return True
        if re.search(r'\b(?:has|add|remove)_\w*flag\s*=\s*"?'+sym+r'\b',text):return True
        if re.search(r'\b(?:name|flag)\s*=\s*"?'+sym+r'\b',text):
            before='\n'.join(source_lines(ref['File'])[max(0,ref['Line']-10):ref['Line']])
            return bool(re.search(r'\b\w*variable\s*=\s*\{[^}]*\b(?:name|flag)\s*=\s*"?'+sym+r'\b',before))
        return False
    if row['Message'].startswith('Event target '):
        return bool(re.search(r'\bscope:'+sym+r'\b|\bsave_(?:temporary_)?scope_as\s*=\s*"?'+sym+r'\b',text))
    return True

CATEGORIES={
 'dna_missing_gene':'DNA: отсутствующие обязательные гены',
 'dna_unknown_gene':'DNA: устаревшие/неизвестные гены',
 'dna_template':'DNA: неизвестные шаблоны генов',
 'dna_accessory':'DNA закладок: неизвестные группы одежды',
 'dna_duplicate':'DNA: повторная запись гена',
 'portrait_rules':'Условия и синтаксис портретных скриптов',
 'portrait_templates':'Шаблоны, аксессуары и значения портретных модификаторов',
 'accessory_entity':'Аксессуары: отсутствующие entity/варианты',
 'mesh_uv':'Модели: UV-развёртки',
 'mesh_blendshape':'Модели: blendshape и базовая геометрия',
 'mesh_duplicates':'Дубли моделей и текстур',
 'heraldry':'Гербы: отсутствующие текстуры',
 'animations':'Портретные анимации',
 'asset_other':'Другие графические ресурсы',
 'ai_decisions':'Решения: интервал проверки ИИ',
 'character_links':'Ссылки на отсутствующих персонажей',
 'artifact_visuals':'Артефакты: отсутствующее визуальное описание',
 'variable_not_set':'Переменные/области: используются, но не устанавливаются',
 'variable_unused':'Переменные: устанавливаются, но не используются',
 'modifier_unused':'Неиспользуемые модификаторы',
 'orphan_events':'События без обнаруженных вызовов',
 'localization':'Локализация',
 'database_other':'Прочие скриптовые/базовые ссылки',
}
def category(row):
    c=row['Component'];msg=row['Message'];files=row['Files']
    specific={'portraitcontext.cpp:326':'dna_missing_gene','portraitcontext.cpp:184':'dna_unknown_gene',
       'portraitcontext.cpp:136':'dna_template','portraitcontext.cpp:151':'dna_accessory','portraitcontext.cpp:239':'dna_duplicate',
       'pdxassetutil.cpp:2002':'mesh_uv','pdxassetutil.cpp:556':'mesh_uv','pdxassetutil.cpp:1009':'mesh_duplicates',
       'pdx_3dtypes.cpp:145':'mesh_duplicates','pdx_entity.cpp:585':'mesh_blendshape',
       'artifact_visual_type.cpp:31':'artifact_visuals','decision_type.cpp:224':'ai_decisions',
       'history.cpp:644':'character_links','jomini_effect.cpp:1145':'variable_unused','jomini_effect.cpp:1161':'variable_not_set',
       'static_modifier.cpp:200':'modifier_unused','jomini_eventmanager.cpp:372':'orphan_events'}
    if c in specific:return specific[c]
    if c.startswith('pdx_blend_shape_database.'):return 'mesh_blendshape'
    if c.startswith('dnamodifier.'):return 'portrait_templates'
    if c.startswith('coat_of_arms_render_description.'):return 'heraldry'
    if c.startswith('portraitaccessories.'):return 'accessory_entity'
    if c.startswith('portraitanimations.'):return 'animations'
    if c.startswith(('pdx_persistent_reader.','jomini_eventtarget.')) and 'gfx/portraits/' in files:return 'portrait_rules'
    if c.startswith(('pdx_locstring.','jomini_dynamicdescription.','artifact_feature.')):return 'localization'
    if c.startswith(('pdx_entity.','pdxassetutil.','pdx_3dtypes.')):return 'asset_other'
    return 'database_other'

selected=[];excluded=[];duplicates=[];ambiguous=[]
for row in data:
    if row['Key']:
        if 'AGOT+' in row['Owner'] or 'asoiaf' in row['Files'] or 'asoiaf' in row['Key']:duplicates.append(row)
        continue
    files=row['Files'].split(' | ') if row['Files'] else []
    ownfiles=[f for f in files if (p:=provider(f)) and p['Name'] in names]
    symbols_here=keys(row)
    refs=[r for k in symbols_here for r in by_symbol[k] if relevant_reference(row,r)]
    ownrefs=[r for r in refs if r['Mod'] in names]
    if ownfiles:
        level='Direct file' if row['Owner'] in names else 'Source/resource paths include AGOT+'
        evidence=' | '.join(ownfiles)
    elif row in unlocated and ownrefs:
        othermods=sorted({r['Mod'] for r in refs if r['Mod'] not in names})
        level='Symbol only in AGOT+ effective text' if not othermods else 'Symbol shared with other sources'
        evidence=' | '.join(dict.fromkeys(f"{r['Mod']}: {r['File']}:{r['Line']}" for r in ownrefs))
    else:
        excluded.append(dict(LogLine=row['Line'],Component=row['Component'],Owner=row['Owner'],Symbols=' | '.join(symbols_here),
                             SourceMods=' | '.join(sorted({r['Mod'] for r in refs})),Message=row['Message']))
        if row['Component']=='jomini_scriptvalue.h:459':ambiguous.append(row)
        continue
    selected.append(dict(LogLine=row['Line'],Category=category(row),Attribution=level,Symbols=' | '.join(symbols_here),
                         Evidence=evidence,SourceMods=' | '.join(sorted({r['Mod'] for r in refs})),
                         Component=row['Component'],OriginalOwner=row['Owner'],Files=row['Files'],Message=row['Message']))
fields=['LogLine','Category','Attribution','Symbols','Evidence','SourceMods','Component','OriginalOwner','Files','Message']
export('all-agot-plus-associated.csv',selected,fields)
export('other-or-unattributed.csv',excluded,['LogLine','Component','Owner','Symbols','SourceMods','Message'])
export('localization-duplicates.csv',duplicates,list(data[0]))
export('context-only-candidates.csv',ambiguous,list(data[0]))
categories=[]
for cat,label in CATEGORIES.items():
    items=[r for r in selected if r['Category']==cat]
    if not items:continue
    counts=collections.Counter(r['Attribution'] for r in items)
    categories.append(dict(Category=cat,Label=label,Messages=len(items),DirectFileMessages=counts['Direct file'],
                           MultiPathMessages=counts['Source/resource paths include AGOT+'],
                           UniqueSymbolMessages=counts['Symbol only in AGOT+ effective text'],SharedSymbolMessages=counts['Symbol shared with other sources']))
    export(cat+'.csv',items,fields)
    (HERE/(cat+'.log')).write_text('\n\n'.join(f"[original line {r['LogLine']}][{r['Component']}] {r['Message']}" for r in items)+'\n',encoding='utf-8', newline='\n')
export('categories.csv',categories,list(categories[0]))
save('summary.json',dict(LogSHA256=sha(RUN/'snapshot/error.log'),ManifestSHA256=sha(REPO/'AGOT_Submods/AGOT_PLUS_FIX/docs/source-manifest.json'),
 TotalLogEntries=len(data),AssociatedMessages=len(selected),AttributionCounts=dict(collections.Counter(r['Attribution'] for r in selected)),
 ExpectedLocalizationDuplicateCandidates=len(duplicates),ContextOnlyCandidates=len(ambiguous),Categories=categories,
 SearchSymbols=len(symbols),EffectiveReferenceSites=len(references),ReadOnlyAudit=True))
assert len({r['LogLine'] for r in selected})==len(selected)
assert sum(r['Messages'] for r in categories)==len(selected)
assert len(selected)+len(excluded)+sum(bool(r['Key']) for r in data)==len(data)

groups=[]
for row in selected:
    cat=row['Category'];msg=row['Message']
    if cat=='dna_missing_gene':key=re.search(r'missing gene (\S+)!',msg)[1]
    elif cat=='dna_unknown_gene':key=re.search(r'gene with key: (\S+)',msg)[1]
    elif cat=='dna_template':key=re.search(r'Unknown (\S+) gene template (\S+)',msg).group(0)
    elif cat in ('variable_not_set','variable_unused','character_links','ai_decisions','modifier_unused','orphan_events','localization','artifact_visuals'):key=row['Symbols']
    else:
        key=re.split(r' at file:| at \'file:|, near file:|\. file:| in file:',msg)[0]
        key=re.sub(r'\b(near line|line):\s*\d+',r'\1: *',key)
    groups.append((cat,key,row))
bucket=collections.defaultdict(list)
for cat,key,row in groups:bucket[(cat,key)].append(row)
group_rows=[dict(Category=cat,Diagnostic=key,Messages=len(items),FirstLogLine=items[0]['LogLine'],
                 Files=' | '.join(sorted({f for r in items for f in r['Files'].split(' | ') if f})))
            for (cat,key),items in sorted(bucket.items())]
export('grouped-issues.csv',group_rows,['Category','Diagnostic','Messages','FirstLogLine','Files'])
detail=['# Сгруппированные диагностические сообщения AGOT+',
        '', 'Счётчик означает число записей журнала. Полные тексты и все места источников — в CSV соответствующей категории.', '']
for cat in ('dna_missing_gene','dna_unknown_gene','dna_template','dna_accessory','dna_duplicate','portrait_templates',
            'ai_decisions','character_links','artifact_visuals','variable_not_set','variable_unused','modifier_unused','orphan_events','localization'):
    detail+=['## '+CATEGORIES[cat],'',f'[Все сообщения]({cat}.csv) · [Текст журнала]({cat}.log)','',
             '| ID / диагностика | Записей | Первая строка лога |','| --- | ---: | ---: |']
    for item in group_rows:
        if item['Category']==cat:
            key=item['Diagnostic'].replace('|','\\|').replace('\n','; ')
            detail.append(f"| `{key}` | {item['Messages']} | {item['FirstLogLine']} |")
    detail.append('')
(HERE/'details.md').write_text('\n'.join(detail)+'\n',encoding='utf-8', newline='\n')
print(json.dumps(dict(Associated=len(selected),Attribution=dict(collections.Counter(r['Attribution'] for r in selected)),
 CategoryCounts={r['Category']:r['Messages'] for r in categories},DuplicateCandidates=len(duplicates),
 ReferenceSites=len(references),GroupedDiagnostics=len(group_rows)),ensure_ascii=False,indent=2))
