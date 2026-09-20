"""Read-only audit of installed Fire and Blood and its Russian translation.

Writes reports beside this script; never changes game files or the playset.
Candidates are not automatically classified as translation errors.
"""
from pathlib import Path
from collections import defaultdict, Counter
import csv
import hashlib
import json
import re
import sys
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(__file__).resolve().parent
WORKSHOP = Path("E:/SteamLibrary/steamapps/workshop/content/1158310")
MAIN = WORKSHOP / "3765282284"
RU = WORKSHOP / "3766951310"
GAME = Path("E:/SteamLibrary/steamapps/common/Crusader Kings III/game")
PROFILE = Path("C:/Users/RUSBAR/Documents/Paradox Interactive/Crusader Kings III")
ENTRY = re.compile(r'^\s*([^\s#":]+):\s*(?:\d+\s*)?"(.*)$')
END = re.compile(r'^(.*)"\s*(?:#.*)?$')
sources = []
diagnostics = []


def write_json(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def write_csv(name, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with (OUT / name).open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        if fields:
            w.writeheader()
            w.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in row.items()} for row in rows)


def read(path, pin=False):
    b = path.read_bytes()
    if pin:
        sources.append({"path": str(path), "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b)})
    return b, b.decode("utf-8-sig")


def catalog(root, language, label, audit=False):
    records = []
    files = sorted((root / "localization").rglob(f"*_l_{language}.yml"))
    for path in files:
        raw, content = read(path, pin=audit)
        rel = path.relative_to(root).as_posix()
        if audit and not raw.startswith(b"\xef\xbb\xbf"):
            diagnostics.append(dict(catalog=label, file=rel, line=1, kind="no_bom", key=""))
        has_header = bool(re.search(rf"(?m)^\s*l_{language}:\s*(?:#.*)?$", content))
        if audit and not has_header:
            diagnostics.append(dict(catalog=label, file=rel, line=1, kind="bad_header", key=""))
        for i, line in enumerate(content.splitlines(), 1):
            m = ENTRY.match(line)
            if not m:
                if audit and line.strip() and not line.lstrip().startswith("#") and not re.match(r"\s*l_\w+:\s*$", line):
                    diagnostics.append(dict(catalog=label, file=rel, line=i, kind="unparsed_line", key="", text=line))
                continue
            key, tail = m.groups()
            end = END.match(tail)
            text = end.group(1) if end else tail
            records.append(dict(catalog=label, file=rel, line=i, key=key, text=text, header_valid=has_header, closed_quote=bool(end)))
            if audit and not end:
                diagnostics.append(dict(catalog=label, file=rel, line=i, kind="unclosed_quote", key=key, text=text))
    index = defaultdict(list)
    for r in records:
        if r["header_valid"]:
            index[r["key"]].append(r)
    return records, index, len(files)


def queries(text):
    # Nested queries are retained as one expression; no regex truncation at inner ].
    result, start, depth = [], 0, 0
    for i, c in enumerate(text):
        if c == "[":
            if depth == 0:
                start = i
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                result.append(text[start:i + 1])
    return result


def visible(text):
    for q in queries(text):
        text = text.replace(q, " ")
    return re.sub(r"\$[^$]*\$|@[^!\s]+!|#[A-Za-z0-9_!]+|\\[ntr]", " ", text)


en_rows, en, en_files = catalog(MAIN, "english", "EN", True)
ru_rows, ru, ru_files = catalog(RU, "russian", "RU", True)
builtin_rows, builtin, builtin_files = catalog(MAIN, "russian", "BUILTIN_RU", True)
versions = {}
for root in (MAIN, RU):
    _, descriptor = read(root / "descriptor.mod", True)
    versions[root] = re.search(r'^version="([^"]+)"', descriptor, re.M).group(1)

# Known active Russian localization providers are consulted as fallback candidates.
# Presence does not prove semantic equivalence or runtime localization precedence.
profile_bytes = (PROFILE / "dlc_load.json").read_bytes()
profile_data = json.loads(profile_bytes.decode("utf-8-sig"))
profile_snapshot = dict(path=str(PROFILE / "dlc_load.json"), sha256=hashlib.sha256(profile_bytes).hexdigest(), enabled_mods=profile_data["enabled_mods"], descriptors=[])
fallback = defaultdict(list)
active_roots = []
for descriptor in profile_data["enabled_mods"]:
    descriptor_bytes = (PROFILE / descriptor).read_bytes()
    text = descriptor_bytes.decode("utf-8-sig")
    m = re.search(r'^path="([^"]+)"', text, re.M)
    if m:
        root = Path(m.group(1))
        active_roots.append(root)
        profile_snapshot["descriptors"].append(dict(path=str(PROFILE / descriptor), sha256=hashlib.sha256(descriptor_bytes).hexdigest(), mod_path=str(root)))
for root in [GAME] + active_roots:
    if root in (MAIN, RU):
        continue
    rows, _, _ = catalog(root, "russian", root.name)
    for row in rows:
        if row["key"] in en or row["key"] in ru:
            fallback[row["key"]].append(row)

missing, extra, pairs, duplicates, structure, differences, english_prose = [], [], [], [], [], [], []
for label, index in (("EN", en), ("RU", ru)):
    for key, rows in index.items():
        if len(rows) > 1:
            duplicates.append(dict(catalog=label, key=key, count=len(rows), distinct_values=len(set(r["text"] for r in rows)), definitions=rows))

for key, rows in en.items():
    e = rows[-1]
    if key not in ru:
        missing.append(dict(key=key, file=e["file"], line=e["line"], english=e["text"], builtin=builtin.get(key, []), fallback=fallback.get(key, [])))
    else:
        for r in ru[key]:
            pair = dict(key=key, en_file=e["file"], en_line=e["line"], ru_file=r["file"], ru_line=r["line"], english=e["text"], russian=r["text"])
            pairs.append(pair)
            eq, rq = Counter(queries(e["text"])), Counter(queries(r["text"]))
            ed, rd = Counter(re.findall(r"\$([^$]+)\$", e["text"])), Counter(re.findall(r"\$([^$]+)\$", r["text"]))
            if eq != rq or ed != rd:
                differences.append(dict(**pair, en_only_queries=list((eq-rq).elements()), ru_only_queries=list((rq-eq).elements()), en_only_refs=list((ed-rd).elements()), ru_only_refs=list((rd-ed).elements())))
            v = visible(r["text"])
            if not re.search(r"[\u0400-\u04ff]", v) and re.search(r"[A-Za-z]{2,}", v):
                english_prose.append(pair)
for key, rows in ru.items():
    if key not in en:
        extra.append(dict(key=key, definitions=rows))

for row in en_rows + ru_rows:
    t = row["text"]
    reasons = []
    if t.count("[") != t.count("]"):
        reasons.append("square_brackets")
    if t.count("$") % 2:
        reasons.append("dollar_references")
    tags = re.findall(r"#(!|[A-Za-z][A-Za-z0-9_;:.,-]*)", t)
    balance = 0
    for tag in tags:
        balance += -1 if tag == "!" else 1
        if balance < 0:
            reasons.append("extra_format_close")
            break
    if balance > 0:
        reasons.append("unclosed_format")
    if reasons:
        structure.append(dict(**row, reasons=reasons))

# Pin script inputs and record direct token references for retired-key review.
scripts = []
for folder in ("events", "common", "gui"):
    for path in sorted((MAIN / folder).rglob("*")):
        if path.is_file() and path.suffix.lower() in (".txt", ".gui"):
            _, s = read(path, True)
            scripts.append((path.relative_to(MAIN).as_posix(), s))
token_locations = defaultdict(list)
for path, content in scripts:
    for i, line in enumerate(content.splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        for tok in set(re.findall(r"[A-Za-z_][A-Za-z0-9_.-]*", line)):
            if tok in ru or tok in en:
                token_locations[tok].append(dict(file=path, line=i))
for row in extra:
    row["direct_script_references"] = token_locations.get(row["key"], [])
    row["fallback"] = fallback.get(row["key"], [])
    row["optional_compatch"] = all("/Compatch/" in r["file"] for r in row["definitions"])

shortened = []
for pair in pairs:
    en_length, ru_length = len(visible(pair["english"])), len(visible(pair["russian"]))
    if en_length >= 350 and ru_length / en_length < 0.6:
        shortened.append(dict(**pair, en_visible_chars=en_length, ru_visible_chars=ru_length, ratio=round(ru_length/en_length, 4)))

source_hashes = {s["path"]:s["sha256"] for s in sources}
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == digest for p,digest in source_hashes.items())
summary = dict(
    AuditedAtUTC=datetime.now(timezone.utc).isoformat(),
    MainVersion=versions[MAIN], TranslationVersion=versions[RU], MainWorkshopID=MAIN.name, TranslationWorkshopID=RU.name,
    MainEnglishFiles=en_files, MainEnglishEntries=len(en_rows), MainUniqueKeys=len(en),
    TranslationRussianFiles=ru_files, TranslationRussianEntries=len(ru_rows), TranslationUniqueKeys=len(ru),
    BuiltinRussianFiles=builtin_files, SharedKeys=len(en.keys() & ru.keys()),
    MissingFromTranslation=len(missing), MissingWithoutFallback=sum(not r["fallback"] and not r["builtin"] for r in missing),
    ExtraTranslationKeys=len(extra), ExtraCompatchKeys=sum(r["optional_compatch"] for r in extra),
    DuplicateKeys=dict(Counter(d["catalog"] for d in duplicates)),
    Diagnostics=dict(Counter((d["catalog"] + ":" + d["kind"]) for d in diagnostics)),
    QueryDifferenceCandidates=len(differences), StructureCandidates=len(structure), EnglishTextCandidates=len(english_prose),
    ShortenedTextCandidates=len(shortened), SharedKeyCoveragePercent=round(100 * len(en.keys() & ru.keys()) / len(en), 4),
    MainIsInLastLaunchedPlayset=MAIN in active_roots, TranslationIsInLastLaunchedPlayset=RU in active_roots,
    PinnedSources=len(source_hashes), SourcesUnchanged=True, RuntimeFilesChanged=False,
    Scope="Static localization audit; automatic candidates require manual review. No engine load order assumed for duplicate keys."
)
for name, rows in (("catalog-entries",en_rows+ru_rows),("missing-from-translation",missing),("extra-translation-keys",extra),("paired-texts",pairs),("duplicates-review",duplicates),("structure-review",structure),("query-differences-review",differences),("english-text-review",english_prose),("shortened-text-review",shortened),("diagnostics",diagnostics)):
    write_json(name + ".json", rows)
    write_csv(name + ".csv", rows)
write_json("source-baseline.json", sources)
write_json("summary.json", summary)
write_json("script-key-references.json", token_locations)
write_json("profile-snapshot.json", profile_snapshot)
print(json.dumps(summary, ensure_ascii=False, indent=2))
