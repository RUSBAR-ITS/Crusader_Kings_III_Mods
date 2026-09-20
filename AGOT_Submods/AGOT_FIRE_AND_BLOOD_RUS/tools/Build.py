"""Build standalone Russian localization from pinned source and edited translation data.

Offline: never invokes the draft service and never writes to Workshop or launcher.
"""
from Localization import *
from collections import defaultdict
import Terminology
import sys

sys.stdout.reconfigure(encoding='utf-8')
check_only='--check' in sys.argv
source=json.loads((ROOT/'docs/source-catalog.json').read_text(encoding='utf-8'))
draft=json.loads((ROOT/'docs/translation-draft.json').read_text(encoding='utf-8'))
manifest=json.loads((ROOT/'docs/source-manifest.json').read_text(encoding='utf-8'))
edits={}
for path in sorted((ROOT/'translation').glob('*.json')):
    part=json.loads(path.read_text(encoding='utf-8'))
    assert not edits.keys() & part.keys(),f'Duplicate editorial keys in {path}'
    edits.update(part)
assert not edits.keys()-source.keys(),'Editorial keys not found in the original'
for row in manifest['english_files']:
    assert hashlib.sha256((MAIN/row['file']).read_bytes()).hexdigest()==row['sha256'],f'Updated source: {row["file"]}'
current,current_files=read_catalog(MAIN,'english')
assert current_files==manifest['english_files'] and current==source,'Source catalog changed; review before rebuilding'
assert draft.keys()>=source.keys(),'Incomplete draft; missing keys are not silently filled with English'

# Conservative spelling changes apply to prose only, never to engine expressions.
# Names follow the installed AGOT Russian glossary. Case-changing place names below
# use explicit inflected forms, not stem replacement.
stems={
    'Эйегон':'Эйгон','Эйемон':'Эймон','Дейенерис':'Дейнерис',
    'Висения':'Висенья','Висении':'Висеньи','Висению':'Висенью','Висенией':'Висеньей',
    'Джослин':'Джоселин','Джоселинн':'Джоселин','Торрен':'Торрхен',
    'Саэра':'Сейра','Саэры':'Сейры','Саэре':'Сейре','Саэру':'Сейру','Саэрой':'Сейрой',
    'Висерр':'Визерр','Гаэмон':'Геймон','Гаемон':'Геймон','Ваэгон':'Вейгон','Ваегон':'Вейгон',
    'Даэлл':'Дейлл','Дейелл':'Дейлл','Мэйгор':'Мейгор','Бэлон':'Бейлон','Баэлон':'Бейлон',
    'Мэсси':'Масси','Андроу':'Эндроу','Эндрю':'Эндроу',
}
phrases={
    'Старого города':'Староместа','Старому городу':'Староместу','Старом городе':'Староместе','Старым городом':'Староместом','Старый город':'Старомест',
    'Старого Города':'Староместа','Старый Город':'Старомест','Старом Городе':'Староместе',
    'Драконьей ямы':'Драконьего Логова','Драконьей Ямы':'Драконьего Логова','Драконьей яме':'Драконьем Логове','Драконьей Яме':'Драконьем Логове',
    'Драконью яму':'Драконье Логово','Драконью Яму':'Драконье Логово','Драконья яма':'Драконье Логово','Драконья Яма':'Драконье Логово',
    'Блошиного Дна':'Блошиного Конца','Блошиного дна':'Блошиного Конца','Блошином Дне':'Блошином Конце','Блошином дне':'Блошином Конце','Блошиное Дно':'Блошиный Конец','Блошиное дно':'Блошиный Конец',
    'Ока Бога':'Божьего Ока','Око Бога':'Божье Око','Оке Бога':'Божьем Оке',
    'Кастерли-Рока':'Утёса Кастерли','Кастерли-Роке':'Утёсе Кастерли','Кастерли-Рок':'Утёс Кастерли',
    'Скалы Кастерли':'Утёса Кастерли','Скалу Кастерли':'Утёс Кастерли','Скале Кастерли':'Утёсе Кастерли','Скала Кастерли':'Утёс Кастерли',
    'Галлтауна':'Чаячьего города','Галлтауне':'Чаячьем городе','Галлтаун':'Чаячий город',
    'Мейденпула':'Девичьего Пруда','Мейденпулу':'Девичьему Пруду','Мейденпуле':'Девичьем Пруду','Мейденпул':'Девичий Пруд',
    'Хеллхолта':'Пекла','Хеллхолту':'Пеклу','Хеллхолте':'Пекле','Хеллхолтом':'Пеклом','Хеллхолт':'Пекло',
    'Йронвуд':'Айронвуд',
    'Блэкфайра':'Чёрного Пламени','Блэкфайром':'Чёрным Пламенем','Блэкфайру':'Чёрному Пламени','Блэкфайре':'Чёрном Пламени','Блэкфайр':'Чёрное Пламя',
    'Скайрича':'Поднебесья','Скайриче':'Поднебесье','Скайрич':'Поднебесье',
    'Найтсонга':'Ночной Песни','Найтсонг':'Ночная Песнь',
    'Дремире':'Пламенной Мечте','Дремиру':'Пламенную Мечту','Дремирой':'Пламенной Мечтой','Дремира':'Пламенная Мечта',
    'Вагар':'Вхагар','Вхагаре':'Вхагар','Вхагара':'Вхагар','Мераксеса':'Мераксес','Мераксесе':'Мераксес','Мераксесом':'Мераксес',
    'Сильвервинг':'Среброкрылая',
    'Принцессовом Проходе':'Принцевом перевале','Принцессов Проход':'Принцев перевал',
    'Римгейта':'Инистых Врат','Римгейте':'Инистых Вратах','Римгейт':'Инистые Врата',
    'Сейбл-Холла':'Собольего замка','Сейбл-Холле':'Собольем замке','Сейбл-Холл':'Соболий замок',
    'железные люди':'железнорождённые','железных людей':'железнорождённых','железным людям':'железнорождённым',
}


