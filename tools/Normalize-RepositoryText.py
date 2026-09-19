"""Check or normalize repository text to LF without changing encoding/BOM.

Only tracked and non-ignored files are included. Workshop installations, the
game profile, ignored vendor directories and .git are outside this operation.
"""
import argparse
from collections import Counter
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BINARY = {'.dds', '.mesh', '.anim', '.png', '.jpg', '.jpeg', '.gif', '.ico',
          '.zip', '.7z', '.pdf', '.pyc'}
TEXT = {'.txt', '.log', '.md', '.json', '.csv', '.tsv', '.yml', '.yaml',
        '.py', '.ps1', '.psm1', '.mod', '.asset', '.gui', '.gfx', '.shader',
        '.fxh', '.xml', '.html', '.css', '.js', '.patch', '.diff', '.toml',
        '.ini', '.cfg', '.gitignore', '.gitattributes', '.editorconfig'}


def native(path):
    path = Path(path).absolute()
    return Path('\\\\?\\' + str(path)) if path.drive else path


def files():
    raw = subprocess.check_output(
        ['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT)
    return sorted({p.decode('utf-8') for p in raw.split(b'\0') if p})


def normalized(path, data):
    """Return LF bytes for text, None for binary. Never reinterpret encoding."""
    if Path(path).suffix.lower() in BINARY:
        return None
    for bom, codec in ((b'\xff\xfe', 'utf-16-le'), (b'\xfe\xff', 'utf-16-be')):
        if data.startswith(bom):
            text = data[len(bom):].decode(codec)
            return bom + text.replace('\r\n', '\n').replace('\r', '\n').encode(codec)
    if b'\0' in data:
        return None
    if Path(path).suffix.lower() not in TEXT and Path(path).name not in TEXT:
        try:
            data.decode('utf-8-sig')
        except UnicodeError:
            return None
    # Byte replacement also preserves imperfect historical log encodings.
    return data.replace(b'\r\n', b'\n').replace(b'\r', b'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='normalize in place; otherwise check only')
    args = parser.parse_args()
    counts = Counter()
    changed = []
    for rel in files():
        path = native(ROOT / rel)
        before = path.read_bytes()
        after = normalized(rel, before)
        counts['binary' if after is None else 'text'] += 1
        if after is not None and after != before:
            changed.append(rel)
            if args.write:
                path.write_bytes(after)
    print(f"Text: {counts['text']}; binary: {counts['binary']}; "
          f"{'normalized' if args.write else 'non-LF'}: {len(changed)}")
    if changed and not args.write:
        for rel in changed[:30]:
            print(rel)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
