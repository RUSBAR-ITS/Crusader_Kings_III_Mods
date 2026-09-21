"""Training interactions: modeled effects and native-definition checks, not a CK3 run."""
from pathlib import Path
import copy
import unittest

from test_addon import (PREFIX, SKILLS, PERSONALITY_TRAITS, EFFECTS, INTERACTIONS,
                        Character, field, parse, walk)

MILITARY = PREFIX + 'military_retraining_effect'
SECRETS = PREFIX + 'valyrian_secrets_effect'
KEEP = {'education_martial_5', 'education_martial_prowess_5'}
EDUCATIONS = {f'education_{family}_{level}'
              for family in ('diplomacy', 'martial', 'stewardship', 'intrigue', 'learning',
                             'martial_prowess', 'republican_knowledge', 'heir_training')
              for level in range(1, 5 if family == 'heir_training' else 6)}


class TrainingCharacter(Character):
    """Minimal model of the mentor/story cleanup used here. Court movement is not simulated."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stories = set()
        self.mentors = set()
        self.squires = set()

    def test(self, nodes):
        return all((v in self.flags) if k == 'has_character_flag' else super(TrainingCharacter, self).test([(k, op, v)])
                   for k, op, v in nodes)

    def apply(self, nodes):
        pending = []
        for k, op, v in nodes:
            if k not in ('save_scope_as', 'every_relation', 'every_owned_story', 'remove_character_flag'):
                pending.append((k, op, v))
                continue
            super().apply(pending)
            pending = []
            if k == 'save_scope_as':
                assert v == PREFIX + 'retrained_knight'
            elif k == 'every_relation':
                assert field(v, 'type') == 'agot_knight'
                assert field(v, 'remove_relation_agot_squire') == 'scope:' + PREFIX + 'retrained_knight'
                self.mentors.clear()
            elif k == 'every_owned_story':
                story_type = field(field(v, 'limit'), 'story_type')
                assert field(v, 'end_story') == 'yes'
                if story_type in self.stories:
                    self.stories.remove(story_type)
                    # The relevant native on_end cleanup; unrelated stories are preserved.
                    self.flags.discard('had_ongoing_squire_story')
                    self.variables.pop('years_as_squire', None)
            else:
                self.flags.discard(v)
        super().apply(pending)


def reachable_effects(name, seen=None):
    seen = set() if seen is None else seen
    if name in seen:
        return []
    seen.add(name)
    result = list(walk(EFFECTS[name]))
    for k, _, v in list(result):
        if k in EFFECTS:
            result.extend(reachable_effects(k, seen))
        if k == 'PICKER':
            result.extend(reachable_effects(v, seen))
    return result


class SpecialTrainingTests(unittest.TestCase):
    def test_military_minimums_education_replacement_and_repeat(self):
        for education in EDUCATIONS | {None}:
            for base in (0, 25, 49, 50, 80, 100):
                c = TrainingCharacter(base, {'scarred', 'brave', 'lifestyle_blademaster'} | ({education} if education else set()))
                c.xp['lifestyle_blademaster', ''] = 42
                c.run(MILITARY)
                expected = {s: max(base, 50 if s in ('martial', 'prowess') else 25) for s in SKILLS}
                self.assertEqual(c.skills, expected)
                self.assertEqual(c.traits & EDUCATIONS, KEEP)
                self.assertTrue({'scarred', 'brave', 'lifestyle_blademaster', 'squire'} <= c.traits)
                self.assertEqual(c.xp['squire', 'knight'], 100)
                self.assertEqual(c.xp['lifestyle_blademaster', ''], 42)
                before = copy.deepcopy(c.__dict__)
                c.run(MILITARY)
                self.assertEqual(c.__dict__, before)

    def test_knighting_ends_only_own_apprenticeship(self):
        c = TrainingCharacter(traits={'stripped_knight', 'loyal'})
        c.stories = {'story_agot_squire_ongoing', 'some_unrelated_story'}
        c.mentors = {'former_teacher'}
        c.squires = {'own_apprentice'}
        c.flags = {'cannot_be_knighted', 'had_ongoing_squire_story',
                   'agot_favors_being_a_squire_flag', 'agot_knighthood_knightless_squire_flag', 'unrelated_flag'}
        c.variables = {'years_as_squire': 8, 'unrelated_variable': 3}
        c.run(MILITARY)
        self.assertNotIn('stripped_knight', c.traits)
        self.assertIn('loyal', c.traits)
        self.assertEqual(c.stories, {'some_unrelated_story'})
        self.assertFalse(c.mentors)
        self.assertEqual(c.squires, {'own_apprentice'})
        self.assertEqual(c.flags, {'unrelated_flag'})
        self.assertEqual(c.variables, {'unrelated_variable': 3})

    def test_secrets_all_skills_reforging_education_and_no_inspiration(self):
        for base in (0, 39, 40, 80, 100):
            for seed in range(12):
                c = Character(base=base, traits={'education_learning_2', 'scarred'}, seed=seed).run(SECRETS)
                self.assertEqual(set(c.skills.values()), {max(base, 40)})
                self.assertIn('can_reforge_valyrian_steel', c.flags)
                self.assertEqual(len(c.traits & PERSONALITY_TRAITS), 4)
                self.assertEqual(len(c.traits & EDUCATIONS), 1)
                self.assertTrue(next(iter(c.traits & EDUCATIONS)).endswith('_5'))
                before = copy.deepcopy(c.__dict__)
                c.run(SECRETS)
                self.assertEqual(c.__dict__, before)
        existing = Character(traits={'education_learning_5', 'education_martial_prowess_4'}).run(SECRETS)
        self.assertTrue({'education_learning_5', 'education_martial_prowess_4'} <= existing.traits)
        for name in (MILITARY, SECRETS):
            nodes = reachable_effects(name)
            self.assertFalse({'create_inspiration', 'destroy_inspiration', 'end_inspiration',
                              'create_character', 'appoint_court_position', 'visit_court_of'} & {k for k, _, _ in nodes})
            self.assertFalse(any(k == 'add_trait' and v == 'loyal' for k, _, v in nodes))

    def test_interaction_guards_and_installed_education_and_knight_maximum(self):
        for stem in ('military_retraining', 'valyrian_secrets'):
            interaction = INTERACTIONS[PREFIX + stem + '_interaction']
            self.assertEqual(field(interaction, 'category'), 'interaction_category_cheat_menu')
            for gate in (field(interaction, 'is_shown'), field(interaction, 'can_send'),
                         field(field(field(interaction, 'on_accept'), 'if'), 'limit')):
                self.assertEqual(field(gate, PREFIX + 'human_context_trigger'), 'yes')
                self.assertEqual(field(field(gate, 'scope:recipient'), 'is_adult'), 'yes')
        agot = Path('E:/SteamLibrary/steamapps/workshop/content/1158310/2962333032')
        if not agot.exists():
            self.skipTest('Installed AGOT definitions unavailable')
        traits = {k: v for f in (agot / 'common/traits').glob('*.txt') for k, _, v in parse(f) if isinstance(v, list)}
        known_education = {k for k in traits if k.startswith('education_') and not k.startswith('education_dragon_')}
        self.assertEqual(EDUCATIONS, known_education)
        for trait in KEEP:
            self.assertEqual(field(traits[trait], 'level'), '5')
        knight_track = field(field(traits['squire'], 'tracks'), 'knight')
        self.assertEqual(max(int(k) for k, _, _ in knight_track), 100)
        removed = {v for k, _, v in walk(EFFECTS[MILITARY]) if k == 'remove_trait'}
        self.assertEqual(removed, EDUCATIONS - KEEP)
        native = dict((k, v) for k, _, v in parse(agot / 'common/scripted_triggers/00_agot_knighting_triggers.txt'))
        knight_check = list(walk(native['is_agot_knight_trigger']))
        self.assertIn(('value', '>=', '100'), knight_check)
        self.assertIn(('story_type', '=', 'story_agot_squire_ongoing'), knight_check)


if __name__ == '__main__':
    unittest.main()
