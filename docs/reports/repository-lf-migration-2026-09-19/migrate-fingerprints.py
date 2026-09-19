"""Re-pin only repository artifacts whose pre-migration bytes were recorded.

External source fingerprints are deliberately excluded. JSON is patched at
individual value spans, preserving layout, strings containing recipes and BOM.
"""
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
import zipfile

ROOT = Path.cwd()
CACHE = ROOT / '.git/lf-migration-2026-09-19'
inventory = json.loads((CACHE / 'inventory.json').read_text(encoding='utf-8'))
by_hash = defaultdict(list)
for row in inventory:
    by_hash[row['SHA256']].append(row['File'])


def native(path):
    return Path('\\\\?\\' + str(path))


def sha(path):
    return hashlib.sha256(native(path).read_bytes()).hexdigest().upper()


def slots(text):
    decoder = json.JSONDecoder()
    found = []
    def white(i):
        while i < len(text) and text[i].isspace():
            i += 1
        return i
    def value(i, parent=None, key=None, trail=()):
        i = white(i)
        if text[i] == '{':
            obj = {}
            i = white(i + 1)
            while text[i] != '}':
                name, i = decoder.raw_decode(text, i)
                i = white(i)
                assert text[i] == ':'
                obj[name], i = value(i + 1, obj, name, trail + (name,))
                i = white(i)
                if text[i] == ',':
                    i = white(i + 1)
                else:
                    assert text[i] == '}'
            return obj, i + 1
        if text[i] == '[':
            arr = []
            i = white(i + 1)
            while text[i] != ']':
                item, i = value(i, arr, len(arr), trail + (len(arr),))
                arr.append(item)
                i = white(i)
                if text[i] == ',':
                    i = white(i + 1)
                else:
                    assert text[i] == ']'
            return arr, i + 1
        item, end = decoder.raw_decode(text, i)
        if isinstance(item, str) and re.fullmatch('[0-9a-fA-F]{64}', item):
            found.append((i, end, item, parent, key, trail))
        return item, end
    value(0)
    return found


def csv_slots(text):
    rows, row, i = [], [], 0
    while i < len(text):
        start = i
        if text[i] == '"':
            i += 1
            while i < len(text):
                if text[i] == '"':
                    i += 1
                    if i < len(text) and text[i] == '"':
                        i += 1
                        continue
                    break
                i += 1
            token = text[start:i]
            item = token[1:-1].replace('""', '"')
        else:
            while i < len(text) and text[i] not in ',\n':
                i += 1
            item = text[start:i]
        row.append((item, start, i))
        if i == len(text) or text[i] == '\n':
            rows.append(row)
            row = []
        elif text[i] != ',':
            raise ValueError('Unexpected CSV delimiter')
        i += 1
    if not rows:
        return []
    headers = [x[0] for x in rows[0]]
    result = []
    for number, cells in enumerate(rows[1:]):
        if len(cells) != len(headers):
            raise ValueError('CSV column count differs')
        context = dict(zip(headers, [x[0] for x in cells]))
        for key, (item, start, end) in zip(headers, cells):
            if re.fullmatch('[0-9a-fA-F]{64}', item):
                result.append((start, end, item, context, key, (number, key)))
    return result


def local(path):
    return str(path).lower().replace('/', '\\').startswith(str(ROOT).lower() + '\\')


def external(path):
    return isinstance(path, str) and bool(re.match(r'^[A-Za-z]:[\\/]', path)) and not local(path)


