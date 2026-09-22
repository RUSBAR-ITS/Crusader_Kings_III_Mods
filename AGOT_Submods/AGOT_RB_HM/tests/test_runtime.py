"""Behavioural checks for the generated planner; these do not emulate CK3 itself.

The small interpreter below runs the actual emitted Boolean trees for the three
reviewed conflict components. Terrain/technology are explicit test fixtures; the
game, not this interpreter, remains authoritative for their real definitions.
"""
import copy
import itertools
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from build_catalog import children, parse, walk as nodes_walk
from build_runtime import GROUPS, MODES, REQS, body, render, window_bounds


def signature(n):
    return n.key, n.op, tuple(signature(x) for x in children(n)) if isinstance(n.value, list) else n.value


class Predicates:
    def __init__(self, definitions, buildings, province=None):
        self.defs, self.buildings = definitions, buildings
        self.root = province or self.province()
        self.county = [self.root]
        self.helpers = {"building_requirement_tribal": False, "building_requirement_pirate": False}

    @staticmethod
    def province(**kw):
        p = dict(holding="castle_holding", capital=True, buildings={"castle_01"},
                 culture=set(), holder_culture=set(), variables={f"rbhm_order_{i}": 0 for i in range(3)},
                 modifiers={"agot_province_gold_veins", "agot_province_silver_veins"})
        p.update(kw)
        return p

    def has(self, p, bid, higher):
        if bid in p["buildings"]:
            return True
        return higher and any(bid in {x["root"] for x in self.buildings.get(xid, {}).get("upgrade", {}).get("chains", [])} for xid in p["buildings"])

    @staticmethod
    def compare(lhs, op, rhs):
        return {"=": lambda: lhs == rhs, "==": lambda: lhs == rhs, "!=": lambda: lhs != rhs,
                ">=": lambda: lhs >= rhs, "<=": lambda: lhs <= rhs, ">": lambda: lhs > rhs,
                "<": lambda: lhs < rhs}[op]()

    def sequence(self, nodes, p):
        result = True
        branch_taken = False
        for n in nodes:
            if n.key in ("trigger_if", "trigger_else_if", "trigger_else"):
                if n.key == "trigger_if":
                    branch_taken = False
                lim = next((x for x in children(n) if x.key == "limit"), None)
                match = not branch_taken and (lim is None or self.sequence(children(lim), p))
                if match:
                    branch_taken = True
                    result &= self.sequence([x for x in children(n) if x.key != "limit"], p)
            else:
                result &= self.node(n, p)
        return result

    def node(self, n, p):
        k, v = n.key, n.value
        if k in ("AND", "limit", "custom_tooltip"):
            return self.sequence(children(n), p)
        if k == "OR":
            return any(self.node(x, p) for x in children(n))
        if k in ("NOT", "NOR"):
            return not any(self.node(x, p) for x in children(n))
        if k == "NAND":
            return not all(self.node(x, p) for x in children(n))
        if k.startswith("rbhm_"):
            return self.sequence(children(self.defs[k]), p) == (v != "no")
        if k == "county":
            return self.sequence(children(n), p)
        if k == "any_county_province":
            count = next((x for x in children(n) if x.key == "count"), None)
            candidates = sum(self.sequence([x for x in children(n) if x.key != "count"], q) for q in self.county)
            return self.compare(candidates, count.op, int(count.value)) if count else candidates > 0
        if k in ("culture", "scope:holder.culture"):
            q = dict(p, active_culture=p["holder_culture"] if k.startswith("scope:") else p["culture"])
            return self.sequence(children(n), q)
        if k.startswith("var:"):
            # CK3 reports an error on an unguarded missing variable; inventing
            # a default here used to mask the first-open initialization bug.
            return self.compare(p["variables"][k[4:]], n.op, int(v))
        if k == "has_variable":
            return v in p["variables"]
        if k in ("has_building", "has_building_or_higher"):
            return self.has(p, v, k.endswith("or_higher"))
        if k == "has_holding_type":
            return p["holding"] == v
        if k == "is_county_capital":
            return p["capital"] == (v == "yes")
        if k == "has_province_modifier":
            return v in p["modifiers"]
        if k == "has_cultural_parameter":
            return v in p.get("active_culture", p["culture"])
        if k == "this":
            return p is self.root if v == "root" else False
        if k.startswith("building_"):
            # Terrain/holding availability is supplied by the fixture.
            return self.helpers.get(k, True) == (v != "no")
        if k in ("scope:holder", "scope:holder.culture"):
            return self.sequence(children(n), p)
        if k in ("has_innovation", "has_cultural_tradition", "geographical_region"):
            return True
        if k == "always":
            return v == "yes"
        if k == "text":
            return True
        raise AssertionError(f"Fixture does not implement {k}; do not silently skip requirements")

    def picks(self, group):
        return {bid for bid in group if self.sequence(children(self.defs["rbhm_pick_" + bid]), self.root)}


