# Holding Manager (RUSBAR Edition)

Vanilla-focused, stabilized fork of [Holding Manager Continued](https://steamcommunity.com/sharedfiles/filedetails/?id=3473706726), based on upstream version `1.16`. The project continues the idea of the [original Holding Manager](https://steamcommunity.com/sharedfiles/filedetails/?id=2633505646).

- Mod version: `1.0.0`
- Supported Crusader Kings III version: `1.19.0.6`
- Author and maintainer: Ilya "RUSBAR" Barkalov
- Repository: [RUSBAR-ITS/Crusader_Kings_III_Mods](https://github.com/RUSBAR-ITS/Crusader_Kings_III_Mods)
- Technical documentation: [English](docs/TECHNICAL_DOCUMENTATION_EN.md) · [Русская](docs/TECHNICAL_DOCUMENTATION_RU.md)
- Workshop text: [English](docs/STEAM_WORKSHOP_DESCRIPTION_EN.txt) · [Русский](docs/STEAM_WORKSHOP_DESCRIPTION_RU.txt)

## English

### What the mod does

Holding Manager adds a compact control panel to the county view and provides individual and mass tools for managing holdings:

- build, upgrade, replace, and remove supported regular buildings;
- add building slots according to configurable player and AI rules;
- convert holding types, including optional Nomad and Temple Citadel controls;
- feudalize eligible holdings in the personal domain or the whole sub-realm;
- use personal-domain or realm-wide decisions to build, upgrade, or clear every eligible holding;
- preview every building that a mass decision will construct, upgrade, or remove, grouped by county and holding;
- configure costs, instant-construction surcharge, cooldowns, scope, available controls, and AI slot behavior through game rules.

Building actions are immediate. Their prices are calculated from vanilla building costs plus the configured compensation for skipped construction time. The free-functions rule can remove player costs entirely.

### Why RUSBAR Edition

RUSBAR Edition preserves the useful workflow of its predecessors while rebuilding the implementation around the supported vanilla game:

- the overridden county and title windows were rebased on current vanilla GUI files;
- building eligibility is synchronized with current vanilla `is_enabled`, `can_construct_potential`, `can_construct_showing_failures_only`, and `can_construct` blocks;
- innovations, cultural parameters, government, terrain, holding type, prerequisite chains, and other vanilla restrictions are respected;
- personal and vassal holdings use consistent construction, slot, upgrade, cost, and preview logic;
- six personal-domain and realm-wide mass decisions show exact native effect previews before confirmation;
- old City Walls/COW integration, duplicate data, obsolete compatibility branches, dead rules, and unused interface copies were removed;
- fork-owned files and script objects use the `HM_RE_` namespace;
- building trigger synchronization is reproducible through `tools/Sync-HMREBuildingTriggers.ps1`;
- GUI, localization, encoding, calculations, references, typos, and numerous inherited script errors were corrected.

Duchy buildings are intentionally excluded from the mass-building catalogs in version `1.0.0`.

### Compatibility

The base edition targets the unmodified vanilla game. Support for another building or overhaul mod should be delivered as a separate compatibility patch; see the technical documentation for the required integration points.

The mod replaces:

- `gui/window_county_view.gui`
- `gui/window_title.gui`

Any mod replacing either file requires a GUI compatibility patch. Building mods also require catalog integration before their buildings can participate in HM_RE mass actions.

### Languages

English, Russian, French, German, Spanish, Korean, and Simplified Chinese are included. Only English and Russian were reviewed manually. The other localizations were completed with AI assistance and may contain errors or require refinement.

### Credits and permissions

Thanks to the authors of [Holding Manager Continued](https://steamcommunity.com/sharedfiles/filedetails/?id=3473706726) and the [original Holding Manager](https://steamcommunity.com/sharedfiles/filedetails/?id=2633505646) for the idea and implementation on which this fork is based.

You may use, copy, modify, redistribute, fork, translate, re-upload, or incorporate RUSBAR Edition into other projects, and you may publish any compatibility patches you want. Attribution and links to the predecessors are appreciated. Third-party material remains subject to any rights held by its respective authors.

---

## Русский

### Что делает мод

Holding Manager добавляет компактную панель управления в окно графства и инструменты для индивидуального и массового управления владениями:

- строительство, улучшение, замена и удаление поддерживаемых обычных зданий;
- добавление ячеек зданий по настраиваемым правилам для игрока и ИИ;
- преобразование типов владений, включая опциональные кнопки кочевого владения и храмовой цитадели;
- феодализация подходящих владений в личном домене либо во всей подвластной державе;
- решения для строительства, улучшения и очистки всех подходящих владений личного домена или всей державы;
- точный предпросмотр каждого здания, которое массовое решение построит, улучшит или удалит, с группировкой по графствам и владениям;
- настройка стоимости, доплаты за мгновенное строительство, периодов ожидания, области действия, доступных кнопок и поведения ячеек ИИ через игровые правила.

Строительные действия выполняются мгновенно. Цена рассчитывается на основе ванильной стоимости зданий с учётом настроенной компенсации за пропущенное время строительства. Правило бесплатных функций может полностью убрать расходы игрока.

### Преимущества RUSBAR Edition

RUSBAR Edition сохраняет удобный рабочий процесс предшественников, но перестраивает реализацию вокруг поддерживаемой ванильной игры:

- заменяемые окна графства и титула перенесены на актуальные ванильные GUI-файлы;
- доступность зданий синхронизирована с актуальными ванильными блоками `is_enabled`, `can_construct_potential`, `can_construct_showing_failures_only` и `can_construct`;
- учитываются инновации, культурные параметры, правительство, местность, тип владения, цепочки требований и прочие ванильные ограничения;
- личные и вассальные владения используют согласованную логику строительства, ячеек, улучшения, стоимости и предпросмотра;
- шесть массовых решений для личного домена и всей державы показывают точный нативный список эффектов до подтверждения;
- удалены старые интеграции City Walls/COW, дубли данных, устаревшие ветви совместимости, мёртвые правила и неиспользуемые копии интерфейса;
- собственные файлы и скриптовые объекты используют пространство имён `HM_RE_`;
- строительные триггеры воспроизводимо синхронизируются утилитой `tools/Sync-HMREBuildingTriggers.ps1`;
- исправлены GUI, локализация, кодировки, расчёты, ссылки, опечатки и множество унаследованных скриптовых ошибок.

Герцогские здания намеренно исключены из каталогов массового строительства в версии `1.0.0`.

### Совместимость

Базовая редакция предназначена для неизменённой ванильной игры. Поддержку другого мода со зданиями или глобальной переработки следует выпускать отдельным патчем совместимости; обязательные точки интеграции перечислены в технической документации.

Мод заменяет:

- `gui/window_county_view.gui`
- `gui/window_title.gui`

Для любого мода, заменяющего один из этих файлов, потребуется GUI-патч. Здания других модов также необходимо добавить в каталоги HM_RE, прежде чем они смогут участвовать в массовых действиях.

### Языки

Включены русский, английский, французский, немецкий, испанский, корейский и упрощённый китайский. Вручную вычитаны только русский и английский. Остальные локализации доделывались с помощью нейросети, поэтому могут содержать ошибки и требовать доработки.

### Благодарности и разрешения

Спасибо авторам [Holding Manager Continued](https://steamcommunity.com/sharedfiles/filedetails/?id=3473706726) и [оригинального Holding Manager](https://steamcommunity.com/sharedfiles/filedetails/?id=2633505646) за идею и реализацию, на которых основан этот форк.

RUSBAR Edition разрешено использовать, копировать, изменять, распространять, форкать, переводить, перезаливать и включать в другие проекты. Разрешено публиковать любые патчи совместимости. Указание авторства и ссылок на предшественников приветствуется.
