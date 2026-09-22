"""Compile the reviewed building catalogue into native CK3 scripts and holding UI.

The catalogue remains data, not an interpreter for CK3 triggers. The game evaluates
the original ordered conditions in province scope, with holder/county/character
scopes supplied just as in native construction. No upstream building is replaced.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import itertools
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
PREFIX = "rbhm_"
REQS = ("is_enabled", "can_construct_potential", "can_construct_showing_failures_only", "can_construct")
MODES = ("main_upgrade", "regular_build", "regular_upgrade", "duchy", "special", "great")
CURRENCIES = ("gold", "prestige", "piety", "treasury")
# These are connected components, NOT mutually exclusive cliques. In particular,
# two mines can coexist and the mills/caravanserai restriction is conditional.
GROUPS = (
    ("apiaries_01", "agot_gold_mines_01", "agot_silver_mines_01"),
    ("building_moat_01", "curtain_walls_01"),
    ("watermills_01", "windmills_01", "caravanserai_01"),
)


def block(key, body):
    return f"{key} = {{\n" + "\n".join("\t" + x for x in body.splitlines()) + "\n}\n"


def render(node):
    k = node["key"]
    op = node.get("operator")
    if "children" in node:
        return f"{k} {op or '='} {{\n" + "\n".join("\t" + l for n in node["children"] for l in render(n).splitlines()) + "\n}"
    if op is None:
        return k
    return f"{k} {op} {node['value']}"


def body(node):
    return "\n".join(render(n) for n in node.get("children", []))


def walk(node):
    yield node
    for n in node.get("children", []):
        yield from walk(n)


def sections(node, key):
    return [n for n in node.get("children", []) if n["key"] == key]


def write(path, content, bom=False):
    path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    # CK3 1.19's script lexer explicitly requires UTF-8 with BOM for these files.
    bom = bom or (path.suffix == ".txt" and path.is_relative_to(ROOT / "common"))
    path.write_text(content.rstrip() + "\n", encoding="utf-8-sig" if bom else "utf-8", newline="\n")


def choice_key(bid):
    # The original label hashes to the same engine key as vanilla's
    # feature_decoration_pattern_quotes (confirmed in the 2026-09-22 log).
    if bid == "agot_grassfield_florestries_01":
        return "rbhm_pick_label_" + bid
    return "rbhm_choice_" + bid


def req_body(b, keys=REQS):
    return "\n".join(body(x["syntax"]) for k in keys for x in b["requirements"][k])


def project_physical(node):
    """Explicit allowlist: keep geographic improvements, not project rewards/events."""
    allowed = {"add_county_modifier", "add_province_modifier", "remove_county_modifier", "remove_province_modifier"}
    out = []
    for n in node.get("children", []):
        if n["key"] in allowed:
            out.append(render(n))
        elif n["key"] in ("scope:province", "scope:province.county", "scope:province.barony"):
            v = project_physical(n)
            if v:
                out.append(block(n["key"], v))
        elif n["key"] in ("custom_tooltip", "hidden_effect", "on_complete"):
            out.append(project_physical(n))
    return "\n".join(x for x in out if x)


class Compiler:
    def __init__(self, catalog):
        self.catalog = catalog
        self.buildings = catalog["buildings"]
        self.triggers = []
        self.values = []
        self.effects = []
        self.guis = []
        self.rows = []
        self.included = {}
        self.excluded = {}
        self.actions = {mode: [] for mode in MODES}
        self.projects = {}

    def add_trigger(self, key, value):
        self.triggers.append(block(PREFIX + key, value or "always = yes"))

    def add_value(self, key, value):
        self.values.append(block(PREFIX + key, value))

    def gui(self, key, shown, valid, effect):
        # The root is ALWAYS the selected province, not the paying character.
        self.guis.append(block(PREFIX + key,
            "scope = province\nsaved_scopes = { actor holder county character province founder owner duchy_slot special_slot }\n"
            + block("is_shown", shown) + block("is_valid", valid) + block("effect", effect)))

    def choose_buildings(self):
        for bid, b in self.buildings.items():
            why = None
            if b["is_graphical_background"]:
                why = "graphical_background"
            elif b["category"] == "great":
                project = b["great_project_upgrade_pointer"]
                if not project and bid == "mandala_capital_01":
                    project = "mandala_capital_01"
                if project:
                    definition = self.catalog["definitions"].get("great_project:" + project)
                    if definition:
                        self.projects[bid] = (project, definition)
                    else:
                        why = "project_definition_missing"
                else:
                    why = "no_construction_project_or_price"
            elif b["explicit_potential_always_no"]:
                why = "construction_explicitly_disabled"
            elif not b["construction_cost"]["resolved_base_cost"]:
                why = "no_declared_price"
            elif b["category"] in ("regular", "base") and not b["holding_memberships"]:
                why = "not_in_holding_construction_list"
            elif b["category"] == "base" and not b["upgrade"]["previous"]:
                why = "primary_construction_not_upgrade"
            if why:
                self.excluded[bid] = why
            else:
                self.included[bid] = b
                mode = {"base": "main_upgrade", "regular": "regular_upgrade" if b["upgrade"]["previous"] else "regular_build"}.get(b["category"], b["category"])
                self.actions[mode].append(bid)

    def prereq(self, bid):
        b = self.buildings[bid]
        result = []
        cat = b["category"]
        if cat in ("regular", "base"):
            holds = sorted({x["holding"] for x in b["holding_memberships"]})
            result.append(block("OR", "\n".join("has_holding_type = " + h for h in holds)))
        prev = b["upgrade"]["previous"]
        if prev:
            result.append(block("OR", "\n".join("has_building = " + p for p in prev)))
        else:
            roots = {x["root"] for x in b["upgrade"]["chains"]}
            result.append(block("NOR", "\n".join("has_building_or_higher = " + p for p in sorted(roots))))
        if cat == "duchy":
            result.append("scope:duchy_slot = yes")
            if not prev:
                result.append(block("NOR", "\n".join("has_building = " + k for k, v in self.buildings.items() if v["category"] == "duchy")))
        if cat == "special":
            # The native holding UI reports the actual slot's type. History is
            # not used as an authorization list; events may change that slot.
            result.append("has_special_building_slot = yes")
            roots = sorted({x["root"] for x in b["upgrade"]["chains"]})
            chain = {bid, *prev, *roots}
            result.append(block("OR", "\n".join("scope:special_slot = flag:" + x for x in sorted(chain))))
            if not prev:
                result.append("has_special_building = no")
        if cat == "great":
            result.append("has_ruined_great_building = no")
            result.append("NOT = { any_great_project_in_province = { always = yes } }")
            if not prev:
                result.append("has_great_building = no")
        if bid == "caravanserai_01":
            # is_enabled counts the completed building as well. Its <= limit is
            # insufficient before construction; reserve the new member now.
            result.append("""trigger_if = {
    limit = { culture = { has_cultural_parameter = second_caravanserai } }
    county = { NOT = { any_county_province = { count >= 2 has_building_or_higher = caravanserai_01 } } }
}
trigger_else = {
    county = { NOT = { any_county_province = { has_building_or_higher = caravanserai_01 } } }
}""")
        return "\n".join(result)

    def compile_conditions(self):
        for bid, b in self.included.items():
            requirements = req_body(b)
            if bid in self.projects:
                project, definition = self.projects[bid]
                # Native planner supplies its own proper founder and location scopes.
                # Project-only buildings deliberately have can_construct = no;
                # the project replaces that gate, but not their is_enabled gate.
                requirements = req_body(b, ("is_enabled",))
                requirements += f"\nscope:founder = {{ can_plan_great_project_in_province = {{ type_name = {project} province = root }} }}"
            self.add_trigger("eligible_" + bid, self.prereq(bid) + "\n" + requirements)

        # Live predicates, randomized ordering fixed per province. Previewing never
        # rerolls. A group is evaluated as a greedy compatible set, not a clique.
        grouped = {bid for group in GROUPS for bid in group}
        for mode, bids in self.actions.items():
            for bid in bids:
                if mode != "regular_build" or bid not in grouped:
                    self.add_trigger("pick_" + bid, f"rbhm_eligible_{bid} = yes")
        for gi, group in enumerate(GROUPS):
            for pi, order in enumerate(itertools.permutations(group)):
                earlier = []
                for bid in order:
                    nodes = [copy.deepcopy(n) for key in REQS for entry in self.buildings[bid]["requirements"][key] for n in entry["syntax"].get("children", [])]
                    # Only replace direct building references; their parent logic,
                    # conditional branches and province scoping remain untouched.
                    for n in nodes:
                        self.project_presence(n, earlier, gi, pi)
                    self.add_trigger(f"order_{gi}_{pi}_{bid}", self.prereq(bid) + "\n" + "\n".join(render(n) for n in nodes))
                    earlier.append(bid)
            for bid in group:
                tests = [block("AND", f"var:rbhm_order_{gi} = {pi}\nrbhm_order_{gi}_{pi}_{bid} = yes") for pi, _ in enumerate(itertools.permutations(group))]
                # GUI conditions can be evaluated before the initialization
                # state runs. AND does not guarantee a short circuit in CK3;
                # a conditional branch must guard every missing-variable read.
                ready = block("trigger_if", block("limit", f"has_variable = rbhm_order_{gi}") + block("OR", "\n".join(tests)))
                ready += block("trigger_else", "always = no")
                self.add_trigger("pick_" + bid, ready)

    def project_presence(self, node, earlier, gi, pi):
        for child in node.get("children", []):
            self.project_presence(child, earlier, gi, pi)
        if node["key"] == "has_building_or_higher" and node.get("value") in earlier:
            bid = node["value"]
            original = copy.deepcopy(node)
            node.clear()
            node.update(key="OR", operator="=", children=[original, {
                "key": "AND", "operator": "=", "children": [
                    {"key": "this", "operator": "=", "value": "root"},
                    {"key": f"rbhm_order_{gi}_{pi}_{bid}", "operator": "=", "value": "yes"},
                ],
            }])

    def compile_prices(self):
        for bid, b in self.included.items():
            costs = dict(b["construction_cost"]["resolved_base_cost"])
            if bid in self.projects:
                project, definition = self.projects[bid]
                syntax = definition["syntax"]
                costs = {}
                charges = list(sections(syntax, "cost"))
                contributions = sections(syntax, "project_contributions")
                for contribution in contributions:
                    for part in contribution["children"]:
                        charges.extend(sections(part, "cost"))
                raw = {}
                for charge in charges:
                    seen = set()
                    for n in charge["children"]:
                        currency = n["key"]
                        if currency in seen:
                            continue
                        seen.add(currency)
                        raw.setdefault(currency, []).append(n)
                unknown = set(raw) - set(CURRENCIES) - {"treasury_or_gold"}
                if unknown:
                    raise ValueError(f"Unreviewed project currencies for {bid}: {unknown}")
                for currency, entries in raw.items():
                    val = "value = 0\n" + "\n".join(block("add", body(n)) if "children" in n else "add = " + n["value"] for n in entries)
                    # Project base charges are character-scoped (income, treasury).
                    self.add_value(f"project_{bid}_{currency}", val + "\nmultiply = 10")
                    costs[currency] = f"scope:actor.rbhm_project_{bid}_{currency}"
                self.projects[bid] = (project, definition, raw)
            for currency in CURRENCIES:
                value = costs.get(currency, 0)
                if isinstance(value, (int, float)):
                    value *= 10
                code = f"value = {value}"
                if "treasury_or_gold" in costs and currency in ("gold", "treasury"):
                    condition = "yes" if currency == "treasury" else "no"
                    code += "\n" + block("if", block("limit", f"scope:actor = {{ has_treasury = {condition} }}") + "add = " + costs["treasury_or_gold"])
                self.add_value(f"price_{bid}_{currency}", code)
            self.add_trigger("afford_" + bid, "\n".join(f"OR = {{ rbhm_price_{bid}_{c} = 0 scope:actor = {{ {c} >= root.rbhm_price_{bid}_{c} }} }}" for c in CURRENCIES))

    def compile_totals(self):
        for mode, bids in self.actions.items():
            conditional = mode in ("duchy", "special", "great")
            for what in ("count", *CURRENCIES):
                code = "value = 0\n"
                for bid in bids:
                    check = f"rbhm_pick_{bid} = yes"
                    if conditional:
                        check += f"\nrbhm_afford_{bid} = yes"
                    add = "1" if what == "count" else f"rbhm_price_{bid}_{what}"
                    code += block("if", block("limit", check) + "add = " + add)
                if mode == "regular_build" and what == "gold":
                    code += "add = { value = rbhm_slots_needed multiply = 1000 }\n"
                self.add_value(f"{mode}_{what}", code)
            validity = f"rbhm_context = yes\nrbhm_idle = yes\nrbhm_{mode}_count > 0"
            if not conditional:
                validity += "\n" + "\n".join(f"OR = {{ rbhm_{mode}_{c} = 0 scope:actor = {{ {c} >= root.rbhm_{mode}_{c} }} }}" for c in CURRENCIES)
            if mode == "regular_build":
                validity += "\nrbhm_final_slots <= define:NProvince|MAX_BUILDINGS\nhas_variable = rbhm_order_0\nhas_variable = rbhm_order_1\nhas_variable = rbhm_order_2"
            self.add_trigger("can_" + mode, validity)
        self.add_value("slots_needed", "value = rbhm_regular_build_count\nsubtract = free_building_slots\nmin = 0")
        self.add_value("final_slots", "value = building_slots\nadd = rbhm_slots_needed")

    def snapshot(self, bids, affordable=False):
        code = ""
        for bid in bids:
            check = f"rbhm_pick_{bid} = yes"
            if affordable:
                check += f"\nrbhm_afford_{bid} = yes"
            code += block("if", block("limit", check) + f"save_scope_value_as = {{ name = rbhm_selected_{bid} value = 1 }}")
        return code

    def apply_building(self, bid):
        b = self.buildings[bid]
        if bid in self.projects:
            project, definition, _ = self.projects[bid]
            effect = ("replace_building_effect" if b["upgrade"]["previous"] else "add_great_building") + " = " + bid
            if bid == "mandala_capital_01":
                effect = "if = { limit = { NOT = { has_holding_type = temple_citadel_holding } } set_holding_type = temple_citadel_holding }\n" + effect
                effect += "\nadd_to_global_variable_list = { name = mandala_poi_list target = this }"
            # The building and all purchased geographic contribution improvements.
            improvements = ""
            for n in sections(definition["syntax"], "project_contributions"):
                for part in n["children"]:
                    for completed in sections(part, "on_complete"):
                        improvements += "\n" + project_physical(completed)
            improvements = "\n".join(line for line in improvements.splitlines() if line.strip())
            if improvements:
                effect += "\n" + block("if", block("limit", "has_building = " + bid) + improvements)
            return effect
        # add_building upgrades regular slots, but rejects an occupied duchy
        # slot (confirmed by the 07:52 log). Use the native replacement effect
        # for unique-slot upgrades, after the exact predecessor was validated.
        if b["category"] in ("duchy", "special") and b["upgrade"]["previous"]:
            return "replace_building_effect = " + bid
        # Do not replay on_complete manually: it belongs to the engine.
        return "add_building = " + bid

    def compile_effects(self):
        for mode, bids in self.actions.items():
            conditional = mode in ("duchy", "special", "great")
            tooltip = f"custom_tooltip = rbhm_{mode}_desc\n"
            for bid in bids:
                condition = f"rbhm_pick_{bid} = yes"
                if conditional:
                    condition += f"\nrbhm_afford_{bid} = yes"
                prices = "\n".join(f"save_temporary_scope_value_as = {{ name = rbhm_line_{c} value = rbhm_price_{bid}_{c} }}" for c in CURRENCIES)
                tooltip += block("if", block("limit", condition) + prices + f"\ncustom_tooltip = rbhm_line_{bid}")
            if not conditional:
                for c in CURRENCIES:
                    tooltip += f"save_temporary_scope_value_as = {{ name = rbhm_total_{c} value = rbhm_{mode}_{c} }}\n"
                tooltip += "save_temporary_scope_value_as = { name = rbhm_slot_count value = rbhm_slots_needed }\n" if mode == "regular_build" else "save_temporary_scope_value_as = { name = rbhm_slot_count value = 0 }\n"
                tooltip += "custom_tooltip = rbhm_total\n"
            tooltip += "custom_tooltip = rbhm_conditions\n"
            action = self.snapshot(bids, conditional)
            if conditional:
                action += block("if", block("limit", f"rbhm_{mode}_count = 1") + self.execute_selected(bids))
                action += block("else", "scope:actor = { set_variable = { name = rbhm_menu_province value = root } set_variable = { name = rbhm_menu value = flag:" + mode + " } }")
            else:
                for c in CURRENCIES:
                    action += f"save_scope_value_as = {{ name = rbhm_pay_{c} value = rbhm_{mode}_{c} }}\n"
                action += "save_scope_value_as = { name = rbhm_slot_count value = rbhm_slots_needed }\n" if mode == "regular_build" else ""
                action += self.pay()
                if mode == "regular_build":
                    action += "while = { count = scope:rbhm_slot_count add_province_modifier = extra_building_slot }\n"
                for bid in bids:
                    action += block("if", block("limit", f"exists = scope:rbhm_selected_{bid}") + self.apply_building(bid))
            code = block("show_as_tooltip", tooltip) + block("hidden_effect", block("if", block("limit", "rbhm_can_" + mode + " = yes") + action))
            self.gui(mode, f"rbhm_can_{mode} = yes" if conditional else "rbhm_context = yes", "rbhm_can_" + mode + " = yes", code)
            if conditional:
                for bid in bids:
                    menu = f"rbhm_menu_context = yes\nscope:actor = {{ var:rbhm_menu = flag:{mode} }}"
                    valid = f"{menu}\nrbhm_idle = yes\nrbhm_pick_{bid} = yes\nrbhm_afford_{bid} = yes"
                    prices = "\n".join(f"save_temporary_scope_value_as = {{ name = rbhm_line_{c} value = rbhm_price_{bid}_{c} }}" for c in CURRENCIES)
                    effect = block("show_as_tooltip", prices + f"\ncustom_tooltip = rbhm_line_{bid}")
                    effect += block("hidden_effect", block("if", block("limit", valid) + self.execute_single(bid, close_menu=True)))
                    self.gui("select_" + bid, f"{menu}\nrbhm_pick_{bid} = yes", valid, effect)

    @staticmethod
    def pay():
        # remove_* avoids awarding fame/devotion for paying a price.
        payments = []
        for c in CURRENCIES:
            if c in ("prestige", "piety"):
                pay = f"add_{c}_no_experience = {{ value = scope:rbhm_pay_{c} multiply = -1 }}"
            else:
                pay = f"remove_{'long_term_gold' if c == 'gold' else c} = scope:rbhm_pay_{c}"
            payments.append(f"if = {{ limit = {{ scope:rbhm_pay_{c} > 0 }} {pay} }}")
        return block("scope:actor", "\n".join(payments))

    def execute_single(self, bid, close_menu=False):
        # Freeze dynamic prices before construction changes province income.
        # Only pay (and close the picker) after the requested building exists;
        # a rejected engine effect must not consume the quoted resources.
        prices = "\n".join(f"save_scope_value_as = {{ name = rbhm_pay_{c} value = rbhm_price_{bid}_{c} }}" for c in CURRENCIES)
        success = self.pay().rstrip()
        if close_menu:
            success += "\nscope:actor = { remove_variable = rbhm_menu remove_variable = rbhm_menu_province }"
        return prices + "\n" + self.apply_building(bid).rstrip() + "\n" + block("if", block("limit", "has_building = " + bid) + success)

    def execute_selected(self, bids):
        return "\n".join(block("if", block("limit", f"exists = scope:rbhm_selected_{bid}") + self.execute_single(bid)) for bid in bids)

    def compile_context(self):
        self.add_trigger("context", """has_holding = yes