class UniqueSlotEffects:
    """Payment fixture, not an engine emulator. An occupied unique slot rejects
    add_building, as in the captured log; replacement can succeed or be refused.
    Execute emitted action bodies so ordering and success guards are exercised.
    """
    def __init__(self, building, reject=False):
        self.building, self.reject = building, reject
        self.prices = dict(gold=2500, prestige=100, piety=50, treasury=200)
        self.balances = dict.fromkeys(self.prices, 10000)
        self.saved = {}
        self.menu = {"rbhm_menu", "rbhm_menu_province"}

    def number(self, value):
        if value.startswith("scope:"):
            return self.saved[value.removeprefix("scope:")]
        if value.startswith("rbhm_price_"):
            return self.prices[value.rsplit("_", 1)[1]]
        return float(value)

    def condition(self, node):
        if node.key == "has_building":
            return self.building == node.value
        if node.key.startswith("scope:rbhm_pay_") and node.op == ">":
            return self.number(node.key) > self.number(node.value)
        raise AssertionError(f"Unimplemented condition: {node.key}")

    def run(self, nodes):
        for n in nodes:
            if n.key == "save_scope_value_as":
                props = {x.key: x.value for x in children(n)}
                self.saved[props["name"]] = self.number(props["value"])
            elif n.key in ("add_building", "replace_building_effect"):
                if not self.reject and (n.key == "replace_building_effect" or self.building is None):
                    self.building = n.value
                    # A changed income can alter dynamic project prices. The
                    # fee must still use the quote captured before this point.
                    self.prices = {k: 2 * v for k, v in self.prices.items()}
            elif n.key == "if":
                limit = next(x for x in children(n) if x.key == "limit")
                if all(self.condition(x) for x in children(limit)):
                    self.run([x for x in children(n) if x.key != "limit"])
            elif n.key == "scope:actor":
                self.run(children(n))
            elif n.key in ("remove_long_term_gold", "remove_treasury"):
                currency = "gold" if n.key == "remove_long_term_gold" else "treasury"
                self.balances[currency] -= self.number(n.value)
            elif n.key in ("add_prestige_no_experience", "add_piety_no_experience"):
                props = {x.key: x.value for x in children(n)}
                self.balances[n.key.split("_")[1]] += self.number(props["value"]) * self.number(props["multiply"])
            elif n.key == "remove_variable":
                self.menu.discard(n.value)
            else:
                raise AssertionError(f"Unimplemented effect: {n.key}")


