"""Audit the captured revision-14 startup; write reports, never game files."""
from collections import Counter, defaultdict
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PREVIOUS = HERE.parent / 'ck3-agot-plus-fix-stage13-log-2026-09-19'
STAGE12 = HERE.parent / 'ck3-agot-plus-fix-stage12-log-2026-09-19'
PATCH = REPO / 'AGOT_Submods/AGOT_PLUS_FIX'


def read(path):
    return Path(path).read_text(encoding='utf-8-sig')


def load(path):
    return json.loads(read(path))


def rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


def save(name, data):
    (HERE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n',
                             encoding='utf-8', newline='\n')


def export(name, data, fields):
    with (HERE / name).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(data)


def signature(row):
    text = re.sub(r'\[args#\d+\]', '[args#*]', row['Message'])
    text = re.sub(r'\b(near line|line):\s*\d+', r'\1: *', text, flags=re.I)
    text = re.sub(r'\bline\s+\d+', 'line *', text, flags=re.I)
    return row['Component'] + ' ' + text


before = rows(PREVIOUS / 'classified-entries.csv')
after = rows(HERE / 'classified-entries.csv')
old, new = [Counter(map(signature, items)) for items in (before, after)]
samples = {signature(row): row for row in before + after}
changes = [dict(Before=old[key], After=new[key], Difference=new[key] - old[key],
                Component=samples[key]['Component'], Message=samples[key]['Message'])
           for key in sorted(old.keys() | new.keys()) if old[key] != new[key]]
fields = ['Before', 'After', 'Difference', 'Component', 'Message']
export('changed-messages.csv', changes, fields)
export('new-messages.csv', [r for r in changes if r['Difference'] > 0], fields)
export('disappeared-messages.csv', [r for r in changes if r['Difference'] < 0], fields)

by_signature = defaultdict(list)
for row in after:
    by_signature[signature(row)].append(row)
prior = rows(PREVIOUS / 'all-agot-plus-associated.csv')
associated, consumed, verification = [], Counter(), []
for row in prior:
    key = signature(row)
    if consumed[key] < len(by_signature[key]):
        current = by_signature[key][consumed[key]]
        consumed[key] += 1
        associated.append(dict(row, LogLine=current['Line'], Message=current['Message'],
                               OriginalOwner=current['Owner'], PriorLogLine=row['LogLine'],
                               EvidenceBasis='Retained functional-code warning; matched against revision-14 plan'))
    else:
        verification.append(dict(Category=row['Category'], PriorLogLine=row['LogLine'],
                                 Component=row['Component'], Message=row['Message'], AfterCount=new[key]))
assert len(prior) == 40 and len(associated) == 2
assert all(any(token in r['Message'] for token in
           ('asoiaf_stark_throne_modifier', 'asoiaf_young_griff_landing_events.2')) for r in associated)
assert len(verification) == 38 and all(r['AfterCount'] == 0 for r in verification)
export('all-agot-plus-associated.csv', associated, list(prior[0]))
export('fix-verification.csv', verification, list(verification[0]))
oldcounts, counts = [Counter(row['Category'] for row in data) for data in (prior, associated)]
labels = {r['Category']: r['Label'] for r in rows(PREVIOUS / 'agot-plus-categories.csv')}
categories = [dict(Category=key, Label=labels[key], Before=oldcounts[key], After=counts[key],
                   Removed=oldcounts[key] - counts[key]) for key in labels if oldcounts[key]]
export('agot-plus-categories.csv', categories, list(categories[0]))

# Review the changed crown-event path explicitly, without normalizing away paths.
removed, added = old-new, new-old
assert removed.total() == 45 and added.total() == 1
prefix = "jomini_eventmanager.cpp:428 Duplicated event ID 'agot_activity_commission_crown.0001' found."
old_keys = [key for key in removed if key.startswith(prefix)]
new_key = next(iter(added))
assert len(old_keys) == 1 and new_key.startswith(prefix)
assert old_keys[0].replace('agot_activity_events_crown_commission.txt',
                           'agot_coronation_crown_commission_events.txt') == new_key
event_sources = load(PREVIOUS / 'duplicate-event-source-evidence.json')
for row in event_sources:
    assert sha(row['Path']) == row['SHA256']
    assert re.search(r'(?m)^agot_activity_commission_crown\.0001\s*=\s*\{', read(row['Path']))
