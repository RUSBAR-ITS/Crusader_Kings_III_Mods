# Проверка русификатора AGOT — 18 сентября 2026

Проверены установленные файлы **A Game of Thrones 0.5.2.1** (Workshop `2962333032`) и **A Game of Thrones | Русификатор** (Workshop `2962803371`). Оба мода включены в `dlc_load.json`; русификатор стоит после основного мода. В `descriptor.mod` русификатора указана версия `1.0`, но это не свидетельствует о дате его обновления.

Каталоги:

- AGOT: `E:/SteamLibrary/steamapps/workshop/content/1158310/2962333032`.
- Русификатор: `E:/SteamLibrary/steamapps/workshop/content/1158310/2962803371`.
- CK3: `E:/SteamLibrary/steamapps/common/Crusader Kings III/game`.

## Результат сравнения ключей

В 666 английских файлах AGOT найдено **162 418 уникальных ключей**. Сравнение с 674 русскими файлами русификатора выявило **15 отсутствующих ключей**. Для восьми есть строки в русской локализации самой CK3; семь не найдены ни в русификаторе, ни в русской локализации CK3.

Ключ — идентификатор, по которому игра находит текст. Наличие перевода под похожим, но другим ключом не закрывает отсутствие требуемого идентификатора.

### Семь ключей без точного русского соответствия

Пути в столбце «Источник» отсчитываются от `localization/english/agot/` основного мода.

| Ключ | Что обозначает | Источник: строка | Что найдено в русификаторе |
|---|---|---|---|
| `absolute_controlperk_landless_pirate_name` | Название способности: Captain in Command | `event_localization/agot_pirate_events_l_english.yml:97` | «Капитан у руля» есть под другим ключом: `absolute_control_perk_landless_pirate_name` — лишнее подчёркивание после `control`. |
| `agot_nw_ranger_events.1901.desc.intro_b` | Вступление к событию о дезертире Ночного Дозора | `agot_nw_ranger_l_english.yml:1308` | Перевод есть под ключом `agot_nw_ranger_events.1901.desc.intro_b_hash` — лишний суффикс `_hash`. |
| `ended_engagement_opinion` | Модификатор мнения «Бывшая помолвка» / Formerly Engaged | `00_agot_lmf_l_english.yml:290` | Точного русского ключа нет. |
| `gene_bs_eye_lower_lid_size` | Размер нижнего века в редакторе внешности | `gui/epe_ruler_designer_l_english.yml:332` | Есть общий `eye_lower_lid_size` («Размер нижнего века»), но нет этого отдельного ключа. |
| `vanilla_eye_lower_lid_size` | Vanilla Lower Eyelid Size — вариант параметра нижнего века | `gui/epe_ruler_designer_l_english.yml:333` | Есть общий `eye_lower_lid_size`, но нет этого отдельного ключа. |
| `nick_agot_historical_the_black_harren_desc` | Описание прозвища Харрена Чёрного | `agot_nicknames_historical_l_english.yml:523` | Точного русского ключа нет. |
| `reprimanded_me_unjustly__spouse_corresponding` | Текст о несправедливом наказании за оскорбление супруга/супруги | `00_agot_lmf_l_english.yml:4351` | Русский текст есть под `reprimanded_me_unjustly_spouse_corresponding`, с одним подчёркиванием вместо двух. Возможно, опечатка находится в английском оригинале. |

Для первых двух несовпадений дополнительно подтверждено, что скрипты AGOT запрашивают именно английский ключ из таблицы:

- `common/lifestyle_perks/00_martial_2_authority_tree_perks.txt:526` — `absolute_controlperk_landless_pirate_name`.
- `events/agot_events/agot_nw_ranger_events.txt:7830` — `agot_nw_ranger_events.1901.desc.intro_b`.

У последнего ключа с двойным подчёркиванием прямых ссылок в проверенных `common`, `events` и `gui` не найдено. Само расхождение подтверждено, но его влияние на отображение в игре не установлено: возможны динамические обращения к ключам.

Полные английские тексты и номера строк: [missing-russian.csv](missing-russian.csv).

### Восемь ключей, присутствующих в русской локализации CK3

Эти ключи отсутствуют в самом русификаторе, но имеют русское соответствие в базовой игре:

- `building_type_swahili_port_pembas`
- `building_type_swahili_port_pemba_desc`
- `COURT_POSITION_TOOLTIP_EFFECT_ON_YOUR_LIEGE`
- `game_concept_contract_assisting`
- `low_mandala_tribute_prestige`
- `normal_mandala_tribute_prestige`
- `high_mandala_tribute_prestige`
- `warhorse.0004.courser`

