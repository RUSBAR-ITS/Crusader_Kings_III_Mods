"""Read-only audit of two orphan events and five miscellaneous log entries."""
from collections import Counter
from pathlib import Path
import csv
import hashlib
import json
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PROFILE = Path('C:/Users/RUSBAR/Documents/Paradox Interactive/Crusader Kings III')
GAME = Path('E:/SteamLibrary/steamapps/common/Crusader Kings III/game')
RUN = HERE.parent/'ck3-agot-submods-resource-log-2026-09-20'
sys.path.insert(0, str(REPO/'AGOT_Submods/AGOT_SUBMODS_FIX/tools'))
from ScriptBlocks import parse

pins = {}
def read(p):
    p = Path(p); raw = p.read_bytes()
    pins[str(p.resolve())] = hashlib.sha256(raw).hexdigest()
    return raw.decode('utf-8-sig')
def load(p): return json.loads(read(p))
def rows(p): return list(csv.DictReader(read(p).splitlines()))
def save(name, obj):
    (HERE/name).write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')

enabled = load(PROFILE/'dlc_load.json')['enabled_mods']
mods = rows(RUN/'active-mods.csv')
assert enabled == [r['Descriptor'] for r in mods]
mounts = [dict(Path=str(GAME), Name='CK3', Replace=[])]
for row in mods:
    text = read(PROFILE/row['Descriptor'])
    path = re.search(r'(?m)^\s*path\s*=\s*"([^"]+)"', text)[1]
    assert Path(path).resolve() == Path(row['Path']).resolve()
    mounts.append(dict(Path=path, Name=row['Name'], Replace=re.findall(r'(?m)^\s*replace_path\s*=\s*"([^"]+)"', text)))
def provider(rel):
    result = None
    for mod in mounts:
        if any(rel.lower() == q.lower() or rel.lower().startswith(q.rstrip('/').lower()+'/') for q in mod['Replace']):
            result = None
        p = Path(mod['Path'])/rel
        if p.is_file(): result = p
    return result

# Exact namespaces, allowing alternate numeric spellings such as .1/.0001.
pattern = r'\b(?:buy_valyrian_mask|asoiaf_young_griff_landing_events)\.0*[123]\b'
dirs = [str(Path(m['Path'])/sub) for m in mounts for sub in ('common', 'events', 'history', 'gui')
        if (Path(m['Path'])/sub).is_dir()]
result = subprocess.run(['rg', '-l', pattern, *dirs], capture_output=True, text=True, encoding='utf-8')
assert result.returncode == 0, result.stderr
references = []
for filename in result.stdout.splitlines():
    p = Path(filename)
    owners = [m for m in mounts if p.is_relative_to(Path(m['Path']))]
    assert len(owners) == 1
    rel = p.relative_to(owners[0]['Path']).as_posix()
    active = provider(rel).resolve() == p.resolve()
    for line, text in enumerate(read(p).splitlines(), 1):
        for match in re.finditer(pattern, text):
            namespace, number = match[0].split('.')
            references.append(dict(File=rel, Path=str(p), Owner=owners[0]['Name'], Active=active,
                                   Line=line, Event=namespace+'.'+str(int(number)),
                                   CommentOnly=text.lstrip().startswith('#'), Text=text.strip()))
save('event-references.json', references)
active_refs = [r for r in references if r['Active'] and not r['CommentOnly']]
assert Counter(r['Event'] for r in active_refs) == {
    'buy_valyrian_mask.1':1, 'buy_valyrian_mask.2':6, 'buy_valyrian_mask.3':2,
    'asoiaf_young_griff_landing_events.1':2, 'asoiaf_young_griff_landing_events.2':1,
    'asoiaf_young_griff_landing_events.3':2}

decision_path = provider('common/decisions/10_lotd_decisions.txt')
decision = next(n for n in parse(read(decision_path)) if n.key == 'buy_facemask_decision')
body = read(decision_path)[decision.start:decision.end]
assert 'buy_valyrian_mask.' not in body
assert 'decision_option_list_controller' in body
assert all('add_character_flag = wears_valyrian_mask_0'+str(i) in body for i in range(1,6))
assert len(decision.one('widget').children('item')) == 5

