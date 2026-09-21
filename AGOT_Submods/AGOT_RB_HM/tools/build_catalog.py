"""Read-only extraction of CK3/AGOT holding buildings; Python standard library only.

The syntax tree is deliberately not a boolean evaluator: scopes, repeated keys,
conditional chains, metadata and parameterized calls retain their original order.
"""
from __future__ import annotations

import argparse
import ast
import bisect
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from decimal import Decimal
from datetime import date
import hashlib
import json
from pathlib import Path
import re


TOKEN = re.compile(r'\s+|\#[^\n]*|"(?:\\.|[^"\\])*"|@\[[^\]]*\]|\[\[[^\]]*\]|>=|<=|!=|\?=|==|[{}=<>\]]|[^\s{}=<>\]"#]+')
OPS = {'=', '?=', '==', '!=', '<', '>', '<=', '>='}
REQUIREMENTS = ('is_enabled', 'can_construct_potential',
                'can_construct_showing_failures_only', 'can_construct', 'can_rebuild')
FOLDERS = {
    'buildings': 'common/buildings', 'holdings': 'common/holdings',
    'scripted_trigger': 'common/scripted_triggers', 'script_value': 'common/script_values',
    'scripted_effect': 'common/scripted_effects',
    'great_project': 'common/great_projects/types',
}
READ_CACHE = {}
CATEGORIES = {
    'base': {'name': 'Базовые постройки', 'source_types': ['regular'], 'membership_role': 'primary_building'},
    'regular': {'name': 'Обычные здания', 'source_types': ['regular']},
    'duchy': {'name': 'Герцогские постройки', 'source_types': ['duchy_capital']},
    'special': {'name': 'Особые постройки', 'source_types': ['special']},
    'great': {'name': 'Великие постройки', 'source_types': ['great_building']},
}
CATEGORY_BY_TYPE = {kind: category for category, info in CATEGORIES.items() if category != 'base'
                    for kind in info['source_types']}
CATEGORY_SEMANTICS = ('base = primary_building and its upgrades from holding definitions (takes precedence); '
                      'regular = remaining regular buildings; duchy = duchy_capital; '
                      'special = special; great = great_building. Original engine type and '
                      'technical/availability flags are preserved.')


def building_category(building_type, memberships):
    if any(membership['role'] == 'primary_building' for membership in memberships):
        return 'base'
    return CATEGORY_BY_TYPE[building_type]


def category_index(buildings):
    return {category: {**info, 'building_ids': [key for key, b in buildings.items() if b['category'] == category]}
            for category, info in CATEGORIES.items()}


@dataclass
class Node:
    key: str
    op: str | None
    value: str | list[Node] | None
    start: int
    end: int
    line: int
    prefix: str | None = None


def parse(text: str) -> list[Node]:
    """Strict tokenization; no silently discarded characters or broken braces."""
    tokens = []
    end = 0
    lines = [-1] + [m.start() for m in re.finditer('\n', text)]
    for match in TOKEN.finditer(text):
        if match.start() != end:
            raise ValueError(f'Unrecognized script at offset {end}: {text[end:end+60]!r}')
        end = match.end()
        word = match.group()
        if not word.isspace() and not word.startswith('#'):
            tokens.append((word, match.start(), match.end()))
    if end != len(text):
        raise ValueError(f'Unrecognized script at offset {end}')
    index = 0

    def sequence(close=None):
        nonlocal index
        result = []
        while index < len(tokens):
            key, start, finish = tokens[index]
            if key == close:
                index += 1
                return result, finish
            if key in ('}', ']') or key in OPS:
                raise ValueError(f'Unexpected {key!r}, line {bisect.bisect_left(lines, start)}')
            index += 1
            op = None
            value = None
            prefix = None
            if key.startswith('[['):
                value, finish = sequence(']')
                prefix = 'optional_parameter'
            elif key == '{':
                value, finish = sequence('}')
                prefix = 'anonymous_block'
            elif index < len(tokens) and tokens[index][0] in OPS:
                op = tokens[index][0]
                index += 1
                if index == len(tokens):
                    raise ValueError(f'Missing value for {key}')
                word, _, finish = tokens[index]
                index += 1
                if word == '{':
                    value, finish = sequence('}')
                elif index < len(tokens) and tokens[index][0] == '{':
                    # rgb/hsv/LIST typed blocks must not change scope/order.
                    prefix = word
                    index += 1
                    value, finish = sequence('}')
                elif word in ('}', ']'):
                    # Preserve malformed source data explicitly without consuming
                    # its parent's closing brace (e.g. an empty asset sound Tier).
                    index -= 1
                    finish = tokens[index - 1][2]
                    prefix = 'missing_value_in_source'
                elif word in OPS:
                    raise ValueError(f'Invalid value for {key}, line {bisect.bisect_left(lines, start)}: {word}')
                else:
                    value = word
            result.append(Node(key, op, value, start, finish,
                               bisect.bisect_left(lines, start), prefix))
        if close:
            raise ValueError(f'Unclosed {close}')
        return result, len(text)

    return sequence()[0]


