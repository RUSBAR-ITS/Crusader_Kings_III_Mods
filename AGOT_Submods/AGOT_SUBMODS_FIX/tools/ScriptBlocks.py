"""Small CK3 text reader: block boundaries and direct assignments, no evaluation."""
from dataclasses import dataclass
import re

TOKEN = re.compile(r'#[^\n]*|"(?:\\.|[^"\\])*"|[{}]|\?=|!=|>=|<=|[=<>]|[^\s{}=<>!#"]+')


@dataclass
class Node:
    key: str
    op: str
    value: str | list
    start: int
    end: int
    opening: int = -1
    closing: int = -1

    def children(self, key):
        return [n for n in self.value if n.key == key] if isinstance(self.value, list) else []

    def one(self, key):
        found = self.children(key)
        assert len(found) == 1, (self.key, key, len(found))
        return found[0]


def parse(text):
    tokens = [(m[0], m.start(), m.end()) for m in TOKEN.finditer(text) if not m[0].startswith('#')]
    index = 0

    def sequence(nested=False):
        nonlocal index
        out = []
        while index < len(tokens):
            key, start, end = tokens[index]
            if key == '}':
                assert nested, ('Unexpected closing brace', start)
                return out
            if key == '{':
                # Anonymous blocks occur in exported bookmark portrait tags.
                index += 1
                value = sequence(True)
                assert index < len(tokens) and tokens[index][0] == '}', 'Unclosed anonymous block'
                closing, end = tokens[index][1:]
                index += 1
                out.append(Node('', '', value, start, end, start, closing))
                continue
            index += 1
            op = ''
            value = key
            opening = closing = -1
            if index < len(tokens) and tokens[index][0] in ('=', '?=', '!=', '>=', '<=', '>', '<'):
                op = tokens[index][0]
                index += 1
                assert index < len(tokens), ('Missing value', key)
                val, a, b = tokens[index]
                if val == '{':
                    opening = a
                    index += 1
                    value = sequence(True)
                    assert index < len(tokens) and tokens[index][0] == '}', key
                    closing, end = tokens[index][1:]
                    index += 1
                else:
                    value, end = val, b
                    index += 1
            out.append(Node(key, op, value, start, end, opening, closing))
        assert not nested, 'Unclosed block'
        return out

    return sequence()


def one(text, key):
    found = [n for n in parse(text) if n.key == key]
    assert len(found) == 1, (key, len(found))
    return found[0]


def semantic(node):
    return (node.key, node.op, [semantic(n) for n in node.value] if isinstance(node.value, list) else node.value)


def walk(nodes):
    for n in nodes:
        yield n
        if isinstance(n.value, list):
            yield from walk(n.value)


def edit(text, changes):
    last = len(text) + 1
    for start, end, replacement in sorted(changes, reverse=True):
        assert 0 <= start <= end < last, ('Overlapping edits', start, end, last)
        text = text[:start] + replacement + text[end:]
        last = start
    return text


def comment(text, explanation):
    return '# USF: ' + explanation + '\n' + '\n'.join('# ' + s for s in text.splitlines())
