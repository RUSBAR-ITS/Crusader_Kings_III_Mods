"""Holding-button guards and GUI integration; not a CK3 engine/renderer test."""
from dataclasses import dataclass
from pathlib import Path
import re
import unittest

from test_addon import BASE, PREFIX, SGUIS, TOKEN, TRIGGERS, field, parse


GUI = SGUIS[PREFIX + 'add_holding_slot']
CAP = int(field(field(parse(BASE / 'common/defines/zzzz_agot_di_rusbar_holdings_defines.txt'), 'NProvince'), 'MAX_BUILDINGS'))
COST = int(field(parse(BASE / 'common/script_values/agot_di_rusbar_holding_values.txt'), PREFIX + 'holding_slot_cost'))


@dataclass(eq=False)
class Ruler:
    liege: object = None
    ai: bool = False
    alive: bool = True
    gold: int = 100000


@dataclass
class Holding:
    owner: object
    kind: str = 'castle_holding'
    built: bool = True
    slots: int = 10


class HoldingContext:
    """Evaluate the actual guard AST with a small modeled feudal hierarchy."""

    def __init__(self, player, holding):
        self.player, self.holding = player, holding

    def resolve(self, name, current):
        return {
            'root': self.player,
            'scope:gui_holding': self.holding,
            'scope:gui_holding.province_owner': self.holding.owner if self.holding else None,
            'province_owner': current.owner if isinstance(current, Holding) else None,
        }[name]

    def test(self, nodes, current=None):
        current = self.player if current is None else current

        def one(k, op, v):
            if k in TRIGGERS:
                return self.test(TRIGGERS[k], current) == (v == 'yes')
            if k == 'OR':
                return any(one(*n) for n in v)
            if k == 'NOR':
                return not any(one(*n) for n in v)
            if k == 'exists':
                return self.resolve(v, current) is not None
            if k.startswith('scope:'):
                target = self.resolve(k, current)
                if isinstance(v, list):
                    return target is not None and self.test(v, target)
                return target is self.resolve(v, current)
            if k == 'is_ai':
                return current.ai == (v == 'yes')
            if k == 'is_alive':
                return current.alive == (v == 'yes')
            if k == 'gold':
                assert op == '>=' and v == PREFIX + 'holding_slot_cost'
                return current.gold >= COST
            if k == 'has_holding':
                return current.built == (v == 'yes')
            if k == 'has_holding_type':
                return current.kind == v
            if k == 'building_slots':
                assert op == '<' and v == 'define:NProvince|MAX_BUILDINGS'
                return current.slots < CAP
            if k == 'is_liege_or_above_of':
                target = self.resolve(v, current)
                while target is not None:
                    target = target.liege
                    if target is current:
                        return True
                return False
            raise AssertionError(('Unhandled holding predicate', k, op, v))

        return all(one(*n) for n in nodes)

    def execute(self):
        # Follow the guarded province effect, without treating GUI visibility as
        # an authorization check. This catches missing revalidation in effect.
        def apply(nodes, current):
            for k, _, v in nodes:
                if k == 'if':
                    if self.test(field(v, 'limit'), current):
                        apply([n for n in v if n[0] != 'limit'], current)
                elif k == 'scope:gui_holding':
                    apply(v, self.holding)
                elif k == 'add_province_modifier':
                    assert v == 'extra_building_slot'
                    current.slots += 1
                elif k == 'remove_long_term_gold':
                    assert v == PREFIX + 'holding_slot_cost'
                    current.gold -= COST
                else:
                    raise AssertionError(('Unhandled holding effect', k))
        apply(field(GUI, 'effect'), self.player)


