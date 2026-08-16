# Аудит ванильных домицилей для Unlimited Domiciles

- Версия схемы отчёта: `2`
- Версия CK3: `1.19.0.6`
- Время анализа (UTC): `2026-08-16T14:04:33Z`
- Корень ванили: `E:\SteamLibrary\steamapps\common\Crusader Kings III\game`
- Отчёт только описывает ванильные данные и ничего в них не изменяет.

## Сводка

| Домицилий | Зданий | Физические внешние линии | Конечные специализации при старой модели | Рекомендовано внешних ячеек | Нарисовано | Вместимость | Дефицит интерфейса | Дефицит вместимости | Внешних развилок | Внутренних развилок |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| camp | 104 | 7 | 7 | 7 | 4 | 6 | 3 | 1 | 0 | 0 |
| estate | 186 | 16 | 27 | 16 | 6 | 8 | 10 | 8 | 6 | 1 |
| yurt | 438 | 7 | 7 | 7 | 6 | 8 | 1 | 0 | 0 | 0 |
| east_asian_estate | 545 | 15 | 23 | 15 | 6 | 8 | 9 | 7 | 5 | 0 |
| japanese_manor | 347 | 12 | 12 | 12 | 6 | 8 | 6 | 4 | 0 | 0 |

> Политика RB_UD: одна физическая корневая линия занимает одну внешнюю ячейку. Взаимоисключающие внешние специализации после общей части переводятся в параллельные внутренние треки. Поэтому рекомендуемое число внешних ячеек равно числу физических корневых линий, а не числу всех конечных листьев графа.

> Уже внутренние развилки нельзя исправить простой сменой `slot_type`: для их одновременного существования общую внутреннюю начальную часть необходимо расщепить на независимые параллельные линии. Теоретическая вместимость внешних ячеек равна `base_external_slots` плюс унаследованная сумма `domicile_external_slots_capacity_add` по главной линии.

### Масштаб планируемого преобразования

- Внешних групп специализаций: 11.
- Независимых специализационных треков: 30.
- Ванильных зданий, чьи определения потребуется перевести во внутренний тип: 96.
- Уже внутренних развилок с общей начальной частью: 1.
- Домицилии с внешними развилками: `estate`, `east_asian_estate`.
- Домицилии с внутренними развилками: `estate`.

### Политика условной совместимости

- Всего зданий с условиями доступности: 915.
- Линий-кандидатов на условное взаимоисключение: 47.
- Линий, требующих ручной проверки: 24.
- Линий с не классифицированными автоматически условиями: 0.
- Раскрыто определений scripted triggers: 38.
- Неразрешённых ссылок на scripted triggers: 0.

| Категория | Политика |
|---|---|
| CampPurpose | remove_gate_and_disable_only_corresponding_purpose_change_cleanup |
| CultureOrLanguage | manual_review_remove_only_mutual_exclusivity |
| Territory | manual_review_remove_only_mutual_exclusivity |
| Progression | preserve_vanilla_prerequisite |
| GovernmentOrStatus | preserve_vanilla_prerequisite |
| Faith | preserve_vanilla_prerequisite |
| OtherRealmLaw | preserve_vanilla_prerequisite |
| ScriptedTrigger | resolve_definition_then_preserve_unrelated_prerequisite |
| CharacterDynastyOrHouse | preserve_vanilla_prerequisite |
| StateOrFeature | preserve_vanilla_prerequisite |
| Unclassified | preserve_until_manually_classified |

### Сигнатуры ванильных данных

Эти стабильные SHA-256 позволяют после обновления CK3 отличить изменение графа, условий, ассетов или сценариев удаления. Обычный `git diff` перегенерированного JSON покажет, какая именно часть изменилась.

| Область | SHA-256 |
|---|---|
| Структура | `2849429AF9694F4BAA11ADEADBF1F49E15BB140DE25E331CE9649AB638E1D863` |
| Условная доступность | `24221FFD23F7D0C8E9651BC3ECA5B7C24E406B41BF349E3DB191F6CD109949DB` |
| Иконки и панорамы | `37B2FAACC940920D6307377C2112DD1267BE3062274D9C7252671D2C149958BE` |
| Явные удаления | `FC5A97EED605A282395782ABF5227E44D50F060DB796583BB58CD555F2C6A74A` |

## `camp`

Источник типа: `common\domiciles\types\00_domicile_types.txt:1`

### Физические внешние линии

| Корневое здание | Конечных специализаций | Конечные здания | Ограничения корня |
|---|---:|---|---|
| baggage_train_01 | 1 | baggage_train_06 |  |
| barber_tent_01 | 1 | barber_tent_06 |  |
| camp_fire_01 | 1 | camp_fire_06 |  |
| camp_perimeter_01 | 1 | camp_perimeter_06 |  |
| mess_tent_01 | 1 | mess_tent_06 |  |
| proving_grounds_01 | 1 | proving_grounds_06 |  |
| supply_tent_01 | 1 | supply_tent_06 |  |

### Внешние развилки, переводимые во внутренние треки

| Общая внешняя часть | Уровень развилки | Специализации | Новых внутренних ячеек | Всего внутренних ячеек у родителя | Иконки различаются | Панорамы совпадают | Стратегия | Источник |
|---|---:|---|---:|---:|---|---|---|---|
| — | — | — | 0 | 0 | — | — | — | — |

### Уже внутренние развилки, требующие расщепления общей части

| Общая внутренняя часть | Родитель | Общий префикс | Специализации | Нужно параллельных ячеек | Стратегия | Источник |
|---|---|---|---|---:|---|---|
| — | — | — | — | 0 | — | — |

### Существующие требования внутренних ячеек

| Родительская линия | Нужно для всех ветвей | Текущий максимум | Дефицит |
|---|---:|---:|---:|
| baggage_train_01 | 13 | 6 | 7 |
| barber_tent_01 | 5 | 3 | 2 |
| camp_fire_01 | 8 | 3 | 5 |
| camp_perimeter_01 | 6 | 3 | 3 |
| mess_tent_01 | 5 | 3 | 2 |
| proving_grounds_01 | 13 | 6 | 7 |
| supply_tent_01 | 8 | 6 | 2 |

### Все исходные точки ветвления

| Здание | Тип ячейки | Дочерние ветви |
|---|---|---|
| — | — | — |

### Условная доступность и кандидаты на взаимоисключение

- Зданий с `can_construct`/`can_construct_potential`: 28.
- Затронутых линий: 28.
- Линий с возможным взаимоисключением: 25.
- Линий, требующих ручной проверки культурных или территориальных условий: 2.
- Линий с пока не классифицированными условиями: 0.

| Линия | Тип | Внешняя опора | Категории-кандидаты | Условные здания | Извлечённые зависимости | Рекомендуемые действия | Ручная проверка |
|---|---|---|---|---|---|---|---|
| baggage_train_ascetics | internal | baggage_train_01 | camp_purpose | baggage_train_ascetics | laws: unlocks_baggage_train_ascetics | remove_camp_purpose_gate_and_disable_corresponding_cleanup | нет |
| baggage_train_negotiators | internal | baggage_train_01 | camp_purpose | baggage_train_negotiators | laws: unlocks_baggage_train_negotiators | remove_camp_purpose_gate_and_disable_corresponding_cleanup | нет |
| baggage_train_proof_of_claims | internal | baggage_train_01 | camp_purpose | baggage_train_proof_of_claims | laws: unlocks_baggage_train_proof_of_claims | remove_camp_purpose_gate_and_disable_corresponding_cleanup | нет |
| baggage_train_ransom_cages | internal | baggage_train_01 | camp_purpose | baggage_train_ransom_cages | laws: unlocks_baggage_train_ransom_cages | remove_camp_purpose_gate_and_disable_corresponding_cleanup | нет |
| baggage_train_scribes | internal | baggage_train_01 | camp_purpose | baggage_train_scribes | laws: unlocks_baggage_train_scribes | remove_camp_purpose_gate_and_disable_corresponding_cleanup | нет |
| baggage_train_siege_engineers | internal | baggage_train_01 | camp_purpose | baggage_train_siege_engineers | laws: unlocks_baggage_train_siege_engineers | remove_camp_purpose_gate_and_disable_corresponding_cleanup | нет |
| barber_tent_morticians_tools | internal | barber_tent_01 | camp_purpose | barber_tent_morticians_tools | laws: unlocks_barber_tent_morticians_tools | remove_camp_purpose_gate_and_disable_corresponding_cleanup | нет |
| barber_tent_reference_corpus | internal | barber_tent_01 | camp_purpose | barber_tent_reference_corpus | laws: unlocks_barber_tent_reference_corpus | remove_camp_purpose_gate_and_disable_corresponding_cleanup | нет |
| camp_fire_future_dreams | internal | camp_fire_01 | camp_purpose | camp_fire_future_dreams | laws: unlocks_camp_fire_future_dreams | remove_camp_purpose_gate_and_disable_corresponding_cleanup | нет |
| camp_fire_juicy_rumors | internal | camp_fire_01 | camp_purpose | camp_fire_juicy_rumors | laws: unlocks_camp_fire_juicy_rumors | remove_camp_purpose_gate_and_disable_corresponding_cleanup | нет |
| camp_fire_local_hangers_on | internal | camp_fire_01 | camp_purpose | camp_fire_local_hangers_on | laws: unlocks_camp_fire_local_hangers_on | remove_camp_purpose_gate_and_disable_corresponding_cleanup | нет |
| camp_fire_nightly_debates | internal | camp_fire_01 | camp_purpose | camp_fire_nightly_debates | laws: unlocks_camp_fire_nightly_debates | remove_camp_purpose_gate_and_disable_corresponding_cleanup | нет |
| camp_perimeter_ditch | internal | camp_perimeter_01 | camp_purpose | camp_perimeter_ditch | laws: unlocks_camp_perimeter_ditch | remove_camp_purpose_gate_and_disable_corresponding_cleanup | нет |
| camp_perimeter_extra_watch | internal | camp_perimeter_01 | camp_purpose | camp_perimeter_extra_watch | laws: unlocks_camp_perimeter_extra_watch | remove_camp_purpose_gate_and_disable_corresponding_cleanup | нет |
| camp_perimeter_palisade | internal | camp_perimeter_01 | camp_purpose | camp_perimeter_palisade | laws: unlocks_camp_perimeter_palisade | remove_camp_purpose_gate_and_disable_corresponding_cleanup | нет |
| proving_grounds_bodyguard_drills | internal | proving_grounds_01 | camp_purpose | proving_grounds_bodyguard_drills | laws: unlocks_proving_grounds_bodyguard_drills | remove_camp_purpose_gate_and_disable_corresponding_cleanup | нет |
| proving_grounds_camel_run | internal | proving_grounds_01 | culture_or_language | proving_grounds_camel_run | innovations: innovation_war_camels | preserve_unrelated_vanilla_prerequisites, review_culture_condition_and_remove_only_track_exclusivity | да |
| proving_grounds_elephantry_reserve | internal | proving_grounds_01 | culture_or_language, territory | proving_grounds_elephantry_reserve | regions: world_innovation_elephants; character_flags: recently_ate_elephants | preserve_unrelated_vanilla_prerequisites, review_culture_condition_and_remove_only_track_exclusivity, review_territory_condition_and_remove_only_track_exclusivity | да |
| proving_grounds_lockwagon | internal | proving_grounds_01 | camp_purpose | proving_grounds_lockwagon | laws: unlocks_proving_grounds_lockwagon | remove_camp_purpose_gate_and_disable_corresponding_cleanup | нет |
| proving_grounds_martial_study | internal | proving_grounds_01 | camp_purpose | proving_grounds_martial_study | laws: unlocks_proving_grounds_martial_study | remove_camp_purpose_gate_and_disable_corresponding_cleanup | нет |
| proving_grounds_the_stick_game | internal | proving_grounds_01 | camp_purpose | proving_grounds_the_stick_game | laws: unlocks_proving_grounds_the_stick_game | remove_camp_purpose_gate_and_disable_corresponding_cleanup | нет |
| supply_tent_climbing_gear | internal | supply_tent_01 | camp_purpose | supply_tent_climbing_gear | laws: unlocks_supply_tent_climbing_gear | remove_camp_purpose_gate_and_disable_corresponding_cleanup | нет |
| supply_tent_reserve_provisions | internal | supply_tent_01 | camp_purpose | supply_tent_reserve_provisions | laws: unlocks_supply_tent_reserve_provisions | remove_camp_purpose_gate_and_disable_corresponding_cleanup | нет |
| supply_tent_reserve_water | internal | supply_tent_01 | camp_purpose | supply_tent_reserve_water | laws: unlocks_supply_tent_reserve_water | remove_camp_purpose_gate_and_disable_corresponding_cleanup | нет |
| supply_tent_subdued_gear | internal | supply_tent_01 | camp_purpose | supply_tent_subdued_gear | laws: unlocks_supply_tent_subdued_gear | remove_camp_purpose_gate_and_disable_corresponding_cleanup | нет |