def target_for(owner, digest, parent, key, trail):
    candidates = by_hash.get(digest.upper(), [])
    if not candidates:
        return None
    key = str(key)
    context = parent if isinstance(parent, dict) else {}
    if context.get('Mod') and not local(context.get('Path', '')):
        if not (ROOT/'AGOT_Submods'/context['Mod']).is_dir():
            return None
    if context.get('Catalog') and key.lower() == 'expectedsha256':
        return None
    if external(key):
        return None
    hints = []
    if local(key):
        hints.append(key)
    if key.lower() in ('sourcesha256', 'mainsha256', 'translationsha256', 'meshsha256'):
        specific = {'sourcesha256': ('Source', 'SourcePath'), 'meshsha256': ('CurrentMesh',),
                    'mainsha256': ('MainFile',), 'translationsha256': ('TranslationFile',)}[key.lower()]
        hints += [context[k] for k in specific if isinstance(context.get(k), str)]
        if not any(local(p) for p in hints):
            return None
    elif key.lower() in ('sha256', 'hash'):
        primary = context.get('Path', context.get('File'))
        if external(primary):
            return None
        if context.get('Catalog') and not local(primary):
            return None
        hints += [p for p in (primary, context.get('Snapshot'), context.get('Destination')) if isinstance(p, str)]
    else:
        prefix = re.sub(r'(?i)(sha256|hash)$', '', key)
        hints += [context[k] for k in (prefix, prefix+'File', prefix+'Path') if isinstance(context.get(k), str)]
    for hint in hints:
        normalized = hint.replace('\\', '/')
        for candidate in candidates:
            if normalized.lower() == str(ROOT/candidate).replace('\\', '/').lower():
                return candidate
            if not re.match(r'^[A-Za-z]:', normalized):
                for base in (Path(owner).parent, Path(owner).parent.parent, Path('.')):
                    if (base/normalized).as_posix().lower() == candidate.lower():
                        return candidate
        if not re.match(r'^[A-Za-z]:', normalized):
            suffixes = [p for p in candidates if p.lower().endswith('/' + normalized.lower())]
            if len(suffixes) == 1:
                return suffixes[0]
    hashes = {sha(ROOT/p) for p in candidates}
    if len(hashes) == 1:
        return candidates[0]
    # Identical snapshots may diverge when a live validator is regenerated.
    # Prefer the reference's own report/package before a global equivalent.
    for base in (Path(owner).parent, Path(owner).parent.parent):
        nearby = [p for p in candidates if Path(p).is_relative_to(base)]
        if nearby and len({sha(ROOT/p) for p in nearby}) == 1:
            return nearby[0]
    # The copies are visited at different points in a dependency pass. Prefer
    # the package copy while their identical metadata propagates; convergence
    # and the package's independent source checks validate the final graph.
    return candidates[0]


def main():
    originals = {}
    with zipfile.ZipFile(CACHE/'original-text.zip') as archive:
        for rel in archive.namelist():
            if rel.endswith(('.json', '.csv')):
                raw = archive.read(rel).replace(b'\r\n', b'\n').replace(b'\r', b'\n')
                try:
                    text = raw.decode('utf-8-sig')
                    items = slots(text) if rel.endswith('.json') else csv_slots(text)
                except (ValueError, UnicodeError):
                    continue
                originals[rel] = (b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'', text, items)
    for turn in range(15):
        updated = 0
        records = []
        for rel, (bom, text, items) in originals.items():
            edits = []
            for start, end, digest, parent, key, trail in items:
                target = target_for(rel, digest, parent, key, trail)
                if not target:
                    continue
                replacement = sha(ROOT/target)
                if replacement == digest.upper():
                    continue
                if digest == digest.lower():
                    replacement = replacement.lower()
                rendered = json.dumps(replacement) if text[start] == '"' else replacement
                edits.append((start, end, rendered))
                records.append(dict(File=rel, Field=list(trail), Target=target, Before=digest, After=replacement))
            result = text
            for start, end, replacement in reversed(edits):
                result = result[:start] + replacement + result[end:]
            data = bom + result.encode('utf-8')
            p = native(ROOT/rel)
            if p.read_bytes() != data:
                p.write_bytes(data)
                updated += 1
        print('Re-pin pass', turn + 1, 'updated', updated, 'metadata files;',len(records),'references',flush=True)
        if not updated:
            (CACHE/'repinned-references.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8',newline='\n')
            return
    raise RuntimeError('Fingerprint graph did not converge')


if __name__ == '__main__':
    main()
