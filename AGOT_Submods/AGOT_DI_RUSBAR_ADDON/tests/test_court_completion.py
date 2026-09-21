"""Court preparation regressions; script model, not an in-game execution."""
from pathlib import Path
import copy
import csv
import random
import re
import unittest

from test_addon import (BASE, PREFIX, PROFILES, EFFECTS, PERSONALITY_TRAITS,
                        SKILLS, Character, field, parse, walk)

FILL = PREFIX + 'fill_court_personality_effect'
FLOOR = PREFIX + 'court_base_skill_floor_effect'


def picker_for(profile):
    return field(field(PROFILES[profile], FILL), 'PICKER')


class CourtCompletionTests(unittest.TestCase):
    def test_all_skills_floor_preserves_high_values_and_stooge_exception(self):
        for name in PROFILES:
            for base in (0, 12, 24, 25, 26, 70, 100):
                with self.subTest(profile=name, base=base):
                    c = Character(base=base).run(name)
                    if 'stooge_' in name:
                        self.assertEqual(set(c.skills.values()), {0})
                        self.assertIn(PREFIX + 'valyrian_slave', c.modifiers)
                        self.assertIsNone(field(PROFILES[name], FLOOR))
                    else:
                        self.assertTrue(all(value >= max(base, 25) for value in c.skills.values()))
                        self.assertEqual(field(PROFILES[name], FLOOR), 'yes')
        tutor = Character().run(PREFIX + 'prepare_court_tutor_court_position_effect')
        self.assertEqual(tutor.skills, dict.fromkeys(SKILLS, 25) | {'learning': 50})
        smith = Character().run(PREFIX + 'prepare_court_smith_court_position_effect')
        self.assertEqual(smith.skills, dict.fromkeys(SKILLS, 25) | {'stewardship': 60, 'prowess': 60})

    def test_random_completion_across_profiles_and_repeated_use(self):
        outcomes = set()
        for name, nodes in PROFILES.items():
            removed = {v for k, _, v in walk(nodes) if k == 'remove_trait'}
            for seed in range(24):
                # Valid pre-existing personalities; count ranges from zero to five.
                prior = {'patient', 'content', 'generous', 'calm', 'chaste'}
                prior = set(random.Random(seed).sample(sorted(prior), seed % 6))
                c = Character(traits=prior | {'loyal', 'scholar', 'education_learning_5'}, seed=seed)
                prepared = copy.deepcopy(c)
                prepared.apply([n for n in nodes if n[0] != FILL])
                c.run(name)
                self.assertGreaterEqual(len(c.traits & PERSONALITY_TRAITS), 4, name)
                self.assertIn('loyal', c.traits)
                # A profile can remove and re-add a trait while resolving alternatives;
                # the random filler itself must never restore any excluded trait.
                self.assertFalse((c.traits - prepared.traits) & removed & PERSONALITY_TRAITS, name)
                state = copy.deepcopy(c.__dict__)
                c.run(name)
                self.assertEqual(c.__dict__, state, (name, seed))
                if name == PREFIX + 'prepare_armorer_camp_officer_effect':
                    outcomes.add(tuple(sorted(c.traits & PERSONALITY_TRAITS)))
        self.assertGreater(len(outcomes), 10, 'Filling must provide different valid personalities')

    def test_filler_preserves_four_or_more_and_does_not_count_professions(self):
        picker = picker_for(PREFIX + 'prepare_armorer_camp_officer_effect')
        for initial in ({'patient', 'content', 'generous', 'calm'},
                        {'patient', 'content', 'generous', 'calm', 'chaste'}):
            c = Character(traits=initial | {'loyal', 'scholar'})
            c.run(FILL, {'PICKER': picker})
            self.assertEqual(c.traits, initial | {'loyal', 'scholar'})
            self.assertEqual(c.random_choices, 0)
        c = Character(traits={'loyal', 'scholar', 'education_learning_5', 'maester'})
        c.run(FILL, {'PICKER': picker})
        self.assertEqual(len(c.traits & PERSONALITY_TRAITS), 4)
        self.assertEqual(c.random_choices, 4)

    def test_candidates_against_installed_traits_and_role_research(self):
        game = Path('E:/SteamLibrary/steamapps/common/Crusader Kings III/game')
        agot = Path('E:/SteamLibrary/steamapps/workshop/content/1158310/2962333032')
        if not (agot / 'common/traits').exists():
            self.skipTest('Installed AGOT trait definitions unavailable')
        files = {}
        for root in (game, agot):
            files.update({f.name: f for f in (root / 'common/traits').glob('*.txt')})
        traits = {k: v for f in files.values() for k, _, v in parse(f) if isinstance(v, list)}
        human_personalities = {k for k, v in traits.items()
                               if field(v, 'category') == 'personality' and not k.startswith('dragon_')}
        self.assertEqual(human_personalities, PERSONALITY_TRAITS)
        negatives = {}
        for filename, idcol, negcol in (
            ('court-position-aptitude-2026-09-20.csv', 'position_id', 'negative_traits_including_shared_health_penalties'),
            ('court-position-base-and-camp-2026-09-20.csv', 'id', 'negative_traits'),
        ):
            with (BASE / 'docs' / filename).open(encoding='utf-8-sig') as stream:
                for row in csv.DictReader(stream):
                    negatives[row[idcol]] = set(re.findall(r'\b[a-z][a-z_]+\b', row[negcol])) & human_personalities
        for profile in PROFILES:
            role = profile.removeprefix(PREFIX + 'prepare_').removesuffix('_effect')
            picker = picker_for(profile)
            for _, _, branch in field(EFFECTS[picker], 'random_list'):
                candidate = field(branch, 'add_trait')
                self.assertIn(candidate, human_personalities)
                self.assertNotIn(candidate, negatives.get(role, set()), (role, candidate))
                self.assertTrue(all(float(field(traits[candidate], s, 0)) >= 0 for s in SKILLS))
                gate = field(branch, 'trigger')
                self.assertFalse(Character(traits={candidate}).test(gate), (role, 'duplicate', candidate))
                # Check both directions: humble omits authoritative/rude in its own opposites.
                for other in human_personalities:
                    forward = {k for k, _, _ in field(traits[candidate], 'opposites', [])}
                    reverse = {k for k, _, _ in field(traits[other], 'opposites', [])}
                    if other in forward or candidate in reverse:
                        self.assertFalse(Character(traits={other}).test(gate), (role, candidate, other))
            # A personality bonus cannot overcome the agreed -100 slave modifier on zero base.
            if role == 'stooge_camp_officer':
                candidates = [field(b, 'add_trait') for _, _, b in field(EFFECTS[picker], 'random_list')]
                for skill in SKILLS:
                    self.assertLess(sum(sorted((float(field(traits[t], skill, 0)) for t in candidates), reverse=True)[:4]), 100)


if __name__ == '__main__':
    unittest.main()