Полные исходные блоки условий и поключевые профили зданий сохранены в JSON. Культурные и территориальные совпадения являются кандидатами, а не автоматически удаляемыми ограничениями: сначала следует отделить взаимоисключение специализаций от обычных требований прогресса.

### Классифицированные ограничения

| Категория | Количество | Здания |
|---|---:|---|
| camp_purpose | 23 | baggage_train_ascetics, baggage_train_negotiators, baggage_train_proof_of_claims, baggage_train_ransom_cages, baggage_train_scribes, baggage_train_siege_engineers, barber_tent_morticians_tools, barber_tent_reference_corpus, camp_fire_future_dreams, camp_fire_juicy_rumors, camp_fire_local_hangers_on, camp_fire_nightly_debates, camp_perimeter_ditch, camp_perimeter_extra_watch, camp_perimeter_palisade, proving_grounds_bodyguard_drills, proving_grounds_lockwagon, proving_grounds_martial_study, proving_grounds_the_stick_game, supply_tent_climbing_gear, supply_tent_reserve_provisions, supply_tent_reserve_water, supply_tent_subdued_gear |
| realm_law | 0 |  |
| culture_or_language | 2 | proving_grounds_camel_run, proving_grounds_elephantry_reserve |
| territory | 1 | proving_grounds_elephantry_reserve |
| progression | 1 | proving_grounds_camel_run |
| government_or_status | 0 |  |
| faith | 0 |  |
| scripted_trigger | 0 |  |
| character_dynasty_or_house | 3 | baggage_train_ample_steeds, baggage_train_kennel, proving_grounds_elephantry_reserve |
| state_or_feature | 1 | proving_grounds_life_in_the_saddle |

## `estate`

Источник типа: `common\domiciles\types\00_domicile_types.txt:1032`

### Физические внешние линии

| Корневое здание | Конечных специализаций | Конечные здания | Ограничения корня |
|---|---:|---|---|
| barracks_01 | 1 | barracks_06 |  |
| garden_01 | 2 | garden_fruit_06, garden_leisure_06 |  |
| grain_field_01 | 1 | grain_field_06 |  |
| grazing_land_01 | 4 | camel_pasture_06, elephant_pasture_06, grazing_land_06, horse_pasture_06 |  |
| guardhouse_01 | 1 | guardhouse_04 |  |
| market_01 | 1 | market_06 |  |
| olive_01 | 1 | olive_06 |  |
| rice_field_01 | 1 | rice_field_06 | culture_or_language, progression |
| silk_01 | 1 | silk_06 | character_dynasty_or_house, culture_or_language |
| stable_01 | 3 | stable_chariot_06, stable_grand_06, stable_kennel_06 |  |
| storage_01 | 2 | storage_granary_04, storage_warehouse_04 |  |
| tea_01 | 1 | tea_06 | culture_or_language, progression |
| temple_small_01 | 3 | temple_crypt_06, temple_large_06, temple_monastery_06 | government_or_status |
| vineyard_01 | 1 | vineyard_06 |  |
| watchtower_01 | 1 | watchtower_06 |  |
| workshop_01 | 3 | workshop_carpenter_06, workshop_mason_06, workshop_textile_06 |  |

### Внешние развилки, переводимые во внутренние треки

| Общая внешняя часть | Уровень развилки | Специализации | Новых внутренних ячеек | Всего внутренних ячеек у родителя | Иконки различаются | Панорамы совпадают | Стратегия | Источник |
|---|---:|---|---:|---:|---|---|---|---|
| garden_03 | 3 | garden_fruit_04, garden_leisure_04 | 2 | 2 | да | да | internalize_external_specialization_tails | common\domiciles\buildings\00_estate_buildings.txt:6086 |
| grazing_land_03 | 3 | camel_pasture_04, elephant_pasture_04, grazing_land_04, horse_pasture_04 | 4 | 4 | да | да | internalize_external_specialization_tails | common\domiciles\buildings\00_estate_buildings.txt:10468 |
| stable_03 | 3 | stable_chariot_04, stable_grand_04, stable_kennel_04 | 3 | 3 | да | да | internalize_external_specialization_tails | common\domiciles\buildings\00_estate_buildings.txt:7140 |
| storage_02 | 2 | storage_granary_03, storage_warehouse_03 | 2 | 2 | да | да | internalize_external_specialization_tails | common\domiciles\buildings\00_estate_buildings.txt:9280 |
| temple_small_03 | 3 | temple_crypt_04, temple_large_04, temple_monastery_04 | 3 | 3 | да | да | internalize_external_specialization_tails | common\domiciles\buildings\00_estate_buildings.txt:3043 |
| workshop_02 | 2 | workshop_carpenter_03, workshop_mason_03, workshop_textile_03 | 3 | 3 | да | да | internalize_external_specialization_tails | common\domiciles\buildings\00_estate_buildings.txt:8106 |

#### Специализации после `garden_03`

| Корень специализации | Стартовый уровень | Здания, переводимые во внутренний тип | Листья | Иконки корня | Панорамы корня |
|---|---:|---|---|---|---|
| garden_fruit_04 | 4 | garden_fruit_04, garden_fruit_05, garden_fruit_06 | garden_fruit_06 | gfx/interface/icons/domicile_building/domicile_building_fruit_garden.dds | gfx/interface/window_domiciles/estate_building_garden_byzantine.dds, gfx/interface/window_domiciles/estate_building_garden_chinese.dds, gfx/interface/window_domiciles/estate_building_garden_mena.dds, gfx/interface/window_domiciles/estate_building_garden_western.dds |
| garden_leisure_04 | 4 | garden_leisure_04, garden_leisure_05, garden_leisure_06 | garden_leisure_06 | gfx/interface/icons/domicile_building/domicile_building_leisure_garden.dds | gfx/interface/window_domiciles/estate_building_garden_byzantine.dds, gfx/interface/window_domiciles/estate_building_garden_chinese.dds, gfx/interface/window_domiciles/estate_building_garden_mena.dds, gfx/interface/window_domiciles/estate_building_garden_western.dds |

#### Специализации после `grazing_land_03`

| Корень специализации | Стартовый уровень | Здания, переводимые во внутренний тип | Листья | Иконки корня | Панорамы корня |
|---|---:|---|---|---|---|
| camel_pasture_04 | 4 | camel_pasture_04, camel_pasture_05, camel_pasture_06 | camel_pasture_06 | gfx/interface/icons/domicile_building/domicile_building_camel_run.dds | gfx/interface/window_domiciles/estate_building_grazing_fields.dds, gfx/interface/window_domiciles/estate_building_horse_pastures_japanese.dds |
| elephant_pasture_04 | 4 | elephant_pasture_04, elephant_pasture_05, elephant_pasture_06 | elephant_pasture_06 | gfx/interface/icons/domicile_building/domicile_building_elephantry_reserves.dds | gfx/interface/window_domiciles/estate_building_grazing_fields.dds, gfx/interface/window_domiciles/estate_building_horse_pastures_japanese.dds |
| grazing_land_04 | 4 | grazing_land_04, grazing_land_05, grazing_land_06 | grazing_land_06 | gfx/interface/icons/domicile_building/domicile_building_horse_run.dds | gfx/interface/window_domiciles/estate_building_grazing_fields.dds, gfx/interface/window_domiciles/estate_building_horse_pastures_japanese.dds |
| horse_pasture_04 | 4 | horse_pasture_04, horse_pasture_05, horse_pasture_06 | horse_pasture_06 | gfx/interface/icons/domicile_building/domicile_building_life_in_the_saddle.dds | gfx/interface/window_domiciles/estate_building_grazing_fields.dds, gfx/interface/window_domiciles/estate_building_horse_pastures_japanese.dds |

#### Специализации после `stable_03`

| Корень специализации | Стартовый уровень | Здания, переводимые во внутренний тип | Листья | Иконки корня | Панорамы корня |
|---|---:|---|---|---|---|
| stable_chariot_04 | 4 | stable_chariot_04, stable_chariot_05, stable_chariot_06 | stable_chariot_06 | gfx/interface/icons/domicile_building/domicile_building_chariot_track.dds | gfx/interface/window_domiciles/estate_building_stable_byzantine.dds, gfx/interface/window_domiciles/estate_building_stable_china.dds, gfx/interface/window_domiciles/estate_building_stable_mena.dds, gfx/interface/window_domiciles/estate_building_stable_western.dds |
| stable_grand_04 | 4 | stable_grand_04, stable_grand_05, stable_grand_06 | stable_grand_06 | gfx/interface/icons/domicile_building/domicile_building_grand_stable.dds | gfx/interface/window_domiciles/estate_building_stable_byzantine.dds, gfx/interface/window_domiciles/estate_building_stable_china.dds, gfx/interface/window_domiciles/estate_building_stable_mena.dds, gfx/interface/window_domiciles/estate_building_stable_western.dds |
| stable_kennel_04 | 4 | stable_kennel_04, stable_kennel_05, stable_kennel_06 | stable_kennel_06 | gfx/interface/icons/domicile_building/domicile_building_kennel.dds | gfx/interface/window_domiciles/estate_building_stable_byzantine.dds, gfx/interface/window_domiciles/estate_building_stable_china.dds, gfx/interface/window_domiciles/estate_building_stable_mena.dds, gfx/interface/window_domiciles/estate_building_stable_western.dds |

#### Специализации после `storage_02`

| Корень специализации | Стартовый уровень | Здания, переводимые во внутренний тип | Листья | Иконки корня | Панорамы корня |
|---|---:|---|---|---|---|
| storage_granary_03 | 3 | storage_granary_03, storage_granary_04 | storage_granary_04 | gfx/interface/icons/domicile_building/domicile_building_granary.dds | gfx/interface/window_domiciles/estate_building_storage_byzantine.dds, gfx/interface/window_domiciles/estate_building_storage_chinese.dds, gfx/interface/window_domiciles/estate_building_storage_mena.dds, gfx/interface/window_domiciles/estate_building_storage_western.dds |
| storage_warehouse_03 | 3 | storage_warehouse_03, storage_warehouse_04 | storage_warehouse_04 | gfx/interface/icons/domicile_building/domicile_building_warehouse.dds | gfx/interface/window_domiciles/estate_building_storage_byzantine.dds, gfx/interface/window_domiciles/estate_building_storage_chinese.dds, gfx/interface/window_domiciles/estate_building_storage_mena.dds, gfx/interface/window_domiciles/estate_building_storage_western.dds |

#### Специализации после `temple_small_03`

| Корень специализации | Стартовый уровень | Здания, переводимые во внутренний тип | Листья | Иконки корня | Панорамы корня |
|---|---:|---|---|---|---|
| temple_crypt_04 | 4 | temple_crypt_04, temple_crypt_05, temple_crypt_06 | temple_crypt_06 | gfx/interface/icons/domicile_building/domicile_building_crypt.dds | gfx/interface/window_domiciles/estate_building_ancestral_shrine_chinese.dds, gfx/interface/window_domiciles/estate_building_temple_christian.dds, gfx/interface/window_domiciles/estate_building_temple_christian_orthodox.dds, gfx/interface/window_domiciles/estate_building_temple_generic_mena.dds, gfx/interface/window_domiciles/estate_building_temple_generic_western.dds, gfx/interface/window_domiciles/estate_building_temple_islamic.dds |
| temple_large_04 | 4 | temple_large_04, temple_large_05, temple_large_06 | temple_large_06 | gfx/interface/icons/domicile_building/domicile_building_church.dds | gfx/interface/window_domiciles/estate_building_ancestral_shrine_chinese.dds, gfx/interface/window_domiciles/estate_building_temple_christian.dds, gfx/interface/window_domiciles/estate_building_temple_christian_orthodox.dds, gfx/interface/window_domiciles/estate_building_temple_generic_mena.dds, gfx/interface/window_domiciles/estate_building_temple_generic_western.dds, gfx/interface/window_domiciles/estate_building_temple_islamic.dds |
| temple_monastery_04 | 4 | temple_monastery_04, temple_monastery_05, temple_monastery_06 | temple_monastery_06 | gfx/interface/icons/domicile_building/domicile_building_monastery.dds | gfx/interface/window_domiciles/estate_building_ancestral_shrine_chinese.dds, gfx/interface/window_domiciles/estate_building_temple_christian.dds, gfx/interface/window_domiciles/estate_building_temple_christian_orthodox.dds, gfx/interface/window_domiciles/estate_building_temple_generic_mena.dds, gfx/interface/window_domiciles/estate_building_temple_generic_western.dds, gfx/interface/window_domiciles/estate_building_temple_islamic.dds |

#### Специализации после `workshop_02`