class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads((ROOT / "data/buildings-playset.json").read_text(encoding="utf-8"))
        cls.manifest = json.loads((ROOT / "data/runtime-manifest.json").read_text(encoding="utf-8"))
        cls.triggers = {n.key: n for n in parse((ROOT / "common/scripted_triggers/rbhm_buildings.txt").read_text(encoding="utf-8-sig"))}
        cls.values = {n.key: n for n in parse((ROOT / "common/script_values/rbhm_buildings.txt").read_text(encoding="utf-8-sig"))}
        cls.guis = {n.key: n for n in parse((ROOT / "common/scripted_guis/rbhm_buildings.txt").read_text(encoding="utf-8-sig"))}

    def test_original_conditions_survive_in_order_with_scopes(self):
        for bid, entry in self.manifest["included"].items():
            keys = ("is_enabled",) if entry["category"] == "great" else REQS
            required = [signature(parse(render(x))[0]) for k in keys for r in self.catalog["buildings"][bid]["requirements"][k] for x in r["syntax"].get("children", [])]
            generated = [signature(n) for n in children(self.triggers["rbhm_eligible_" + bid])]
            if required:
                self.assertTrue(any(generated[i:i+len(required)] == required for i in range(len(generated))), bid)
        for g in self.guis.values():
            self.assertEqual(next(x.value for x in children(g) if x.key == "scope"), "province")

    def test_price_uses_first_catalog_value_and_multiplies_every_resource(self):
        for bid in self.manifest["included"]:
            b = self.catalog["buildings"][bid]
            if b["category"] == "great":
                continue
            for c, price in b["construction_cost"]["resolved_base_cost"].items():
                value = children(self.values[f"rbhm_price_{bid}_{c}"])[0]
                self.assertEqual(float(value.value), price * 10, (bid, c))
        self.assertEqual(float(children(self.values["rbhm_price_agot_midges_inn_01_gold"])[0].value), 2000)

    def test_mills_can_coexist_in_county_capital(self):
        e = Predicates(self.triggers, self.catalog["buildings"])
        for pi in range(6):
            e.root["variables"]["rbhm_order_2"] = pi
            self.assertEqual(e.picks(GROUPS[2]), set(GROUPS[2]))

    def test_conflict_preview_waits_for_its_order_variable(self):
        e = Predicates(self.triggers, self.catalog["buildings"], Predicates.province(variables={}))
        for group in GROUPS:
            self.assertEqual(e.picks(group), set())
        # A partially initialized province must not evaluate another group's
        # missing variable either. Present variables still select normally.
        for gi, group in enumerate(GROUPS):
            e.root["variables"] = {f"rbhm_order_{gi}": 0}
            self.assertTrue(e.picks(group))
            for other in range(len(GROUPS)):
                if other != gi:
                    self.assertEqual(e.picks(GROUPS[other]), set())

    def test_mills_randomly_select_one_only_in_restricted_city(self):
        e = Predicates(self.triggers, self.catalog["buildings"], Predicates.province(
            holding="city_holding", buildings={"city_01"}, capital=False,
            culture={"watermills_windmills_cities"}, holder_culture={"watermills_windmills_cities"}))
        choices = set()
        for pi in range(6):
            e.root["variables"]["rbhm_order_2"] = pi
            chosen = e.picks(GROUPS[2])
            self.assertEqual(len(chosen), 1)
            choices |= chosen
            self.assertEqual(chosen, e.picks(GROUPS[2]), "Tooltip evaluation must not reroll")
        self.assertEqual(choices, set(GROUPS[2]))

    def test_mines_are_not_a_false_exclusive_clique(self):
        e = Predicates(self.triggers, self.catalog["buildings"])
        sets = set()
        for pi in range(6):
            e.root["variables"]["rbhm_order_0"] = pi
            chosen = e.picks(GROUPS[0])
            self.assertFalse("apiaries_01" in chosen and len(chosen) > 1)
            sets.add(frozenset(chosen))
        self.assertEqual(sets, {frozenset({"apiaries_01"}), frozenset({"agot_gold_mines_01", "agot_silver_mines_01"})})

    def test_existing_upgrade_blocks_opposite_new_chain(self):
        e = Predicates(self.triggers, self.catalog["buildings"])
        e.root["buildings"].add("apiaries_04")
        for pi in range(6):
            e.root["variables"]["rbhm_order_0"] = pi
            self.assertEqual(e.picks(GROUPS[0]), set())

    def test_failed_terrain_is_not_randomly_selected(self):
        e = Predicates(self.triggers, self.catalog["buildings"])
        e.helpers["building_apiaries_requirement_terrain"] = False
        for pi in range(6):
            e.root["variables"]["rbhm_order_0"] = pi
            self.assertEqual(e.picks(GROUPS[0]), {"agot_gold_mines_01", "agot_silver_mines_01"})

    def test_caravanserai_reserves_its_own_county_place(self):
        e = Predicates(self.triggers, self.catalog["buildings"])
        other = Predicates.province(buildings={"caravanserai_03"})
        e.county.append(other)
        self.assertNotIn("caravanserai_01", e.picks(GROUPS[2]))
        e.root["culture"].add("second_caravanserai")
        self.assertIn("caravanserai_01", e.picks(GROUPS[2]))
        e.county.append(Predicates.province(buildings={"caravanserai_01"}))
        self.assertNotIn("caravanserai_01", e.picks(GROUPS[2]))

    def test_batch_snapshots_precede_every_payment_and_build(self):
        for mode in MODES[:3]:
            text = (ROOT / "common/scripted_guis/rbhm_buildings.txt").read_text(encoding="utf-8-sig")
            gui = self.guis["rbhm_" + mode]
            script = text[gui.start:gui.end]
            last_snapshot = script.rfind("save_scope_value_as = { name = rbhm_selected_")
            first_payment = script.find("remove_long_term_gold")
            first_build = script.find("add_building =")
            self.assertGreater(first_payment, last_snapshot)
            self.assertGreater(first_build, first_payment)
            for bid in self.manifest["actions"][mode]:
                self.assertIn("exists = scope:rbhm_selected_" + bid, script)
            # Revalidation is inside the effect, not only in the enabled binding.
            self.assertIn("rbhm_can_" + mode + " = yes", script[script.index("hidden_effect"):])

    def test_unique_upgrades_replace_exact_target_and_preserve_first_construction(self):
        for mode in MODES[3:]:
            auto = list(nodes_walk(children(self.guis["rbhm_" + mode])))
            for bid in self.manifest["actions"][mode]:
                previous = self.catalog["buildings"][bid]["upgrade"]["previous"]
                expected = "replace_building_effect" if previous else ("add_great_building" if mode == "great" else "add_building")
                for path in (auto, list(nodes_walk(children(self.guis["rbhm_select_" + bid])))):
                    operations = [n.key for n in path if n.value == bid and n.key in (
                        "add_building", "add_great_building", "set_great_building", "replace_building_effect")]
                    self.assertEqual(operations, [expected], bid)
                if previous:
                    gates = list(nodes_walk(children(self.triggers["rbhm_eligible_" + bid])))
                    self.assertTrue(any(n.key == "has_building" and n.value in previous for n in gates), bid)

    def single_action_body(self, bid, picker):
        gui = self.guis["rbhm_select_" + bid if picker else "rbhm_duchy"]
        branch = next(n for n in nodes_walk(children(gui)) if n.key == "if" and any(
            x.key in ("add_building", "replace_building_effect") and x.value == bid for x in children(n)))
        # The surrounding availability gates are covered by the requirements
        # tests. Here the requested action is already selected and affordable.
        return [x for x in children(branch) if x.key != "limit"]

    def test_duchy_build_and_upgrade_charge_once_after_success_at_original_quote(self):
        for bid, previous in (("military_academy_01", None), ("military_academy_02", "military_academy_01")):
            for picker in (False, True):
                with self.subTest(bid=bid, picker=picker):
                    e = UniqueSlotEffects(previous)
                    expected = {k: e.balances[k] - v for k, v in e.prices.items()}
                    e.run(self.single_action_body(bid, picker))
                    self.assertEqual(e.building, bid)
                    self.assertEqual(e.balances, expected)
                    self.assertEqual(bool(e.menu), not picker)

    def test_refused_duchy_upgrade_keeps_old_building_resources_and_picker(self):
        for picker in (False, True):
            with self.subTest(picker=picker):
                e = UniqueSlotEffects("military_academy_01", reject=True)
                balances = dict(e.balances)
                e.run(self.single_action_body("military_academy_02", picker))
                self.assertEqual(e.building, "military_academy_01")
                self.assertEqual(e.balances, balances)
                self.assertEqual(e.menu, {"rbhm_menu", "rbhm_menu_province"})

    def test_no_debt_in_unspent_currencies_and_no_fame_loss(self):
        afford = children(self.triggers["rbhm_afford_castle_02"])
        self.assertEqual(len(afford), 4)
        self.assertTrue(all(n.key == "OR" and children(n)[0].value == "0" for n in afford))
        code = (ROOT / "common/scripted_guis/rbhm_buildings.txt").read_text(encoding="utf-8")
        self.assertIn("add_piety_no_experience", code)
        self.assertIn("add_prestige_no_experience", code)
        self.assertNotIn("remove_piety =", code)

    def test_great_fleet_full_cost_and_geographic_rewards(self):
        for level, materials in ((1, 7500), (2, 9000), (3, 10500)):
            name = f"rbhm_project_agot_great_fleet_0{level}_treasury_or_gold"
            nodes = children(self.values[name])
            self.assertEqual(len([x for x in nodes if x.key == "add"]), 6)
            self.assertEqual(nodes[-1].key, "multiply")
            self.assertEqual(nodes[-1].value, "10")
            code = (ROOT / "common/scripted_guis/rbhm_buildings.txt").read_text(encoding="utf-8-sig")
            g = self.guis[f"rbhm_select_agot_great_fleet_0{level}"]
            snippet = code[g.start:g.end]
            self.assertIn("agot_build_great_fleet_engineers_modifier", snippet)
            self.assertIn("agot_build_great_fleet_military_wharf_modifier", snippet)
            self.assertIn("agot_build_great_fleet_merchant_quays_modifier", snippet)
            self.assertNotIn("trigger_event", snippet)
            self.assertNotIn("add_legitimacy", snippet)

    def test_native_special_slot_and_separate_conditional_buttons(self):
        for bid, entry in self.manifest["included"].items():
            if entry["category"] == "special":
                keys = {n.key for n in nodes_walk(children(self.triggers["rbhm_eligible_" + bid]))}
                self.assertIn("scope:special_slot", keys)
                self.assertIn("has_special_building_slot", keys)
        text = (ROOT / "gui/window_county_view.gui").read_text(encoding="utf-8")
        self.assertEqual(text.count("rbhm_controls = {}"), 1)
        self.assertIn("rbhm_legacy_slot_button = {}", text)
        self.assertIn("agot_di_rusbar_buildings_grid_scroll_area", text)
        for mode in MODES[3:]:
            g = self.guis["rbhm_" + mode]
            shown = next(n for n in children(g) if n.key == "is_shown")
            self.assertEqual(children(shown)[0].key, "rbhm_can_" + mode)

    def test_runtime_localization_encoding_and_references(self):
        localized = {}
        for lang in ("russian", "english"):
            keys = set()
            for p in (ROOT / "localization" / lang).glob("*.yml"):
                data = p.read_bytes()
                self.assertTrue(data.startswith(b"\xef\xbb\xbf"), p)
                self.assertNotIn(b"\r", data, p)
                content = data.decode("utf-8-sig")
                self.assertNotRegex(content, r"\?{3,}")
                for key in re.findall(r"^ ([\w.]+):", content, re.M):
                    self.assertNotIn(key, keys, p)
                    keys.add(key)
            localized[lang] = keys
        self.assertEqual(localized["russian"], localized["english"])
        # This exact ID collides with a vanilla localization hash in CK3 1.19.
        self.assertNotIn("rbhm_choice_agot_grassfield_florestries_01", localized["russian"])
        gui = (ROOT / "gui/window_county_view.gui").read_text(encoding="utf-8")
        for key in re.findall(r"text = (rbhm_\w+)", gui):
            self.assertIn(key, localized["russian"])
        for path in (ROOT / "common/scripted_guis").glob("*.txt"):
            for key in re.findall(r"custom_tooltip = (rbhm_\w+)", path.read_text(encoding="utf-8")):
                self.assertIn(key, localized["russian"])

    def test_picker_layout_and_visibility_regressions_from_game_log(self):
        text = (ROOT / "gui/window_county_view.gui").read_text(encoding="utf-8")
        self.assertNotIn("GetPlayer.HasVariable", text)
        # Extract our widget: the catalogue parser intentionally does not cover
        # the GUI language's native template definitions elsewhere in the file.
        start = text.rindex("widget = {", 0, text.index('name = "rbhm_picker"'))
        depth = 0
        for token in re.finditer(r'"(?:\\.|[^"\\])*"|\#[^\n]*|[{}]', text[start:]):
            depth += (token.group() == "{") - (token.group() == "}")
            if token.group() == "}" and depth == 0:
                picker = parse(text[start:start + token.end()])[0]
                break
        else:
            self.fail("Unclosed picker widget")
        boxes = [n for n in nodes_walk(children(picker)) if n.key == "vbox"]
        self.assertEqual(len(boxes), 1)
        self.assertTrue(any(n.key == "ignoreinvisible" and n.value == "yes" for n in children(boxes[0])))
        rows = [n for n in children(boxes[0]) if n.key == "button_standard"]
        expected = sum(len(self.manifest["actions"][m]) for m in MODES[3:])
        self.assertEqual(len(rows), expected)
        for row in rows:
            self.assertNotIn("ignoreinvisible", {n.key for n in children(row)}, "Layout property is invalid on game_button")
            shown = next(n.value for n in children(row) if n.key == "visible")
            gui_name = re.search(r"GetScriptedGui\('([^']+)'\)", shown).group(1)
            self.assertIn(gui_name, self.guis)
            gui = self.guis[gui_name]
            for field in ("is_shown", "is_valid"):
                gate = next(n for n in children(gui) if n.key == field)
                self.assertEqual(children(gate)[0].key, "rbhm_menu_context")
            effect = next(n for n in children(gui) if n.key == "effect")
            self.assertIn("rbhm_menu_context", {n.key for n in nodes_walk(children(effect))})
        actor = next(n for n in children(self.triggers["rbhm_menu_context"]) if n.key == "scope:actor")
        self.assertEqual([(n.key, n.value) for n in children(actor)], [
            ("has_variable", "rbhm_menu"), ("has_variable", "rbhm_menu_province"),
            ("var:rbhm_menu_province", "root"),
        ])

    def test_game_scripts_have_required_bom_and_lf(self):
        for path in (ROOT / "common").rglob("*.txt"):
            data = path.read_bytes()
            self.assertTrue(data.startswith(b"\xef\xbb\xbf"), path)
            self.assertNotIn(b"\r", data, path)
            data.decode("utf-8-sig")

    def test_controls_belong_to_holding_screen_not_selection_windows(self):
        text = (ROOT / "gui/window_county_view.gui").read_text(encoding="utf-8")
        source = (ROOT.parent / "AGOT_DI_RUSBAR_ADDON/gui/window_county_view.gui").read_text(encoding="utf-8-sig")
        # Independent of the generator's brace locator: split the top-level
        # window headers in this concrete source and check the owning window.
        sections = re.split(r"(?m)^window\s*=", text)[1:]
        owners = {}
        for section in sections:
            name = re.search(r'^\s*\{\s*name\s*=\s*"([^"]+)"', section).group(1)
            owners[name] = section
        self.assertIn("rbhm_controls = {}", owners["holding_view"])
        self.assertIn('name = "rbhm_picker"', owners["holding_view"])
        for name in ("holding_tracks_view", "holding_type_selection_view"):
            self.assertNotIn("rbhm_controls = {}", owners[name])
            self.assertNotIn('name = "rbhm_picker"', owners[name])
            start, end = window_bounds(text, name)
            old_start, old_end = window_bounds(source, name)
            self.assertEqual(text[start:end + 1], source[old_start:old_end + 1])
        controls = (ROOT / "gui/rbhm_controls.gui").read_text(encoding="utf-8")
        self.assertNotIn("parentanchor = bottom|left", controls)
        self.assertIn('GetScriptedGui(\'rbhm_legacy_add_slot\').IsShown', controls)
        panel = next(n for n in nodes_walk(parse(controls)) if n.key == "rbhm_controls")
        # Explicit engine errors in the 06:41 log: these layout properties
        # are unsupported by widget and prevent successful panel creation.
        self.assertFalse({"margin_left", "margin_bottom"} & {n.key for n in children(panel)})
        # The panel occupies a cell in the existing holding layout, not an
        # absolute overlay relative to the outer host window's nominal height.
        before = owners["holding_view"].split("rbhm_controls = {}", 1)[0]
        self.assertRegex(before, r'vbox = \{\s+layoutpolicy_vertical = expanding\s+allow_outside = yes\s+$')
        buttons = [n for n in nodes_walk(parse(controls)) if n.key == "button_icon"]
        self.assertEqual(len(buttons), 6)
        for i, button in enumerate(buttons):
            self.assertEqual(any(n.key == "visible" for n in children(button)), i >= 3)
            self.assertTrue(any(n.key == "enabled" for n in children(button)))

    def test_window_locator_ignores_braces_in_tooltips_and_comments(self):
        source = '''window = {
 name = "holding_view"
 widget = { tooltip = "nested { and } with escaped \\\"quote" }
 # } not a real closing brace
}
window = { name = "holding_type_selection_view" }
'''
        start, close = window_bounds(source, "holding_view")
        self.assertEqual(start, 0)
        self.assertEqual(source[close:], '}\nwindow = { name = "holding_type_selection_view" }\n')
        with self.assertRaises(ValueError):
            window_bounds(source, "missing_window")
        with self.assertRaises(ValueError):
            window_bounds(source + source, "holding_view")

    def test_button_states_reference_existing_artwork_frames(self):
        from PIL import Image
        text = (ROOT / "gui/rbhm_controls.gui").read_text(encoding="utf-8")
        buttons = [n for n in nodes_walk(parse(text)) if n.key == "button_icon"]
        for button in buttons:
            snippet = text[button.start:button.end]
            size = re.search(r'framesize\s*=\s*\{\s*(\d+)\s+(\d+)\s*\}', snippet)
            self.assertIsNotNone(size, "Artwork frame size must not depend on flat-icon defaults")
            fw, fh = map(int, size.groups())
            frames = re.search(r'blockoverride "button_frames"\s*\{([^{}]*)\}', snippet)
            self.assertIsNotNone(frames)
            values = dict(re.findall(r'(upframe|uphoverframe|uppressedframe|downframe|downhoverframe|downpressedframe|disableframe)\s*=\s*(\d+)', frames[1]))
            self.assertEqual(len(values), 7, "Do not inherit any native flat-icon state")
            self.assertRegex(snippet, r'blockoverride "button_icon_modify_texture"\s*\{\s*\}')
            textures = set(re.findall(r'(?m)^\s*texture\s*=\s*"(gfx/[^"\n]+\.dds)"', snippet))
            self.assertEqual(len(textures), 2)
            for texture in textures:
                with Image.open(ROOT / texture) as im:
                    self.assertEqual(im.width % fw, 0)
                    self.assertEqual(im.height % fh, 0)
                    count = (im.width // fw) * (im.height // fh)
                for frame in values.values():
                    self.assertTrue(1 <= int(frame) <= count, (texture, frame, count))

    def test_button_artwork_uses_static_paths_and_keeps_clicks_on_button(self):
        text = (ROOT / "gui/rbhm_controls.gui").read_text(encoding="utf-8")
        for button in (n for n in nodes_walk(parse(text)) if n.key == "button_icon"):
            props = {n.key: n for n in children(button)}
            self.assertRegex(props["texture"].value, r'^"gfx/[^"\n]+_inactive\.dds"$')
            icon = next(n for n in children(button) if n.key == "icon")
            artwork = {n.key: n for n in children(icon)}
            self.assertRegex(artwork["texture"].value, r'^"gfx/[^"\n]+_active\.dds"$')
            self.assertEqual(artwork["visible"].value, props["enabled"].value)
            self.assertEqual(artwork["alwaystransparent"].value, "yes")
            self.assertNotIn("onclick", artwork)
            self.assertIn("onclick", props)
            for n in (props["texture"], artwork["texture"]):
                self.assertTrue((ROOT / n.value.strip('"')).is_file())

    def test_tooltip_has_a_background_and_bounded_scrollable_text(self):
        text = (ROOT / "gui/rbhm_controls.gui").read_text(encoding="utf-8")
        for button in (n for n in nodes_walk(parse(text)) if n.key == "button_icon"):
            tooltip = next(n for n in children(button) if n.key == "tooltipwidget")
            container = next(n for n in children(tooltip) if n.key == "container")
            self.assertTrue(any(n.key == "alwaystransparent" and n.value == "no" for n in children(container)))
            background = next(n for n in children(container) if n.key == "widget")
            self.assertTrue(any(n.key == "using" and n.value == "DefaultTooltipBackground" for n in children(background)))
            scroll = next(n for n in nodes_walk(children(tooltip)) if n.key == "scrollbox")
            label = next(n for n in nodes_walk(children(scroll)) if n.key == "textbox")
            width = int(next(n.value for n in children(label) if n.key == "max_width"))
            scroll_width = int(re.search(r'size\s*=\s*\{\s*(\d+)', text[scroll.start:scroll.end])[1])
            self.assertTrue(0 < width < scroll_width, "Leave room for the scrollbar and avoid clipped prose")
            self.assertTrue(any(n.key == "using" and n.value == "DefaultTooltipText" for n in children(label)))
            self.assertFalse(any(n.key in ("textbox", "text_multi", "scrollbox") for n in children(button)), "Tooltip content must not be an ordinary screen child")
        for path in (ROOT / "localization").glob("*/rbhm_buildings_l_*.yml"):
            self.assertNotRegex(path.read_text(encoding="utf-8-sig"), r'rbhm_line_\w+:0 "•')

    def test_dds_assets_are_complete_small_and_distinct(self):
        from PIL import Image
        for mode in MODES:
            data = []
            for state in ("active", "inactive"):
                p = ROOT / f"gfx/interface/icons/rbhm/{mode}_{state}.dds"
                with Image.open(p) as im:
                    self.assertEqual(im.size, (128, 128))
                    self.assertEqual(im.mode, "RGBA")
                data.append(p.read_bytes())
            self.assertNotEqual(*data)


if __name__ == "__main__":
    unittest.main()
