# Holding Manager (RUSBAR Edition)

## English

`Holding Manager (RUSBAR Edition)` is a vanilla-focused fork of [Holding Manager Continued](https://steamcommunity.com/sharedfiles/filedetails/?id=3473706726), based on upstream version `1.16`.

- Fork version: `1.0.0`
- Supported Crusader Kings III version: `1.19.0.6`
- Fork author and maintainer: Ilya "RUSBAR" Barkalov
- Supported languages: English, Russian, French, German, Spanish, Korean, and Simplified Chinese

> **Localization notice:** Only the English and Russian localizations have been reviewed. The French, German, Spanish, Korean, and Simplified Chinese localizations were completed with AI assistance and may contain translation errors or require further refinement.

### Why use RUSBAR Edition?

The original mod provides a powerful holding-management interface, but its accumulated compatibility layers, outdated vanilla copies, duplicated data, and hand-written building checks made its behavior inconsistent on current game versions. RUSBAR Edition keeps the useful workflow while rebuilding and stabilizing its internals for the current vanilla game.

The main advantages are:

- current vanilla interface logic is preserved in the two overridden game windows;
- building availability follows current vanilla requirements, including innovations, cultural parameters, government, terrain, holding type, and other construction restrictions;
- building construction and upgrades work consistently in both personal and vassal holdings;
- personal-domain and realm-wide mass actions use the same eligibility rules and cost calculations;
- every mass action shows an exact preview grouped by county and holding before confirmation;
- internal objects and files use the isolated `HM_RE_` namespace;
- every supported language has the same complete localization key set.

### Added and improved

- Rebased `window_county_view.gui` and `window_title.gui` on the supported vanilla version while retaining the Holding Manager controls.
- Rebuilt the building eligibility layer from current vanilla building definitions and their construction blocks.
- Reused vanilla scripted requirements where their scope permits it and added only thin province-to-holder adapters where required.
- Added generated, reproducible building trigger files and the `tools/Sync-HMREBuildingTriggers.ps1` synchronization utility.
- Corrected building catalogs, prerequisite chains, era and innovation checks, cultural unlocks, government restrictions, and holding compatibility.
- Corrected mass-action gold and prestige calculations.
- Corrected building construction and upgrades in vassal holdings.
- Made mass construction add available building slots in vassal holdings just as it does in the player's own holdings.
- Added **Build All Buildings** for the personal domain.
- Added realm-wide **Build All Buildings**, **Upgrade All Buildings**, and **Clear All Building Slots** decisions.
- Added detailed native previews to all six personal-domain and realm-wide construction, upgrade, and removal decisions.
- Added game-rule controls for costs, cooldowns, building replacement, holding conversion, player and AI building slots, and mass actions.
- Restored the original French, German, Spanish, Korean, and Simplified Chinese translations, migrated every reference to the `HM_RE_` namespace, and translated all fork-specific keys.
- Stabilized GUI, scripted effects, scripted triggers, scripted values, decisions, localization, and file encoding.
- Renamed fork-owned files and script objects with the `HM_RE_` prefix to reduce collisions.

### Removed and intentionally unsupported

- Removed obsolete compatibility code for City Walls/COW and other non-vanilla integrations.
- Removed the unused alternative `ui option` interface copy.
- Removed duplicate Russian localization.
- Removed duplicated and misplaced localization files; every language now uses its standard CK3 subdirectory and the same four-file layout.
- Removed `debug_only = no` bypasses from building eligibility logic.
- Removed stale compatibility branches that did not belong to the supported vanilla configuration.
- Duchy buildings are intentionally excluded from the mass-building catalogs for version `1.0.0`.

### Compatibility

This edition targets the unmodified vanilla game. Compatibility with other gameplay or total-conversion mods is not included unless released as a separate, explicitly marked patch.

The mod overrides these interface files:

- `gui/window_county_view.gui`
- `gui/window_title.gui`

It may conflict with other mods that override the same files.

---

## Русский

`Holding Manager (RUSBAR Edition)` — ориентированный на ванильную игру форк мода [Holding Manager Continued](https://steamcommunity.com/sharedfiles/filedetails/?id=3473706726), основанный на версии оригинального мода `1.16`.

- Версия форка: `1.0.0`
- Поддерживаемая версия Crusader Kings III: `1.19.0.6`
- Автор и сопровождающий форка: Ilya "RUSBAR" Barkalov
- Поддерживаемые языки: русский, английский, французский, немецкий, испанский, корейский и упрощённый китайский

> **Примечание о локализациях:** вычитаны только русская и английская локализации. Французская, немецкая, испанская, корейская и упрощённая китайская локализации дорабатывались с помощью нейросети, поэтому могут содержать ошибки перевода и требовать дальнейшей доработки.

### Преимущества RUSBAR Edition

Оригинальный мод предоставляет мощный интерфейс управления владениями, однако накопленные слои совместимости, устаревшие копии ванильных файлов, дублирование данных и вручную написанные проверки зданий привели к непоследовательному поведению на современных версиях игры. RUSBAR Edition сохраняет удобный рабочий процесс, но заново выстраивает и стабилизирует внутреннюю механику для текущей ванильной игры.

Основные преимущества:

- в двух заменяемых окнах сохранена актуальная ванильная логика интерфейса;
- доступность зданий следует современным ванильным требованиям, включая инновации, культурные параметры, правительство, местность, тип владения и прочие ограничения строительства;
- строительство и улучшение зданий одинаково надёжно работают в личных и вассальных владениях;
- массовые действия для личного домена и всей державы используют одинаковые правила доступности и расчёта стоимости;
- перед подтверждением каждого массового действия показывается точный список изменений, сгруппированный по графствам и владениям;
- внутренние объекты и файлы изолированы префиксом `HM_RE_`;
- каждый поддерживаемый язык содержит одинаковый полный набор ключей локализации.

### Добавлено и улучшено

- `window_county_view.gui` и `window_title.gui` перенесены на поддерживаемую ванильную версию с сохранением элементов управления Holding Manager.
- Слой доступности зданий заново сформирован из актуальных ванильных определений зданий и их блоков строительства.
- Везде, где позволяет контекст, повторно используются ванильные scripted requirements; собственные тонкие адаптеры добавлены только для перехода от провинции к владельцу.
- Добавлены воспроизводимо генерируемые файлы триггеров зданий и утилита синхронизации `tools/Sync-HMREBuildingTriggers.ps1`.
- Исправлены справочники зданий, цепочки предварительных условий, проверки эпох и инноваций, культурные разблокировки, ограничения правительства и совместимость с типами владений.
- Исправлены расчёты стоимости массовых действий в золоте и престиже.
- Исправлено строительство и улучшение зданий во владениях вассалов.
- Массовое строительство теперь добавляет доступные ячейки во владениях вассалов так же, как в личных владениях игрока.
- Добавлено решение **«Построить все здания»** для личного домена.
- Добавлены державные решения **«Построить все здания»**, **«Улучшить все здания»** и **«Очистить все ячейки зданий»**.
- Во все шесть личных и державных решений строительства, улучшения и удаления добавлен подробный ванильный предпросмотр изменений.
- Добавлены игровые правила для стоимости, периодов ожидания, замены зданий, преобразования владений, дополнительных ячеек игрока и ИИ, а также массовых действий.
- Восстановлены оригинальные французская, немецкая, испанская, корейская и упрощённая китайская локализации, все их ссылки перенесены в пространство имён `HM_RE_`, а новые ключи форка полностью переведены.
- Стабилизированы GUI, scripted effects, scripted triggers, scripted values, решения, локализация и кодировка файлов.
- Собственные файлы и скриптовые объекты форка переименованы с префиксом `HM_RE_`, чтобы уменьшить риск конфликтов.

### Удалено и намеренно не поддерживается

- Удалён устаревший код совместимости с City Walls/COW и другими неванильными интеграциями.
- Удалена неиспользуемая альтернативная копия интерфейса `ui option`.
- Удалена дублирующая русская локализация.
- Удалены дублирующиеся и неправильно размещённые файлы локализации; теперь каждый язык находится в стандартной папке CK3 и использует одинаковую структуру из четырёх файлов.
- Из логики доступности зданий удалены обходы `debug_only = no`.
- Удалены устаревшие ветви совместимости, не относящиеся к поддерживаемой ванильной конфигурации.
- Герцогские здания намеренно исключены из справочников массового строительства в версии `1.0.0`.

### Совместимость

Эта редакция предназначена для неизменённой ванильной игры. Совместимость с другими геймплейными и глобальными модификациями не включена, если для них не выпущен отдельный явно обозначенный патч.

Мод заменяет следующие файлы интерфейса:

- `gui/window_county_view.gui`
- `gui/window_title.gui`

Возможны конфликты с другими модами, заменяющими те же файлы.