| Корень специализации | Стартовый уровень | Здания, переводимые во внутренний тип | Листья | Иконки корня | Панорамы корня |
|---|---:|---|---|---|---|
| workshop_carpenter_03 | 3 | workshop_carpenter_03, workshop_carpenter_04, workshop_carpenter_05, workshop_carpenter_06 | workshop_carpenter_06 | gfx/interface/icons/domicile_building/domicile_building_carpenter.dds | gfx/interface/window_domiciles/estate_building_workshop_byzantine.dds, gfx/interface/window_domiciles/estate_building_workshop_chinese.dds, gfx/interface/window_domiciles/estate_building_workshop_mena.dds, gfx/interface/window_domiciles/estate_building_workshop_western.dds |
| workshop_mason_03 | 3 | workshop_mason_03, workshop_mason_04, workshop_mason_05, workshop_mason_06 | workshop_mason_06 | gfx/interface/icons/domicile_building/domicile_building_mason.dds | gfx/interface/window_domiciles/estate_building_workshop_byzantine.dds, gfx/interface/window_domiciles/estate_building_workshop_chinese.dds, gfx/interface/window_domiciles/estate_building_workshop_mena.dds, gfx/interface/window_domiciles/estate_building_workshop_western.dds |
| workshop_textile_03 | 3 | workshop_textile_03, workshop_textile_04, workshop_textile_05, workshop_textile_06 | workshop_textile_06 | gfx/interface/icons/domicile_building/domicile_building_textile.dds | gfx/interface/window_domiciles/estate_building_workshop_byzantine.dds, gfx/interface/window_domiciles/estate_building_workshop_chinese.dds, gfx/interface/window_domiciles/estate_building_workshop_mena.dds, gfx/interface/window_domiciles/estate_building_workshop_western.dds |

### Уже внутренние развилки, требующие расщепления общей части

| Общая внутренняя часть | Родитель | Общий префикс | Специализации | Нужно параллельных ячеек | Стратегия | Источник |
|---|---|---|---|---:|---|---|
| library_02 | estate_main_01 | library_01 → library_02 | library_education_03, library_observatory_03 | 2 | split_shared_internal_prefix_into_parallel_tracks | common\domiciles\buildings\00_estate_buildings.txt:1094 |

### Существующие требования внутренних ячеек

| Родительская линия | Нужно для всех ветвей | Текущий максимум | Дефицит |
|---|---:|---:|---:|
| estate_main_01 | 14 | 10 | 4 |

### Все исходные точки ветвления

| Здание | Тип ячейки | Дочерние ветви |
|---|---|---|
| garden_03 | external | garden_fruit_04, garden_leisure_04 |
| grazing_land_03 | external | camel_pasture_04, elephant_pasture_04, grazing_land_04, horse_pasture_04 |
| library_02 | internal | library_education_03, library_observatory_03 |
| stable_03 | external | stable_chariot_04, stable_grand_04, stable_kennel_04 |
| storage_02 | external | storage_granary_03, storage_warehouse_03 |
| temple_small_03 | external | temple_crypt_04, temple_large_04, temple_monastery_04 |
| workshop_02 | external | workshop_carpenter_03, workshop_mason_03, workshop_textile_03 |

### Условная доступность и кандидаты на взаимоисключение

- Зданий с `can_construct`/`can_construct_potential`: 134.
- Затронутых линий: 29.
- Линий с возможным взаимоисключением: 6.
- Линий, требующих ручной проверки культурных или территориальных условий: 6.
- Линий с пока не классифицированными условиями: 0.

| Линия | Тип | Внешняя опора | Категории-кандидаты | Условные здания | Извлечённые зависимости | Рекомендуемые действия | Ручная проверка |
|---|---|---|---|---|---|---|---|
| grazing_land_01 | external | grazing_land_01 | culture_or_language | camel_pasture_04, camel_pasture_05, camel_pasture_06, elephant_pasture_04, elephant_pasture_05, elephant_pasture_06, grazing_land_04, grazing_land_05, grazing_land_06, horse_pasture_04, horse_pasture_05, horse_pasture_06 | innovations: innovation_elephantry, innovation_war_camels; domicile_buildings: estate_main_03, estate_main_04, estate_main_05; scripted_triggers: can_recruit_archer_cavalry_trigger | preserve_unrelated_vanilla_prerequisites, review_culture_condition_and_remove_only_track_exclusivity | да |
| rice_field_01 | external | rice_field_01 | culture_or_language | rice_field_01, rice_field_03, rice_field_04, rice_field_05, rice_field_06 | innovations: innovation_champa_rice; domicile_buildings: estate_main_02, estate_main_03, estate_main_04, estate_main_05 | preserve_unrelated_vanilla_prerequisites, review_culture_condition_and_remove_only_track_exclusivity | да |
| silk_01 | external | silk_01 | culture_or_language | silk_01, silk_02, silk_03, silk_04, silk_05, silk_06 | culture_parameters: unlocks_silk_buildings_parameter; domicile_buildings: estate_main_02, estate_main_03, estate_main_04, estate_main_05 | preserve_unrelated_vanilla_prerequisites, review_culture_condition_and_remove_only_track_exclusivity | да |
| stable_01 | external | stable_01 | culture_or_language | stable_chariot_04, stable_chariot_05, stable_chariot_06, stable_grand_04, stable_grand_05, stable_grand_06, stable_kennel_04, stable_kennel_05, stable_kennel_06 | culture_parameters: hosts_chariot_races; domicile_buildings: estate_main_03, estate_main_04, estate_main_05 | preserve_unrelated_vanilla_prerequisites, review_culture_condition_and_remove_only_track_exclusivity | да |
| tea_01 | external | tea_01 | culture_or_language | tea_01, tea_03, tea_04, tea_05, tea_06 | innovations: innovation_champa_rice; domicile_buildings: estate_main_02, estate_main_03, estate_main_04, estate_main_05 | preserve_unrelated_vanilla_prerequisites, review_culture_condition_and_remove_only_track_exclusivity | да |
| estate_main_01 | main | estate_main_01 | culture_or_language | estate_main_02, estate_main_03, estate_main_04, estate_main_05 | innovations: innovation_city_planning, innovation_cranes, innovation_development_03, innovation_manorialism | preserve_unrelated_vanilla_prerequisites, review_culture_condition_and_remove_only_track_exclusivity | да |

Полные исходные блоки условий и поключевые профили зданий сохранены в JSON. Культурные и территориальные совпадения являются кандидатами, а не автоматически удаляемыми ограничениями: сначала следует отделить взаимоисключение специализаций от обычных требований прогресса.

### Классифицированные ограничения

| Категория | Количество | Здания |
|---|---:|---|
| camp_purpose | 0 |  |
| realm_law | 0 |  |
| culture_or_language | 19 | camel_pasture_04, camel_pasture_05, camel_pasture_06, elephant_pasture_04, elephant_pasture_05, elephant_pasture_06, estate_main_02, estate_main_03, estate_main_04, estate_main_05, rice_field_01, silk_01, silk_02, silk_03, silk_04, silk_05, silk_06, stable_chariot_04, tea_01 |
| territory | 0 |  |
| progression | 88 | bath_03, bath_04, camel_pasture_04, camel_pasture_05, camel_pasture_06, courtyard_03, courtyard_04, elephant_pasture_04, elephant_pasture_05, elephant_pasture_06, estate_main_02, estate_main_03, estate_main_04, estate_main_05, grain_field_03, grain_field_04, grain_field_05, grain_field_06, grand_solar_03, grand_solar_04, grazing_land_04, grazing_land_05, grazing_land_06, guest_room_03, guest_room_04, guest_room_05, guest_room_06, horse_pasture_04, horse_pasture_05, horse_pasture_06, library_education_03, library_education_04, library_observatory_03, library_observatory_04, living_quarters_03, living_quarters_04, office_03, office_04, prison_03, prison_04, reception_hall_03, reception_hall_04, reception_hall_05, rice_field_01, rice_field_03, rice_field_04, rice_field_05, rice_field_06, servants_quarters_03, servants_quarters_04, silk_03, silk_04, silk_05, silk_06, stable_chariot_04, stable_chariot_05, stable_chariot_06, stable_grand_04, stable_grand_05, stable_grand_06, stable_kennel_04, stable_kennel_05, stable_kennel_06, storage_granary_03, storage_granary_04, storage_warehouse_03, storage_warehouse_04, tea_01, tea_03, tea_04, tea_05, tea_06, temple_crypt_04, temple_crypt_05, temple_crypt_06, temple_large_04, temple_large_05, temple_large_06, temple_monastery_04, temple_monastery_05, temple_monastery_06, temple_small_03, trophy_room_03, trophy_room_04, watchtower_03, watchtower_04, watchtower_05, watchtower_06 |
| government_or_status | 9 | cabinet_of_curiosities_01, cabinet_of_curiosities_02, cabinet_of_curiosities_03, reception_hall_01, reception_hall_02, reception_hall_03, reception_hall_04, reception_hall_05, temple_small_01 |
| faith | 3 | temple_monastery_04, temple_monastery_05, temple_monastery_06 |
| scripted_trigger | 39 | barracks_03, barracks_04, barracks_05, barracks_06, garden_fruit_04, garden_fruit_05, garden_fruit_06, garden_leisure_04, garden_leisure_05, garden_leisure_06, guardhouse_03, guardhouse_04, horse_pasture_04, horse_pasture_05, horse_pasture_06, market_03, market_04, market_05, market_06, olive_03, olive_04, olive_05, olive_06, vineyard_03, vineyard_04, vineyard_05, vineyard_06, workshop_carpenter_03, workshop_carpenter_04, workshop_carpenter_05, workshop_carpenter_06, workshop_mason_03, workshop_mason_04, workshop_mason_05, workshop_mason_06, workshop_textile_03, workshop_textile_04, workshop_textile_05, workshop_textile_06 |
| character_dynasty_or_house | 18 | cabinet_of_curiosities_01, cabinet_of_curiosities_02, cabinet_of_curiosities_03, grand_solar_01, grand_solar_02, grand_solar_03, grand_solar_04, reception_hall_01, reception_hall_02, reception_hall_03, reception_hall_04, reception_hall_05, silk_01, silk_02, silk_03, silk_04, silk_05, silk_06 |
| state_or_feature | 0 |  |

## `yurt`

Источник типа: `common\domiciles\types\00_domicile_types.txt:1955`

### Физические внешние линии

| Корневое здание | Конечных специализаций | Конечные здания | Ограничения корня |
|---|---:|---|---|
| character_warfare_yurt_01 | 1 | character_warfare_yurt_06 |  |
| court_yurt_01 | 1 | court_yurt_06 |  |
| family_yurt_01 | 1 | family_yurt_06 |  |
| herd_welfare_yurt_01 | 1 | herd_welfare_yurt_06 |  |
| mass_warfare_yurt_01 | 1 | mass_warfare_yurt_06 |  |
| mystical_yurt_01 | 1 | mystical_yurt_06 |  |
| trade_yurt_01 | 1 | trade_yurt_06 | government_or_status |

### Внешние развилки, переводимые во внутренние треки

| Общая внешняя часть | Уровень развилки | Специализации | Новых внутренних ячеек | Всего внутренних ячеек у родителя | Иконки различаются | Панорамы совпадают | Стратегия | Источник |
|---|---:|---|---:|---:|---|---|---|---|
| — | — | — | 0 | 0 | — | — | — | — |

### Уже внутренние развилки, требующие расщепления общей части

| Общая внутренняя часть | Родитель | Общий префикс | Специализации | Нужно параллельных ячеек | Стратегия | Источник |
|---|---|---|---|---:|---|---|
| — | — | — | — | 0 | — | — |

### Существующие требования внутренних ячеек

| Родительская линия | Нужно для всех ветвей | Текущий максимум | Дефицит |
|---|---:|---:|---:|
| character_warfare_yurt_01 | 5 | 5 | 0 |
| court_yurt_01 | 8 | 5 | 3 |
| family_yurt_01 | 8 | 5 | 3 |
| herd_welfare_yurt_01 | 9 | 5 | 4 |
| mass_warfare_yurt_01 | 6 | 5 | 1 |
| mystical_yurt_01 | 7 | 5 | 2 |
| trade_yurt_01 | 7 | 5 | 2 |
| yurt_main_01 | 15 | 5 | 10 |

### Все исходные точки ветвления

| Здание | Тип ячейки | Дочерние ветви |
|---|---|---|
| — | — | — |

### Условная доступность и кандидаты на взаимоисключение

- Зданий с `can_construct`/`can_construct_potential`: 120.
- Затронутых линий: 24.
- Линий с возможным взаимоисключением: 10.
- Линий, требующих ручной проверки культурных или территориальных условий: 10.
- Линий с пока не классифицированными условиями: 0.

