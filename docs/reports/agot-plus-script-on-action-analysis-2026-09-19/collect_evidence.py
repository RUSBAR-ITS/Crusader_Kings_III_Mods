"""Collect supporting evidence and verify coverage; never writes runtime files."""
import hashlib
import re
from collections import Counter

import analyze_scripts as a


GROUPS = [
    ('decision_widgets', [9753, 9755, 9758, 9761], 'Remove two obsolete widget properties in each of four decisions; retain option list, selection flags and effects.'),
    ('unfinished_births', [9994, 9995, 9996, 9997, 9998, 9999, 10000, 10001, 10002, 10003, 10004, 10046, 10047], 'Restore seven births from existing AGOT identities and PLUS birth templates; correct trigger numbering, complete sequencing and historical initialization, and make overlapping mother conditions mutually exclusive. See followup-analysis.md for evidence and bounded implementation choices.'),
    ('orphan_megawar', [10017], 'Retain the hidden event ID as an inert compatibility shell; comment the undefined effect call.'),
    ('heir_availability', [10033], 'Replace the missing legacy check with a namespaced helper preserving its two documented negative yearly_1010 flag checks and localized explanations; retain all other heir conditions and consequences. Historical implementation located; see followup-analysis.md.'),
    ('siege_claimant', [10035, 10036], 'Use primary_defender = root in war scope, and explicitly guard the saved claimant scope in both siege handlers.'),
    ('duplicate_title_handler', [10052, 10053], 'Keep one explicitly disabled native CoA handler in its canonical AGOT file; remove the PLUS duplicate definition and redundant registration; retain the separate PLUS cadet-branch handler.'),
    ('child_regency', [10054], 'Migrate start_diarchy to try_start_diarchy, respecting eligibility and existing diarchy state before setting the mother as regent.'),
    ('retired_crownlands_cleanup', [10055], 'Comment the remaining obsolete destroy-Crownlands call; preserve the Young Griff victory event and flag.'),
]


