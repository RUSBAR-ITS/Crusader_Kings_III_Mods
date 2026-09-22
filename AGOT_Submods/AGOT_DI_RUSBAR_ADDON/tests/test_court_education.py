"""Court education and knighting: character effects, not an engine/appointment test."""
import copy
import csv
import re
import unittest

from test_addon import BASE, PREFIX, SKILLS, EFFECTS, field, walk
from test_special_training import TrainingCharacter

MAIN = SKILLS[:-1]
MAIN_TRAITS = {f'education_{family}_{level}' for family in MAIN for level in range(1, 6)}
PROWESS = {f'education_martial_prowess_{level}' for level in range(1, 6)}
KNIGHTING = PREFIX + 'court_knighthood_effect'
SELECTOR = PREFIX + 'court_education_'
SPAWNS = {name.removeprefix(PREFIX + 'spawn_').removesuffix('_effect'): nodes
          for name, nodes in EFFECTS.items() if name.startswith(PREFIX + 'spawn_')}


def expected_choices():
    """Independent aptitude research, before the general minimum of 25 was added."""
    profiles = {}
    with (BASE / 'docs/court-position-aptitude-2026-09-20.csv').open(encoding='utf-8-sig') as f:
        labels = dict(zip(SKILLS, ('дипломатия', 'военное дело', 'управление', 'интриги', 'учёность', 'доблесть')))
        for row in csv.DictReader(f):
            profiles[row['position_id']] = {s for s, word in labels.items() if word in row['base_and_skills']}
    with (BASE / 'docs/court-position-base-and-camp-2026-09-20.csv').open(encoding='utf-8-sig') as f:
        letters = dict(zip('DMSILP', SKILLS))
        for row in csv.DictReader(f):
            profiles[row['id']] = {letters[s] for s, goal in re.findall(r'([DMSILP])(\d+)', row['base_skills'])
                                   if int(goal) > 0}
    result = {}
    for role in SPAWNS:
        skills = profiles[role]
        choices = skills & set(MAIN)
        result[role] = choices or ({'martial'} if 'prowess' in skills else set(MAIN))
    return result


def creation_preparation(nodes):
    # The model does not create world scopes or inspirations; these are checked statically.
    return [n for n in field(nodes, 'scope:' + PREFIX + 'new_courtier')
            if n[0] not in ('save_scope_as', 'create_inspiration')]


