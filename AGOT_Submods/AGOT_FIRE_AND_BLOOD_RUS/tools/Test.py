"""Technical checks for directly edited localization (not a literary/game test)."""
from Localization import *
import sys
sys.stdout.reconfigure(encoding='utf-8')
en,current_files=read_catalog(MAIN,'english')
ru,files=read_catalog(ROOT,'russian')
errors=[];review=[];counts=Counter();exceptions=[]
allowed_literal_keys={'ERA_SEL_SGI','ERA_SEL_SR','ERA_SEL_BSD','sotd_soulmate_reason'}
# These four descriptions concern named male story characters (Jaehaerys/Baelon).
# Russian prose uses the actual name instead of English you/he/is helper chains.
# Each exception checks the exact removed token multiset and the replacement name.
nickname_grammar = {
    'nick_sotd_the_boy_king_desc': ['[CHARACTER.GetShortUINameNoTooltipNoFormat]', '[CharYouSheHe(CHARACTER)]'],
    'nick_sotd_the_forsaken_desc': ['[CHARACTER.GetShortUINameNoTooltipNoFormat]', '[CharYouHerHim(CHARACTER)]', '[CharYouSheHe(CHARACTER)]', '[CharYouSheHe(CHARACTER)]', '[CharAreIs(CHARACTER)]'],
    'nick_sotd_the_cruel_desc': ['[CHARACTER.GetShortUINameNoTooltipNoFormat]', '[CharYourHerHis(CHARACTER)]', '[CharYouHerHim(CHARACTER)]', '[CharYouHerHim(CHARACTER)]'],
    'nick_sotd_the_brave_desc': ['[CHARACTER.GetShortUINameNoTooltipNoFormat]', '[CharYouHerHim(CHARACTER)]'],
}

def translate_literals(t,key):
    pairs=[('A.C. ','З.Э. '),('A.D. ','Р.В. '),('C.A. ','Д.Р. ')] if key.startswith('ERA_SEL_') else [('You have','Вы принадлежите'),('They have','Они принадлежат'),('you were','вы были'),('they were','они были'),('you are','вы —'),('they are','они —')]
    for a,b in pairs:t=t.replace("'"+a+"'","'"+b+"'")
    return t

expected_files={p['file'].replace('/english/','/russian/').replace('_l_english.yml','_l_russian.yml') for p in current_files}
if {p['file'] for p in files}!=expected_files:errors.append(dict(kind='file_inventory'))
for folder in ['common','events','history','gui','gfx']:
    if (ROOT/folder).exists():errors.append(dict(kind='unexpected_gameplay_directory',folder=folder))
for p in sorted((ROOT/'localization').rglob('*.yml')):
    raw=p.read_bytes();text=raw.decode('utf-8-sig')
    if not raw.startswith(b'\xef\xbb\xbf') or b'\r' in raw:errors.append(dict(file=str(p),kind='encoding_or_eol'))
    if text.splitlines()[0]!='l_russian:':errors.append(dict(file=str(p),kind='header'))
    for n,line in enumerate(text.splitlines()[1:],2):
        if not line.strip() or line.lstrip().startswith('#'):continue
        m=ENTRY.match(line)
        if not m:errors.append(dict(file=str(p),line=n,kind='syntax'));continue
        counts[m[1]]+=1
for key,n in counts.items():
    if n!=1:errors.append(dict(key=key,kind='duplicate',count=n))
for key in en.keys()-ru.keys():errors.append(dict(key=key,kind='missing'))
for key in ru.keys()-en.keys():errors.append(dict(key=key,kind='extra'))
for key,row in ru.items():
    if key not in en:continue
    e=en[key]['text'];r=row['text']
    a,b=signature(e),signature(r)
    if a!=b and key not in allowed_literal_keys and key not in nickname_grammar:errors.append(dict(key=key,kind='tokens',expected=list(a.elements()),actual=list(b.elements())))
    if key in nickname_grammar:
        removed=Counter(nickname_grammar[key])
        expected=(a-removed)+Counter(['[CHARACTER.GetFirstNameNoTooltip]'])
        if any(a[t]!=n for t,n in removed.items()) or expected!=b:
            errors.append(dict(key=key,kind='russian_nickname_grammar'))
    if key in allowed_literal_keys:
        # Literal translations are explicit exceptions, not general token suppression.
        if Counter(translate_literals(t,key) for t in a.elements())!=b:errors.append(dict(key=key,kind='localized_expression_structure'))
    if re.search(r'ZXQ|ZBND|QXZ',r):errors.append(dict(key=key,kind='draft_marker'))
    if r.count('[')!=r.count(']') or r.count('$')%2:errors.append(dict(key=key,kind='unbalanced_expression'))
    plain=r
    for _,_,t in reversed(tokens(r)):plain=plain.replace(t,' ')
    plain=plain.replace('\\n',' ').replace('\\t',' ')
    if key=='setting_fab_canon_dragon_eggs_no_desc':
        plain=plain.replace('AGOT More Dragon Eggs','')
        exceptions.append(dict(key=key,reason='Название другого установленного мода сохраняется для поиска в лаунчере.'))
    if key=='dynn_Museveni_motto':
        if e!='TO DO' or r!='TO DO':errors.append(dict(key=key,kind='changed_upstream_placeholder'))
        exceptions.append(dict(key=key,reason='Незаполненный девиз оригинала; содержание не выдумывается.'))
    elif re.search(r'[A-Za-z]{3,}',plain):review.append(dict(key=key,kind='latin_prose',text=r))
    if re.search(r'[А-Яа-яЁё][A-Za-z]|[A-Za-z][А-Яа-яЁё]',plain):errors.append(dict(key=key,kind='mixed_alphabet',text=r))
    n1=Counter(re.findall(r'\b\d+(?:[.,]\d+)?\b',e));n2=Counter(re.findall(r'\b\d+(?:[.,]\d+)?\b',r))
    if n1!=n2:review.append(dict(key=key,kind='numbers',english=e,russian=r))
    if e.count('\\n')!=r.count('\\n'):review.append(dict(key=key,kind='paragraphs',english_count=e.count('\\n'),russian_count=r.count('\\n')))
    if not re.search(r'[А-Яа-яЁё]',plain) and re.search(r'[A-Za-z]',e) and key!='dynn_Museveni_motto':
        if not tokens(r):errors.append(dict(key=key,kind='no_russian'))
result=dict(original_keys=len(en),russian_keys=len(ru),files=len(files),errors=errors,review_candidates=review,documented_exceptions=exceptions,game_run=False)
save(ROOT/'docs/validation.json',result)
print(json.dumps(dict(keys=len(ru),files=len(files),errors=len(errors),error_types=dict(Counter(r['kind'] for r in errors)),review_types=dict(Counter(r['kind'] for r in review))),ensure_ascii=False,indent=2))
sys.exit(bool(errors or review))
