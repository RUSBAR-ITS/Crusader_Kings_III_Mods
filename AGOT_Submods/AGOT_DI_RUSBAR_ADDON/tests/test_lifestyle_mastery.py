"""Mastery regression tests; modeled script semantics, not a CK3 engine run."""
from pathlib import Path
import struct
import unittest

from test_addon import BASE, PREFIX, EFFECTS, TRIGGERS, ON_ACTIONS, definitions, parse, field, walk

LIFESTYLES = {
    'diplomacy': 'valyrian_diplomat',
    'martial': 'valyrian_warrior',
    'stewardship': 'dragon_lord',
    'intrigue': 'valyrian_spy',
    'learning': 'valyrian_sage',
    'wanderer': 'valyria_returned',
}


def requirements(life, kind):
    return {v for k, _, v in TRIGGERS[PREFIX + life + '_mastered_trigger'] if k == kind}


class MasteryCharacter:
    def __init__(self, perks=(), traits=(), dlc=True):
        self.perks, self.traits = set(perks), set(traits)
        self.modifiers = set()
        self.points = dict.fromkeys(LIFESTYLES, 17)
        self.dlc = dlc

    def matches(self, nodes):
        def one(key, op, value):
            if key in TRIGGERS:
                return self.matches(TRIGGERS[key]) == (value == 'yes')
            if key == 'has_trait':
                return value in self.traits
            if key == 'has_perk':
                return value in self.perks
            if key == 'has_character_modifier':
                return value in self.modifiers
            if key == 'has_dlc_feature':
                assert value == 'wandering_nobles'
                return self.dlc
            if key == 'NOT':
                return not self.matches(value)
            if key == 'OR':
                return any(one(*n) for n in value)
            raise AssertionError(('Unexpected predicate', key, value))
        return all(one(*n) for n in nodes)

    def apply(self, nodes):
        taken = False
        for key, _, value in nodes:
            if key in ('if', 'else_if'):
                if key == 'if':
                    taken = False
                if not taken and self.matches(field(value, 'limit')):
                    self.apply([n for n in value if n[0] != 'limit'])
                    taken = True
            elif key == 'add_character_modifier':
                self.modifiers.add(field(value, 'modifier'))
            elif key == 'remove_character_modifier':
                self.modifiers.discard(value)
            elif key.startswith('add_') and key.endswith('_lifestyle_perk_points'):
                life = key.removeprefix('add_').removesuffix('_lifestyle_perk_points')
                self.points[life] = max(0, self.points[life] + int(value))
            else:
                raise AssertionError(('Unexpected effect', key, value))

    def process(self):
        self.apply(EFFECTS[PREFIX + 'process_lifestyle_mastery_effect'])