class CourtEducationTests(unittest.TestCase):
    def test_all_eye_choices_follow_role_skills_and_use_equal_weights(self):
        self.assertEqual(len(SPAWNS), 93)
        for role, expected in expected_choices().items():
            with self.subTest(role=role):
                body = creation_preparation(SPAWNS[role])
                names = [k for k, _, _ in body]
                selectors = [k for k in names if k.startswith(SELECTOR)]
                self.assertEqual(len(selectors), 1)
                selection = EFFECTS[selectors[0]]
                traits = {v for k, _, v in walk(selection) if k == 'add_trait'}
                self.assertEqual(traits, {f'education_{s}_5' for s in expected})
                lottery = next((v for k, _, v in walk(selection) if k == 'random_list'), None)
                if len(expected) > 1:
                    self.assertEqual(len(lottery), len(expected))
                    self.assertEqual({weight for weight, _, _ in lottery}, {'100'})
                else:
                    self.assertIsNone(lottery)
                self.assertLess(names.index(PREFIX + 'prepare_' + role + '_effect'), names.index(selectors[0]))
                self.assertLess(names.index(selectors[0]), names.index(KNIGHTING))
                # Both effects are in the created character's scope, before native appointment checks.
                keys = [k for k, _, _ in SPAWNS[role]]
                self.assertLess(keys.index('create_character'), keys.index('scope:' + PREFIX + 'new_courtier'))
                appointment = next(i for i, (_, _, v) in enumerate(SPAWNS[role])
                                   if isinstance(v, list) and any(k == 'appoint_court_position' for k, _, _ in walk(v)))
                self.assertLess(keys.index('scope:' + PREFIX + 'new_courtier'), appointment)

    def test_all_summoned_characters_have_one_main_education_and_are_knights(self):
        for role, choices in expected_choices().items():
            observed = set()
            for seed in range(48):
                c = TrainingCharacter(seed=seed)
                c.apply(creation_preparation(SPAWNS[role]))
                education = c.traits & MAIN_TRAITS
                self.assertEqual(len(education), 1, role)
                self.assertTrue(education <= {f'education_{s}_5' for s in choices}, role)
                observed |= education
                self.assertEqual(c.traits & PROWESS, {'education_martial_prowess_5'}, role)
                self.assertIn('loyal', c.traits, role)
                self.assertIn('squire', c.traits, role)
                self.assertEqual(c.xp['squire', 'knight'], 100, role)
                if role == 'stooge_camp_officer':
                    self.assertEqual(set(c.skills.values()), {0})
                    self.assertIn(PREFIX + 'valyrian_slave', c.modifiers)
                if role == 'eparch_court_position':
                    self.assertIn('education_republican_knowledge_4', c.traits)
                # A second preparation preserves a compatible maximum education and character.
                before = copy.deepcopy(c.__dict__)
                c.apply(creation_preparation(SPAWNS[role]))
                self.assertEqual(c.__dict__, before, role)
            self.assertEqual(observed, {f'education_{s}_5' for s in choices}, role)

    def test_treatises_knight_every_supported_role_after_preparation(self):
        branches = EFFECTS[PREFIX + 'treatises_effect']
        self.assertEqual(len(branches), 120)
        for branch, _, nodes in branches:
            self.assertIn(branch, ('if', 'else_if'))
            role = field(field(nodes, 'limit'), 'has_court_position')
            self.assertIsNotNone(role)
            names = [k for k, _, _ in nodes]
            self.assertEqual(names.count(KNIGHTING), 1, role)
            self.assertLess(names.index(PREFIX + 'prepare_' + role + '_effect'), names.index(KNIGHTING))
            self.assertFalse(any(k.startswith(SELECTOR) for k in names), role)
            c = TrainingCharacter(base=80, traits={'education_diplomacy_5', 'education_martial_prowess_2', 'stripped_knight'})
            c.mentors = {'teacher'}
            c.squires = {'own_squire'}
            c.stories = {'story_agot_squire_ongoing', 'unrelated_story'}
            baseline = copy.deepcopy(c).run(PREFIX + 'prepare_' + role + '_effect')
            # Employer lookup is a world operation; run character effects from the selected branch.
            c.apply([n for n in nodes if n[0] not in ('limit', 'random_court_position_employer')])
            self.assertEqual(c.traits & PROWESS, {'education_martial_prowess_5'}, role)
            self.assertEqual(c.traits & MAIN_TRAITS, baseline.traits & MAIN_TRAITS, role)
            self.assertEqual(c.xp['squire', 'knight'], 100, role)
            self.assertNotIn('stripped_knight', c.traits, role)
            self.assertNotIn('loyal', c.traits, role)
            self.assertFalse(c.mentors, role)
            self.assertEqual(c.squires, {'own_squire'}, role)
            self.assertEqual(c.stories, {'unrelated_story'}, role)
            self.assertEqual(set(c.skills.values()), {0 if role == 'stooge_camp_officer' else 80}, role)

    def test_knighting_removes_lower_prowess_only_and_cleans_squire_state(self):
        for previous in PROWESS | {None}:
            c = TrainingCharacter(traits={'education_learning_2', 'education_heir_training_3', 'stripped_knight'}
                                  | ({previous} if previous else set()))
            c.stories = {'story_agot_squire_ongoing', 'unrelated_story'}
            c.mentors = {'mentor'}
            c.squires = {'apprentice'}
            c.variables = {'years_as_squire': 4, 'other_variable': 1}
            c.flags = {'cannot_be_knighted', 'had_ongoing_squire_story', 'agot_favors_being_a_squire_flag',
                       'agot_knighthood_knightless_squire_flag', 'other_flag'}
            c.run(KNIGHTING)
            self.assertEqual(c.traits, {'education_learning_2', 'education_heir_training_3',
                                        'education_martial_prowess_5', 'squire'})
            self.assertEqual(c.xp['squire', 'knight'], 100)
            self.assertEqual(c.flags, {'other_flag'})
            self.assertEqual(c.variables, {'other_variable': 1})
            self.assertEqual(c.stories, {'unrelated_story'})
            self.assertFalse(c.mentors)
            self.assertEqual(c.squires, {'apprentice'})
            before = copy.deepcopy(c.__dict__)
            c.run(KNIGHTING)
            self.assertEqual(c.__dict__, before)

    def test_eye_education_replaces_main_only_and_preserves_maximum_on_repeat(self):
        for name in EFFECTS:
            if not name.startswith(SELECTOR):
                continue
            for previous in MAIN_TRAITS | {None}:
                c = TrainingCharacter(traits={'education_republican_knowledge_4', 'education_martial_prowess_5', 'scarred'}
                                      | ({previous} if previous else set()))
                c.run(name)
                self.assertEqual(len(c.traits & MAIN_TRAITS), 1, name)
                self.assertTrue(next(iter(c.traits & MAIN_TRAITS)).endswith('_5'), name)
                self.assertTrue({'education_republican_knowledge_4', 'education_martial_prowess_5', 'scarred'} <= c.traits)
                before = copy.deepcopy(c.__dict__)
                c.run(name)
                self.assertEqual(c.__dict__, before, name)


if __name__ == '__main__':
    unittest.main()