| Линия | Тип | Внешняя опора | Категории-кандидаты | Условные здания | Извлечённые зависимости | Рекомендуемые действия | Ручная проверка |
|---|---|---|---|---|---|---|---|
| camel_yurt_01 | internal | herd_welfare_yurt_01 | territory | camel_yurt_01, camel_yurt_02, camel_yurt_03, camel_yurt_04, camel_yurt_05, camel_yurt_06 | terrains: desert | review_territory_condition_and_remove_only_track_exclusivity | да |
| forbearing_yurt_01 | internal | yurt_main_01 | culture_or_language | forbearing_yurt_01, forbearing_yurt_02, forbearing_yurt_03, forbearing_yurt_04, forbearing_yurt_05, forbearing_yurt_06 | culture_parameters: forbearing_internal_yurt_unlock; traits: patient | preserve_unrelated_vanilla_prerequisites, review_culture_condition_and_remove_only_track_exclusivity | да |
| goat_yurt_01 | internal | herd_welfare_yurt_01 | territory | goat_yurt_01, goat_yurt_02, goat_yurt_03, goat_yurt_04, goat_yurt_05, goat_yurt_06 | terrains: hills, mountains | review_territory_condition_and_remove_only_track_exclusivity | да |
| horse_breeder_yurt_01 | internal | yurt_main_01 | culture_or_language | horse_breeder_yurt_01, horse_breeder_yurt_02, horse_breeder_yurt_03, horse_breeder_yurt_04, horse_breeder_yurt_05, horse_breeder_yurt_06 | culture_parameters: horse_breeder_internal_yurt_unlock | review_culture_condition_and_remove_only_track_exclusivity | да |
| language_yurt_01 | internal | mystical_yurt_01 | culture_or_language | language_yurt_01, language_yurt_02, language_yurt_03, language_yurt_04, language_yurt_05, language_yurt_06 |  | review_culture_condition_and_remove_only_track_exclusivity | да |
| metalworkers_cultrad_yurt_01 | internal | yurt_main_01 | culture_or_language | metalworkers_cultrad_yurt_01, metalworkers_cultrad_yurt_02, metalworkers_cultrad_yurt_03, metalworkers_cultrad_yurt_04, metalworkers_cultrad_yurt_05, metalworkers_cultrad_yurt_06 | culture_parameters: metalworkers_internal_yurt_unlock | review_culture_condition_and_remove_only_track_exclusivity | да |
| reindeer_yurt_01 | internal | herd_welfare_yurt_01 | territory | reindeer_yurt_01, reindeer_yurt_02, reindeer_yurt_03, reindeer_yurt_04, reindeer_yurt_05, reindeer_yurt_06 | terrains: forest, taiga | review_territory_condition_and_remove_only_track_exclusivity | да |
| sheep_yurt_01 | internal | herd_welfare_yurt_01 | territory | sheep_yurt_01, sheep_yurt_02, sheep_yurt_03, sheep_yurt_04, sheep_yurt_05, sheep_yurt_06 | terrains: plains, steppe | review_territory_condition_and_remove_only_track_exclusivity | да |
| stalwart_defenders_yurt_01 | internal | yurt_main_01 | culture_or_language | stalwart_defenders_yurt_01, stalwart_defenders_yurt_02, stalwart_defenders_yurt_03, stalwart_defenders_yurt_04, stalwart_defenders_yurt_05, stalwart_defenders_yurt_06 | culture_parameters: stalwart_defenders_internal_yurt_unlock | review_culture_condition_and_remove_only_track_exclusivity | да |
| zealous_people_yurt_01 | internal | yurt_main_01 | culture_or_language | zealous_people_yurt_01, zealous_people_yurt_02, zealous_people_yurt_03, zealous_people_yurt_04, zealous_people_yurt_05, zealous_people_yurt_06 | culture_parameters: zealous_people_internal_yurt_unlock | review_culture_condition_and_remove_only_track_exclusivity | да |

Полные исходные блоки условий и поключевые профили зданий сохранены в JSON. Культурные и территориальные совпадения являются кандидатами, а не автоматически удаляемыми ограничениями: сначала следует отделить взаимоисключение специализаций от обычных требований прогресса.

### Классифицированные ограничения

| Категория | Количество | Здания |
|---|---:|---|
| camp_purpose | 0 |  |
| realm_law | 4 | yurt_main_03, yurt_main_04, yurt_main_05, yurt_main_06 |
| culture_or_language | 36 | forbearing_yurt_01, forbearing_yurt_02, forbearing_yurt_03, forbearing_yurt_04, forbearing_yurt_05, forbearing_yurt_06, horse_breeder_yurt_01, horse_breeder_yurt_02, horse_breeder_yurt_03, horse_breeder_yurt_04, horse_breeder_yurt_05, horse_breeder_yurt_06, language_yurt_01, language_yurt_02, language_yurt_03, language_yurt_04, language_yurt_05, language_yurt_06, metalworkers_cultrad_yurt_01, metalworkers_cultrad_yurt_02, metalworkers_cultrad_yurt_03, metalworkers_cultrad_yurt_04, metalworkers_cultrad_yurt_05, metalworkers_cultrad_yurt_06, stalwart_defenders_yurt_01, stalwart_defenders_yurt_02, stalwart_defenders_yurt_03, stalwart_defenders_yurt_04, stalwart_defenders_yurt_05, stalwart_defenders_yurt_06, zealous_people_yurt_01, zealous_people_yurt_02, zealous_people_yurt_03, zealous_people_yurt_04, zealous_people_yurt_05, zealous_people_yurt_06 |
| territory | 24 | camel_yurt_01, camel_yurt_02, camel_yurt_03, camel_yurt_04, camel_yurt_05, camel_yurt_06, goat_yurt_01, goat_yurt_02, goat_yurt_03, goat_yurt_04, goat_yurt_05, goat_yurt_06, reindeer_yurt_01, reindeer_yurt_02, reindeer_yurt_03, reindeer_yurt_04, reindeer_yurt_05, reindeer_yurt_06, sheep_yurt_01, sheep_yurt_02, sheep_yurt_03, sheep_yurt_04, sheep_yurt_05, sheep_yurt_06 |
| progression | 20 | character_warfare_yurt_04, character_warfare_yurt_05, character_warfare_yurt_06, court_yurt_04, court_yurt_05, court_yurt_06, family_yurt_04, family_yurt_05, family_yurt_06, herd_welfare_yurt_04, herd_welfare_yurt_05, herd_welfare_yurt_06, mass_warfare_yurt_04, mass_warfare_yurt_05, mass_warfare_yurt_06, mystical_yurt_04, mystical_yurt_05, mystical_yurt_06, wet_nurse_yurt_01, wet_nurse_yurt_02 |
| government_or_status | 22 | fishing_yurt_01, fishing_yurt_02, fishing_yurt_03, fishing_yurt_04, fishing_yurt_05, fishing_yurt_06, legalistic_yurt_01, legalistic_yurt_02, legalistic_yurt_03, legalistic_yurt_04, legalistic_yurt_05, legalistic_yurt_06, trade_yurt_01, trade_yurt_02, trade_yurt_03, trade_yurt_04, trade_yurt_05, trade_yurt_06, yurt_main_03, yurt_main_04, yurt_main_05, yurt_main_06 |
| faith | 0 |  |
| scripted_trigger | 0 |  |
| character_dynasty_or_house | 30 | fishing_yurt_01, fishing_yurt_02, fishing_yurt_03, fishing_yurt_04, fishing_yurt_05, fishing_yurt_06, forbearing_yurt_01, forbearing_yurt_02, forbearing_yurt_03, forbearing_yurt_04, forbearing_yurt_05, forbearing_yurt_06, loyal_soldiers_yurt_01, loyal_soldiers_yurt_02, loyal_soldiers_yurt_03, loyal_soldiers_yurt_04, loyal_soldiers_yurt_05, loyal_soldiers_yurt_06, paiza_metal_trade_yurt_01, paiza_metal_trade_yurt_02, paiza_metal_trade_yurt_03, paiza_metal_trade_yurt_04, paiza_metal_trade_yurt_05, paiza_metal_trade_yurt_06, sorcerous_metallurgy_yurt_01, sorcerous_metallurgy_yurt_02, sorcerous_metallurgy_yurt_03, sorcerous_metallurgy_yurt_04, sorcerous_metallurgy_yurt_05, sorcerous_metallurgy_yurt_06 |
| state_or_feature | 0 |  |

## `east_asian_estate`

Источник типа: `common\domiciles\types\00_domicile_types.txt:2101`

### Физические внешние линии

| Корневое здание | Конечных специализаций | Конечные здания | Ограничения корня |
|---|---:|---|---|
| east_asian_estate_ancestral_shrine_01 | 1 | east_asian_estate_ancestral_shrine_06 |  |
| east_asian_estate_barracks_01 | 1 | east_asian_estate_barracks_06 |  |
| east_asian_estate_garden_01 | 2 | east_asian_estate_garden_fruit_06, east_asian_estate_garden_leisure_06 |  |
| east_asian_estate_gate_01 | 1 | east_asian_estate_gate_06 | character_dynasty_or_house |
| east_asian_estate_grazing_land_01 | 4 | east_asian_estate_camel_pasture_06, east_asian_estate_elephant_pasture_06, east_asian_estate_grazing_land_06, east_asian_estate_horse_pasture_06 |  |
| east_asian_estate_health_01 | 1 | east_asian_estate_health_06 |  |
| east_asian_estate_market_01 | 1 | east_asian_estate_market_06 |  |
| east_asian_estate_rice_field_01 | 1 | east_asian_estate_rice_field_06 |  |
| east_asian_estate_silk_01 | 1 | east_asian_estate_silk_06 | character_dynasty_or_house, culture_or_language |
| east_asian_estate_stable_01 | 2 | east_asian_estate_stable_grand_06, east_asian_estate_stable_kennel_06 |  |
| east_asian_estate_storage_01 | 2 | east_asian_estate_storage_granary_06, east_asian_estate_storage_warehouse_06 |  |
| east_asian_estate_tea_01 | 1 | east_asian_estate_tea_06 |  |
| east_asian_estate_temple_01 | 1 | east_asian_estate_temple_06 |  |
| east_asian_estate_watchtower_01 | 1 | east_asian_estate_watchtower_06 |  |
| east_asian_estate_workshop_01 | 3 | east_asian_estate_workshop_carpenter_06, east_asian_estate_workshop_mason_06, east_asian_estate_workshop_textile_06 |  |

### Внешние развилки, переводимые во внутренние треки

| Общая внешняя часть | Уровень развилки | Специализации | Новых внутренних ячеек | Всего внутренних ячеек у родителя | Иконки различаются | Панорамы совпадают | Стратегия | Источник |
|---|---:|---|---:|---:|---|---|---|---|
| east_asian_estate_garden_03 | 3 | east_asian_estate_garden_fruit_04, east_asian_estate_garden_leisure_04 | 2 | 2 | да | да | internalize_external_specialization_tails | common\domiciles\buildings\00_chinese_estate_buildings.txt:7007 |
| east_asian_estate_grazing_land_03 | 3 | east_asian_estate_camel_pasture_04, east_asian_estate_elephant_pasture_04, east_asian_estate_grazing_land_04, east_asian_estate_horse_pasture_04 | 4 | 4 | да | да | internalize_external_specialization_tails | common\domiciles\buildings\00_chinese_estate_buildings.txt:9258 |
| east_asian_estate_stable_03 | 3 | east_asian_estate_stable_grand_04, east_asian_estate_stable_kennel_04 | 2 | 2 | да | да | internalize_external_specialization_tails | common\domiciles\buildings\00_chinese_estate_buildings.txt:7713 |
| east_asian_estate_storage_02 | 2 | east_asian_estate_storage_granary_03, east_asian_estate_storage_warehouse_03 | 2 | 2 | да | да | internalize_external_specialization_tails | common\domiciles\buildings\00_chinese_estate_buildings.txt:8684 |
| east_asian_estate_workshop_02 | 2 | east_asian_estate_workshop_carpenter_03, east_asian_estate_workshop_mason_03, east_asian_estate_workshop_textile_03 | 3 | 3 | да | да | internalize_external_specialization_tails | common\domiciles\buildings\00_chinese_estate_buildings.txt:8098 |

#### Специализации после `east_asian_estate_garden_03`

| Корень специализации | Стартовый уровень | Здания, переводимые во внутренний тип | Листья | Иконки корня | Панорамы корня |
|---|---:|---|---|---|---|
| east_asian_estate_garden_fruit_04 | 4 | east_asian_estate_garden_fruit_04, east_asian_estate_garden_fruit_05, east_asian_estate_garden_fruit_06 | east_asian_estate_garden_fruit_06 | gfx/interface/icons/domicile_building/domicile_building_fruit_garden.dds | gfx/interface/window_domiciles/estate_building_garden_chinese.dds |
| east_asian_estate_garden_leisure_04 | 4 | east_asian_estate_garden_leisure_04, east_asian_estate_garden_leisure_05, east_asian_estate_garden_leisure_06 | east_asian_estate_garden_leisure_06 | gfx/interface/icons/domicile_building/domicile_building_leisure_garden.dds | gfx/interface/window_domiciles/estate_building_garden_chinese.dds |

#### Специализации после `east_asian_estate_grazing_land_03`