class HoldingSlotTests(unittest.TestCase):
    def test_price_boundaries_payer_and_stale_funds(self):
        self.assertEqual(COST, 1000)
        for gold in (0, 999, 1000, 2500):
            player = Ruler(gold=gold)
            vassal = Ruler(liege=player, ai=True, gold=0)
            holding = Holding(vassal)
            context = HoldingContext(player, holding)
            self.assertTrue(context.test(field(GUI, 'is_shown')))
            self.assertEqual(context.test(field(GUI, 'is_valid')), gold >= COST)
            context.execute()
            self.assertEqual(player.gold, gold-COST if gold >= COST else gold)
            self.assertEqual(vassal.gold, 0)
            self.assertEqual(holding.slots, 11 if gold >= COST else 10)
        player = Ruler(gold=COST)
        holding = Holding(player)
        context = HoldingContext(player, holding)
        self.assertTrue(context.test(field(GUI, 'is_valid')))
        player.gold = 999
        context.execute()
        self.assertEqual((player.gold, holding.slots), (999, 10))
        player.gold = COST
        holding.slots = CAP
        context.execute()
        self.assertEqual((player.gold, holding.slots), (COST, CAP))

    def test_own_realm_including_indirect_vassals_only(self):
        king = Ruler()
        player = Ruler(liege=king)
        direct = Ruler(liege=player, ai=True)
        indirect = Ruler(liege=direct, ai=True)
        sibling = Ruler(liege=king, ai=True)
        foreign = Ruler()
        for owner, allowed in ((player, True), (direct, True), (indirect, True),
                               (king, False), (sibling, False), (foreign, False)):
            with self.subTest(owner=owner):
                holding = Holding(owner)
                context = HoldingContext(player, holding)
                self.assertEqual(context.test(field(GUI, 'is_shown')), allowed)
                self.assertEqual(context.test(field(GUI, 'is_valid')), allowed)
                context.execute()
                self.assertEqual(holding.slots, 11 if allowed else 10)

    def test_invalid_context_and_agot_holding_types(self):
        player = Ruler()
        for context in (HoldingContext(Ruler(ai=True), Holding(player)),
                        HoldingContext(Ruler(alive=False), Holding(player)),
                        HoldingContext(player, None),
                        HoldingContext(player, Holding(None)),
                        HoldingContext(player, Holding(player, built=False))):
            self.assertFalse(context.test(field(GUI, 'is_shown')))
            self.assertFalse(context.test(field(GUI, 'is_valid')))
            context.execute()
        for kind in ('castle', 'tribal', 'city', 'church', 'monastery', 'pirate_den',
                     'settlement', 'temple_citadel', 'unknown', 'wilderness', 'ruin', 'nomad', 'herder'):
            with self.subTest(kind=kind):
                holding = Holding(player, kind=kind + '_holding')
                context = HoldingContext(player, holding)
                allowed = kind not in ('unknown', 'wilderness', 'ruin', 'nomad', 'herder')
                self.assertEqual(context.test(field(GUI, 'is_shown')), allowed)
                context.execute()
                self.assertEqual(holding.slots, 11 if allowed else 10)

    def test_repeat_cap_selected_holding_and_stale_owner(self):
        player = Ruler()
        first, second = Holding(player, slots=CAP-2), Holding(player)
        context = HoldingContext(player, first)
        for _ in range(3):
            context.execute()
        self.assertEqual(first.slots, CAP)
        self.assertFalse(context.test(field(GUI, 'is_valid')))
        self.assertEqual(second.slots, 10)
        context.holding = second
        self.assertTrue(context.test(field(GUI, 'is_valid')))
        second.owner = Ruler()  # Lost after rendering, before execution.
        context.execute()
        self.assertEqual(second.slots, 10)
        second.owner = player
        context.execute()
        self.assertEqual(second.slots, 11)
        self.assertEqual(first.slots, CAP)

    def test_gui_scope_grid_and_native_modifier(self):
        controls = (BASE / 'gui/agot_di_rusbar_holding_controls.gui').read_text(encoding='utf-8')
        scope = "GuiScope.SetRoot(GetPlayer.MakeScope).AddScope('gui_holding', HoldingView.GetProvince.MakeScope).End"
        for method in ('IsShown', 'IsValid', 'Execute'):
            self.assertIn(f'ScriptedGui.{method}({scope})', controls)
        self.assertIn(('gui_holding', '', None), field(GUI, 'saved_scopes'))
        self.assertEqual(field(GUI, 'scope'), 'character')
        view = (BASE / 'gui/window_county_view.gui').read_text(encoding='utf-8')
        self.assertEqual(view.count('agot_di_rusbar_holding_slot_button = {}'), 1)
        self.assertIn('scrollbarpolicy_horizontal = always_off', view)
        self.assertIn('datamodel = "[HoldingView.GetBuildings]"', view)
        area = view.split('# AGOT DI RUSBAR: BUILDING SLOTS START', 1)[1].split('# AGOT DI RUSBAR: BUILDING SLOTS END', 1)[0]
        cols = int(re.search(r'maxhorizontalslots = (\d+)', area)[1])
        rows = int(re.search(r'maxverticalslots = (\d+)', area)[1])
        self.assertGreaterEqual(cols * rows, CAP)
        self.assertGreater(CAP, 10)
        game = Path('E:/SteamLibrary/steamapps/common/Crusader Kings III/game')
        native = game / 'common/modifiers/00_province_modifiers.txt'
        if native.exists():
            modifier = field(parse(native), 'extra_building_slot')
            self.assertEqual(field(modifier, 'stacking'), 'yes')
            self.assertEqual(field(modifier, 'building_slot_add'), '1')
            self.assertTrue((game / 'gfx/interface/icons/flat_icons/plus.dds').exists())

    def test_agot_gui_preserved_outside_building_area(self):
        source = Path('E:/SteamLibrary/steamapps/workshop/content/1158310/2962333032/gui/window_county_view.gui')
        if not source.exists():
            self.skipTest('AGOT installation not available')
        original = source.read_text(encoding='utf-8-sig')
        modified = (BASE / 'gui/window_county_view.gui').read_text(encoding='utf-8')

        def area_bounds(text):
            start = text.rfind('flowcontainer = {', 0, text.index('name = "holding_view_buildings_area"'))
            level = 0
            for token in TOKEN.finditer(text, start):
                if token[0] == '{':
                    level += 1
                elif token[0] == '}':
                    level -= 1
                    if level == 0:
                        return start, token.end()
            raise AssertionError('Unclosed holding building area')

        modified = re.sub(r'^\t*# AGOT DI RUSBAR: BUILDING SLOTS (?:START|END)\n', '', modified, flags=re.M)
        a, b = area_bounds(original)
        c, d = area_bounds(modified)
        self.assertEqual(original[:a], modified[:c])
        self.assertEqual(original[b:], modified[d:])
        # Special/duchy/great-building controls retain AGOT logic and warnings.
        for name in ('duchy_capital_building', 'special_building', 'great_building', 'ruined_great_building'):
            pattern = rf'name = "{name}".*?(?=\n\s*spacer = |\n\s*widget = |\Z)'
            before = re.search(pattern, original[a:b], re.S)[0]
            after = re.search(pattern, modified[c:d], re.S)[0]
            self.assertEqual([t[0] for t in TOKEN.finditer(before)], [t[0] for t in TOKEN.finditer(after)])


if __name__ == '__main__':
    unittest.main()