save('duplicate-event-source-evidence.json', event_sources)
save('reviewed-diagnostic-variation.json', dict(Event='agot_activity_commission_crown.0001',
     Before=old_keys[0], After=new_key, BeforeCount=1, AfterCount=1, SourceHashesUnchanged=True,
     Interpretation='Known AGOT/Crowns of Westeros duplicate; only the reported source path changed.'))
primary = Counter(map(signature, verification))
secondary = removed-primary-Counter({old_keys[0]: 1})
assert secondary.total() == 6
for key in secondary:
    assert key.startswith('coat_of_arms_render_description.cpp:190 Failed to find textured emblem texture')
    assert any(name in key for name in ('asoiaf_unicorn.dds', 'vale_seldon_rayonne.dds',
                                       'north_wibberly.dds', 'ce_bottom_solid.dds', 're_block_02.dds'))
export('secondary-heraldry-resolved.csv', [dict(Occurrences=n, Component=samples[k]['Component'],
       Message=samples[k]['Message']) for k,n in secondary.items()], ['Occurrences','Component','Message'])

# Previously repaired diagnostics must remain absent in this captured run.
regressions = {}
for stage in range(1, 7):
    name = 'targeted-log-messages.csv' if stage == 1 else f'stage{stage}-targeted-log-messages.csv'
    regressions[str(stage)] = sum(new[signature(r)] > 0 for r in rows(PATCH / 'docs' / name))
for label in ('stage8', 'stage9', 'stage10', 'stage13'):
    targets = rows(HERE.parent / f'ck3-agot-plus-fix-{label}-log-2026-09-19/fix-verification.csv')
    regressions[label] = sum(new[signature(r)] > 0 for r in targets)
assert not any(regressions.values()), regressions
variables = [r for r in rows(STAGE12 / 'fix-verification.csv') if r['Category'].startswith('variable_')]
assert len(variables) == 130 and all(new[signature(r)] == 0 for r in variables)
loc_keys = {r['Key'] for r in load(REPO / 'AGOT_Submods/AGOT_PLUS_RUS_CORRECT/docs/runtime-localization-additions.json')['Entries']}
assert not [r for r in after if (m := re.match(r'Unrecognized loc key ([^. ]+)\.', r['Message'])) and m[1] in loc_keys]
mde = rows(PREVIOUS / 'mde-disappeared.csv')
assert sum(int(r['Occurrences']) for r in mde) == 141
assert all(new[signature(r)] == 0 for r in mde)
assert not [r for r in after if 'blendshape' in r['Message'].lower()]
other_dna = [r for r in after if r['Component'].startswith('portraitcontext')]
assert len(other_dna) == 2 and all(r['Owner'] == 'AGOT Bookmarked' for r in other_dna)

# Verify that the launched files match the approved package, all sources, and snapshot.
mods, previous_mods = [rows(path / 'active-mods.csv') for path in (HERE, PREVIOUS)]
assert [(m['Order'], m['Descriptor'], m['Path']) for m in mods] == [(m['Order'], m['Descriptor'], m['Path']) for m in previous_mods]
capture = load(HERE / 'snapshot-summary.json')
for row in capture['Copies']:
    assert sha(HERE / 'snapshot' / row['Snapshot']) == row['SnapshotSHA256']
debug = read(HERE / 'snapshot/debug.log')
start = re.search(r'^\[(\d\d:\d\d:\d\d)\].*Log system initialized\.', debug)[1]
exit_line = next(line for line in debug.splitlines() if 'Quit: Quit from inside game' in line)
meta = next(row for row in capture['Logs'] if row['File'] == 'error.log')
launch = dt.datetime.fromisoformat(meta['LastWriteTime']).replace(
    **dict(zip(('hour', 'minute', 'second'), map(int, start.split(':')))), microsecond=0)
mounts = [line for line in debug.splitlines() if 'Mounted Data:' in line and PATCH.as_posix() in line]
assert len(mounts) == 1
runtime = rows(HERE / 'runtime-files.csv')
for row in runtime:
    path = REPO / 'AGOT_Submods' / row['Mod'] / row['File']
    assert sha(path) == row['SHA256']
    assert dt.datetime.fromisoformat(row['LastWriteTime']) < launch