def unquote(value):
    return value[1:-1] if isinstance(value, str) and value.startswith('"') and value.endswith('"') else value


def children(node):
    return node.value if isinstance(node.value, list) else []


def fields(node, key):
    return [n for n in children(node) if n.key == key]


def scalar(node, key, default=None):
    found = fields(node, key)
    return unquote(found[-1].value) if found else default


def walk(nodes):
    for node in nodes:
        yield node
        yield from walk(children(node))


@dataclass
class Layer:
    id: str
    path: Path
    name: str
    version: str | None
    replace_paths: list[str]

    @classmethod
    def from_mod(cls, path, layer_id=None, descriptor=None):
        path = Path(path)
        descriptor = Path(descriptor) if descriptor else path / 'descriptor.mod'
        nodes = parse(descriptor.read_text(encoding='utf-8-sig')) if descriptor.exists() else []
        props = Node('descriptor', '=', nodes, 0, 0, 1)
        return cls(layer_id or path.name, path, scalar(props, 'name', path.name),
                   scalar(props, 'version'), [unquote(n.value).strip('/') for n in nodes if n.key == 'replace_path'])


@dataclass
class Source:
    layer: Layer
    relative: str
    path: Path
    text: str
    nodes: list[Node]
    digest: str

    @classmethod
    def read(cls, layer, relative):
        path = layer.path / relative
        if path not in READ_CACHE:
            data = path.read_bytes()
            text = data.decode('utf-8-sig').replace('\r\n', '\n')
            try:
                nodes = parse(text)
            except ValueError as exc:
                raise ValueError(f'{path}: {exc}') from exc
            READ_CACHE[path] = (text, nodes, hashlib.sha256(data).hexdigest())
        text, nodes, digest = READ_CACHE[path]
        return cls(layer, relative, path, text, nodes, digest)

    def location(self, node=None):
        return {'layer': self.layer.id, 'path': self.relative,
                **({'line': node.line} if node else {})}


