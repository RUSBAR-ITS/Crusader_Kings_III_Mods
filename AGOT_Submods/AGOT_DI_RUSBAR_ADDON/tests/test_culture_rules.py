"""Culture-rule scenarios using the shipped AST; does not run the CK3 engine."""
from pathlib import Path
import math
import re
import unittest

from test_addon import (BASE, PREFIX, EFFECTS, GAME_RULES, INNOVATIONS, ON_ACTIONS,
                        definitions, field, parse, walk)


SLOTS = (5, 10, 15, 45, 95)
COOLDOWNS = ('vanilla', '25_years', '10_years', '5_years', '1_year', 'none')


class Culture:
    def __init__(self, extra=0, cooldown='vanilla', head='player', discount=None, fascination='innovation_test'):
        self.rules = {
            PREFIX + 'tradition_slots_' + (f'plus_{extra}' if extra else 'vanilla'),
            PREFIX + 'tradition_cooldown_' + cooldown,
        }
        self.head = head
        self.discount = discount
        self.innovations = {'innovation_existing'}
        self.variables = {'tradition_cooldown'}
        self.fascination = fascination
        self.progress = 12
        self.completions = 0

    def test(self, nodes, head_scope=False):
        def one(k, op, v):
            if k == 'has_game_rule':
                return v in self.rules
            if k == 'has_innovation':
                return v in self.innovations
            if k == 'has_variable':
                if head_scope:
                    assert v == 'kurultai_culture_variable_value'
                    return self.discount is not None
                return v in self.variables
            if k == 'NOT':
                return not self.test(v, head_scope)
            if k == 'exists':
                assert v == 'culture_head'
                return self.head is not None
            if k == 'culture_head':
                # The shipped non-optional scope requires an actual culture head.
                return self.head is not None and self.test(v, True)
            if k == 'is_ai':
                return (self.head == 'ai') == (v == 'yes')
            if k == 'is_alive':
                return (self.head != 'dead') == (v == 'yes')
            if k == 'culture_has_any_fascination':
                return (self.fascination is not None) == (v == 'yes')
            raise AssertionError(('Unmodeled predicate', k, op, v))
        return all(one(*n) for n in nodes)

    def apply(self, nodes):
        for k, _, v in nodes:
            if k in EFFECTS:
                self.apply(EFFECTS[k])
            elif k == 'if':
                if self.test(field(v, 'limit')):
                    self.apply([n for n in v if n[0] != 'limit'])
            elif k == 'add_innovation':
                self.innovations.add(v)
            elif k == 'remove_innovation':
                self.innovations.discard(v)
            elif k == 'remove_variable':
                self.variables.discard(v)
            elif k == 'add_fascination_progress':
                assert self.fascination is not None
                self.progress += float(v)
                if self.progress >= 100:
                    self.innovations.add(self.fascination)
                    self.completions += 1
                    self.fascination = None
            else:
                raise AssertionError(('Unmodeled effect', k))

    def cooldown_value(self, nodes):
        value = 0
        def operand(v):
            if isinstance(v, list):
                return self.cooldown_value(v)
            if v == 'culture_head.var:kurultai_culture_variable_value':
                return self.discount
            return float(v)
        for k, _, v in nodes:
            if k == 'if':
                if self.test(field(v, 'limit')):
                    # These branches operate on the accumulated outer value.
                    value = self.cooldown_value([('value', '=', str(value))] + [n for n in v if n[0] != 'limit'])
            elif k == 'value':
                value = operand(v)
            elif k == 'multiply':
                value *= operand(v)
            elif k == 'subtract':
                value -= operand(v)
            elif k == 'divide':
                value /= operand(v)
            elif k == 'max':
                value = min(value, operand(v))  # CK3 max = upper bound.
            else:
                raise AssertionError(('Unmodeled script value', k))
        return value