exists = province_owner
exists = scope:actor
scope:actor = { is_ai = no is_alive = yes }
OR = {
    province_owner = scope:actor
    scope:actor = { is_liege_or_above_of = root.province_owner }
}
NOR = {
    has_holding_type = unknown_holding
    has_holding_type = wilderness_holding
    has_holding_type = ruin_holding
    has_holding_type = nomad_holding
    has_holding_type = herder_holding
}""")
        self.add_trigger("idle", "has_ongoing_construction = no\nis_occupied = no")
        init = ""
        for gi, group in enumerate(GROUPS):
            options = "\n".join(block("1", f"set_variable = {{ name = rbhm_order_{gi} value = {pi} }}") for pi, _ in enumerate(itertools.permutations(group)))
            init += block("if", block("limit", f"NOT = {{ has_variable = rbhm_order_{gi} }}") + block("random_list", options))
        needs = "rbhm_context = yes\nOR = { " + " ".join(f"NOT = {{ has_variable = rbhm_order_{i} }}" for i in range(len(GROUPS))) + " }"
        self.gui("initialize", "rbhm_context = yes", needs, block("if", block("limit", needs) + init))
        # Character has no GUI HasVariable function. Use native script triggers
        # and keep an old picker from applying an order to another province.
        self.add_trigger("menu_context", """rbhm_context = yes