class Catalog:
    def __init__(self, layers):
        self.layers = layers
        self.sources = {}
        self.file_overrides = []
        self.duplicates = []
        self.duplicate_candidates = defaultdict(list)
        self.tables = {}
        self.definitions = {}
        self.used = set()
        self.used_sources = set()
        self.unknown_calls = set()
        self.warnings = []
        for kind, directory in FOLDERS.items():
            table = {}
            # Different-file duplicate IDs: expose every candidate. The selected
            # projection is later mod, then later lexical path; never hide ambiguity.
            files = sorted(self.effective_files(directory).items(),
                           key=lambda pair: (self.layers.index(pair[1]), pair[0].casefold()))
            for relative, layer in files:
                source = self.read(layer, relative)
                for node in source.nodes:
                    if node.op != '=' or node.key.startswith('@'):
                        continue
                    if node.key in table:
                        previous, old_source = table[node.key]
                        if not self.duplicate_candidates[(kind, node.key)]:
                            self.duplicate_candidates[(kind, node.key)].append((previous, old_source))
                        self.duplicate_candidates[(kind, node.key)].append((node, source))
                        self.duplicates.append({'kind': kind, 'id': node.key,
                                                'previous': old_source.location(previous),
                                                'selected': source.location(node)})
                    table[node.key] = (node, source)
            self.tables[kind] = table
        for kind in ('scripted_trigger', 'script_value', 'scripted_effect', 'great_project'):
            for key, pair in self.tables[kind].items():
                self.definitions[f'{kind}:{key}'] = pair
        for source in self.sources.values():
            for node in source.nodes:
                if node.key.startswith('@') and node.op == '=':
                    self.definitions[self.macro_id(node.key, source)] = (node, source)

    def effective_files(self, directory, suffix='.txt'):
        effective = {}
        for layer in self.layers:
            for replace in layer.replace_paths:
                for key in list(effective):
                    if key == replace or key.startswith(replace + '/'):
                        self.file_overrides.append({'path': key, 'removed_by_replace_path': layer.id,
                                                    'previous_layer': effective[key].id})
                        del effective[key]
            root = layer.path / directory
            if not root.is_dir():
                continue
            for path in sorted(root.rglob('*' + suffix)):
                relative = path.relative_to(layer.path).as_posix()
                if relative in effective:
                    self.file_overrides.append({'path': relative, 'selected_layer': layer.id,
                                                'previous_layer': effective[relative].id})
                effective[relative] = layer
        return effective

    def read(self, layer, relative):
        key = (layer.id, relative)
        if key not in self.sources:
            self.sources[key] = Source.read(layer, relative)
        return self.sources[key]

    @staticmethod
    def macro_id(key, source):
        return f'macro:{source.layer.id}:{source.relative}:{key}'

    def references(self, node, source):
        refs = set()
        for kind in ('scripted_trigger', 'scripted_effect'):
            ref = f'{kind}:{unquote(node.key)}'
            if ref in self.definitions:
                refs.add(ref)
        if (node.key.endswith('_trigger') or node.key.startswith('building_requirement_')) and not refs and node.key != 'ai_target_quick_trigger':
            self.unknown_calls.add(node.key)
        values = [node.key] if node.value is None else ([node.value] if isinstance(node.value, str) else [])
        for value in values:
            value = unquote(value)
            for kind in ('script_value', 'great_project'):
                ref = f'{kind}:{value}'
                if ref in self.definitions:
                    refs.add(ref)
            if value.startswith('@['):
                for name in re.findall(r'[A-Za-z_][A-Za-z_0-9]*', value[2:-1]):
                    ref = self.macro_id('@' + name, source)
                    if ref in self.definitions:
                        refs.add(ref)
            elif value.startswith('@'):
                ref = self.macro_id(value, source)
                if ref in self.definitions:
                    refs.add(ref)
        self.used.update(refs)
        return sorted(refs)

    def tree(self, nodes, source):
        result = []
        for node in nodes:
            data = {'key': node.key, 'operator': node.op}
            if isinstance(node.value, list):
                data['children'] = self.tree(node.value, source)
            else:
                data['value'] = node.value
            if node.prefix:
                data['prefix'] = node.prefix
            refs = self.references(node, source)
            if refs:
                data['definition_refs'] = refs
            result.append(data)
        return result

    def snippet(self, node, source):
        self.used_sources.add((source.layer.id, source.relative))
        return {'source': source.location(node),
                'script': source.text[node.start:node.end],
                'syntax': self.tree([node], source)[0]}

    def evaluate(self, value, source, stack=()):
        """Only resolve provably constant arithmetic. Conditional formulas stay dynamic."""
        if isinstance(value, list):
            current = Decimal(0)
            for node in value:
                if node.op != '=' or node.key not in ('value', 'add', 'subtract', 'multiply', 'divide', 'min', 'max'):
                    raise ValueError(f'context_or_unsupported_operation:{node.key}')
                rhs = self.evaluate(node.value, source, stack)
                if node.key == 'value': current = rhs
                elif node.key == 'add': current += rhs
                elif node.key == 'subtract': current -= rhs
                elif node.key == 'multiply': current *= rhs
                elif node.key == 'divide': current /= rhs
                elif node.key == 'min': current = max(current, rhs)  # lower bound
                elif node.key == 'max': current = min(current, rhs)  # upper bound
            return current
        value = unquote(value)
        if value is None:
            raise ValueError('missing_value_in_source')
        if re.fullmatch(r'-?\d+(?:\.\d+)?', value):
            return Decimal(value)
        if value.startswith('@['):
            expression = ast.parse(value[2:-1].strip(), mode='eval').body
            def arithmetic(term):
                if isinstance(term, ast.Constant) and isinstance(term.value, (int, float)):
                    return Decimal(str(term.value))
                if isinstance(term, ast.Name):
                    return self.evaluate('@' + term.id, source, stack)
                if isinstance(term, ast.UnaryOp) and isinstance(term.op, (ast.USub, ast.UAdd)):
                    return (-1 if isinstance(term.op, ast.USub) else 1) * arithmetic(term.operand)
                if isinstance(term, ast.BinOp):
                    a, b = arithmetic(term.left), arithmetic(term.right)
                    if isinstance(term.op, ast.Add): return a + b
                    if isinstance(term.op, ast.Sub): return a - b
                    if isinstance(term.op, ast.Mult): return a * b
                    if isinstance(term.op, ast.Div): return a / b
                raise ValueError('unsupported_inline_math')
            return arithmetic(expression)
        ref = self.macro_id(value, source) if value.startswith('@') else f'script_value:{value}'
        if ref in stack:
            raise ValueError(f'reference_cycle:{ref}')
        if ref not in self.definitions:
            raise ValueError(f'context_or_unknown_value:{value}')
        self.used.add(ref)
        node, definition_source = self.definitions[ref]
        return self.evaluate(node.value, definition_source, (*stack, ref))

    def quantity(self, node, source):
        result = self.snippet(node, source)
        try:
            number = self.evaluate(node.value, source)
            result.update(status='constant', base_value=int(number) if number == int(number) else float(number))
        except (ValueError, SyntaxError, ArithmeticError) as exc:
            result.update(status='requires_context_or_review', base_value=None, reason=str(exc))
        return result

    def cost(self, node, source):
        price_fields = []
        for field in children(node):
            if field.key.startswith('cost_'):
                price_fields.append((field.key.removeprefix('cost_'), field))
            elif field.key == 'cost':
                if isinstance(field.value, list):
                    price_fields.extend((f.key, f) for f in field.value)
                else:
                    price_fields.append((None, field))
        entries = []
        resolved = {}
        repeated = []
        for currency, field in price_fields:
            if currency in resolved:
                if currency not in repeated:
                    repeated.append(currency)
                continue
            # User's catalog policy: retain only the first price per currency.
            entry = {'currency': currency, **self.quantity(field, source)}
            entries.append(entry)
            resolved[currency] = entry['base_value']
        return {'status': 'declared' if entries else 'not_declared',
                'resolved_base_cost': resolved, 'repeated_currency_fields': repeated,
                'entries': entries}

    def names(self, extra_layers=()):
        """Names are a convenience only; localization never alters building data."""
        wanted = {'building_' + key for key in self.tables['buildings']}
        result = {}
        # Load aliases too (building_type_X, $OTHER_KEY$), resolve only plain aliases.
        patterns = re.compile(r'^\s*([^\s:#]+):\d*\s+"(.*)"\s*(?:#.*)?$')
        for language in ('english', 'russian'):
            all_names = {}
            for layer in [*self.layers, *extra_layers]:
                root = layer.path / 'localization'
                paths = list(root.rglob(f'*_l_{language}.yml')) if root.exists() else []
                for path in sorted(paths, key=lambda p: ('replace' in p.parts, p.as_posix())):
                    for line, text in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
                        match = patterns.match(text)
                        if match:
                            all_names[match[1]] = (match[2], {'layer': layer.id,
                                'path': path.relative_to(layer.path).as_posix(), 'line': line})
            def resolve(key, stack=()):
                if key in stack or key not in all_names:
                    return '$' + key + '$'
                value, _ = all_names[key]
                return re.sub(r'\$([A-Za-z_0-9.]+)\$', lambda m: resolve(m[1], (*stack, key)), value)
            for key in wanted & all_names.keys():
                result.setdefault(key, {})[language] = {'text': resolve(key), 'source': all_names[key][1]}
        return result

    def history_slots(self):
        assignments = defaultdict(list)
        keys = {'special_building_slot', 'special_building', 'duchy_capital_building', 'great_building'}
        for relative, layer in sorted(self.effective_files('history/provinces').items()):
            source = self.read(layer, relative)
            for province in source.nodes:
                def visit(nodes, path=()):
                    for node in nodes:
                        if node.key in keys and isinstance(node.value, str):
                            assignments[unquote(node.value)].append({'province': province.key,
                                'history_path': list(path), 'field': node.key, 'source': source.location(node)})
                        elif isinstance(node.value, list):
                            visit(node.value, (*path, node.key))
                visit(children(province))
        return assignments

    def export(self, label, names_layers=()):
        table = self.tables['buildings']
        names = self.names(names_layers)
        slots = self.history_slots()
        incoming = defaultdict(list)
        next_ids = {}
        for key, (node, _) in table.items():
            following = scalar(node, 'next_building')
            next_ids[key] = following
            if following:
                incoming[following].append(key)
                if following not in table:
                    self.warnings.append({'kind': 'missing_next_building', 'id': key, 'target': following})

        def chain_paths(key, stack=()):
            if key in stack:
                raise ValueError('Upgrade cycle: ' + ' -> '.join((*stack, key)))
            if not incoming[key]:
                return [(key, 1)]
            return sorted(set((root, level + 1) for before in incoming[key]
                              for root, level in chain_paths(before, (*stack, key))))

        holding_memberships = defaultdict(list)
        holdings = {}
        for key, (node, source) in sorted(self.tables['holdings'].items()):
            holdings[key] = self.snippet(node, source)
            entries = [('primary_building', scalar(node, 'primary_building'))]
            entries += [('buildings', unquote(entry.key)) for field in fields(node, 'buildings') for entry in children(field)]
            for role, first in entries:
                if not first:
                    continue
                if first not in table:
                    self.warnings.append({'kind': 'missing_holding_building', 'holding': key, 'target': first})
                    continue
                seen = set()
                current = first
                while current in table and current not in seen:
                    seen.add(current)
                    holding_memberships[current].append({'holding': key, 'role': role,
                        'listed_building': first, 'source': source.location(node)})
                    current = next_ids[current]

        # Projects that actually grant a building can differ from its UI upgrade
        # pointer (e.g. fleet tier 1 is granted by project 01, not free construction).
        projects_granting = defaultdict(list)
        for project, (definition, _) in self.tables['great_project'].items():
            for node in walk(children(definition)):
                if node.key in ('add_building', 'add_great_building', 'add_special_building') and isinstance(node.value, str):
                    projects_granting[unquote(node.value)].append(project)

        buildings = {}
        for key, (node, source) in sorted(table.items()):
            paths = chain_paths(key)
            roots = sorted({root for root, _ in paths})
            requirements = {name: [self.snippet(n, source) for n in fields(node, name)] for name in REQUIREMENTS}
            suffix = re.search(r'_(\d+)$', key)
            project_ids = sorted(set(projects_granting[key]))
            project_pointer = scalar(node, 'great_project_type')
            if project_pointer:
                project_ids = sorted(set([*project_ids, project_pointer]))
            for project in project_ids:
                ref = 'great_project:' + project
                if ref in self.definitions:
                    self.used.add(ref)
                else:
                    self.warnings.append({'kind': 'missing_great_project', 'id': key, 'target': project})
            graphical = scalar(node, 'is_graphical_background', 'no') == 'yes'
            always_hidden = any(n.key == 'always' and n.value == 'no'
                                for block in fields(node, 'can_construct_potential') for n in children(block))
            building_type = scalar(node, 'type', 'regular')
            data = {
                'id': key, 'name_key': 'building_' + key, 'names': names.get('building_' + key, {}),
                'source': source.location(node),
                'type': building_type,
                'category': building_category(building_type, holding_memberships[key]),
                'is_graphical_background': graphical,
                'explicit_potential_always_no': always_hidden,
                'show_disabled': scalar(node, 'show_disabled', 'no'),
                'upgrade': {'previous': sorted(incoming[key]), 'next': next_ids[key],
                            'chains': [{'root': r, 'level': level} for r, level in paths],
                            'id_numeric_suffix': int(suffix[1]) if suffix else None},
                'holding_memberships': holding_memberships[key],
                'requirements': requirements,
                'construction_cost': self.cost(node, source),
                'construction_time_days': [self.quantity(n, source) for n in fields(node, 'construction_time')],
                'rebuild_cost': [{**self.snippet(n, source),
                                 'entries': [{'currency': entry.key, **self.quantity(entry, source)} for entry in children(n)]}
                                for n in fields(node, 'rebuild_cost')],
                'great_project_upgrade_pointer': project_pointer,
                'great_projects_granting_this_building': sorted(set(projects_granting[key])),
                'great_project_definition_refs': ['great_project:' + p for p in project_ids],
                'history_assignments_exact_id': slots.get(key, []),
                'history_assignments_chain_roots': {r: slots[r] for r in roots if r in slots},
                'flags': [unquote(n.value) for n in fields(node, 'flag')],
                'construction_callbacks': {k: [self.snippet(n, source) for n in fields(node, k)]
                                           for k in ('on_start', 'on_cancelled', 'on_complete')},
            }
            buildings[key] = data
            self.used_sources.add((source.layer.id, source.relative))

        # Close all references, including local @ macros, without unrolling cycles
        # or erasing parameter arguments/negative scripted-trigger calls.
        definitions = {}
        duplicate_candidates = {}
        for (kind, key), candidates in self.duplicate_candidates.items():
            if kind in ('buildings', 'holdings'):
                duplicate_candidates[f'{kind}:{key}'] = [self.snippet(n, s) for n, s in candidates]
                if kind == 'buildings':
                    buildings[key]['definition_selection_status'] = 'provisional_duplicate_id'
        while self.used - definitions.keys():
            for ref in sorted(self.used - definitions.keys()):
                node, source = self.definitions[ref]
                definitions[ref] = self.snippet(node, source)
                definitions[ref]['parameters'] = sorted(set(re.findall(r'\$([^$\s]+)\$', source.text[node.start:node.end])))
                kind, _, key = ref.partition(':')
                if (kind, key) in self.duplicate_candidates:
                    duplicate_candidates[ref] = [self.snippet(n, s) for n, s in self.duplicate_candidates[(kind, key)]]

        relevant_duplicates = [d for d in self.duplicates if d['kind'] in ('buildings', 'holdings')
                               or d['kind'] + ':' + d['id'] in definitions]
        for source in self.sources.values():
            if (source.layer.id, source.relative) in self.used_sources:
                for n in walk(source.nodes):
                    if n.prefix == 'missing_value_in_source':
                        self.warnings.append({'kind': 'missing_value_in_source', 'source': source.location(n), 'key': n.key})
        entries = [e for b in buildings.values() for e in b['construction_cost']['entries']]
        manifest = [{'layer': s.layer.id, 'path': s.relative, 'sha256': s.digest}
                    for s in sorted(self.sources.values(), key=lambda s: (s.layer.id, s.relative))]
        categories = category_index(buildings)
        return {
            'schema_version': 1, 'catalog': label, 'generated_date': date.today().isoformat(),
            'scope': 'Effective common/buildings (not domicile buildings), all definitions including hidden/inherited ones',
            'layers': [{'id': l.id, 'name': l.name, 'version': l.version, 'path': l.path.as_posix(),
                        'replace_paths': l.replace_paths} for l in self.layers],
            'extra_name_layers': [{'id': l.id, 'name': l.name, 'path': l.path.as_posix()} for l in names_layers],
            'semantics': {
                'categories': CATEGORY_SEMANTICS,
                'syntax': 'Ordered script AST, not a simplified boolean formula. Repeated keys and all operators are retained.',
                'absent_requirement': 'Empty array means no explicit block in this definition; engine/slot constraints still apply.',
                'scopes': {'root': 'province', 'scope:holder': 'barony holder', 'scope:county': 'county title'},
                'construction': 'is_enabled AND all three can_construct* blocks (see CK3 common/buildings/_buildings.info).',
                'conditions': 'Preserve implicit AND, OR/AND/NOT/NOR/NAND, conditional order, iterators, tooltips and optional ?= scopes.',
                'calls': 'definition_refs link to definitions; call arguments such as LEVEL=01 and inversion (=no) stay on the call node.',
                'prices': 'Base script values only, before live character/province cost modifiers. Missing cost is not asserted to be free.',
                'repeated_prices': 'User-selected catalog policy: keep only the first declaration per currency, including in entries and resolved_base_cost. repeated_currency_fields lists currencies with discarded later declarations; this is not a claim about engine precedence.',
                'levels': 'Count next_building edges from chain root starting at 1; id_numeric_suffix is separate and is not a tier guarantee.',
                'holdings': 'Membership follows the listed building and its upgrades; it does not bypass scripted requirements.',
                'history': 'Raw dated assignments, not a whitelist of constructible provinces. Runtime scripts can change slots.',
                'great_projects': 'Upgrade pointer and project grant are separate. Project costs/conditions are in linked definitions.',
                'duplicates': 'Cross-file duplicate winners use mod order then lexical path as a provisional projection; candidates are reported.',
                'limits': 'No live-save evaluator or engine affordability/slot/DLC/government simulator. Native predicates remain native.',
            },
            'summary': {
                'buildings_and_levels': len(buildings),
                'chain_roots': sum(not b['upgrade']['previous'] for b in buildings.values()),
                'by_category': {category: len(info['building_ids']) for category, info in categories.items()},
                'by_type': dict(sorted(Counter(b['type'] for b in buildings.values()).items())),
                'by_source_layer': dict(sorted(Counter(b['source']['layer'] for b in buildings.values()).items())),
                'graphical_background': sum(b['is_graphical_background'] for b in buildings.values()),
                'potential_always_no': sum(b['explicit_potential_always_no'] for b in buildings.values()),
                'buildings_with_declared_construction_cost': sum(b['construction_cost']['status'] == 'declared' for b in buildings.values()),
                'construction_currency_entries': len(entries),
                'constant_construction_currency_entries': sum(e['status'] == 'constant' for e in entries),
                'buildings_without_declared_construction_cost': sum(b['construction_cost']['status'] == 'not_declared' for b in buildings.values()),
                'buildings_with_repeated_cost_fields': [key for key, b in buildings.items() if b['construction_cost']['repeated_currency_fields']],
                'holdings': len(holdings), 'linked_definitions': len(definitions),
                'relevant_duplicate_definitions': len(relevant_duplicates),
            },
            'categories': categories,
            'buildings': buildings, 'holdings': holdings, 'definitions': dict(sorted(definitions.items())),
            'diagnostics': {'warnings': self.warnings, 'unknown_trigger_like_calls': sorted(self.unknown_calls),
                            'duplicate_definitions': relevant_duplicates, 'duplicate_candidates': duplicate_candidates,
                            'file_overrides': self.file_overrides},
            'source_files': manifest,
        }


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def playset_layers(profile, game_layer, agot_path):
    layers = [game_layer]
    for descriptor in json.loads((profile / 'dlc_load.json').read_text(encoding='utf-8-sig'))['enabled_mods']:
        path = profile / descriptor
        definition = Node('descriptor', '=', parse(path.read_text(encoding='utf-8-sig')), 0, 0, 1)
        root = scalar(definition, 'path')
        if not root:
            raise ValueError(f'No local path in enabled mod descriptor: {path}')
        root = Path(root)
        if not root.is_dir():
            raise ValueError(f'Missing enabled mod directory: {root}')
        layer_id = 'agot' if root.resolve() == agot_path.resolve() else path.stem
        layers.append(Layer.from_mod(root, layer_id, path))
    if not any(l.id == 'agot' for l in layers):
        raise ValueError('The active playset does not include the specified AGOT source')
    return layers