| Корень специализации | Стартовый уровень | Здания, переводимые во внутренний тип | Листья | Иконки корня | Панорамы корня |
|---|---:|---|---|---|---|
| east_asian_estate_camel_pasture_04 | 4 | east_asian_estate_camel_pasture_04, east_asian_estate_camel_pasture_05, east_asian_estate_camel_pasture_06 | east_asian_estate_camel_pasture_06 | gfx/interface/icons/domicile_building/domicile_building_camel_run.dds | gfx/interface/window_domiciles/estate_building_horse_pastures_japanese.dds |
| east_asian_estate_elephant_pasture_04 | 4 | east_asian_estate_elephant_pasture_04, east_asian_estate_elephant_pasture_05, east_asian_estate_elephant_pasture_06 | east_asian_estate_elephant_pasture_06 | gfx/interface/icons/domicile_building/domicile_building_elephantry_reserves.dds | gfx/interface/window_domiciles/estate_building_horse_pastures_japanese.dds |
| east_asian_estate_grazing_land_04 | 4 | east_asian_estate_grazing_land_04, east_asian_estate_grazing_land_05, east_asian_estate_grazing_land_06 | east_asian_estate_grazing_land_06 | gfx/interface/icons/domicile_building/domicile_building_horse_run.dds | gfx/interface/window_domiciles/estate_building_horse_pastures_japanese.dds |
| east_asian_estate_horse_pasture_04 | 4 | east_asian_estate_horse_pasture_04, east_asian_estate_horse_pasture_05, east_asian_estate_horse_pasture_06 | east_asian_estate_horse_pasture_06 | gfx/interface/icons/domicile_building/domicile_building_life_in_the_saddle.dds | gfx/interface/window_domiciles/estate_building_horse_pastures_japanese.dds |

#### Специализации после `east_asian_estate_stable_03`

| Корень специализации | Стартовый уровень | Здания, переводимые во внутренний тип | Листья | Иконки корня | Панорамы корня |
|---|---:|---|---|---|---|
| east_asian_estate_stable_grand_04 | 4 | east_asian_estate_stable_grand_04, east_asian_estate_stable_grand_05, east_asian_estate_stable_grand_06 | east_asian_estate_stable_grand_06 | gfx/interface/icons/domicile_building/domicile_building_grand_stable.dds | gfx/interface/window_domiciles/estate_building_stable_china.dds |
| east_asian_estate_stable_kennel_04 | 4 | east_asian_estate_stable_kennel_04, east_asian_estate_stable_kennel_05, east_asian_estate_stable_kennel_06 | east_asian_estate_stable_kennel_06 | gfx/interface/icons/domicile_building/domicile_building_kennel.dds | gfx/interface/window_domiciles/estate_building_stable_china.dds |

#### Специализации после `east_asian_estate_storage_02`

| Корень специализации | Стартовый уровень | Здания, переводимые во внутренний тип | Листья | Иконки корня | Панорамы корня |
|---|---:|---|---|---|---|
| east_asian_estate_storage_granary_03 | 3 | east_asian_estate_storage_granary_03, east_asian_estate_storage_granary_04, east_asian_estate_storage_granary_05, east_asian_estate_storage_granary_06 | east_asian_estate_storage_granary_06 | gfx/interface/icons/domicile_building/domicile_building_granary.dds | gfx/interface/window_domiciles/estate_building_storage_chinese.dds |
| east_asian_estate_storage_warehouse_03 | 3 | east_asian_estate_storage_warehouse_03, east_asian_estate_storage_warehouse_04, east_asian_estate_storage_warehouse_05, east_asian_estate_storage_warehouse_06 | east_asian_estate_storage_warehouse_06 | gfx/interface/icons/domicile_building/domicile_building_warehouse.dds | gfx/interface/window_domiciles/estate_building_storage_chinese.dds |

#### Специализации после `east_asian_estate_workshop_02`

| Корень специализации | Стартовый уровень | Здания, переводимые во внутренний тип | Листья | Иконки корня | Панорамы корня |
|---|---:|---|---|---|---|
| east_asian_estate_workshop_carpenter_03 | 3 | east_asian_estate_workshop_carpenter_03, east_asian_estate_workshop_carpenter_04, east_asian_estate_workshop_carpenter_05, east_asian_estate_workshop_carpenter_06 | east_asian_estate_workshop_carpenter_06 | gfx/interface/icons/domicile_building/domicile_building_carpenter.dds | gfx/interface/window_domiciles/estate_building_workshop_chinese.dds |
| east_asian_estate_workshop_mason_03 | 3 | east_asian_estate_workshop_mason_03, east_asian_estate_workshop_mason_04, east_asian_estate_workshop_mason_05, east_asian_estate_workshop_mason_06 | east_asian_estate_workshop_mason_06 | gfx/interface/icons/domicile_building/domicile_building_mason.dds | gfx/interface/window_domiciles/estate_building_workshop_chinese.dds |
| east_asian_estate_workshop_textile_03 | 3 | east_asian_estate_workshop_textile_03, east_asian_estate_workshop_textile_04, east_asian_estate_workshop_textile_05, east_asian_estate_workshop_textile_06 | east_asian_estate_workshop_textile_06 | gfx/interface/icons/domicile_building/domicile_building_textile.dds | gfx/interface/window_domiciles/estate_building_workshop_chinese.dds |

### Уже внутренние развилки, требующие расщепления общей части

| Общая внутренняя часть | Родитель | Общий префикс | Специализации | Нужно параллельных ячеек | Стратегия | Источник |
|---|---|---|---|---:|---|---|
| — | — | — | — | 0 | — | — |

### Существующие требования внутренних ячеек

| Родительская линия | Нужно для всех ветвей | Текущий максимум | Дефицит |
|---|---:|---:|---:|
| east_asian_estate_ancestral_shrine_01 | 5 | 4 | 1 |
| east_asian_estate_barracks_01 | 6 | 4 | 2 |
| east_asian_estate_garden_01 | 6 | 4 | 2 |
| east_asian_estate_gate_01 | 5 | 4 | 1 |
| east_asian_estate_grazing_land_01 | 5 | 4 | 1 |
| east_asian_estate_health_01 | 5 | 4 | 1 |
| east_asian_estate_main_01 | 26 | 15 | 11 |
| east_asian_estate_market_01 | 6 | 4 | 2 |
| east_asian_estate_rice_field_01 | 6 | 4 | 2 |
| east_asian_estate_silk_01 | 5 | 4 | 1 |
| east_asian_estate_stable_01 | 5 | 4 | 1 |
| east_asian_estate_storage_01 | 6 | 4 | 2 |
| east_asian_estate_tea_01 | 5 | 4 | 1 |
| east_asian_estate_temple_01 | 5 | 4 | 1 |
| east_asian_estate_watchtower_01 | 5 | 4 | 1 |
| east_asian_estate_workshop_01 | 5 | 4 | 1 |

### Все исходные точки ветвления

| Здание | Тип ячейки | Дочерние ветви |
|---|---|---|
| east_asian_estate_garden_03 | external | east_asian_estate_garden_fruit_04, east_asian_estate_garden_leisure_04 |
| east_asian_estate_grazing_land_03 | external | east_asian_estate_camel_pasture_04, east_asian_estate_elephant_pasture_04, east_asian_estate_grazing_land_04, east_asian_estate_horse_pasture_04 |
| east_asian_estate_stable_03 | external | east_asian_estate_stable_grand_04, east_asian_estate_stable_kennel_04 |
| east_asian_estate_storage_02 | external | east_asian_estate_storage_granary_03, east_asian_estate_storage_warehouse_03 |
| east_asian_estate_workshop_02 | external | east_asian_estate_workshop_carpenter_03, east_asian_estate_workshop_mason_03, east_asian_estate_workshop_textile_03 |

### Условная доступность и кандидаты на взаимоисключение

- Зданий с `can_construct`/`can_construct_potential`: 337.
- Затронутых линий: 119.
- Линий с возможным взаимоисключением: 5.
- Линий, требующих ручной проверки культурных или территориальных условий: 5.
- Линий с пока не классифицированными условиями: 0.

| Линия | Тип | Внешняя опора | Категории-кандидаты | Условные здания | Извлечённые зависимости | Рекомендуемые действия | Ручная проверка |
|---|---|---|---|---|---|---|---|
| east_asian_estate_grazing_land_01 | external | east_asian_estate_grazing_land_01 | culture_or_language | east_asian_estate_camel_pasture_04, east_asian_estate_camel_pasture_05, east_asian_estate_camel_pasture_06, east_asian_estate_elephant_pasture_04, east_asian_estate_elephant_pasture_05, east_asian_estate_elephant_pasture_06, east_asian_estate_grazing_land_03, east_asian_estate_grazing_land_04, east_asian_estate_grazing_land_05, east_asian_estate_grazing_land_06, east_asian_estate_horse_pasture_04, east_asian_estate_horse_pasture_05, east_asian_estate_horse_pasture_06 | innovations: innovation_elephantry, innovation_war_camels; domicile_buildings: east_asian_estate_main_02, east_asian_estate_main_03, east_asian_estate_main_04, east_asian_estate_main_05; scripted_triggers: can_recruit_archer_cavalry_trigger | preserve_unrelated_vanilla_prerequisites, review_culture_condition_and_remove_only_track_exclusivity | да |
| east_asian_estate_silk_01 | external | east_asian_estate_silk_01 | culture_or_language | east_asian_estate_silk_01, east_asian_estate_silk_02, east_asian_estate_silk_03, east_asian_estate_silk_04, east_asian_estate_silk_05, east_asian_estate_silk_06 | culture_parameters: unlocks_silk_buildings_parameter; domicile_buildings: east_asian_estate_main_02, east_asian_estate_main_03, east_asian_estate_main_04, east_asian_estate_main_05 | preserve_unrelated_vanilla_prerequisites, review_culture_condition_and_remove_only_track_exclusivity | да |
| east_asian_estate_gunpowder_storage_01 | internal | east_asian_estate_watchtower_01 | culture_or_language | east_asian_estate_gunpowder_storage_01, east_asian_estate_gunpowder_storage_03, east_asian_estate_gunpowder_storage_04 | innovations: innovation_fire_medicine; domicile_buildings: east_asian_estate_main_02, east_asian_estate_main_03 | preserve_unrelated_vanilla_prerequisites, review_culture_condition_and_remove_only_track_exclusivity | да |
| east_asian_estate_lacquer_studio_01 | internal | east_asian_estate_workshop_01 | culture_or_language | east_asian_estate_lacquer_studio_01, east_asian_estate_lacquer_studio_03, east_asian_estate_lacquer_studio_04 | innovations: innovation_lacquered_armor; domicile_buildings: east_asian_estate_main_02, east_asian_estate_main_03 | preserve_unrelated_vanilla_prerequisites, review_culture_condition_and_remove_only_track_exclusivity | да |
| east_asian_estate_main_01 | main | east_asian_estate_main_01 | culture_or_language | east_asian_estate_main_02, east_asian_estate_main_03, east_asian_estate_main_04, east_asian_estate_main_05 | innovations: innovation_city_planning, innovation_cranes, innovation_development_03, innovation_manorialism | preserve_unrelated_vanilla_prerequisites, review_culture_condition_and_remove_only_track_exclusivity | да |

Полные исходные блоки условий и поключевые профили зданий сохранены в JSON. Культурные и территориальные совпадения являются кандидатами, а не автоматически удаляемыми ограничениями: сначала следует отделить взаимоисключение специализаций от обычных требований прогресса.

### Классифицированные ограничения