previous_files = {(r['Mod'],r['File']): r for r in rows(PREVIOUS / 'runtime-files.csv')}
assert all(r['SHA256'] == previous_files[(r['Mod'],r['File'])]['SHA256']
           for r in runtime if r['Mod'] != 'AGOT_PLUS_FIX')
manifest = load(HERE / 'snapshot/patch-source-manifest.json')
assert manifest['Revision'] == 14 and len(manifest['Files']) == 139
plan = load(HERE / 'snapshot/stage14-plan.json')
for path, digest in (plan['Sources'] | plan['Evidence']).items():
    assert sha(path) == digest, path
changed_existing = {r['File'] for r in plan['Files'] if r['ExistingShadow']}
unchanged = [r for r in plan['PreviousFiles'] if r['File'] not in changed_existing]
assert len(unchanged) == 126 and len(changed_existing) == 6
for row in unchanged:
    assert sha(PATCH / row['File']) == row['PatchedSHA256']
for row in plan['Files']:
    assert sha(PATCH / row['File']) == row['OutputSHA256']
roots = {'AGOT_PLUS': Path('E:/SteamLibrary/steamapps/workshop/content/1158310/2950245430'),
         'AGOT': Path('E:/SteamLibrary/steamapps/workshop/content/1158310/2962333032')}
sources = load(HERE / 'snapshot/source-baseline.json')
for row in sources:
    assert sha(roots[row['Catalog']] / row['File']) == row['SHA256']
descriptors = [PATCH / 'descriptor.mod', PATCH.with_suffix('.mod'), HERE / 'snapshot/descriptor-04.mod']
for path in descriptors:
    assert re.findall(r'(?m)^replace_path="([^"]+)"', read(path)) == [plan['ReplacePath']]
cloak_dir = roots['AGOT_PLUS'] / plan['ReplacePath']
assert sorted(p.name for p in cloak_dir.iterdir() if p.is_file()) == sorted(r['Name'] for r in plan['CloakInventory'])
for row in plan['CloakInventory']:
    assert sha(cloak_dir / row['Name']) == row['PlusSHA256']
assert sum(r['Name'].endswith('.dds') for r in plan['CloakInventory']) == 4

# Exclusive categories for every non-localization-duplicate entry. These counts
# count diagnostics, not independent root causes: PostValidate, paired texture
# failures and repeated variable warnings can describe the same underlying defect.
category_specs = [
    ('scripts', 'Скрипты, параметры и проверка данных', 192,
     ['jomini_script_system.cpp:303','jomini_trigger.cpp:243','jomini_effect.cpp:139',
      'pdx_persistent_reader.cpp:216','jomini_script_argument.cpp:227','jomini_eventtarget.cpp:692',
      'jomini_eventtarget.h:291','jomini_eventmanager.cpp:119','jomini_eventmanager.cpp:428',
      'databases.h:36','character_currency_effects_impl.cpp:227']),
    ('read_not_set', 'Переменные/флаги используются, установка не найдена', 50, ['jomini_effect.cpp:1161']),
    ('set_not_read', 'Переменные/флаги устанавливаются, использование не найдено', 22, ['jomini_effect.cpp:1145']),
    ('animations', 'Неизвестные состояния портретных анимаций', 48, ['portraitanimations.cpp:110']),
    ('accessories', 'Недоступные аксессуары в группах генов', 32, ['portraitaccessories.cpp:159']),
    ('entities', 'Отсутствующие сущности моделей', 26, ['pdx_entity.cpp:666','portraitaccessories.cpp:65']),
    ('mesh_settings', 'Несогласованные настройки моделей', 40, ['pdxassetutil.cpp:1763']),
    ('mesh_uv', 'UV-развёртки моделей', 39, ['pdxassetutil.cpp:556','pdxassetutil.cpp:2002']),
    ('textures', 'Отсутствующие текстуры и иконки', 32, ['pdxassetutil.cpp:1053','virtualfilesystem.cpp:456','game_icons.cpp:746']),
    ('texture_duplicates', 'Дубли текстур', 10, ['pdxassetutil.cpp:1009']),
    ('history', 'Ссылки на персонажей и титулы', 9, ['title_links.cpp:214','history.cpp:644']),
    ('dna', 'Повторное поле в DNA закладок', 2, ['portraitcontext.cpp:239']),
    ('localization', 'Отсутствующие ключи локализации', 4, ['artifact_feature.cpp:33','jomini_dynamicdescription.cpp:66']),
    ('modifiers', 'Неиспользуемые/некорректные модификаторы', 6, ['static_modifier.cpp:200','opinion_modifier.cpp:83']),
    ('orphan_events', 'События без найденного вызова', 2, ['jomini_eventmanager.cpp:372']),
    ('ai_decision', 'Период проверки решения ИИ', 1, ['decision_type.cpp:224']),
    ('descriptor', 'Некорректная версия в дескрипторе', 1, ['dlc_descriptor.cpp:70']),
    ('rule_references', 'Неизвестные ссылки на игровые правила', 2, []),
    ('achievement_assert', 'Сообщение проверки загрузки достижений', 1, ['pdx_assert.cpp:619']),
]
component_categories = {comp: key for key,_,_,comps in category_specs for comp in comps}
remaining = []
duplicates = []
for row in after:
    if row['Component'] == 'pdx_localize.cpp:279':
        duplicates.append(row)
        continue
    category = component_categories[row['Component']]
    if row['Component'] == 'pdx_persistent_reader.cpp:216' and 'Failed to read key reference:' in row['Message']:
        category = 'rule_references'
    remaining.append(dict(FineCategory=category, **row))