def normalize_plain(text):
    text=text.replace('\\n','\n')
    for a,b in phrases.items():text=re.sub(r'\b'+re.escape(a)+r'\b',b,text)
    for a,b in stems.items():text=re.sub(r'\b'+re.escape(a),b,text)
    text=re.sub(r'(?<=\d)\s*(?:г\.\s*)?(?:н\.\s*э\.|AC\b|АС\b)', ' г. от З.Э.',text)
    text=text.replace(' - ',' — ').replace(' – ',' — ')
    return text


def normalize(text,english):
    out=[];previous=0
    for start,end,token in tokens(text):
        out.append(Terminology.apply(normalize_plain(text[previous:start]),english));out.append(token);previous=end
    out.append(Terminology.apply(normalize_plain(text[previous:]),english));return ''.join(out)


groups=defaultdict(list);provenance={}
for key,row in source.items():
    value=edits.get(key,normalize(draft[key]['text'],row['text'])).replace('\r\n','\n').replace('\n','\\n')
    # Event descriptions are sometimes concatenated; boundary breaks are structural.
    leading=re.match(r'^(?:\\n)+',row['text'])
    trailing=re.search(r'(?:\\n)+$',row['text'])
    if leading and not value.startswith(leading[0]):value=leading[0]+value
    if trailing and not value.endswith(trailing[0]):value+=trailing[0]
    assert '\r' not in value,f'Carriage return in {key}'
    file=row['file'].replace('/english/','/russian/').replace('_l_english.yml','_l_russian.yml')
    groups[file].append(f' {key}:0 "{value}"')
    provenance[key]=dict(origin='editorial' if key in edits else draft[key]['origin'],english_sha256=hashlib.sha256(row['text'].encode()).hexdigest(),russian_sha256=hashlib.sha256(value.encode()).hexdigest())
outputs=[]
for rel,lines in groups.items():
    p=ROOT/rel
    data=('l_russian:\n'+'\n'.join(lines)+'\n').encode('utf-8-sig')
    if check_only:
        assert p.read_bytes()==data,f'Not reproducible: {rel}'
    else:
        p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    outputs.append(dict(file=rel,sha256=hashlib.sha256(data).hexdigest(),keys=len(lines)))
result=dict(keys=len(source),files=outputs,editorial_keys=len(edits),provenance=provenance)
if check_only:
    assert json.loads((ROOT/'docs/build-manifest.json').read_text(encoding='utf-8'))==result,'Build manifest differs'
else:save(ROOT/'docs/build-manifest.json',result)
print(f'{"Checked" if check_only else "Built"} {len(source)} keys in {len(outputs)} files; {len(edits)} editorial entries')