| Категория | Количество | Здания |
|---|---:|---|
| camp_purpose | 0 |  |
| realm_law | 0 |  |
| culture_or_language | 18 | east_asian_estate_camel_pasture_04, east_asian_estate_camel_pasture_05, east_asian_estate_camel_pasture_06, east_asian_estate_elephant_pasture_04, east_asian_estate_elephant_pasture_05, east_asian_estate_elephant_pasture_06, east_asian_estate_gunpowder_storage_01, east_asian_estate_lacquer_studio_01, east_asian_estate_main_02, east_asian_estate_main_03, east_asian_estate_main_04, east_asian_estate_main_05, east_asian_estate_silk_01, east_asian_estate_silk_02, east_asian_estate_silk_03, east_asian_estate_silk_04, east_asian_estate_silk_05, east_asian_estate_silk_06 |
| territory | 0 |  |
| progression | 291 | east_asian_estate_ancestral_orchard_03, east_asian_estate_ancestral_orchard_04, east_asian_estate_ancestral_shrine_03, east_asian_estate_ancestral_shrine_04, east_asian_estate_ancestral_shrine_05, east_asian_estate_ancestral_shrine_06, east_asian_estate_archive_03, east_asian_estate_archive_04, east_asian_estate_armorer_03, east_asian_estate_armorer_04, east_asian_estate_aviary_03, east_asian_estate_aviary_04, east_asian_estate_barracks_03, east_asian_estate_barracks_04, east_asian_estate_barracks_05, east_asian_estate_barracks_06, east_asian_estate_bath_03, east_asian_estate_bath_04, east_asian_estate_bell_drum_tower_03, east_asian_estate_bell_drum_tower_04, east_asian_estate_block_printing_hall_03, east_asian_estate_block_printing_hall_04, east_asian_estate_bloodline_records_office_03, east_asian_estate_bloodline_records_office_04, east_asian_estate_buffer_stock_granary_03, east_asian_estate_buffer_stock_granary_04, east_asian_estate_camel_pasture_04, east_asian_estate_camel_pasture_05, east_asian_estate_camel_pasture_06, east_asian_estate_cartography_office_03, east_asian_estate_cartography_office_04, east_asian_estate_cellar_cave_03, east_asian_estate_cellar_cave_04, east_asian_estate_ceramics_kiln_03, east_asian_estate_ceramics_kiln_04, east_asian_estate_chanting_hall_03, east_asian_estate_chanting_hall_04, east_asian_estate_clerks_hall_03, east_asian_estate_clerks_hall_04, east_asian_estate_commander_study_03, east_asian_estate_commander_study_04, east_asian_estate_courier_posthouse_03, east_asian_estate_courier_posthouse_04, east_asian_estate_courtyard_03, east_asian_estate_courtyard_04, east_asian_estate_crossbow_storage_03, east_asian_estate_crossbow_storage_04, east_asian_estate_disciples_hall_03, east_asian_estate_disciples_hall_04, east_asian_estate_donation_box_03, east_asian_estate_donation_box_04, east_asian_estate_drafting_room_03, east_asian_estate_drafting_room_04, east_asian_estate_drill_yard_03, east_asian_estate_drill_yard_04, east_asian_estate_drying_loft_03, east_asian_estate_drying_loft_04, east_asian_estate_dye_works_03, east_asian_estate_dye_works_04, east_asian_estate_elephant_pasture_04, east_asian_estate_elephant_pasture_05, east_asian_estate_elephant_pasture_06, east_asian_estate_ever_normal_granaries_03, east_asian_estate_ever_normal_granaries_04, east_asian_estate_examination_room_03, east_asian_estate_examination_room_04, east_asian_estate_farriers_office_03, east_asian_estate_farriers_office_04, east_asian_estate_field_surgeon_cart_03, east_asian_estate_field_surgeon_cart_04, east_asian_estate_field_surveyors_office_03, east_asian_estate_field_surveyors_office_04, east_asian_estate_fire_brigade_03, east_asian_estate_fire_brigade_04, east_asian_estate_foaling_pens_03, east_asian_estate_foaling_pens_04, east_asian_estate_fodder_reserves_03, east_asian_estate_fodder_reserves_04, east_asian_estate_four_gentlemen_03, east_asian_estate_four_gentlemen_04, east_asian_estate_fruit_trees_03, east_asian_estate_fruit_trees_04, east_asian_estate_garden_03, east_asian_estate_garden_fruit_04, east_asian_estate_garden_fruit_05, east_asian_estate_garden_fruit_06, east_asian_estate_garden_leisure_04, east_asian_estate_garden_leisure_05, east_asian_estate_garden_leisure_06, east_asian_estate_gate_plaques_03, east_asian_estate_gate_plaques_04, east_asian_estate_genealogy_hall_03, east_asian_estate_genealogy_hall_04, east_asian_estate_grading_hall_03, east_asian_estate_grading_hall_04, east_asian_estate_grazing_land_03, east_asian_estate_grazing_land_04, east_asian_estate_grazing_land_05, east_asian_estate_grazing_land_06, east_asian_estate_guest_room_03, east_asian_estate_guest_room_04, east_asian_estate_guesthouse_03, east_asian_estate_guesthouse_04, east_asian_estate_gunpowder_storage_01, east_asian_estate_gunpowder_storage_03, east_asian_estate_gunpowder_storage_04, east_asian_estate_health_03, east_asian_estate_health_04, east_asian_estate_health_05, east_asian_estate_health_06, east_asian_estate_herb_drying_terrace_03, east_asian_estate_herb_drying_terrace_04, east_asian_estate_history_school_03, east_asian_estate_history_school_04, east_asian_estate_horse_pasture_04, east_asian_estate_horse_pasture_05, east_asian_estate_horse_pasture_06, east_asian_estate_hot_baths_03, east_asian_estate_hot_baths_04, east_asian_estate_ink_brush_makers_03, east_asian_estate_ink_brush_makers_04, east_asian_estate_inspection_office_03, east_asian_estate_inspection_office_04, east_asian_estate_jar_kiln_03, east_asian_estate_jar_kiln_04, east_asian_estate_lacquer_studio_01, east_asian_estate_lacquer_studio_03, east_asian_estate_lacquer_studio_04, east_asian_estate_leatherworks_03, east_asian_estate_leatherworks_04, east_asian_estate_lecture_pavilion_03, east_asian_estate_lecture_pavilion_04, east_asian_estate_ledger_office_03, east_asian_estate_ledger_office_04, east_asian_estate_library_education_03, east_asian_estate_library_education_04, east_asian_estate_living_quarters_03, east_asian_estate_living_quarters_04, east_asian_estate_lotus_pond_03, east_asian_estate_lotus_pond_04, east_asian_estate_main_02, east_asian_estate_main_03, east_asian_estate_main_04, east_asian_estate_main_05, east_asian_estate_market_03, east_asian_estate_market_04, east_asian_estate_market_05, east_asian_estate_market_06, east_asian_estate_medical_library_03, east_asian_estate_medical_library_04, east_asian_estate_meeting_houses_03, east_asian_estate_meeting_houses_04, east_asian_estate_memorial_archway_03, east_asian_estate_memorial_archway_04, east_asian_estate_militia_muster_green_03, east_asian_estate_militia_muster_green_04, east_asian_estate_millhouse_03, east_asian_estate_millhouse_04, east_asian_estate_minister_office_03, east_asian_estate_minister_office_04, east_asian_estate_movement_study_03, east_asian_estate_movement_study_04, east_asian_estate_mulberry_nursery_03, east_asian_estate_mulberry_nursery_04, east_asian_estate_night_watch_03, east_asian_estate_night_watch_04, east_asian_estate_office_03, east_asian_estate_office_04, east_asian_estate_paper_mill_03, east_asian_estate_paper_mill_04, east_asian_estate_pass_office_03, east_asian_estate_pass_office_04, east_asian_estate_pavilion_03, east_asian_estate_pavilion_04, east_asian_estate_performance_stage_03, east_asian_estate_performance_stage_04, east_asian_estate_pharmacy_03, east_asian_estate_pharmacy_04, east_asian_estate_prison_03, east_asian_estate_prison_04, east_asian_estate_quartermaster_03, east_asian_estate_quartermaster_04, east_asian_estate_ration_wine_stores_03, east_asian_estate_ration_wine_stores_04, east_asian_estate_reception_hall_03, east_asian_estate_reception_hall_05, east_asian_estate_regular_patrols_03, east_asian_estate_regular_patrols_04, east_asian_estate_revenue_audit_desk_03, east_asian_estate_revenue_audit_desk_04, east_asian_estate_rice_field_03, east_asian_estate_rice_field_04, east_asian_estate_rice_field_05, east_asian_estate_rice_field_06, east_asian_estate_rice_fish_duck_ponds_03, east_asian_estate_rice_fish_duck_ponds_04, east_asian_estate_riding_arena_03, east_asian_estate_riding_arena_04, east_asian_estate_rites_office_03, east_asian_estate_rites_office_04, east_asian_estate_roasting_house_03, east_asian_estate_roasting_house_04, east_asian_estate_rotation_paddocks_03, east_asian_estate_rotation_paddocks_04, east_asian_estate_salt_lick_terraces_03, east_asian_estate_salt_lick_terraces_04, east_asian_estate_scholars_rocks_03, east_asian_estate_scholars_rocks_04, east_asian_estate_seasonal_shelters_03, east_asian_estate_seasonal_shelters_04, east_asian_estate_sergeants_school_03, east_asian_estate_sergeants_school_04, east_asian_estate_sericulture_school_03, east_asian_estate_sericulture_school_04, east_asian_estate_servants_quarters_03, east_asian_estate_servants_quarters_04, east_asian_estate_signal_fires_03, east_asian_estate_signal_fires_04, east_asian_estate_silk_03, east_asian_estate_silk_04, east_asian_estate_silk_05, east_asian_estate_silk_06, east_asian_estate_silk_storage_03, east_asian_estate_silk_storage_04, east_asian_estate_stable_03, east_asian_estate_stable_grand_04, east_asian_estate_stable_grand_05, east_asian_estate_stable_grand_06, east_asian_estate_stable_kennel_04, east_asian_estate_stable_kennel_05, east_asian_estate_stable_kennel_06, east_asian_estate_storage_granary_03, east_asian_estate_storage_granary_04, east_asian_estate_storage_granary_05, east_asian_estate_storage_granary_06, east_asian_estate_storage_warehouse_03, east_asian_estate_storage_warehouse_04, east_asian_estate_storage_warehouse_05, east_asian_estate_storage_warehouse_06, east_asian_estate_study_03, east_asian_estate_study_04, east_asian_estate_taxation_03, east_asian_estate_taxation_04, east_asian_estate_tea_horse_road_office_03, east_asian_estate_tea_horse_road_office_04, east_asian_estate_tea_tax_office_03, east_asian_estate_tea_tax_office_04, east_asian_estate_teahouse_03, east_asian_estate_teahouse_04, east_asian_estate_temple_03, east_asian_estate_temple_04, east_asian_estate_temple_05, east_asian_estate_temple_06, east_asian_estate_temple_land_office_03, east_asian_estate_temple_land_office_04, east_asian_estate_veterans_hall_03, east_asian_estate_veterans_hall_04, east_asian_estate_veterinary_shed_03, east_asian_estate_veterinary_shed_04, east_asian_estate_vintner_halls_03, east_asian_estate_vintner_halls_04, east_asian_estate_watchtower_03, east_asian_estate_watchtower_04, east_asian_estate_watchtower_05, east_asian_estate_watchtower_06, east_asian_estate_water_clock_room_03, east_asian_estate_water_clock_room_04, east_asian_estate_watering_ditches_03, east_asian_estate_watering_ditches_04, east_asian_estate_waterways_office_03, east_asian_estate_waterways_office_04, east_asian_estate_weighing_house_03, east_asian_estate_weighing_house_04, east_asian_estate_weights_measures_bench_03, east_asian_estate_weights_measures_bench_04, east_asian_estate_wine_press_03, east_asian_estate_wine_press_04, east_asian_estate_workshop_carpenter_03, east_asian_estate_workshop_carpenter_04, east_asian_estate_workshop_carpenter_05, east_asian_estate_workshop_carpenter_06, east_asian_estate_workshop_mason_03, east_asian_estate_workshop_mason_04, east_asian_estate_workshop_mason_05, east_asian_estate_workshop_mason_06, east_asian_estate_workshop_textile_03, east_asian_estate_workshop_textile_04, east_asian_estate_workshop_textile_05, east_asian_estate_workshop_textile_06, east_asian_estate_xuan_paper_stores_03, east_asian_estate_xuan_paper_stores_04 |
| government_or_status | 31 | east_asian_estate_armorer_01, east_asian_estate_bell_drum_tower_01, east_asian_estate_cabinet_of_curiosities_01, east_asian_estate_cartography_office_01, east_asian_estate_ceramics_kiln_01, east_asian_estate_commander_study_01, east_asian_estate_commander_study_02, east_asian_estate_commander_study_03, east_asian_estate_crossbow_storage_01, east_asian_estate_drill_yard_01, east_asian_estate_field_surgeon_cart_01, east_asian_estate_foaling_pens_01, east_asian_estate_jar_kiln_01, east_asian_estate_leatherworks_01, east_asian_estate_militia_muster_green_01, east_asian_estate_millhouse_01, east_asian_estate_minister_office_01, east_asian_estate_office_01, east_asian_estate_office_02, east_asian_estate_office_03, east_asian_estate_pass_office_01, east_asian_estate_ration_wine_stores_01, east_asian_estate_rites_office_01, east_asian_estate_rotation_paddocks_01, east_asian_estate_salt_lick_terraces_01, east_asian_estate_seasonal_shelters_01, east_asian_estate_sergeants_school_01, east_asian_estate_signal_fires_01, east_asian_estate_tea_horse_road_office_01, east_asian_estate_waterways_office_01, east_asian_estate_weights_measures_bench_01 |
| faith | 0 |  |
| scripted_trigger | 4 | east_asian_estate_horse_pasture_04, east_asian_estate_horse_pasture_05, east_asian_estate_horse_pasture_06, east_asian_estate_minister_office_01 |
| character_dynasty_or_house | 18 | east_asian_estate_archive_01, east_asian_estate_cabinet_of_curiosities_01, east_asian_estate_cabinet_of_curiosities_02, east_asian_estate_cabinet_of_curiosities_03, east_asian_estate_gate_01, east_asian_estate_gate_02, east_asian_estate_gate_03, east_asian_estate_gate_04, east_asian_estate_gate_05, east_asian_estate_gate_06, east_asian_estate_silk_01, east_asian_estate_silk_02, east_asian_estate_silk_03, east_asian_estate_silk_04, east_asian_estate_silk_05, east_asian_estate_silk_06, east_asian_estate_tea_tax_office_01, east_asian_estate_temple_land_office_01 |
| state_or_feature | 9 | east_asian_estate_gate_02, east_asian_estate_gate_03, east_asian_estate_gate_04, east_asian_estate_gate_05, east_asian_estate_gate_06, east_asian_estate_guesthouse_01, east_asian_estate_meeting_houses_01, east_asian_estate_movement_study_01, east_asian_estate_teahouse_01 |

