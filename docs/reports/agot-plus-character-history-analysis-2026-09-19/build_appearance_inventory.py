"""Build a readable inventory from the audit; inspect Workshop sources read-only."""
import ast
import bisect
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[2]
PLUS = Path('E:/SteamLibrary/steamapps/workshop/content/1158310/2950245430')


def rows(name):
    with (OUT / name).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


# Reuse the audit's lexer without executing its report-writing module body.
audit = OUT / 'analyze_history.py'
tree = ast.parse(audit.read_text(encoding='utf-8'))
helpers = ast.Module(body=[node for node in tree.body
                          if isinstance(node, ast.FunctionDef)
                          and node.name in ('mask', 'definitions')], type_ignores=[])
exec(compile(helpers, str(audit), 'exec'), globals())

missing = rows('missing-dna.csv')
links = [r for r in rows('character-links.csv') if int(r['AppearanceDonorSites'])]
sites = [r for r in rows('character-link-reference-sites.csv')
         if 'copy_inheritable_appearance_from' in r['SourceText']]
assert len(missing) == 98 and len(links) == len(sites) == 80
assert len({r['Character'] for r in missing}) == 98
assert {r['Character'] for r in sites} == {r['Character'] for r in links}

source_hashes = {}


def source(path):
    data = path.read_bytes()
    source_hashes[str(path)] = hashlib.sha256(data).hexdigest().upper()
    return data.decode('utf-8-sig')


# This physical-source check is independent of later mods' VFS overrides.
physical = {}
for category in ('common/dna_data', 'history/characters'):
    index = defaultdict(list)
    for path in sorted((PLUS / category).rglob('*.txt')):
        for definition in definitions(source(path)):
            index[definition['Id']].append(str(path.relative_to(PLUS)))
    physical[category] = index

physical_missing_dna_hits = {r['DNA']: physical['common/dna_data'][r['DNA']]
                             for r in missing if physical['common/dna_data'][r['DNA']]}
physical_donor_hits = {r['Character']: physical['history/characters'][r['Character']]
                      for r in links if physical['history/characters'][r['Character']]}

donors = []
for site in sites:
    path = REPO / 'AGOT_Submods/AGOT_PLUS_FIX' / site['File']
    text = source(path)
    offset = sum(len(s) for s in text.splitlines(keepends=True)[:int(site['Line']) - 1])
    enclosing = [d for d in definitions(text) if d['Start'] <= offset < d['End']]
    assert len(enclosing) == 1, site
    definition = enclosing[0]
    header = definition['Body'].splitlines()[0]
    name = re.search(r'(?m)^\s*name\s*=\s*"([^"]+)"', definition['Body'])
    assert name, site
    # Keep source comments literally: they are author labels, not verified genealogy.
    label = header.split('#', 1)[1].strip() if '#' in header else name[1]
    donors.append({'Character': site['Character'], 'Name': name[1], 'AuthorLabel': label,
                   'BirthEffect': definition['Id'], 'File': site['File'], 'Line': site['Line']})

with (OUT / 'missing-appearance-donors.csv').open('w', encoding='utf-8-sig', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=list(donors[0]))
    writer.writeheader()
    writer.writerows(donors)


def group(row):
    cid = row['Character']
    if cid.startswith('Forrester_'): return 'Thorren Forrester'
    if cid == 'Baratheon_asoiaf_baby': return 'Alaric Baratheon'
    for family in ('Bitov', 'Leipa', 'Lichtenburg', 'Ronov', 'Capon', 'Zleb', 'Toth'):
        if cid.startswith('asoiaf_' + family + '_'): return family
    return 'Другие персонажи пасхалки'


groups = defaultdict(list)
for row in missing:
    groups[group(row)].append(row)

