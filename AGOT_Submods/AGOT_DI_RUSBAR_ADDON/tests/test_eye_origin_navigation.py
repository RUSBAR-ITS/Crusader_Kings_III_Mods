"""Guards for grouped origin selection; these do not render the CK3 GUI."""
import re
import unittest

from test_addon import BASE, EFFECTS, PREFIX, SGUIS, field, walk


class EyeOriginNavigationTests(unittest.TestCase):
    def test_group_lists_are_rebuilt_and_player_scoped(self):
        opening = EFFECTS[PREFIX + 'eye_open_effect']
        closing = EFFECTS[PREFIX + 'eye_close_effect']
        self.assertEqual(opening[0], (PREFIX + 'eye_close_effect', '=', 'yes'))
        cleared = {v for k, _, v in closing if k == 'clear_variable_list'}
        self.assertTrue({PREFIX + 'eye_heritages', PREFIX + 'eye_religions'} <= cleared)
        populated = {field(v, 'name') for k, _, v in walk(opening) if k == 'add_to_variable_list'}
        self.assertEqual(cleared, populated, 'Stale list cleanup produces never-set warnings')

        # A representative is added only when its heritage is not in this player's list.
        cultures = field(opening, 'every_culture_global')
        representative = 'scope:' + field(cultures, 'save_scope_as')
        owner = field(cultures, 'scope:' + PREFIX + 'operator')
        branch = field(owner, 'if')
        exclusion = field(field(field(branch, 'limit'), 'NOT'), 'any_in_list')
        insertion = field(branch, 'add_to_variable_list')
        self.assertEqual(field(exclusion, 'variable'), PREFIX + 'eye_heritages')
        self.assertEqual(field(exclusion, 'has_same_culture_heritage'), representative)
        self.assertEqual(field(insertion, 'name'), field(exclusion, 'variable'))
        self.assertEqual(field(insertion, 'target'), representative)

        religions = field(opening, 'every_religion_global')
        owner = field(religions, 'scope:' + PREFIX + 'operator')
        insertion = field(owner, 'add_to_variable_list')
        self.assertEqual(field(insertion, 'name'), PREFIX + 'eye_religions')
        self.assertEqual(field(insertion, 'target'), 'prev')
        self.assertFalse(any('global_list' in k for k, _, _ in walk(opening)))

    def test_selection_only_changes_the_future_characters_origin(self):
        gui = (BASE / 'gui/agot_di_rusbar_eye_origin_lists.gui').read_text(encoding='utf-8')
        for kind, data_type in [('culture', 'Culture'), ('faith', 'Faith')]:
            selection = PREFIX + 'eye_select_' + kind
            route = ("GetScriptedGui('" + selection + "').Execute(GuiScope.SetRoot(GetPlayer.MakeScope)"
                     ".AddScope('agot_di_rusbar_selection', " + data_type + ".MakeScope).End)")
            self.assertIn(route, gui)
            nodes = list(walk(field(SGUIS[selection], 'effect')))
            setters = [v for k, _, v in nodes if k == 'set_variable']
            self.assertEqual(len(setters), 1)
            self.assertEqual(field(setters[0], 'name'), PREFIX + 'eye_' + kind)
            self.assertEqual(field(setters[0], 'value'), 'scope:' + PREFIX + 'selection')
            self.assertFalse(any(k in {'set_culture', 'set_character_faith'} for k, _, _ in nodes))
        self.assertNotRegex(gui, r'using\s*=\s*Button_Select_(?:Culture|Faith)')
        self.assertNotIn('RulerDesignerWindow.', gui)

    def test_live_child_lists_and_isolated_expansion_state(self):
        gui = (BASE / 'gui/agot_di_rusbar_eye_origin_lists.gui').read_text(encoding='utf-8')
        window = (BASE / 'gui/agot_di_rusbar_eye.gui').read_text(encoding='utf-8')
        for kind in ['culture', 'faith']:
            self.assertIn(PREFIX + 'eye_' + kind + '_list = {}', window)
        for expression in ['CulturePillar.GetCulturesWithPillar', 'Religion.GetFaiths']:
            self.assertIn('datamodel = "[' + expression + ']"', gui)
        self.assertIn('texture = "[Faith.GetIcon]"', gui)
        keys = re.findall(r"ConcatIfNeitherEmpty\('([^']+)'", gui)
        self.assertTrue(keys)
        self.assertEqual(set(keys), {PREFIX + 'eye_heritage_', PREFIX + 'eye_religion_'})
        self.assertNotIn('GetGlobalList', gui)

    def test_broken_search_callbacks_are_removed(self):
        window = (BASE / 'gui/agot_di_rusbar_eye.gui').read_text(encoding='utf-8')
        self.assertNotIn('editbox_search_field', window)
        self.assertNotIn('ontextedited', window)
        self.assertNotIn(PREFIX + 'culture_search', window)
        self.assertNotIn(PREFIX + 'faith_search', window)
        self.assertNotIn('EqualTo_string', window)

    def test_scroll_content_override_belongs_to_a_nested_instance(self):
        # Direct scrollbox inheritance displayed the engine's default debug_square
        # in-game. Match DI's wrapper -> scrollbox instance -> content override.
        gui = (BASE / 'gui/agot_di_rusbar_eye_origin_lists.gui').read_text(encoding='utf-8')
        for kind in ['culture', 'faith']:
            with self.subTest(kind=kind):
                self.assertRegex(gui, (
                    rf'type {PREFIX}eye_{kind}_list\s*=\s*vbox\s*\{{'
                    r'[^{}]*\bscrollbox\s*=\s*\{'
                    r'[^{}]*\bblockoverride\s+"scrollbox_content"\s*\{'
                    r'\s*vbox\s*=\s*\{[^{}]*\bdatamodel\s*='
                ))


if __name__ == '__main__':
    unittest.main()