assert len(duplicates) == 1190 and len(remaining) == 519
fine_summary = []
for key,label,expected,_ in category_specs:
    selected = [r for r in remaining if r['FineCategory'] == key]
    assert len(selected) == expected, (key,len(selected),expected)
    fine_summary.append(dict(Category=key, Label=label, Messages=len(selected),
                             DistinctMessages=len({r['Message'] for r in selected})))
    export('remaining-' + key + '.csv', selected, list(remaining[0]))
export('remaining-categories.csv', fine_summary, list(fine_summary[0]))
export('remaining-all.csv', remaining, list(remaining[0]))

summary = dict(PreviousEntries=len(before), CurrentEntries=len(after),
    RawRemovedMessages=removed.total(), RawAddedMessages=added.total(), ReviewedSourcePathVariations=1,
    ResolvedMessages=44, NewDiagnosticsAfterReview=0,
    PreviousAGOTPlusAssociated=len(prior), CurrentAGOTPlusAssociated=len(associated),
    PrimaryTargetsResolved=38, SecondaryHeraldryResolved=6, Categories=categories,
    AllRemainingCategories=fine_summary, LocalizationDuplicates=len(duplicates),
    OtherDiagnostics=len(remaining), DistinctOtherMessages=len({r['Message'] for r in remaining}),
    ActiveMods=len(mods), DescriptorOrderAndPathsUnchanged=True, PatchRevision=14,
    PatchRuntimeFiles=139, PreviousPatchFilesUnchanged=126, VerifiedOutputs=len(runtime),
    MDEOutputsVerified=20, SourcePinsVerified=len(sources),
    Stage14SourceAndEvidencePinsVerified=len(plan['Sources'])+len(plan['Evidence']),
    CloakDescriptorExclusionVerified=True, FourCloakDDSWarningsAbsent=True,
    PriorFixRegressions=regressions, VariableTargetsStillAbsent=len(variables),
    LocalizationTargetsStillAbsent=len(loc_keys), MDEDuplicatesStillAbsent=141,
    OtherModDNAMessages=len(other_dna), Started=launch.isoformat(), ExitLine=exit_line,
    MountEvidence=mounts, SnapshotErrorSHA256=sha(HERE / 'snapshot/error.log'),
    VisualEquivalenceChecked=False, InCampaignBehaviorChecked=False)
save('comparison-summary.json', summary)
print(json.dumps({k: summary[k] for k in ('PreviousEntries','CurrentEntries',
      'PrimaryTargetsResolved','SecondaryHeraldryResolved','CurrentAGOTPlusAssociated',
      'NewDiagnosticsAfterReview','VerifiedOutputs','LocalizationDuplicates','OtherDiagnostics')}))