doc = ['# Отсутствующие источники внешности AGOT+', '',
       'Проверка 19.09.2026 по установленным файлам и ранее сохранённому логу. '
       'Это перечень неразрешимых ссылок, а не список доказанно удалённых автором лиц. '
       'Игровые файлы не менялись.', '',
       '[Результаты поиска в сети и границы выводов](appearance-online-research.md).', '',
       '## 98 отсутствующих DNA-шаблонов', '',
       'Сами персонажи существуют. У каждого ниже ключ `dna` совпадает с указанным ID, '
       'но определения такого шаблона в действующем наборе нет. '
       'Имена оставлены в написании файлов, чтобы не смешивать тёзок.', '',
       '| Группа | Число |', '| --- | ---: |']
for label, items in groups.items():
    doc.append(f'| {label} | {len(items)} |')
doc += ['', '**96 записей относятся к разделу пасхалок; две остальные — Thorren и Alaric.** '
        'Пять узнаваемых героев Kingdom Come (Henry, Hans, Hanush, Erik, Istvan) '
        'в этот список не входят: их шаблоны существуют.', '']
for label, items in groups.items():
    doc += [f'### {label}', '', '| Имя в файле | ID персонажа / отсутствующий DNA | Источник |',
            '| --- | --- | --- |']
    for row in items:
        p = PLUS / row['File']
        doc.append(f"| {row['Name']} | `{row['Character']}` | "
                   f"[{p.name}:{row['Line']}]({p.as_posix()}:{row['Line']}) |")
    doc.append('')

doc += ['## 80 отсутствующих персонажей-доноров', '',
        'Это отдельная категория: при рождении канонического ребёнка скрипт пытается '
        'скопировать наследуемую внешность с несуществующего служебного персонажа. '
        'Из этого нельзя заключать, что все соответствующие исторические персонажи '
        'в основном AGOT лишены внешности.', '',
        'Метки ниже взяты из комментариев автора к функциям рождения. Они помогают '
        'найти нужный код, но сами по себе не доказывают соответствие другому ID '
        'или пригодность чужого DNA в качестве замены.', '',
        '| Группа ID | Число |', '| --- | ---: |']
for family, count in Counter(d['Character'].split('_asoiaf_')[0] for d in donors).items():
    doc.append(f'| {family} | {count} |')
doc += ['', '| Метка автора / персонаж | Отсутствующий донор | Место копирования |',
        '| --- | --- | --- |']
for row in donors:
    p = REPO / 'AGOT_Submods/AGOT_PLUS_FIX' / row['File']
    doc.append(f"| {row['AuthorLabel'].replace('|', '/')} | `{row['Character']}` | "
               f"[строка {row['Line']}](<{p.as_posix()}:{row['Line']}>) |")
doc += ['', '## Проверка', '',
        f'В физических исходниках установленного AGOT+ также найдено '
        f'{len(physical_missing_dna_hits)} из 98 запрошенных DNA и '
        f'{len(physical_donor_hits)} из 80 запрошенных персонажей-доноров. '
        'Таким образом, их отсутствие в этой установленной копии не объясняется только '
        'тем, что более поздний мод перекрыл файл. Полнота самой установки относительно '
        'авторского дистрибутива отдельно не проверена.', '',
        'Машиночитаемые списки: [98 DNA](missing-dna.csv), '
        '[80 доноров с именами](missing-appearance-donors.csv). '
        'Воспроизведение: `python docs/reports/agot-plus-character-history-analysis-2026-09-19/'
        'build_appearance_inventory.py`.']
(OUT / 'missing-appearances.md').write_text('\n'.join(doc) + '\n', encoding='utf-8', newline='\n')
result = {'MissingDNA': len(missing), 'MissingDonors': len(donors),
          'MissingDNAByGroup': {label: len(items) for label, items in groups.items()},
          'PhysicalAGOTPlusDNAHits': physical_missing_dna_hits,
          'PhysicalAGOTPlusCharacterHits': physical_donor_hits,
          'AuditHelperSHA256': hashlib.sha256(audit.read_bytes()).hexdigest().upper(),
          'SourceSHA256': source_hashes, 'RuntimeFilesWritten': 0}
(OUT / 'appearance-inventory-checks.json').write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
print(json.dumps({k: v for k, v in result.items() if k != 'SourceSHA256'}, ensure_ascii=True))