class LifestyleMasteryTests(unittest.TestCase):
    def test_complete_and_incomplete_directions(self):
        for life, name in LIFESTYLES.items():
            perks, traits = requirements(life, 'has_perk'), requirements(life, 'has_trait')
            self.assertEqual(len(perks), 36 if life == 'intrigue' else 27)
            self.assertEqual(len(traits), 4 if life == 'intrigue' else 3)
            c = MasteryCharacter(perks, traits)
            c.modifiers.add('unrelated_modifier')
            c.process()
            self.assertEqual(c.modifiers, {'unrelated_modifier', PREFIX + name})
            self.assertEqual(c.perks, perks)
            self.assertEqual(c.traits, traits)
            self.assertEqual(c.points[life], 0)
            self.assertTrue(all(points == 17 for other, points in c.points.items() if other != life))
            c.points[life] = 5  # A scripted reward can bypass ordinary monthly XP.
            c.process()
            self.assertEqual(c.points[life], 0)
            self.assertEqual(len(c.modifiers), 2)
            for missing in perks:
                with self.subTest(lifestyle=life, missing_perk=missing):
                    incomplete = MasteryCharacter(perks - {missing}, traits)
                    incomplete.modifiers.add(PREFIX + name)
                    incomplete.process()
                    self.assertNotIn(PREFIX + name, incomplete.modifiers)
                    self.assertEqual(incomplete.points[life], 17)
            for missing in traits:
                with self.subTest(lifestyle=life, missing_trait=missing):
                    incomplete = MasteryCharacter(perks, traits - {missing})
                    incomplete.process()
                    self.assertNotIn(PREFIX + name, incomplete.modifiers)
                    self.assertEqual(incomplete.points[life], 17)

    def test_all_mastered_and_refund_preserves_returned_points(self):
        c = MasteryCharacter(
            set().union(*(requirements(life, 'has_perk') for life in LIFESTYLES)),
            set().union(*(requirements(life, 'has_trait') for life in LIFESTYLES)),
        )
        c.process()
        self.assertEqual(len(c.modifiers), 6)
        c.perks.clear()
        c.traits.clear()
        c.points = dict.fromkeys(LIFESTYLES, 27)
        c.apply(EFFECTS[PREFIX + 'remove_lifestyle_mastery_effect'])
        self.assertFalse(c.modifiers)
        c.process()
        self.assertEqual(set(c.points.values()), {27})

    def test_wanderer_dlc_guard_and_candidate_cleanup(self):
        c = MasteryCharacter(requirements('wanderer', 'has_perk'), requirements('wanderer', 'has_trait'), dlc=False)
        c.modifiers.add(PREFIX + 'valyria_returned')
        self.assertTrue(c.matches(TRIGGERS[PREFIX + 'mastery_candidate_trigger']))
        c.process()
        self.assertNotIn(PREFIX + 'valyria_returned', c.modifiers)
        self.assertEqual(c.points['wanderer'], 17)
        empty = MasteryCharacter()
        self.assertFalse(empty.matches(TRIGGERS[PREFIX + 'mastery_candidate_trigger']))
        empty.modifiers.add(PREFIX + 'valyrian_spy')
        self.assertTrue(empty.matches(TRIGGERS[PREFIX + 'mastery_candidate_trigger']))
        empty.process()
        self.assertFalse(empty.modifiers)

    def test_installed_agot_perks_match_every_completion_check(self):
        roots = [Path('E:/SteamLibrary/steamapps/common/Crusader Kings III/game'), Path('E:/SteamLibrary/steamapps/workshop/content/1158310/2962333032')]
        if not (roots[-1] / 'common/lifestyle_perks').exists():
            self.skipTest('Installed AGOT unavailable')
        files = {}
        for root in roots:
            for f in (root / 'common/lifestyle_perks').glob('*.txt'):
                files[f.name] = f
        perks = {k: v for f in files.values() for k, _, v in parse(f) if isinstance(v, list)}
        for life in LIFESTYLES:
            native = {k: v for k, v in perks.items() if field(v, 'lifestyle') == life + '_lifestyle'}
            self.assertEqual(requirements(life, 'has_perk'), set(native), life)
            self.assertEqual(requirements(life, 'has_trait'), {field(v, 'trait') for v in native.values() if field(v, 'trait')}, life)
            self.assertTrue(all(field(v, 'can_be_picked') in (None, [('always', '=', 'yes')]) for v in native.values()), life)

    def test_global_loop_and_append_only_hooks(self):
        for name in ('on_game_start_after_lobby', 'yearly_global_pulse', 'quarterly_playable_pulse', 'on_perks_refunded'):
            self.assertEqual({k for k, _, _ in ON_ACTIONS[name]}, {'on_actions'})
            for child, _, _ in field(ON_ACTIONS[name], 'on_actions'):
                self.assertIn(child, ON_ACTIONS)
        for name in (PREFIX + 'start_mastery_loop', PREFIX + 'mastery_monthly'):
            keys = {k for k, _, _ in walk(ON_ACTIONS[name])}
            self.assertNotIn('is_ai', keys)
            self.assertNotIn('is_ruler', keys)
            self.assertNotIn(PREFIX + 'menu_enabled_trigger', keys)
            self.assertIn('has_global_variable', keys)
            self.assertIn('set_global_variable', keys)
        monthly = ON_ACTIONS[PREFIX + 'mastery_monthly']
        living = [v for k, _, v in walk(monthly) if k == 'every_living_character']
        self.assertEqual(len(living), 1)
        self.assertIn(('is_human', '=', 'yes'), field(living[0], 'limit'))
        self.assertEqual([v for k, _, v in walk(monthly) if k == 'trigger_event'], [[('on_action', '=', PREFIX + 'mastery_monthly'), ('months', '=', '1')]])
        refund = str(ON_ACTIONS[PREFIX + 'mastery_perks_refunded'])
        self.assertIn(PREFIX + 'remove_lifestyle_mastery_effect', refund)
        self.assertNotIn('process_lifestyle_mastery_effect', refund)
        for nodes in ON_ACTIONS.values():
            for key, _, value in walk(nodes):
                if key == 'on_action' and value.startswith(PREFIX):
                    self.assertIn(value, ON_ACTIONS)

    def test_focus_define_and_modifier_assets(self):
        define = parse(BASE / 'common/defines/zzzz_agot_di_rusbar_lifestyle_defines.txt')
        self.assertEqual(field(field(define, 'NCharacter'), 'FOCUS_ADULT_COOLDOWN_MONTHS'), '1')
        mods = definitions('common/modifiers')
        for life, name in LIFESTYLES.items():
            key = PREFIX + name
            self.assertEqual(field(mods[key], 'icon'), key)
            self.assertLess(1 + 999 + float(field(mods[key], 'monthly_' + life + '_lifestyle_xp_gain_mult')), 0)
            self.assertLess(float(field(mods[key], life + '_lifestyle_xp_gain_mult')), -1)
            data = (BASE / 'gfx/interface/icons/modifiers' / (key + '.dds')).read_bytes()
            self.assertEqual(data[:4], b'DDS ')
            header = struct.unpack('<31I', data[4:128])
            self.assertEqual(header[0], 124)
            self.assertEqual(header[2:4], (60, 60))
            self.assertEqual(header[6], 6)
            self.assertEqual(header[19] & 0x41, 0x41)
            self.assertEqual(len(data), 19264)
            self.assertTrue((BASE / 'assets/lifestyle' / (key + '.png')).exists())


if __name__ == '__main__':
    unittest.main()