Дополнительно проверено: соответствующие русские файлы CK3 не перекрыты файлами с тем же относительным путём в AGOT или русификаторе, и их каталоги не отключены через `replace_path` этих модов. Наличие базового перевода не гарантирует, что он отражает все изменения смысла английского текста AGOT.

Все 15 ключей, включая базовые русские тексты: [missing-from-translation.csv](missing-from-translation.csv).

## Три строки русификатора без закрывающей кавычки

Пути относительно каталога русификатора:

| Ключ | Файл: строка |
|---|---|
| `b_jagjebaj` | `localization/replace/russian/agot/00_agot_titles_l_russian.yml:10157` |
| `agot_decisions_events.0102.intro.sacrifice_child` | `localization/russian/agot/event_localization/decision_events/agot_events_decisions_l_russian.yml:56` |
| `IS_CURRENT_DRAGONRIDER_TRIGGER_THIRD` | `localization/russian/agot/triggers/agot_triggers_l_russian.yml:26` |

Эти ключи учтены как присутствующие; ошибки оформления отмечены отдельно. Они могут влиять на загрузку строк. Для `b_jagjebaj` такая же ошибка есть в английском оригинале. Загрузка этих строк непосредственно движком не проверялась.

## Примеры присутствующих, но оставшихся на английском текстов

Пути относительно `localization/russian/agot/` русификатора:

| Ключ | Оставленный текст | Файл: строка |
|---|---|---|
| `agot_ships_armory_cutlass_storage_04_domicile_building_desc` | The cutlass is the preferred sword of the seas. | `agot_buildings_l_russian.yml:2821` |
| `PORTRAIT_MODIFIER_custom_clothes_shiera_dress_01` | Gown of the Seastar | `portraits/agot_portrait_modifiers_l_russian.yml:1431` |
| `yt_court_jewel_religious_head_title_name` | Great Empire of the Dawn | `religion/agot_religious_loc_l_russian.yml:5714` |
| `yt_court_bloodstone_creator_name` | The Great Void | `religion/agot_religious_loc_l_russian.yml:5830` |
| `yt_court_bloodstone_creator_name_possessive` | The Great Void's | `religion/agot_religious_loc_l_russian.yml:5831` |

Автоматически найдено 14 413 ключей с хотя бы одной одинаковой английской и русской записью. **Это не число ошибок перевода**: сюда входят ссылки `$...$`, имена, служебные значения, названия музыки и другие строки, которые могут совпадать правомерно. Фильтр английского текста выделил 33 кандидата для просмотра, также включая музыку и отладочные сообщения. Он не находит все возможные непереведённые строки.

- [english-prose-review.csv](english-prose-review.csv) — 33 кандидата.
- [identical-text-review.csv](identical-text-review.csv) — все совпадения.

## Метод и воспроизведение

Сравнение выполнено по регистрозависимым идентификаторам во всех файлах `*_l_english.yml` основного мода и `*_l_russian.yml` русификатора/CK3, включая `localization/replace`. Проверены UTF-8, BOM и заголовок языка. Ключи с отсутствующей закрывающей кавычкой включены в сравнение присутствия и отдельно отмечены в диагностике.

Дубли сохранены: у AGOT 911 ключей с несколькими определениями, у русификатора — 3893. Проверка не определяет, какое из дублирующихся значений выберет движок. Это статический аудит установленных файлов, а не проверка всех экранов и событий в запущенной игре; он также не оценивает качество русского перевода и корректность всех подстановок.

Скрипт: [Audit-AGOTRussianLocalization.ps1](../../../tools/Audit-AGOTRussianLocalization.ps1). Из корня репозитория:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/Audit-AGOTRussianLocalization.ps1
```

Параметры `-MainModPath`, `-TranslationPath`, `-GamePath`, `-OutputPath` позволяют изменить входные каталоги и место сохранения результатов. Скрипт только читает входные файлы и записывает отчёты в `OutputPath`. Таблица выше содержит ручную проверку, поэтому при повторном запуске скрипта автоматически не обновляется.

- [summary.json](summary.json) — статистика и исходные пути.
- [diagnostics.csv](diagnostics.csv) — замечания парсера с указанием источника: AGOT, Translation или CK3. Помимо трёх строк русификатора, здесь отмечены шесть некорректных строк AGOT и 14 файлов CK3 без активного заголовка языка; это отдельные категории, не дополнительные отсутствующие переводы. Например, `struggles_l_russian.yml` содержит закомментированные устаревшие ключи; такие файлы исключены из сравнения.
