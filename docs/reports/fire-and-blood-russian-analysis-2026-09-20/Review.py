"""Reproduce the reviewed findings from Analyze.py outputs, without editing mods."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(__file__).resolve().parent
AGOT_RU = Path("E:/SteamLibrary/steamapps/workshop/content/1158310/2962803371")


def load(name):
    return json.loads((OUT / (name + ".json")).read_text(encoding="utf-8"))


def save(name, obj):
    (OUT / (name + ".json")).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


pairs = {r["key"]: r for r in load("paired-texts")}
findings = []


def add(category, key, reason, correction, evidence=None):
    assert key in pairs
    findings.append(dict(category=category, key=key, reason=reason, correction=correction, evidence=evidence, **{k:v for k,v in pairs[key].items() if k != "key"}))


for key in ("bookmark_fab_aegon_desc", "bookmark_fab_argilac_desc", "bookmark_sotd_jaehaerys_desc", "bookmark_sotd_rogar_baratheon_desc"):
    add("story_indicator", key, "Пропущены оба Concept-вызова указателя сюжетного контента, присутствующие в актуальном оригинале.", "Вернуть указатель и перевод его подсказки; недостающие определения подсказок учтены среди 1304 отсутствующих ключей.")
for key in ("sotd_lifeline.0002.desc", "sotd_lifeline.0003.desc", "sotd_lifeline.0003.desc.no_alysanne"):
    add("dynamic_character", key, "Вместо текущего владельца Штормовых земель русский текст всегда называет Рогара.", "Восстановить [storm_lord.GetTitledFirstName] и согласовать остальные упоминания.", "events/sons_of_the_dragon/agot_sotd_lifeline_events.txt: immediate выбирает title:e_the_stormlands.holder, без проверки личности Рогара.")
for key in ("fab_betrothal.0001.desc", "fab_betrothal.0001.desc.spare"):
    add("meaning", key, "Джоселин названа единокровной сестрой, хотя оригинал прямо называет её дочерью матери рассказчика.", "Единоутробная сестра.")
add("meaning", "fab_dorne.0002.desc", "Planky Town ошибочно переведён как «Планктон»; также Lemonwood yielded empty halls превратилось в утверждение о сожжении Лимонной Рощи.", "Дощатый Город; вернуть различие между сожжением первого поселения и пустыми залами второго.")
for key in ("fab_dorne.0001.desc", "fab_dorne.0010.desc"):
    add("meaning", key, "Prince's Pass переведён как «Принцессов Проход».", "Принцев перевал; согласовать падеж.")
add("meaning", "fab_dorne.0015.desc", "Фраза «Блэкфайр убил его в пыль» искажает описание падения противника на землю.", "Перевести сцену заново: противник пал в пыль от удара Чёрного Пламени.")

# These are terminology consistency corrections against the installed AGOT RU glossary,
# separately labelled from technical or factual errors.
glossary_specs = [
    ("Скайрич", "Поднебесье", "b_skyreach", "replace/russian/agot/00_agot_titles_l_russian.yml"),
    ("Йронвуд", "Айронвуд", "b_yronwood", "replace/russian/agot/00_agot_titles_l_russian.yml"),
    ("Хеллхолт", "Пекло", "b_hellholt", "replace/russian/agot/00_agot_titles_l_russian.yml"),
    ("Найтсонг", "Ночная Песнь", "b_nightsong", "replace/russian/agot/00_agot_titles_l_russian.yml"),
    ("Мейденпул", "Девичий Пруд", "b_maidenpool", "replace/russian/agot/00_agot_titles_l_russian.yml"),
    ("Дремир", "Пламенная Мечта", "Dreamfyre", "replace/russian/agot/names/agot_historical_character_names_l_russian.yml"),
    ("Блэкфайр", "Чёрное Пламя", "vs_blackfyre_name", "russian/agot/artifacts/agot_artifacts_l_russian.yml"),
]
baseline, glossary = {}, []
for needle, replacement, loc_key, rel in glossary_specs + [
    ("Планктон", "Дощатый Город", "b_plankytown", "replace/russian/agot/00_agot_titles_l_russian.yml"),
    ("Принцессов", "Принцев перевал", "d_the_princes_pass", "replace/russian/agot/00_agot_titles_l_russian.yml"),
]:
    path = AGOT_RU / "localization" / rel
    raw = path.read_bytes()
    baseline[str(path)] = hashlib.sha256(raw).hexdigest()
    definitions = [dict(line=n, text=line) for n,line in enumerate(raw.decode("utf-8-sig").splitlines(), 1) if re.match(r"\s*" + re.escape(loc_key) + r":", line)]
    assert len(definitions) == 1 and replacement in definitions[0]["text"]
    glossary.append(dict(needle=needle, replacement=replacement, key=loc_key, file=str(path), **definitions[0]))
for needle, replacement, loc_key, rel in glossary_specs:
    evidence = next(g for g in glossary if g["needle"] == needle)
    for key,pair in pairs.items():
        if re.search(needle, pair["russian"], re.I):
            add("terminology_consistency", key, f"«{needle}» расходится с названием в установленном русификаторе AGOT.", f"Использовать «{replacement}» с подходящим склонением; автоматическая подстановка не предлагается.", evidence)

shortened = load("shortened-text-review")
sample_notes = {
    "fab_dorne.0001.desc": "Пропущены численность рыцарей и лордов, распределение ролей сестёр; добавлены отравленные колодцы, которых нет в этой английской реплике.",
    "fab_aegon.0001.desc": "Опущены имена охраняющих купальню рыцарей и значительная часть диалога супругов.",
    "fab_betrothal.0001.desc": "Опущено отношение септонов к браку с тёткой; добавлено предложение Алисанны; родство переведено неверно.",
    "sotd_doctrine.0001.desc": "Сокращено обоснование запрета инцеста и происхождение священного текста; это потеря деталей, не техническая поломка.",
    "sotd_dragonpit.0001.desc": "Опущены история места и затраты; добавлено скромное празднование, которого нет в исходном описании.",
    "jaehaerys.0002.desc": "Сокращены условия регентства и характеристика роли Рогара; основная ситуация сохранена.",
    "jaehaerys.0008.desc": "Сокращены мотивировка и намерение вступить в брак без разрешения; топонимы требуют отдельного согласования.",
    "fab_north.0002.desc.both": "Сокращено описание мятежников и моральная оценка милосердия рассказчика.",
    "sotd_rhaena.0002.desc": "Пропущены родство Элиссы с мужем Рейны и детали поисков; изменено имя дракона.",
    "fab_shivers.0001.desc": "Описание развития болезни за два утра сокращено до смерти уже к следующему утру; пропущены названия островов и доклад Бенифера.",
    "fab_vulture.0002.desc": "Опущены география, безымянность Короля-Стервятника и личные потери рассказчика.",
}
assert set(sample_notes) <= {r["key"] for r in shortened}
sample = [dict(**pairs[k], review=note) for k,note in sample_notes.items()]

query_review = []
for row in load("query-differences-review"):
    key = row["key"]
    cats = {r["category"] for r in findings if r["key"] == key}
    if "story_indicator" in cats or "dynamic_character" in cats:
        disposition = "confirmed_sync_fix"
    elif key.startswith("ERA_SEL_") or key == "sotd_soulmate_reason":
        disposition = "localized_literal_not_error"
    elif key.startswith("fab_dorne.") or key == "fab_shivers.0130.desc":
        disposition = "content_omission_review_not_proof_of_broken_function"
    else:
        disposition = "grammar_or_version_review_not_proof_of_broken_function"
    query_review.append(dict(key=key, disposition=disposition))

missing = load("missing-from-translation")
def missing_group(r):
    f = Path(r["file"]).name
    if re.match(r"fab_ac_0[1-9]_", f):
        return "Основные девять цепочек Завоевания"
    if f in ("fab_ac_ourfury_l_english.yml", "fab_ac_defender_l_english.yml", "fab_ac_rollback_l_english.yml"):
        return "Аргилак, защитники и отмена сценарного хода"
    if f in ("agot_sotd_jaehaerys_children_l_english.yml", "agot_sotd_rego_l_english.yml"):
        return "Дети Джейхейриса и цепочка Рего"
    if f == "fab_game_rules_l_english.yml":
        return "Правила кампании"
    return "Остальные тексты, интерфейс и служебные ссылки"

confirmed = {r["key"] for r in findings if r["category"] != "terminology_consistency"}
terms = {r["key"] for r in findings if r["category"] == "terminology_consistency"}
short_keys = {r["key"] for r in shortened}
query_candidates = {r["key"] for r in query_review if r["disposition"] in ("content_omission_review_not_proof_of_broken_function", "grammar_or_version_review_not_proof_of_broken_function")}
summary = dict(
    ConfirmedTechnicalOrMeaningKeys=len(confirmed), TerminologyConsistencyKeys=len(terms),
    ExistingKeysForCorrection=len(confirmed | terms),
    KeysWithBothConfirmedAndTerminologyIssue=len(confirmed & terms),
    ExistingKeysForCorrectionAlsoShortened=len((confirmed | terms) & short_keys),
    ShortenedTextCandidates=len(short_keys), ShortenedSamplesManuallyReviewed=len(sample),
    MissingKeysByGroup=dict(Counter(missing_group(r) for r in missing)),
    MissingKeysByFile=dict(Counter(r["file"] for r in missing)),
    MinimumCurrentKeyWorkItems=len(missing) + len(confirmed | terms),
    CurrentKeyQueueIncludingShortenedCandidates=len(missing) + len(confirmed | terms | short_keys),
    AdditionalQueryCandidates=sorted(query_candidates - confirmed - terms - short_keys),
    CurrentKeyQueueIncludingAllCandidates=len(missing) + len(confirmed | terms | short_keys | query_candidates),
    DuplicateValueGroups=dict(Counter(r["distinct_values"] for r in load("duplicates-review"))),
    MalformedFormatUniqueKeys=len({r["key"] for r in load("structure-review")}),
    FormatIssuesInCurrentMainCatalog=sum(r["key"] in pairs for r in load("structure-review")),
    MissingAliasOnlyKeys=[r["key"] for r in missing if re.fullmatch(r"\$[^$]+\$", r["english"])],
    UpstreamPlaceholders=[r["key"] for r in missing if r["english"].strip() == "TO DO"],
    Interpretation="Minimum findings, not exhaustive proofreading. Shortened candidates are not automatically errors. Categories overlap by key.",
)
for name,obj in (("reviewed-findings", findings), ("glossary-evidence", glossary), ("shortened-manual-samples", sample), ("query-review-disposition", query_review), ("review-summary", summary), ("review-source-baseline", baseline)):
    save(name,obj)
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == sha for p,sha in baseline.items())
assert all(hashlib.sha256(Path(r["path"]).read_bytes()).hexdigest() == r["sha256"] for r in load("source-baseline"))
print(json.dumps(summary, ensure_ascii=False, indent=2))