## `japanese_manor`

Источник типа: `common\domiciles\types\10_tgp_japan_domicile_types.txt:1`

### Физические внешние линии

| Корневое здание | Конечных специализаций | Конечные здания | Ограничения корня |
|---|---:|---|---|
| japanese_archive_01 | 1 | japanese_archive_06 | character_dynasty_or_house, government_or_status |
| japanese_armory_01 | 1 | japanese_armory_06 | character_dynasty_or_house |
| japanese_brewery_01 | 1 | japanese_brewery_06 | character_dynasty_or_house |
| japanese_fields_01 | 1 | japanese_fields_06 |  |
| japanese_garden_01 | 1 | japanese_garden_06 |  |
| japanese_horse_pastures_01 | 1 | japanese_horse_pastures_06 |  |
| japanese_shrine_01 | 1 | japanese_shrine_06 | character_dynasty_or_house |
| japanese_stables_01 | 1 | japanese_stables_06 |  |
| japanese_tea_house_01 | 1 | japanese_tea_house_06 | character_dynasty_or_house |
| japanese_tea_plantation_01 | 1 | japanese_tea_plantation_06 |  |
| japanese_watch_house_01 | 1 | japanese_watch_house_06 | character_dynasty_or_house |
| japanese_workshop_01 | 1 | japanese_workshop_06 |  |

### Внешние развилки, переводимые во внутренние треки

| Общая внешняя часть | Уровень развилки | Специализации | Новых внутренних ячеек | Всего внутренних ячеек у родителя | Иконки различаются | Панорамы совпадают | Стратегия | Источник |
|---|---:|---|---:|---:|---|---|---|---|
| — | — | — | 0 | 0 | — | — | — | — |

### Уже внутренние развилки, требующие расщепления общей части

| Общая внутренняя часть | Родитель | Общий префикс | Специализации | Нужно параллельных ячеек | Стратегия | Источник |
|---|---|---|---|---:|---|---|
| — | — | — | — | 0 | — | — |

### Существующие требования внутренних ячеек

| Родительская линия | Нужно для всех ветвей | Текущий максимум | Дефицит |
|---|---:|---:|---:|
| japanese_archive_01 | 3 | 3 | 0 |
| japanese_armory_01 | 3 | 3 | 0 |
| japanese_brewery_01 | 3 | 3 | 0 |
| japanese_fields_01 | 3 | 3 | 0 |
| japanese_garden_01 | 3 | 3 | 0 |
| japanese_horse_pastures_01 | 3 | 3 | 0 |
| japanese_manor_main_01 | 9 | 5 | 4 |
| japanese_shrine_01 | 3 | 3 | 0 |
| japanese_stables_01 | 3 | 3 | 0 |
| japanese_tea_house_01 | 3 | 3 | 0 |
| japanese_tea_plantation_01 | 3 | 3 | 0 |
| japanese_watch_house_01 | 3 | 3 | 0 |
| japanese_workshop_01 | 3 | 3 | 0 |

### Все исходные точки ветвления

| Здание | Тип ячейки | Дочерние ветви |
|---|---|---|
| — | — | — |

### Условная доступность и кандидаты на взаимоисключение

- Зданий с `can_construct`/`can_construct_potential`: 296.
- Затронутых линий: 58.
- Линий с возможным взаимоисключением: 1.
- Линий, требующих ручной проверки культурных или территориальных условий: 1.
- Линий с пока не классифицированными условиями: 0.

| Линия | Тип | Внешняя опора | Категории-кандидаты | Условные здания | Извлечённые зависимости | Рекомендуемые действия | Ручная проверка |
|---|---|---|---|---|---|---|---|
| japanese_manor_main_01 | main | japanese_manor_main_01 | culture_or_language | japanese_manor_main_02, japanese_manor_main_03, japanese_manor_main_04, japanese_manor_main_05, japanese_manor_main_06 | innovations: innovation_city_planning, innovation_cranes, innovation_development_03, innovation_manorialism | preserve_unrelated_vanilla_prerequisites, review_culture_condition_and_remove_only_track_exclusivity | да |

Полные исходные блоки условий и поключевые профили зданий сохранены в JSON. Культурные и территориальные совпадения являются кандидатами, а не автоматически удаляемыми ограничениями: сначала следует отделить взаимоисключение специализаций от обычных требований прогресса.

### Классифицированные ограничения

| Категория | Количество | Здания |
|---|---:|---|
| camp_purpose | 0 |  |
| realm_law | 0 |  |
| culture_or_language | 5 | japanese_manor_main_02, japanese_manor_main_03, japanese_manor_main_04, japanese_manor_main_05, japanese_manor_main_06 |
| territory | 0 |  |
| progression | 287 | japanese_archive_02, japanese_archive_03, japanese_archive_04, japanese_archive_05, japanese_archive_06, japanese_armorer_02, japanese_armorer_03, japanese_armorer_04, japanese_armorer_05, japanese_armorer_06, japanese_armory_02, japanese_armory_03, japanese_armory_04, japanese_armory_05, japanese_armory_06, japanese_asobi_colony_02, japanese_asobi_colony_03, japanese_asobi_colony_04, japanese_asobi_colony_05, japanese_asobi_colony_06, japanese_barracks_02, japanese_barracks_03, japanese_barracks_04, japanese_barracks_05, japanese_barracks_06, japanese_bladesmith_02, japanese_bladesmith_03, japanese_bladesmith_04, japanese_bladesmith_05, japanese_bladesmith_06, japanese_bowyer_02, japanese_bowyer_03, japanese_bowyer_04, japanese_bowyer_05, japanese_bowyer_06, japanese_brewery_02, japanese_brewery_03, japanese_brewery_04, japanese_brewery_05, japanese_brewery_06, japanese_carpenter_02, japanese_carpenter_03, japanese_carpenter_04, japanese_carpenter_05, japanese_carpenter_06, japanese_cemetery_02, japanese_cemetery_03, japanese_cemetery_04, japanese_cemetery_05, japanese_cemetery_06, japanese_farrier_02, japanese_farrier_03, japanese_farrier_04, japanese_farrier_05, japanese_farrier_06, japanese_fields_02, japanese_fields_03, japanese_fields_04, japanese_fields_05, japanese_fields_06, japanese_gambling_den_02, japanese_gambling_den_03, japanese_gambling_den_04, japanese_gambling_den_05, japanese_gambling_den_06, japanese_garden_02, japanese_garden_03, japanese_garden_04, japanese_garden_05, japanese_garden_06, japanese_granary_02, japanese_granary_03, japanese_granary_04, japanese_granary_05, japanese_granary_06, japanese_guest_house_02, japanese_guest_house_03, japanese_guest_house_04, japanese_guest_house_05, japanese_guest_house_06, japanese_horse_pastures_02, japanese_horse_pastures_03, japanese_horse_pastures_04, japanese_horse_pastures_05, japanese_horse_pastures_06, japanese_hunting_lodge_02, japanese_hunting_lodge_03, japanese_hunting_lodge_04, japanese_hunting_lodge_05, japanese_hunting_lodge_06, japanese_infiltrators_02, japanese_infiltrators_03, japanese_infiltrators_04, japanese_infiltrators_05, japanese_infiltrators_06, japanese_kazan_display_02, japanese_kazan_display_03, japanese_kazan_display_04, japanese_kazan_display_05, japanese_kazan_display_06, japanese_koshu_cellars_02, japanese_koshu_cellars_03, japanese_koshu_cellars_04, japanese_koshu_cellars_05, japanese_koshu_cellars_06, japanese_lacquerer_02, japanese_lacquerer_03, japanese_lacquerer_04, japanese_lacquerer_05, japanese_lacquerer_06, japanese_law_library_02, japanese_law_library_03, japanese_law_library_04, japanese_law_library_05, japanese_law_library_06, japanese_main_carpenter_02, japanese_main_carpenter_03, japanese_main_carpenter_04, japanese_main_carpenter_05, japanese_main_carpenter_06, japanese_main_tax_collectors_02, japanese_main_tax_collectors_03, japanese_main_tax_collectors_04, japanese_main_tax_collectors_05, japanese_main_tax_collectors_06, japanese_manor_library_confucian_02, japanese_manor_library_confucian_03, japanese_manor_library_confucian_04, japanese_manor_library_confucian_05, japanese_manor_library_confucian_06, japanese_manor_main_02, japanese_manor_main_03, japanese_manor_main_04, japanese_manor_main_05, japanese_manor_main_06, japanese_manor_office_03, japanese_manor_office_04, japanese_manor_office_05, japanese_manor_office_06, japanese_manor_poetry_library_02, japanese_manor_poetry_library_03, japanese_manor_poetry_library_04, japanese_manor_poetry_library_05, japanese_manor_poetry_library_06, japanese_manor_retainer_accomodations_02, japanese_manor_retainer_accomodations_03, japanese_manor_retainer_accomodations_04, japanese_manor_retainer_accomodations_05, japanese_manor_servants_quarters_03, japanese_manor_servants_quarters_04, japanese_manor_servants_quarters_05, japanese_manor_servants_quarters_06, japanese_manor_trophy_room_02, japanese_manor_trophy_room_03, japanese_manor_trophy_room_04, japanese_manor_trophy_room_05, japanese_manor_trophy_room_06, japanese_matcha_factory_02, japanese_matcha_factory_03, japanese_matcha_factory_04, japanese_matcha_factory_05, japanese_matcha_factory_06, japanese_medicine_house_02, japanese_medicine_house_03, japanese_medicine_house_04, japanese_medicine_house_05, japanese_medicine_house_06, japanese_messenger_service_02, japanese_messenger_service_03, japanese_messenger_service_04, japanese_messenger_service_05, japanese_messenger_service_06, japanese_monastery_02, japanese_monastery_03, japanese_monastery_04, japanese_monastery_05, japanese_monastery_06, japanese_orchard_02, japanese_orchard_03, japanese_orchard_04, japanese_orchard_05, japanese_orchard_06, japanese_ox_breeder_02, japanese_ox_breeder_03, japanese_ox_breeder_04, japanese_ox_breeder_05, japanese_ox_breeder_06, japanese_performance_stage_02, japanese_performance_stage_03, japanese_performance_stage_04, japanese_performance_stage_05, japanese_performance_stage_06, japanese_prison_02, japanese_prison_03, japanese_prison_04, japanese_prison_05, japanese_prison_06, japanese_rice_broker_02, japanese_rice_broker_03, japanese_rice_broker_04, japanese_rice_broker_05, japanese_rice_broker_06, japanese_riding_school_02, japanese_riding_school_03, japanese_riding_school_04, japanese_riding_school_05, japanese_riding_school_06, japanese_roastery_02, japanese_roastery_03, japanese_roastery_04, japanese_roastery_05, japanese_roastery_06, japanese_rock_garden_02, japanese_rock_garden_03, japanese_rock_garden_04, japanese_rock_garden_05, japanese_rock_garden_06, japanese_schoolhouse_02, japanese_schoolhouse_03, japanese_schoolhouse_04, japanese_schoolhouse_05, japanese_schoolhouse_06, japanese_shokubo_02, japanese_shokubo_03, japanese_shokubo_04, japanese_shokubo_05, japanese_shokubo_06, japanese_shrine_02, japanese_shrine_03, japanese_shrine_04, japanese_shrine_05, japanese_shrine_06, japanese_spy_network_02, japanese_spy_network_03, japanese_spy_network_04, japanese_spy_network_05, japanese_spy_network_06, japanese_stables_02, japanese_stables_03, japanese_stables_04, japanese_stables_05, japanese_stables_06, japanese_stud_farm_02, japanese_stud_farm_03, japanese_stud_farm_04, japanese_stud_farm_05, japanese_stud_farm_06, japanese_sumo_hall_02, japanese_sumo_hall_03, japanese_sumo_hall_04, japanese_sumo_hall_05, japanese_sumo_hall_06, japanese_tea_house_02, japanese_tea_house_03, japanese_tea_house_04, japanese_tea_house_05, japanese_tea_house_06, japanese_tea_plantation_02, japanese_tea_plantation_03, japanese_tea_plantation_04, japanese_tea_plantation_05, japanese_tea_plantation_06, japanese_tenant_farmers_02, japanese_tenant_farmers_03, japanese_tenant_farmers_04, japanese_tenant_farmers_05, japanese_tenant_farmers_06, japanese_watch_house_02, japanese_watch_house_03, japanese_watch_house_04, japanese_watch_house_05, japanese_watch_house_06, japanese_workshop_02, japanese_workshop_03, japanese_workshop_04, japanese_workshop_05, japanese_workshop_06, japanese_yabusame_ground_02, japanese_yabusame_ground_03, japanese_yabusame_ground_04, japanese_yabusame_ground_05, japanese_yabusame_ground_06, sarugaku_stage_02, sarugaku_stage_03, sarugaku_stage_04, sarugaku_stage_05, sarugaku_stage_06 |
| government_or_status | 12 | japanese_archive_01, japanese_archive_02, japanese_archive_03, japanese_archive_04, japanese_archive_05, japanese_archive_06, japanese_manor_trophy_room_01, japanese_manor_trophy_room_02, japanese_manor_trophy_room_03, japanese_manor_trophy_room_04, japanese_manor_trophy_room_05, japanese_manor_trophy_room_06 |
| faith | 0 |  |
| scripted_trigger | 0 |  |
| character_dynasty_or_house | 38 | japanese_archive_01, japanese_archive_02, japanese_archive_03, japanese_archive_04, japanese_archive_05, japanese_archive_06, japanese_armory_01, japanese_armory_02, japanese_armory_03, japanese_armory_04, japanese_armory_05, japanese_armory_06, japanese_brewery_01, japanese_brewery_02, japanese_brewery_03, japanese_brewery_04, japanese_brewery_05, japanese_brewery_06, japanese_manor_poetry_library_01, japanese_manor_retainer_accomodations_01, japanese_shrine_01, japanese_shrine_02, japanese_shrine_03, japanese_shrine_04, japanese_shrine_05, japanese_shrine_06, japanese_tea_house_01, japanese_tea_house_02, japanese_tea_house_03, japanese_tea_house_04, japanese_tea_house_05, japanese_tea_house_06, japanese_watch_house_01, japanese_watch_house_02, japanese_watch_house_03, japanese_watch_house_04, japanese_watch_house_05, japanese_watch_house_06 |
| state_or_feature | 0 |  |