class CultureRuleTests(unittest.TestCase):
    def test_slots_switching_defaults_and_hybrid_inheritance(self):
        apply = EFFECTS[PREFIX + 'apply_culture_tradition_slots_effect']
        for extra in (0,) + SLOTS:
            for head in ('player', 'ai', None):
                culture = Culture(extra=extra, head=head)
                # Simulate a hybrid inheriting several previously selected helpers.
                culture.innovations.update(PREFIX + f'innovation_tradition_slots_plus_{n}' for n in SLOTS)
                culture.apply(apply)
                culture.apply(apply)
                expected = {'innovation_existing'}
                if extra:
                    expected.add(PREFIX + f'innovation_tradition_slots_plus_{extra}')
                self.assertEqual(culture.innovations, expected)
        self.assertEqual(set(GAME_RULES), {PREFIX + 'culture_tradition_slots', PREFIX + 'culture_tradition_cooldown'})
        for rule, nodes in GAME_RULES.items():
            self.assertTrue(field(nodes, 'default').endswith('_vanilla'))
        self.assertEqual(len(INNOVATIONS), len(SLOTS))
        for extra in SLOTS:
            nodes = INNOVATIONS[PREFIX + f'innovation_tradition_slots_plus_{extra}']
            self.assertEqual(field(field(nodes, 'potential'), 'always'), 'no')
            self.assertEqual(field(field(nodes, 'can_progress'), 'always'), 'no')
            self.assertEqual(field(field(nodes, 'culture_modifier'), 'culture_tradition_max_add'), str(extra))

    def test_cooldown_player_only_preserves_smaller_native_result(self):
        nodes = definitions('common/script_values')['add_tradition_cooldown']
        for head in ('player', 'ai', None):
            for discount in (None, 0, 90, 99):
                for cooldown in COOLDOWNS:
                    culture = Culture(head=head, discount=discount, cooldown=cooldown)
                    native = 50 * (1 - (discount or 0) / 100) if head else 50
                    if head == 'player' and cooldown != 'vanilla':
                        cap = 0 if cooldown == 'none' else int(cooldown.split('_')[0])
                        expected = min(native, cap)
                    else:
                        expected = native
                    self.assertAlmostEqual(culture.cooldown_value(nodes), expected)
                    culture.apply(EFFECTS[PREFIX + 'clear_disabled_tradition_cooldown_effect'])
                    self.assertEqual('tradition_cooldown' in culture.variables, not (head == 'player' and cooldown == 'none'))

    def test_annual_fascination_uses_current_head_and_only_selected_innovation(self):
        yearly = field(field(ON_ACTIONS[PREFIX + 'culture_yearly'], 'effect'), 'every_culture_global')
        cultures = [Culture(head='player'), Culture(head='ai'), Culture(head=None),
                    Culture(head='player', fascination=None), Culture(head='dead')]
        for culture in cultures:
            culture.apply(yearly)
        self.assertEqual([c.completions for c in cultures], [1, 0, 0, 0, 0])
        self.assertIn('innovation_existing', cultures[0].innovations)
        self.assertIn('innovation_test', cultures[0].innovations)
        # Next yearly pulse observes a new fascination and a new culture head.
        cultures[0].head = 'ai'
        cultures[0].fascination = 'innovation_next'
        cultures[0].progress = 0
        cultures[1].head = 'player'
        for culture in cultures:
            culture.apply(yearly)
        self.assertEqual([c.completions for c in cultures], [1, 1, 0, 0, 0])
        self.assertNotIn('innovation_next', cultures[0].innovations)
        # No completion in startup, creation or cooldown callbacks.
        for name in ('on_action_apply_culture_rules_on_game_start',
                     'on_action_apply_culture_rules_on_culture_created',
                     'on_action_clear_disabled_tradition_cooldown'):
            self.assertNotIn('add_fascination_progress', str(ON_ACTIONS[PREFIX + name]))
        annual_children = [k for k, _, _ in field(ON_ACTIONS['yearly_global_pulse'], 'on_actions')]
        self.assertEqual(annual_children.count(PREFIX + 'culture_yearly'), 1)
        self.assertIn(PREFIX + 'start_mastery_loop', annual_children)

    def test_defines_localization_and_append_only_native_hooks(self):
        values = dict((k, v) for k, _, v in field(parse(BASE / 'common/defines/zzzz_agot_di_rusbar_culture_defines.txt'), 'NCulture'))
        self.assertEqual(values, {
            'REFORMATION_PROGRESS_GAIN_BASE': '8.34',
            'REFORMATION_PROGRESS_SLOWDOWN_PER_COUNTY_WITH_CULTURE': '0.01',
            'REFORMATION_MAX_YEARS': '1',
            'REFORMATION_PROGRESS_REPLACE_TRADITION_MULT': '0.75',
        })
        self.assertEqual(math.ceil(100 / float(values['REFORMATION_PROGRESS_GAIN_BASE'])), 12)
        self.assertEqual(math.ceil(100 / (float(values['REFORMATION_PROGRESS_GAIN_BASE']) * .75)), 16)
        for hook in ('on_game_start', 'on_culture_created', 'on_tradition_added', 'yearly_global_pulse'):
            self.assertEqual({k for k, _, _ in ON_ACTIONS[hook]}, {'on_actions'})
            for child, _, _ in field(ON_ACTIONS[hook], 'on_actions'):
                self.assertIn(child, ON_ACTIONS)
        for lang in ('russian', 'english'):
            text = (BASE / f'localization/{lang}/agot_di_rusbar_culture_l_{lang}.yml').read_text(encoding='utf-8-sig')
            keys = set(re.findall(r'^ ([^ :]+):', text, re.M))
            for rule, nodes in GAME_RULES.items():
                self.assertIn('rule_' + rule, keys)
                for option, _, body in nodes:
                    if option.startswith(PREFIX) and isinstance(body, list):
                        self.assertIn('setting_' + option, keys)
                        self.assertIn('setting_' + option + '_desc', keys)
            for innovation in INNOVATIONS:
                self.assertIn(innovation, keys)
                self.assertIn(innovation + '_desc', keys)

    def test_compatible_with_installed_agot_baseline(self):
        agot = Path('E:/SteamLibrary/steamapps/workshop/content/1158310/2962333032')
        if not agot.exists():
            self.skipTest('AGOT not installed')
        original = field(parse(agot / 'common/script_values/00_culture_values.txt'), 'add_tradition_cooldown')
        override = definitions('common/script_values')['add_tradition_cooldown']
        self.assertEqual(override[:len(original)], original)
        eras = {k for k, _, _ in parse(agot / 'common/culture/eras/00_culture_eras.txt')}
        for nodes in INNOVATIONS.values():
            self.assertIn(field(nodes, 'culture_era'), eras)
        culture_overrides = parse(BASE / 'common/script_values/zzzz_agot_di_rusbar_culture_values.txt')
        self.assertEqual([k for k, _, _ in culture_overrides], ['add_tradition_cooldown'])


if __name__ == '__main__':
    unittest.main()