def catalog_difference(base, active):
    left, right = base['buildings'], active['buildings']
    def mechanical(value):
        if isinstance(value, dict):
            return {k: mechanical(v) for k, v in value.items()
                    if k not in ('source', 'script', 'names', 'definition_refs', 'parameters')}
        if isinstance(value, list):
            return [mechanical(v) for v in value]
        return value
    changed = []
    relevant = ('type', 'category', 'is_graphical_background', 'upgrade', 'holding_memberships', 'requirements',
                'construction_cost', 'construction_time_days', 'rebuild_cost',
                'great_project_upgrade_pointer', 'great_projects_granting_this_building',
                'flags', 'construction_callbacks', 'history_assignments_exact_id', 'history_assignments_chain_roots')
    for key in sorted(left.keys() & right.keys()):
        differences = [field for field in relevant if mechanical(left[key][field]) != mechanical(right[key][field])]
        if differences:
            changed.append({'id': key, 'fields': differences, 'base_source': left[key]['source'],
                            'playset_source': right[key]['source']})
    defs_left, defs_right = base['definitions'], active['definitions']
    dependency_changes = [key for key in sorted(defs_left.keys() & defs_right.keys())
                          if mechanical(defs_left[key]['syntax']) != mechanical(defs_right[key]['syntax'])]
    return {'base': base['catalog'], 'comparison': active['catalog'],
            'note': 'Definition/price/condition/history changes, not visual assets or localization. Shared dependency changes are listed separately.',
            'added_buildings': sorted(right.keys() - left.keys()), 'removed_buildings': sorted(left.keys() - right.keys()),
            'changed_buildings': changed, 'changed_shared_definitions': dependency_changes}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--game', type=Path, required=True)
    parser.add_argument('--agot', type=Path, required=True)
    parser.add_argument('--profile', type=Path)
    parser.add_argument('--names-mod', action='append', type=Path, default=[])
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'data')
    args = parser.parse_args()
    layers = [Layer('ck3', args.game, 'Crusader Kings III', None, []), Layer.from_mod(args.agot, 'agot')]
    catalog = Catalog(layers)
    data = catalog.export('agot', [Layer.from_mod(p, 'names_' + p.name) for p in args.names_mod])
    dump(args.output / 'buildings-agot.json', data)
    print(json.dumps(data['summary'], indent=2))
    summaries = {'agot': data['summary']}
    if args.profile:
        active = Catalog(playset_layers(args.profile, layers[0], args.agot))
        active_data = active.export('active-playset')
        dump(args.output / 'buildings-playset.json', active_data)
        dump(args.output / 'playset-difference.json', catalog_difference(data, active_data))
        print(json.dumps(active_data['summary'], indent=2))
        summaries['active-playset'] = active_data['summary']
    dump(args.output / 'summary.json', summaries)


if __name__ == '__main__':
    main()
