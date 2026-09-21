"""Extraction regressions and source-to-catalog checks, without launching CK3."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_catalog import Catalog, Layer, Node, Source, children, fields, parse, walk


def plain(node):
    if isinstance(node, Node):
        data = {'key': node.key, 'operator': node.op}
        if isinstance(node.value, list):
            data['children'] = [plain(n) for n in node.value]
        else:
            data['value'] = node.value
        if node.prefix:
            data['prefix'] = node.prefix
        return data
    if isinstance(node, dict):
        return {k: plain(v) for k, v in node.items() if k != 'definition_refs'}
    if isinstance(node, list):
        return [plain(v) for v in node]
    return node


class ParserTests(unittest.TestCase):
    def test_preserves_logic_scopes_repeated_keys_and_arguments(self):
        script = '''can_construct = {
          OR = { has_building = x has_building = y }
          NOR = { is_coastal = yes terrain = desert }
          scope:holder ?= { gold >= 300 }
          requirement = { LEVEL = 01 }
          requirement = no
          trigger_if = { limit = { is_ai = yes } always = no }
          trigger_else_if = { limit = { is_ai = no } always = yes }
          trigger_else = { always = no }
        }'''
        nodes = children(parse(script)[0])
        self.assertEqual([n.key for n in nodes[-3:]], ['trigger_if', 'trigger_else_if', 'trigger_else'])
        self.assertEqual([n.key for n in children(nodes[0])], ['has_building', 'has_building'])
        self.assertEqual(nodes[2].op, '?=')
        self.assertEqual(children(nodes[2])[0].op, '>=')
        self.assertEqual(children(nodes[3])[0].value, '01')
        self.assertEqual(nodes[4].value, 'no')

    def test_quotes_comments_and_inline_math(self):
        text = 'x = { text = "# { literal }" cost = @[base + 5 * 2] } # ignored { '
        node = parse(text)[0]
        self.assertEqual(len(children(node)), 2)
        self.assertEqual(children(node)[0].value, '"# { literal }"')
        self.assertEqual(children(node)[1].value, '@[base + 5 * 2]')
        self.assertEqual(text[node.start:node.end], text.split(' # ignored')[0])

    def test_malformed_asset_value_does_not_drop_other_fields(self):
        nodes = parse('a = { soundparameter = { "Tier" = } cost_gold = 5 }')
        self.assertEqual(children(children(nodes[0])[0])[0].prefix, 'missing_value_in_source')
        self.assertEqual(children(nodes[0])[1].value, '5')
        with self.assertRaises(ValueError):
            parse('x = { OR = { value = yes }')

    def test_script_value_caps_and_dynamic_price(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'common/script_values'
            path.mkdir(parents=True)
            (path / 'values.txt').write_text('@base = 200\nprice = @[base + 25 * 2]', encoding='utf-8')
            catalog = Catalog([Layer('test', root, 'Test', None, [])])
            source = catalog.sources[('test', 'common/script_values/values.txt')]
            self.assertEqual(catalog.evaluate('price', source), 250)
            self.assertEqual(catalog.evaluate(parse('x = { value = 15 max = 10 add = 5 }')[0].value, source), 15)
            self.assertEqual(catalog.evaluate(parse('x = { value = 15 min = 20 }')[0].value, source), 20)
            with self.assertRaises(ValueError):
                catalog.evaluate(parse('x = { if = { limit = { is_ai = yes } value = 5 } }')[0].value, source)

    def test_same_path_shadow_empty_file_and_replace_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('base', 'mod', 'replace'):
                (root / name / 'common/buildings').mkdir(parents=True)
            (root / 'base/common/buildings/a.txt').write_text('a = { cost_gold = 1 }', encoding='utf-8')
            (root / 'base/common/buildings/b.txt').write_text('b = { cost_gold = 2 }', encoding='utf-8')
            (root / 'mod/common/buildings/a.txt').write_text('# intentionally empty', encoding='utf-8')
            layers = [Layer('base', root / 'base', 'Base', None, []), Layer('mod', root / 'mod', 'Mod', None, [])]
            self.assertEqual(set(Catalog(layers).tables['buildings']), {'b'})
            layers.append(Layer('replace', root / 'replace', 'Replace', None, ['common/buildings']))
            self.assertEqual(Catalog(layers).tables['buildings'], {})


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogs = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((ROOT / 'data').glob('buildings-*.json'))]
        if not cls.catalogs:
            raise RuntimeError('Build catalogs before running integration checks')

    def test_requirement_ast_matches_preserved_script(self):
        for data in self.catalogs:
            for b in data['buildings'].values():
                for blocks in b['requirements'].values():
                    for block in blocks:
                        self.assertEqual(plain(block['syntax']), plain(parse(block['script'])[0]), b['id'])

    def test_all_linked_definitions_exist(self):
        for data in self.catalogs:
            def visit(value):
                if isinstance(value, dict):
                    for key, child in value.items():
                        if key in ('definition_refs', 'great_project_definition_refs'):
                            for ref in child:
                                self.assertIn(ref, data['definitions'], ref)
                        visit(child)
                elif isinstance(value, list):
                    for child in value:
                        visit(child)
            visit(data)

    def test_source_requirements_and_first_price_per_currency_are_exported(self):
        for data in self.catalogs:
            layers = {l['id']: Layer(l['id'], Path(l['path']), l['name'], l['version'], l['replace_paths']) for l in data['layers']}
            cache = {}
            for b in data['buildings'].values():
                loc = b['source']
                pair = (loc['layer'], loc['path'])
                if pair not in cache:
                    cache[pair] = Source.read(layers[loc['layer']], loc['path'])
                source = cache[pair]
                definition = next(n for n in source.nodes if n.key == b['id'] and n.line == loc['line'])
                for name, blocks in b['requirements'].items():
                    self.assertEqual([source.text[n.start:n.end] for n in fields(definition, name)], [x['script'] for x in blocks])
                price_fields = {}
                for field in children(definition):
                    if field.key.startswith('cost_'):
                        price_fields.setdefault(field.key.removeprefix('cost_'), field)
                    elif field.key == 'cost':
                        for entry in children(field) or [field]:
                            price_fields.setdefault(entry.key if entry is not field else None, entry)
                self.assertEqual([source.text[n.start:n.end] for n in price_fields.values()], [x['script'] for x in b['construction_cost']['entries']], b['id'])

    def test_reference_chains_and_actual_agot_prices(self):
        data = next(d for d in self.catalogs if d['catalog'] == 'agot')
        b = data['buildings']
        self.assertEqual([b[f'the_red_keep_0{i}']['construction_cost']['entries'][0]['base_value'] for i in range(1, 4)], [200, 725, 3335])
        self.assertEqual(b['castle_05']['upgrade']['chains'], [{'root': 'castle_01', 'level': 5}])
        self.assertEqual(b['castle_05']['construction_cost']['entries'][0]['base_value'], 5500)
        self.assertEqual(b['agot_great_fleet_01']['construction_cost']['status'], 'not_declared')
        self.assertIn('construct_great_fleet_01', b['agot_great_fleet_01']['great_projects_granting_this_building'])
        self.assertTrue(any(x['province'] == '4151' and x['field'] == 'special_building_slot' for x in b['the_red_keep_01']['history_assignments_exact_id']))
        for data in self.catalogs:
            for key, item in data['buildings'].items():
                next_id = item['upgrade']['next']
                if next_id:
                    self.assertIn(next_id, data['buildings'])
                    self.assertIn(key, data['buildings'][next_id]['upgrade']['previous'])

    def test_repeated_prices_keep_only_first_value(self):
        for data in self.catalogs:
            b = data['buildings']
            for key, value in [('agot_midges_inn_01', 200), ('agot_ormyan_palace_01', 200),
                               ('agot_brewery_grove_01', 1110), ('agot_rivermans_haunt_01', 1110)]:
                cost = b[key]['construction_cost']
                self.assertEqual([e['base_value'] for e in cost['entries']], [value])
                self.assertEqual(cost['repeated_currency_fields'], ['gold'])
                self.assertEqual(cost['resolved_base_cost']['gold'], value)
            for building in b.values():
                currencies = [e['currency'] for e in building['construction_cost']['entries']]
                self.assertEqual(len(currencies), len(set(currencies)), building['id'])
            self.assertEqual(b['agot_great_fleet_01']['construction_cost']['resolved_base_cost'], {})


if __name__ == '__main__':
    unittest.main()
