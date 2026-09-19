"""Verify the follow-up analysis; writes report artifacts only, not game files."""
import hashlib
import re
import urllib.request
from pathlib import Path

import analyze_scripts as a
from collect_evidence import GROUPS


LEGACY_URL = ('https://gitlab.com/anbennar/anbennar-ck3-dev/-/raw/'
              'a7050ee82a6be4d921722f999121823b49cc93e4/'
              'common/scripted_triggers/00_available_for_events_triggers.txt')


def main():
    baseline = a.load(a.OUT / 'audit-summary.json')
    manifest_path = a.PATCH / 'docs/source-manifest.json'
    manifest = a.load(manifest_path)
    assert a.sha(manifest_path) == baseline['ManifestSHA256']
    for row in manifest['Files']:
        assert a.sha(a.PATCH / row['File']) == row['PatchedSHA256']
    assert a.sha(a.PROFILE / 'logs/error.log') == baseline['LogSHA256']
    _, files = a.vfs()
    evidence = []

    def source(rel, lo, hi, reason):
        entry = files[rel]
        lines = a.read(entry['Path']).splitlines()
        assert 1 <= lo <= hi <= len(lines)
        evidence.append(dict(File=rel, Provider=entry['Mod'], Path=str(entry['Path']),
                             SHA256=a.sha(entry['Path']), LineStart=lo, LineEnd=hi,
                             Reason=reason, Text='\n'.join(lines[lo-1:hi])))
        return a.read(entry['Path'])

    rel = 'common/decisions/asoiaf_house_branch_decisions.txt'
    text = a.read(files[rel]['Path'])
    obsolete = re.compile(r'(?m)^[ \t]*(decision_has_second_step|decision_custom_widget_container)'
                          r'\s*=\s*[^\r\n]*(?:\r?\n|$)')
    removed = obsolete.findall(text)
    assert removed.count('decision_has_second_step') == 4
    assert removed.count('decision_custom_widget_container') == 4
    candidate = obsolete.sub('', text)  # Memory only: no runtime output file.
    roots = [b for b in a.blocks(text) if b['Depth'] == 0]
    after = {b['Id']: b for b in a.blocks(candidate) if b['Depth'] == 0}
    assert len(roots) == len(after) == 4
    decisions = []
    for root in roots:
        body = root['Body']
        new_body = after[root['Id']]['Body']
        assert obsolete.sub('', body) == new_body
        items = [b for b in a.blocks(body) if b['Id'] == 'item']
        values = [re.search(r'(?m)^\s*value\s*=\s*(\w+)', b['Body'])[1] for b in items]
        assert len(values) == len(set(values))
        effects = [b['Body'] for b in a.blocks(body) if b['Id'] == 'effect' and b['Depth'] == 1]
        new_effects = [b['Body'] for b in a.blocks(new_body) if b['Id'] == 'effect' and b['Depth'] == 1]
        assert effects and effects == new_effects
        for value in values:
            assert re.search(r'scope:' + re.escape(value) + r'\s*=\s*yes', '\n'.join(effects))
        for retained in ('gui', 'controller', 'decision_to_second_step_button'):
            assert re.search(r'\b' + retained + r'\s*=', new_body)
        decisions.append(dict(Decision=root['Id'], Choices=values, EffectsIdentical=True,
                              AllChangesLimitedToTwoObsoleteProperties=True))
    assert sum(len(d['Choices']) for d in decisions) == 9
    evidence.append(dict(File=rel, Provider=files[rel]['Mod'], Path=str(files[rel]['Path']),
                         SHA256=a.sha(files[rel]['Path']), Reason='Four decisions, nine selectable values'))

    for args in [
        ('gui/decision_view_widgets/decision_view_widget_petition_liege.gui', 24, 55, 'Entries and selection handler'),
        ('gui/window_decisions_detail.gui', 180, 190, 'Current custom widget container'),
        ('gui/window_decisions_detail.gui', 216, 218, 'Confirm handler'),
        ('gui/window_decisions_detail.gui', 250, 294, 'Second step and back navigation'),
        ('common/decisions/30_activity_decisions.txt', 448, 465, 'Current native widget declaration'),
        ('common/character_interactions/asoiaf_character_interactions.txt', 108, 194, 'Heir interaction remains unchanged'),
        ('common/trigger_localization/01_character_interaction_triggers.txt', 415, 423, 'Legacy explanation keys still exist'),
        ('events/yearly_events/yearly_events_2.txt', 1244, 1252, 'Abductor flag still set'),
        ('events/yearly_events/yearly_events_2.txt', 1281, 1289, 'Abducted flag still set'),
        ('events/agot_events/agot_scenario_defiance_of_duskendale_events.txt', 2128, 2136, 'Story-specific reuse of abductor flag'),
        ('localization/english/modifiers/asoiaf_modifiers_l_english.yml', 203, 204, 'Explicit intended mother categories and unfinished implementation warning'),
        ('common/scripted_triggers/asoiaf_canon_children_triggers.txt', 1731, 1788, 'Birth sequencing and a historical mother exception precedent'),
        ('common/scripted_effects/asoiaf_canon_children_effects.txt', 20, 93, 'Existing pregnancy and parentage helpers'),
        ('history/characters/00_agot_char_braavos_ancestors.txt', 1331, 1342, 'Historical Bellegere is Braavosi'),
    ]:
        source(*args)

    cultures_rel = 'common/culture/cultures/00_agot_cul_summer_islander.txt'
    cultures = a.read(files[cultures_rel]['Path'])
    culture_info = []
    for b in a.blocks(cultures):
        if b['Depth'] == 0:
            heritage = re.search(r'(?m)^\s*heritage\s*=\s*(\w+)', b['Body'])
            language = re.search(r'(?m)^\s*language\s*=\s*(\w+)', b['Body'])
            culture_info.append(dict(Culture=b['Id'], Heritage=heritage[1] if heritage else None,
                                     Language=language[1] if language else None))
    source(cultures_rel, 1, 7, 'Modern Summer Islander culture definitions; parsed values recorded separately')

    with urllib.request.urlopen(LEGACY_URL, timeout=30) as response:
        legacy_bytes = response.read()
    legacy_text = legacy_bytes.decode('utf-8-sig')
    legacy = [b for b in a.blocks(legacy_text) if b['Id'] == 'is_busy_in_events_localised' and b['Depth'] == 0]
    assert len(legacy) == 1
    body = legacy[0]['Body']
    flags = re.findall(r'NOT\s*=\s*\{\s*has_character_flag\s*=\s*(\w+)\s*\}', body)
    explanations = re.findall(r'\btext\s*=\s*"([^"]+)"', body)
    assert flags == explanations == ['yearly_1010_abducted', 'yearly_1010_abductor']
    assert body.count('custom_description') == 2 and 'is_available' not in body

    cache_root = Path('C:/Users/RUSBAR/AppData/Local/Temp/ck3-agot-rus-correct-7kingdoms')
    cache_ids = [
        '92C46637721D817453311425C70986470F870C88BBB203AC26FA826B9A739904',
        '55185F1447F7C5197A98628E359CE0A31634B3A8CDF75DC647D974115393F968',
        'A79A5B0854DEA05C13B8F9F890E25FE8AF9460BB4051E635C9FEFBA7C7E423C2',
        'DEC9199894C75B6279533700B453A0FA4250665E337D95A28C6EC7B4E69B69AB',
        '1E54714A99E45D2FB65DB957E5303C3FB4EDBBD68D85F4B93C61F63F7C7AB05B',
    ]
    public_sources = []
    for cache_id in cache_ids:
        path = cache_root / (cache_id + '.json')
        data = a.load(path)
        public_sources.append(dict(CachePath=str(path), SHA256=a.sha(path),
                                   Metadata={k: v for k, v in data.items() if k not in ('Text', 'Html', 'HTML')}))

    recs = a.load(a.OUT / 'recommended-changes.json')
    group_map = {key: (lines, recommendation) for key, lines, recommendation in GROUPS}
    assert len(recs) == len(group_map) == 8
    for row in recs:
        lines, recommendation = group_map[row['Group']]
        assert row['LogLines'] == lines and row['Implemented'] is False
        row['Recommendation'] = recommendation
    assert sum(r['MessageCount'] for r in recs) == 25
    a.json_write('recommended-changes.json', recs)

    for row in manifest['Files']:
        assert a.sha(a.PATCH / row['File']) == row['PatchedSHA256']
    assert a.sha(manifest_path) == baseline['ManifestSHA256']
    a.json_write('followup-verification.json', dict(
        RuntimeChangesApplied=False, RuntimeFilesUnchanged=len(manifest['Files']),
        ManifestSHA256=a.sha(manifest_path), ExistingLogUnchanged=True, GameExecutionChecked=False,
        DecisionSimulation=dict(InMemoryOnly=True, RemovedProperties=len(removed), Decisions=decisions),
        LocalEvidence=evidence, ModernCultureDefinitions=culture_info,
        LegacyCheck=dict(URL=LEGACY_URL, SHA256=hashlib.sha256(legacy_bytes).hexdigest().upper(),
                         Function='is_busy_in_events_localised', AbsentFlagsRequired=flags,
                         ExplanationKeys=explanations,
                         ProvenanceLimit='Historical Anbennar source snapshot; not proven to be the exact AGOT+ dependency version'),
        SevenKingdomsSources=public_sources, RecommendationGroups=8, CoveredLogMessages=25))
    print('Verified: 4 decisions / 9 choices / 8 obsolete properties; 2 historical flag checks; '
          '32 runtime files unchanged. Updated report artifacts only.')


if __name__ == '__main__':
    main()