# Match each invalid preset option to both the effective game-rule database and
# the actual two multi-line messages, not merely to similar-looking names.
rule_paths = set()
for mod in mounts:
    root = Path(mod['Path'])
    rule_paths.update(p.relative_to(root).as_posix() for p in (root/'common/game_rules').rglob('*.txt'))
options = {}
for rel in sorted(rule_paths):
    p = provider(rel)
    if p is None: continue
    for rule in parse(read(p)):
        if not isinstance(rule.value, list): continue
        for option in rule.value:
            if isinstance(option.value, list) and option.key not in ('categories', 'is_shown', 'can_pick'):
                options[option.key] = dict(Rule=rule.key, File=rel, Path=str(p))
preset_path = PROFILE/'player/game_rules/presets.txt'
text = read(preset_path)
preset_records = []
for node in parse(text):
    settings = node.one('setting')
    selected = re.findall(r'\b[A-Za-z_0-9]+\b', text[settings.start:settings.end].split('{',1)[1])
    unknown = [s for s in selected if s not in options]
    preset_records.append(dict(Name=node.one('name').value.strip('"'),
                               SettingLine=text[:settings.start].count('\n')+1,
                               Selected=len(selected), Recognized=len(selected)-len(unknown),
                               Unknown=unknown, UnknownCount=len(unknown),
                               ACR=sum(s.startswith('ACR_RE_') for s in unknown),
                               HM=sum(s.startswith('HM_RE_') for s in unknown)))
with (RUN/'remaining-rule_references.csv').open(encoding='utf-8-sig', newline='') as f:
    warnings = list(csv.DictReader(f))
assert len(warnings) == len(preset_records) == 2
for p, w in zip(preset_records, warnings):
    reported = re.findall(r'Failed to read key reference: ([^:]+):', w['Message'])
    assert p['Unknown'] == reported, dict(Name=p['Name'], OnlyScan=sorted(set(p['Unknown'])-set(reported)), OnlyLog=sorted(set(reported)-set(p['Unknown'])), SameSet=set(p['Unknown'])==set(reported))
    assert p['SettingLine'] == int(re.findall(r'near line: (\d+)', w['Message'])[-1])
save('preset-analysis.json', dict(File=str(preset_path), EffectiveOptions=len(options), Presets=preset_records))

achievement_rel = set()
achievement_sources = []
for mod in mounts:
    root = Path(mod['Path'])
    paths = list((root/'common/achievements').rglob('*.txt'))
    achievement_rel.update(p.relative_to(root).as_posix() for p in paths)
    achievement_sources.append(dict(Name=mod['Name'], Files=len(paths),
                                    Replaces='common/achievements' in mod['Replace']))
effective_achievements = [str(provider(rel)) for rel in sorted(achievement_rel) if provider(rel) is not None]
assert not effective_achievements
save('achievement-analysis.json', dict(Mounts=achievement_sources, EffectiveFiles=effective_achievements,
                                      Conclusion='AGOT explicitly replaces common/achievements; no active mod supplies replacement files.',
                                      EngineCauseProven=False, DummyAchievementRecommended=False))

for p in [GAME/'events/_events.info', GAME/'common/decisions/_decisions.info', GAME/'common/game_rules/_game_rules.info',
          Path('E:/SteamLibrary/steamapps/workshop/content/1158310/2261468688/descriptor.mod'),
          Path('E:/SteamLibrary/steamapps/workshop/content/1158310/3101422928/localization/english/event_localization/buy_valyrian_mask_l_english.yml'),
          provider('common/decisions/show_notifications_decision.txt'),
          provider('common/scripted_guis/sgui_message_settings.txt'),
          provider('common/scripted_effects/00_agot_invasion_scripted_effects.txt')]: read(p)
save('source-evidence.json', pins)
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == digest for p, digest in pins.items())
summary = dict(AnalysisOnly=True, GameOrModFilesChanged=False, ActiveMods=len(mods),
               Categories={'orphan_events':2, 'ai_decision':1, 'descriptor':1, 'rule_references':2, 'achievement_assert':1},
               ActiveEventReferences=len(active_refs), SourceFilesPinned=len(pins),
               MaskChoiceAlreadyInDecision=True, PresetNames=[p['Name'] for p in preset_records],
               UnknownPresetOptionsPerEntry=[p['UnknownCount'] for p in preset_records],
               EffectiveAchievementFiles=len(effective_achievements))
save('summary.json', summary)
print(json.dumps(summary, ensure_ascii=False, indent=2))