scope:actor = {
    has_variable = rbhm_menu
    has_variable = rbhm_menu_province
    var:rbhm_menu_province = root
}""")
        self.gui("menu", "rbhm_menu_context = yes", "rbhm_menu_context = yes", "")
        self.gui("close", "always = yes", "always = yes", "scope:actor = { remove_variable = rbhm_menu remove_variable = rbhm_menu_province }")

    def run(self):
        self.choose_buildings()
        self.compile_context()
        self.compile_conditions()
        self.compile_prices()
        self.compile_totals()
        self.compile_effects()
        write("common/scripted_triggers/rbhm_buildings.txt", "# Generated from the selected catalogue; edit tools/build_runtime.py.\n" + "\n".join(self.triggers))
        write("common/script_values/rbhm_buildings.txt", "# Base prices x10, before character construction discounts.\n" + "\n".join(self.values))
        write("common/scripted_guis/rbhm_buildings.txt", "# Province root. GUI supplies the native construction scopes.\n" + "\n".join(self.guis))
        layers_used = {b["source"]["layer"] for b in self.included.values()} - {"ck3"}
        dependencies = [layer["name"] for layer in self.catalog["layers"] if layer["id"] in layers_used]
        write("data/runtime-manifest.json", json.dumps({
            "catalog_sha256": hashlib.sha256(json.dumps(self.catalog, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest(),
            "dependencies": dependencies,
            "included": {k: {"source": b["source"], "category": b["category"]} for k, b in self.included.items()},
            "excluded": self.excluded, "actions": self.actions,
            "projects": {bid: p[0] for bid, p in self.projects.items()},
        }, ensure_ascii=False, indent=2))
        descriptor = 'version="0.1.0"\ntags={ "Utilities" "Gameplay" }\nname="AGOT RB | Управление владениями RUSBAR"\nsupported_version="1.19.0.6"\n'
        descriptor += block("dependencies", "\n".join(json.dumps(name, ensure_ascii=False) for name in dependencies))
        write("descriptor.mod", descriptor)
        write("../AGOT_RB_HM.mod", descriptor + 'path="' + ROOT.as_posix() + '"\n')
        build_gui(self)
        build_localization(self)
        print(json.dumps({"actions": {k: len(v) for k, v in self.actions.items()}, "excluded": len(self.excluded)}, indent=2))


def gui_scope():
    return ("GuiScope.SetRoot(HoldingView.GetProvince.MakeScope)"
        ".AddScope('province', HoldingView.GetProvince.MakeScope)"
        ".AddScope('actor', GetPlayer.MakeScope).AddScope('character', GetPlayer.MakeScope)"
        ".AddScope('holder', HoldingView.GetHolder.MakeScope).AddScope('founder', HoldingView.GetHolder.MakeScope)"
        ".AddScope('owner', HoldingView.GetHolder.MakeScope)"
        ".AddScope('county', HoldingView.GetCountyTitle.MakeScope)"
        ".AddScope('duchy_slot', MakeScopeBool(HoldingView.HasDuchyCapitalBuildingSlot))"
        ".AddScope('special_slot', MakeScopeFlag(Select_CString(HoldingView.HasSpecialBuildingSlot, HoldingView.GetGUISpecialBuilding.GetCurrentOrConstrucingBuilding.GetKey, 'none')))"
        ".End")


def call(name, method="IsValid"):
    return f"GetScriptedGui('rbhm_{name}').{method}({gui_scope()})"


def window_bounds(source, name):
    """Locate one named top-level window, ignoring braces in strings/comments.

    window_county_view.gui also contains holding_tracks_view and holding_type_selection_view.
    The last brace before TYPES belongs to a different window, not holding_view.
    """
    matches = list(re.finditer(r'(?m)^window\s*=\s*\{\s*name\s*=\s*"' + re.escape(name) + r'"', source))
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one top-level window named {name}")
    start = matches[0].start()
    depth = 0
    for token in re.finditer(r'"(?:\\.|[^"\\])*"|\#[^\n]*|[{}]', source[start:]):
        depth += (token.group() == "{") - (token.group() == "}")
        if token.group() == "}" and depth == 0:
            return start, start + token.start()
    raise ValueError(f"Unclosed GUI window {name}")


def build_gui(c):
    # A plain widget has no margin_left/margin_bottom properties. Reserve
    # padding inside its size and offset the buttons, using supported fields.
    panel = 'name = "rbhm_controls"\nsize = { 116 184 }\nalwaystransparent = no\n'
    # Use the same minimal realm check as the working '+' control. Optional
    # construction scopes must not hide the entire panel of ordinary actions.
    shown = "GetScriptedGui('rbhm_legacy_add_slot').IsShown(GuiScope.SetRoot(GetPlayer.MakeScope).AddScope('gui_holding', HoldingView.GetProvince.MakeScope).End)"
    panel += f'visible = "[{shown}]"\n'
    panel += block("state", f'name = rbhm_initialize\ntrigger_when = "[{call("initialize")}]"\non_start = "[{call("initialize", "Execute")}]"')
    for idx, mode in enumerate(MODES):
        x, y = (4, idx * 58) if idx < 3 else (62, (idx - 3) * 58)
        valid = call(mode)
        button = f'name = "rbhm_{mode}_button"\nsize = {{ 52 52 }}\nposition = {{ {x} {y} }}\n'
        if idx >= 3:
            button += f'visible = "[{call(mode, "IsShown")}]"\n'
        button += f'enabled = "[{valid}]"\nonclick = "[{call(mode, "Execute")}]"\n'
        # Literal texture paths go through the GUI asset loader, as on the
        # working '+' button. Do not return a filename string as a texture.
        # Keep a visible inactive base and overlay the active artwork only when
        # the same condition that enables the button succeeds.
        button += f'texture = "gfx/interface/icons/rbhm/{mode}_inactive.dds"\n'
        # These are finished, single-image RGBA artworks. Native button_icon
        # instead shades flat masks through a separate multi-frame color atlas.
        # Do not inherit that tint or request any frame outside our 128px image.
        button += 'framesize = { 128 128 }\nblockoverride "button_icon_modify_texture" {}\n'
        button += 'blockoverride "button_frames" {\n\tgfxtype = togglepushbuttongfx\n\teffectname = "NoHighlight"\n'
        button += "".join(f"\t{state} = 1\n" for state in ("upframe", "uphoverframe", "uppressedframe", "downframe", "downhoverframe", "downpressedframe", "disableframe")) + '}\n'
        button += block("icon", f'name = "rbhm_{mode}_active_artwork"\nsize = {{ 100% 100% }}\nalwaystransparent = yes\nvisible = "[{valid}]"\ntexture = "gfx/interface/icons/rbhm/{mode}_active.dds"')
        button += f'tooltip = "[{call(mode, "BuildTooltip")}]"\nusing = tooltip_ne\n'
        # A full batch can exceed the screen height. Keep the native pinnable
        # tooltip with the same background widget as DefaultTooltipWidget.
        # GeneralTooltipSetup alone only wires mouse/close handling, not a frame.
        scrolltext = block("textbox", f'using = DefaultTooltipText\nusing = Font_Type_Standard\nusing = Font_Size_Small\nmax_width = 440\nfonttintcolor = "[TooltipInfo.GetTintColor]"\ntext = "[{call(mode, "BuildTooltip")}]"')
        scroll = block("scrollbox", 'size = { 480 400 }\n' + block('blockoverride "scrollbox_content"', scrolltext).replace('blockoverride "scrollbox_content" =', 'blockoverride "scrollbox_content"'))
        background = block("widget", 'name = "background"\nusing = DefaultTooltipBackground\nsize = { 100% 100% }\nalwaystransparent = no')
        content = block("flowcontainer", 'direction = vertical\nmargin = { 20 12 }\n' + scroll)
        button += block("tooltipwidget", block("container", "using = GeneralTooltipSetup\nalwaystransparent = no\n" + background + content))
        panel += block("button_icon", button)
    types = block("types rbhm_types", block("type rbhm_controls = widget", panel))
    # block() already adds '=', while type declarations use their own '='.
    types = types.replace("types rbhm_types =", "types rbhm_types").replace("type rbhm_controls = widget =", "type rbhm_controls = widget")
    write("gui/rbhm_controls.gui", types)

    window = ROOT.parent / "AGOT_DI_RUSBAR_ADDON/gui/window_county_view.gui"
    source = window.read_text(encoding="utf-8-sig")
    marker = "\t\t\t\t\t\t\t# AGOT DI RUSBAR: BUILDING SLOTS START"
    if source.count(marker) != 1:
        raise ValueError("Holding view insertion point changed; review upstream GUI")
    # The picker lives inside HoldingView and closes automatically on navigation.
    picker = 'name = "rbhm_picker"\nsize = { 600 510 }\nparentanchor = top|left\nposition = { 650 130 }\nusing = Window_Background\nusing = Window_Decoration\n'
    picker += f'visible = "[{call("menu", "IsShown")}]"\n'
    picker += 'text_single = { position = { 20 15 } text = rbhm_choose fontsize = 24 }\n'
    picker += f'button_close = {{ parentanchor = top|right position = {{ -10 10 }} onclick = "[{call("close", "Execute")}]" }}\n'
    rows = ""
    for mode in ("duchy", "special", "great"):
        for bid in c.actions[mode]:
            vis = call('select_' + bid, 'IsShown')
            row = f'size = {{ 540 46 }}\nvisible = "[{vis}]"\ntext = {choice_key(bid)}\n'
            row += f'enabled = "[{call("select_" + bid)}]"\nonclick = "[{call("select_" + bid, "Execute")}]"\n'
            row += f'tooltip = "[{call("select_" + bid, "BuildTooltip")}]"\n'
            rows += block("button_standard", row)
    picker += block("scrollbox", 'position = { 15 55 }\nsize = { 570 435 }\n' + block('blockoverride "scrollbox_content"', block("vbox", "layoutpolicy_horizontal = expanding\nignoreinvisible = yes\nspacing = 4\n" + rows)).replace('blockoverride "scrollbox_content" =', 'blockoverride "scrollbox_content"'))
    # Place the controls in the actual left-hand holding layout, alongside the
    # building grid. The outer window is only a host for the expanding content.
    left_column = "\t\t\t\t\tvbox = {\n\t\t\t\t\t\tlayoutpolicy_vertical = expanding\n\t\t\t\t\t\tallow_outside = yes\n\n\t\t\t\t\t\texpand = {}"
    start, closing = window_bounds(source, "holding_view")
    if source[start:closing].count(left_column) != 1:
        raise ValueError("Holding view left-hand column changed; review placement")
    source = source[:start] + source[start:closing].replace(left_column,
        left_column.replace("\t\t\t\t\t\texpand = {}", "\t\t\t\t\t\trbhm_controls = {}\n\t\t\t\t\t\texpand = {}"), 1) + source[closing:]
    # The picker remains a floating child of this same holding screen.
    _, closing = window_bounds(source, "holding_view")
    insertion = block("widget", picker)
    source = source[:closing] + insertion + source[closing:]
    write("gui/window_county_view.gui", source)
    # Keep existing '+' available without making this mod depend on the DI addon.
    write("gui/rbhm_legacy_slot.gui", (ROOT.parent / "AGOT_DI_RUSBAR_ADDON/gui/agot_di_rusbar_holding_controls.gui").read_text(encoding="utf-8-sig").replace("agot_di_rusbar_holding_types", "rbhm_legacy_types").replace("agot_di_rusbar_holding_slot_button", "rbhm_legacy_slot_button").replace("agot_di_rusbar_add_holding_slot", "rbhm_legacy_add_slot"))
    source = (ROOT / "gui/window_county_view.gui").read_text(encoding="utf-8")
    write("gui/window_county_view.gui", source.replace("agot_di_rusbar_holding_slot_button = {}", "rbhm_legacy_slot_button = {}"))


def build_localization(c):
    # Mechanical names/prices only. Prose is maintained directly in UI yml files.
    icons = {"gold": "gold", "prestige": "prestige", "piety": "piety", "treasury": "treasury"}
    for language in ("russian", "english"):
        lines = ["l_" + language + ":"]
        for bid, b in c.included.items():
            name = "$" + b["name_key"] + "$"
            prev = b["upgrade"]["previous"]
            if prev:
                names = " / ".join("$" + c.buildings[p]["name_key"] + "$" for p in prev)
                name = names + " → " + name
            currencies = set(b["construction_cost"]["resolved_base_cost"])
            if bid in c.projects:
                currencies = set(c.projects[bid][2])
                if "treasury_or_gold" in currencies:
                    currencies = (currencies - {"treasury_or_gold"}) | {"gold", "treasury"}
            cost = "  ".join(f"[SCOPE.GetValue('rbhm_line_{cur}')|0] @{icons[cur]}_icon!" for cur in CURRENCIES if cur in currencies)
            # custom_tooltip effect already supplies the list marker in CK3.
            lines.append(f' rbhm_line_{bid}:0 "{name}: {cost}"')
            if bid in c.projects:
                label_cost = "×10 цены проекта" if language == "russian" else "×10 project cost"
            else:
                label_cost = "  ".join(f"{float(price)*10:g} @{icons[cur]}_icon!" for cur, price in b["construction_cost"]["resolved_base_cost"].items())
            lines.append(f' {choice_key(bid)}:0 "${b["name_key"]}$ — {label_cost}"')
        write(f"localization/{language}/rbhm_buildings_l_{language}.yml", "\n".join(lines), bom=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=ROOT / "data/buildings-playset.json")
    args = parser.parse_args()
    Compiler(json.loads(args.catalog.read_text(encoding="utf-8"))).run()


if __name__ == "__main__":
    main()