def main():
    summary = a.load(a.OUT / 'audit-summary.json')
    manifest = a.load(a.PATCH / 'docs/source-manifest.json')
    assert a.sha(a.PATCH / 'docs/source-manifest.json') == summary['ManifestSHA256']
    assert all(a.sha(a.PATCH / row['File']) == row['PatchedSHA256'] for row in manifest['Files'])
    prior_sources = a.csv_read(a.OUT / 'source-hashes.csv')
    assert all(a.sha(row['Path']) == row['SHA256'] for row in prior_sources)
    messages = a.csv_read(a.OUT / 'target-messages.csv')
    by_line = {int(row['LogLine']): row for row in messages}
    counts = Counter(line for _, lines, _ in GROUPS for line in lines)
    assert set(counts) == set(by_line) and all(count == 1 for count in counts.values())
    a.json_write('recommended-changes.json', [dict(Group=key, LogLines=lines, MessageCount=len(lines),
        Files=sorted({by_line[n]['Evidence'] for n in lines}), Recommendation=rec,
        Implemented=False) for key, lines, rec in GROUPS])

    _, files = a.vfs()
    sources, excerpts = {}, []

    def add(rel, lo, hi, reason):
        item = files[rel]
        lines = a.read(item['Path']).splitlines()
        assert 1 <= lo <= hi <= len(lines), (rel, lo, hi)
        sources[rel] = dict(File=rel, Mod=item['Mod'], Path=str(item['Path']), SHA256=a.sha(item['Path']))
        excerpts.append(dict(Reason=reason, File=rel, Mod=item['Mod'], LineStart=lo, LineEnd=hi,
                             Text='\n'.join(f'{n}: {lines[n-1]}' for n in range(lo, hi+1))))

    def block(rel, identifier, reason):
        found = [b for b in a.blocks(a.read(files[rel]['Path'])) if b['Depth'] == 0 and b['Id'] == identifier]
        assert found, (rel, identifier)
        for b in found:
            add(rel, b['Line'], b['Line'] + len(b['Body'].splitlines()) - 1, reason)
        return found

    for rel, lo, hi, reason in [
        ('common/decisions/30_activity_decisions.txt', 448, 465, 'Native supported decision widget'),
        ('common/decisions/_decisions.info', 145, 191, 'Shipped widget documentation'),
        ('gui/decision_view_widgets/decision_view_widget_petition_liege.gui', 1, 75, 'Effective GUI and option-list controller'),
        ('common/character_interactions/00_heir.txt', 124, 184, 'Native heir interaction validity conditions'),
        ('common/scripted_triggers/00_available_for_events_triggers.txt', 42, 112, 'Broader availability checks are not mechanical aliases'),
        ('common/on_action/army_on_actions.txt', 413, 424, 'Documented siege-completion scopes'),
        ('events/agot_interaction_events/agot_btw_interaction_events.txt', 369, 380, 'Native primary_defender syntax in war scope'),
        ('common/on_action/title_on_actions.txt', 2814, 2823, 'Native registration of the disputed title handler'),
        ('common/on_action/agot_on_actions/test_title_on_actions.txt', 1, 20, 'PLUS additionally registers the same handler'),
        ('common/on_action/agot_on_actions/test_title_on_actions.txt', 195, 235, 'Separate PLUS cadet-branch handler and obsolete regency call'),
        ('common/scripted_triggers/00_diarchy_scripted_triggers.txt', 210, 240, 'Current diarchy eligibility and personal regency conditions'),
        ('common/diarchies/diarchy_types/00_regencies.txt', 84, 92, 'The named regency type still exists'),
        ('common/scripted_effects/asoiaf_setup_effects.txt', 1, 8, 'Author commented the title destruction function'),
        ('common/on_action/asoiaf_setup.txt', 90, 102, 'Author commented the startup title destruction call'),
        ('common/on_action/agot_on_actions/test_title_on_actions.txt', 435, 452, 'Residual Young Griff call remains active'),
        ('localization/english/asoiaf_game_rules_l_english.yml', 133, 138, 'Leftover MegaWar Cleanup rule descriptions, not an implementation'),
        ('common/scripted_triggers/asoiaf_canon_children_triggers.txt', 1731, 1774, 'Duplicated Lily/Willow ID and Rosey ID shifted by one'),
        ('common/on_action/asoiaf_pregnancy_childbirth_on_actions.txt', 607, 635, 'Both incomplete birth chains are scheduled by pregnancy hook'),
        ('common/scripted_effects/asoiaf_canon_children_effects.txt', 13978, 13985, 'Existing historical Rosey mother pregnancy-negation logic; separate from unfinished chains'),
    ]:
        add(rel, lo, hi, reason)
    for rel, identifier, reason in [
        ('common/on_action/agot_on_actions/agot_title_on_actions.txt', 'agot_on_title_inheritance_lannister_baratheon_coa', 'Native handler definition'),
        ('common/on_action/agot_on_actions/test_title_on_actions.txt', 'agot_on_title_inheritance_lannister_baratheon_coa', 'Author duplicate definition with placeholder gold effect'),
        ('events/diarchy_events/diarchy_events.txt', 'diarchy.0011', 'Native child-regency setup uses try_start_diarchy'),
        ('events/asoiaf_canon_children_events/asoiaf_canon_children_targaryen_events.txt', 'asoiaf_canon_children_targaryen_events.0882', 'Pregnancy terminated before calling missing child creation functions'),
        ('events/asoiaf_canon_children_events/asoiaf_canon_children_targaryen_events.txt', 'asoiaf_canon_children_targaryen_events.0883', 'Second incomplete chain has the same pregnancy loss risk'),
        ('common/scripted_effects/asoiaf_canon_children_effects.txt', 'asoiaf_canon_children_terminate_pregnancy_effect', 'Termination ends the current pregnancy'),
    ]:
        block(rel, identifier, reason)

    children = []
    for n in range(98, 105):
        branch = 'dragonstone' if n <= 101 else 'braavos'
        hist_rel = f'history/characters/00_agot_char_{branch}_ancestors.txt'
        hist = block(hist_rel, f'Targaryen_{n}', 'Existing historical identity does not implement PLUS dynamic birth')[0]
        dummy = block('history/characters/agot_canon_children_dummy_characters.txt', f'Dummy_Targaryen_{n}', 'Native dummy is a template, not a PLUS birth function')[0]
        trait = block('common/traits/asoiaf_canon_children_traits.txt', f'asoiaf_Targaryen_{n}_trait', 'PLUS identity trait exists despite absent birth implementation')[0]
        dna_rel = f'common/dna_data/agot_dna_{branch}_ancestors.txt'
        dna = [b for b in a.blocks(a.read(files[dna_rel]['Path'])) if b['Depth'] == 0 and b['Id'] == f'Targaryen_{n}']
        assert len(dna) == 1
        add(dna_rel, dna[0]['Line'], dna[0]['Line'] + 3, 'DNA preset definition exists')
        children.append(dict(Id=f'Targaryen_{n}', Name=re.search(r'(?m)^\s*name\s*=\s*(\w+)', hist['Body'])[1],
            HistoryFile=hist_rel, HistoryLine=hist['Line'], DummyLine=dummy['Line'], TraitLine=trait['Line'],
            DNAFile=dna_rel, DNALine=dna[0]['Line'], PLUSBirthEffectDefined=False))
    a.csv_write('incomplete-children.csv', children)
    a.json_write('supporting-excerpts.json', excerpts)
    a.csv_write('supporting-source-hashes.csv', list(sources.values()))

    cache = a.OUT.parent / 'agot-plus-dragon-bonding-analysis-2026-09-18/author-sources/changelog-entries.json'
    author = a.load(cache)
    statements = []
    for stamp, meaning in [
        (1757685070, 'Автор отключил базовый личный герб детей Серсеи: у них создаётся отдельная ветвь дома.'),
        (1770417259, 'Автор отменил автоматическое уничтожение Королевских земель.'),
    ]:
        index, entry = next((i, e) for i, e in enumerate(author) if e['Timestamp'] == stamp)
        statements.append(dict(Cache=str(cache.relative_to(a.REPO)), CacheSHA256=a.sha(cache), ArrayIndex=index,
            UTC=entry['UTC'], DateLabel=entry['DateLabel'], URL=entry['URL'], Summary=meaning,
            EntryBodySHA256=hashlib.sha256(entry['Body'].encode()).hexdigest().upper()))
    a.json_write('author-intent.json', statements)
    assert all(a.sha(a.PATCH / row['File']) == row['PatchedSHA256'] for row in manifest['Files'])
    assert a.sha(a.PATCH / 'docs/source-manifest.json') == summary['ManifestSHA256']
    a.json_write('verification.json', dict(UniqueMessagesCovered=len(counts), Groups=len(GROUPS),
        CoverageComplete=True, ExistingEvidenceFilesHashMatched=len(prior_sources),
        AdditionalEvidenceFiles=len(sources), SupportingExcerpts=len(excerpts), HistoricalChildrenIdentified=len(children),
        AuthorStatementsLocated=len(statements), RuntimeFilesUnchanged=len(manifest['Files']),
        ManifestUnchanged=True, RuntimeChangesApplied=False, GameExecutionChecked=False,
        Limits='Lexical audit of effective text files and source comparisons; not an engine execution test.'))
    print(f'Covered {len(counts)} messages in {len(GROUPS)} groups; collected {len(excerpts)} excerpts. Runtime unchanged.')


if __name__ == '__main__':
    main()