## Флаги назначения лагеря

| Флаг закона | Здания | Линии | Удалений при смене назначения | Контейнеры очистки | Политика RB_UD |
|---|---|---|---:|---|---|
| unlocks_baggage_train_ascetics | baggage_train_ascetics | baggage_train_ascetics | 1 | ep3_laamps.1021 | remove_gate_and_disable_only_purpose_change_cleanup |
| unlocks_baggage_train_negotiators | baggage_train_negotiators | baggage_train_negotiators | 1 | ep3_laamps.1021 | remove_gate_and_disable_only_purpose_change_cleanup |
| unlocks_baggage_train_proof_of_claims | baggage_train_proof_of_claims | baggage_train_proof_of_claims | 1 | ep3_laamps.1021 | remove_gate_and_disable_only_purpose_change_cleanup |
| unlocks_baggage_train_ransom_cages | baggage_train_ransom_cages | baggage_train_ransom_cages | 1 | ep3_laamps.1021 | remove_gate_and_disable_only_purpose_change_cleanup |
| unlocks_baggage_train_scribes | baggage_train_scribes | baggage_train_scribes | 1 | ep3_laamps.1021 | remove_gate_and_disable_only_purpose_change_cleanup |
| unlocks_baggage_train_siege_engineers | baggage_train_siege_engineers | baggage_train_siege_engineers | 1 | ep3_laamps.1021 | remove_gate_and_disable_only_purpose_change_cleanup |
| unlocks_barber_tent_morticians_tools | barber_tent_morticians_tools | barber_tent_morticians_tools | 1 | ep3_laamps.1021 | remove_gate_and_disable_only_purpose_change_cleanup |
| unlocks_barber_tent_reference_corpus | barber_tent_reference_corpus | barber_tent_reference_corpus | 1 | ep3_laamps.1021 | remove_gate_and_disable_only_purpose_change_cleanup |
| unlocks_camp_fire_future_dreams | camp_fire_future_dreams | camp_fire_future_dreams | 1 | ep3_laamps.1021 | remove_gate_and_disable_only_purpose_change_cleanup |
| unlocks_camp_fire_juicy_rumors | camp_fire_juicy_rumors | camp_fire_juicy_rumors | 1 | ep3_laamps.1021 | remove_gate_and_disable_only_purpose_change_cleanup |
| unlocks_camp_fire_local_hangers_on | camp_fire_local_hangers_on | camp_fire_local_hangers_on | 1 | ep3_laamps.1021 | remove_gate_and_disable_only_purpose_change_cleanup |
| unlocks_camp_fire_nightly_debates | camp_fire_nightly_debates | camp_fire_nightly_debates | 1 | ep3_laamps.1021 | remove_gate_and_disable_only_purpose_change_cleanup |
| unlocks_camp_perimeter_ditch | camp_perimeter_ditch | camp_perimeter_ditch | 1 | ep3_laamps.1021 | remove_gate_and_disable_only_purpose_change_cleanup |
| unlocks_camp_perimeter_extra_watch | camp_perimeter_extra_watch | camp_perimeter_extra_watch | 1 | ep3_laamps.1021 | remove_gate_and_disable_only_purpose_change_cleanup |
| unlocks_camp_perimeter_palisade | camp_perimeter_palisade | camp_perimeter_palisade | 1 | ep3_laamps.1021 | remove_gate_and_disable_only_purpose_change_cleanup |
| unlocks_proving_grounds_bodyguard_drills | proving_grounds_bodyguard_drills | proving_grounds_bodyguard_drills | 1 | ep3_laamps.1021 | remove_gate_and_disable_only_purpose_change_cleanup |
| unlocks_proving_grounds_lockwagon | proving_grounds_lockwagon | proving_grounds_lockwagon | 1 | ep3_laamps.1021 | remove_gate_and_disable_only_purpose_change_cleanup |
| unlocks_proving_grounds_martial_study | proving_grounds_martial_study | proving_grounds_martial_study | 1 | ep3_laamps.1021 | remove_gate_and_disable_only_purpose_change_cleanup |
| unlocks_proving_grounds_the_stick_game | proving_grounds_the_stick_game | proving_grounds_the_stick_game | 1 | ep3_laamps.1021 | remove_gate_and_disable_only_purpose_change_cleanup |
| unlocks_supply_tent_climbing_gear | supply_tent_climbing_gear | supply_tent_climbing_gear | 1 | ep3_laamps.1021 | remove_gate_and_disable_only_purpose_change_cleanup |
| unlocks_supply_tent_reserve_provisions | supply_tent_reserve_provisions | supply_tent_reserve_provisions | 1 | ep3_laamps.1021 | remove_gate_and_disable_only_purpose_change_cleanup |
| unlocks_supply_tent_reserve_water | supply_tent_reserve_water | supply_tent_reserve_water | 1 | ep3_laamps.1021 | remove_gate_and_disable_only_purpose_change_cleanup |
| unlocks_supply_tent_subdued_gear | supply_tent_subdued_gear | supply_tent_subdued_gear | 1 | ep3_laamps.1021 | remove_gate_and_disable_only_purpose_change_cleanup |

## Явные удаления и понижения зданий домицилей

Анализ охватывает явные эффекты `remove_domicile_building`, `remove_domicile_building_no_refund` и `lower_domicile_building_no_refund`. Уничтожение целого объекта домиция движковыми командами без перечисления ID зданий в эту таблицу не входит.

| Категория | Ссылок | Уникальных зданий | Домицилии | Контейнеры |
|---|---:|---:|---|---|
| camp_purpose_change_cleanup | 23 | 23 | camp | ep3_laamps.1021 |
| domicile_type_conversion | 1078 | 1078 | east_asian_estate, estate, japanese_manor | tgp_wipe_domicile_effect |
| full_domicile_liquidation | 104 | 104 | camp | laamp_clear_domicile_buildings_effect |
| targeted_gameplay_action | 3 | 3 | camp | ep3_laamp_decision_event.1201, ep3_laamp_decision_event.1203, ep3_laamp_decision_event.1204 |

### Точечные игровые удаления

| Контейнер | Эффект | Здание | Домицилий | Источник |
|---|---|---|---|---|
| ep3_laamp_decision_event.1201 | remove_domicile_building | baggage_train_kennel | camp | events\dlc\ep3\ep3_laamp_decision_events.txt:21819 |
| ep3_laamp_decision_event.1203 | remove_domicile_building | baggage_train_ample_steeds | camp | events\dlc\ep3\ep3_laamp_decision_events.txt:22192 |
| ep3_laamp_decision_event.1204 | remove_domicile_building | proving_grounds_elephantry_reserve | camp | events\dlc\ep3\ep3_laamp_decision_events.txt:22268 |

Полный поключевой список ссылок хранится в JSON-манифесте в поле `DomicileRemovalReferences`. Массовые очистки при смене назначения лагеря, полной ликвидации и преобразовании типа домиция сохраняются как отдельные категории и не должны автоматически отключаться модом.

## Эффекты начального заполнения внешних ячеек

| Эффект | Порог свободных ячеек | Вызываемые эффекты | Источник |
|---|---|---|---|
| fill_external_estate_building_effect | >= 1, >= 2, >= 3, >= 4, >= 5 | add_random_external_estate_building | common\scripted_effects\07_dlc_ep3_scripted_effects.txt:13277 |
| fill_external_japanese_manor_building_effect | >= 1, >= 2, >= 3, >= 4, >= 5 | add_random_external_estate_building, add_random_external_japanese_manor_building | common\scripted_effects\10_dlc_tgp_japan_scripted_effects.txt:222 |
| fill_external_east_asian_estate_building_effect | >= 2, >= 3, >= 4, >= 5, >= 6 | add_random_external_east_asian_estate_building | common\scripted_effects\10_dlc_tgp_scripted_effects.txt:2922 |

## Диагностика графа

- Циклические ссылки: 0
- Повторно определённые ID зданий в ванильной базе: 0
- Повторно определённые ID типов домицилей: 0
- Повторно определённые scripted triggers: 0
- Специализации без корневых иконок: 0
- Специализации без корневых панорам: 0
- Не классифицированные типы структурных развилок: 0
- Условные линии, требующие ручной проверки: 24
- Условные линии без автоматической классификации: 0
- Неразрешённые ссылки на scripted triggers: 0

## Входные файлы

| Файл | SHA-256 |
|---|---|
| common\domiciles\buildings\00_camp_buildings.txt | 6281C1F3853469043D342D8501AA6F4087569D7CF600BD193CD7EC1CC3E86ECC |
| common\domiciles\buildings\00_chinese_estate_buildings.txt | 032A0BC2EA179D20C313678985B7DA46F04F124EDFEBCA1574C5C6025FBAFE49 |
| common\domiciles\buildings\00_estate_buildings.txt | 4A643F33ED101A2EAC6C94C069C5C65BBAD0EB7002CB024F31B4A079E2C54FED |
| common\domiciles\buildings\00_yurt_buildings.txt | 39885BA8D5909024DD0B178E976A73AF9E7A2785B319775E633D7058E61F49B1 |
| common\domiciles\buildings\10_japanese_manor_buildings.txt | 276472F9FA15D4818D16C968F9BEE132D6288BA1D4C316764B486ABAEE64BBB0 |
| common\domiciles\types\00_domicile_types.txt | 03F4981EE157F27D4D5C9533CBB1B21262FC5F8817D0E0E506A2BF01C99B99CC |
| common\domiciles\types\10_tgp_japan_domicile_types.txt | CCE9685A8240E0A64ACC8950F82999F86B0D76B2F9288B0ECC1431DD49BB747E |
| common\laws\00_realm_laws.txt | EC96F526706B454A883B78429161B8C19D36B6DC8A5324C5DB95E73A6806E2DF |
| common\scripted_effects\00_laamp_effects.txt | EDFA35F1B97AE7A28FA42162004FB4C3F6327737D495F3C636F2C751E15EBA6F |
| common\scripted_effects\07_dlc_ep3_scripted_effects.txt | D2F5FE80E7BC000A749642CD26BDE1626DBEA7409C39314B8583547AE43DB43D |
| common\scripted_effects\10_dlc_tgp_japan_scripted_effects.txt | E62CE9F628EF5B52CBD57BE17A9F81F355D901A8488A04DC79FE3C5F0FFBBF78 |
| common\scripted_effects\10_dlc_tgp_scripted_effects.txt | AEF36B884DC5E315DD5C655BC96012FF9FA8BB46BB0AF2C18FA878C890907747 |
| common\scripted_triggers\07_ep3_triggers.txt | A05CAD169B9C0708126A2D908E1858A241EB62D835F109705DC3144D08A8EF47 |
| common\scripted_triggers\10_tgp_triggers.txt | 8294C1D72ECC909428ABFBA27D6F10B127D796D2BEE350D1BB95024F36D60C99 |
| events\dlc\ep3\ep3_laamp_decision_events.txt | 24305B3F414A5CF246A0B880EA0293B5A2B581C8F015FE3D90DE8076566B43A8 |
| events\dlc\ep3\ep3_laamp_events.txt | FE5E1048AB557CD4ACCFA2DC98022C440DF9A2ACA7D8E10DD2EF5DADDD246F92 |

