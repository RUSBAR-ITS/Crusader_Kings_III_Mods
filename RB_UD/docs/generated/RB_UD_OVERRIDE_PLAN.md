# RB_UD — план переопределений ванильных домицилей

Версия CK3: **1.19.0.6**. Сигнатура плана: `EB632CC3ACFD73B6C1DAA8DED064BB208912CDA33893A869A64E5AD9EAF58C67`.

Это dry-run: документ определяет точные объекты и преобразования, но ещё не создаёт игровых переопределений.

## Принципы

- Override only affected vanilla objects; never use replace_path.
- Vanilla objects retain vanilla IDs; new helper objects use the RB_UD_ prefix.
- Preserve vanilla costs, construction times, effects, upgrade order, and unrelated prerequisites.
- Remove only mutual-exclusivity access gates and camp-purpose cleanup targeted by this plan.
- Grant complete slot capacity from the first main or anchor level; progression still controls higher building tiers.
- No mass-build action and no construction-speed modifier are part of this mod.

## Типы домицилей и внешняя ёмкость

| Тип | Видимых сейчас | Максимум сейчас | Цель | Добавка на первом главном здании | Последующие добавки |
|---|---:|---:|---:|---:|---|
| camp | 4 | 6 | 7 | 5 | обнулить |
| estate | 6 | 8 | 16 | 14 | обнулить |
| yurt | 6 | 8 | 7 | 5 | обнулить |
| east_asian_estate | 6 | 8 | 15 | 13 | обнулить |
| japanese_manor | 6 | 8 | 12 | 10 | обнулить |

Полная внешняя ёмкость доступна с первого уровня главного здания. Это не открывает более высокие уровни построек: их ванильная прогрессия сохраняется.

## Внутренние ячейки

| Тип | Опорная линия | Цель на каждом уровне линии | Причина |
|---|---|---:|---|
| camp | baggage_train_01 | 13 | all_existing_internal_tracks_can_coexist |
| camp | barber_tent_01 | 5 | all_existing_internal_tracks_can_coexist |
| camp | camp_fire_01 | 8 | all_existing_internal_tracks_can_coexist |
| camp | camp_perimeter_01 | 6 | all_existing_internal_tracks_can_coexist |
| camp | mess_tent_01 | 5 | all_existing_internal_tracks_can_coexist |
| camp | proving_grounds_01 | 13 | all_existing_internal_tracks_can_coexist |
| camp | supply_tent_01 | 8 | all_existing_internal_tracks_can_coexist |
| east_asian_estate | east_asian_estate_ancestral_shrine_01 | 5 | all_existing_internal_tracks_can_coexist |
| east_asian_estate | east_asian_estate_barracks_01 | 6 | all_existing_internal_tracks_can_coexist |
| east_asian_estate | east_asian_estate_garden_01 | 8 | all_existing_internal_tracks_can_coexist, internalize_external_branch_at_east_asian_estate_garden_03 |
| east_asian_estate | east_asian_estate_gate_01 | 5 | all_existing_internal_tracks_can_coexist |
| east_asian_estate | east_asian_estate_grazing_land_01 | 9 | all_existing_internal_tracks_can_coexist, internalize_external_branch_at_east_asian_estate_grazing_land_03 |
| east_asian_estate | east_asian_estate_health_01 | 5 | all_existing_internal_tracks_can_coexist |
| east_asian_estate | east_asian_estate_main_01 | 26 | all_existing_internal_tracks_can_coexist |
| east_asian_estate | east_asian_estate_market_01 | 6 | all_existing_internal_tracks_can_coexist |
| east_asian_estate | east_asian_estate_rice_field_01 | 6 | all_existing_internal_tracks_can_coexist |
| east_asian_estate | east_asian_estate_silk_01 | 5 | all_existing_internal_tracks_can_coexist |
| east_asian_estate | east_asian_estate_stable_01 | 7 | all_existing_internal_tracks_can_coexist, internalize_external_branch_at_east_asian_estate_stable_03 |
| east_asian_estate | east_asian_estate_storage_01 | 8 | all_existing_internal_tracks_can_coexist, internalize_external_branch_at_east_asian_estate_storage_02 |
| east_asian_estate | east_asian_estate_tea_01 | 5 | all_existing_internal_tracks_can_coexist |
| east_asian_estate | east_asian_estate_temple_01 | 5 | all_existing_internal_tracks_can_coexist |
| east_asian_estate | east_asian_estate_watchtower_01 | 5 | all_existing_internal_tracks_can_coexist |
| east_asian_estate | east_asian_estate_workshop_01 | 8 | all_existing_internal_tracks_can_coexist, internalize_external_branch_at_east_asian_estate_workshop_02 |
| estate | estate_main_01 | 15 | all_existing_internal_tracks_can_coexist, keep_library_shared_prefix_plus_two_parallel_specializations |
| estate | garden_01 | 2 | internalize_external_branch_at_garden_03 |
| estate | grazing_land_01 | 4 | internalize_external_branch_at_grazing_land_03 |
| estate | stable_01 | 3 | internalize_external_branch_at_stable_03 |
| estate | storage_01 | 2 | internalize_external_branch_at_storage_02 |
| estate | temple_small_01 | 3 | internalize_external_branch_at_temple_small_03 |
| estate | workshop_01 | 3 | internalize_external_branch_at_workshop_02 |
| japanese_manor | japanese_archive_01 | 3 | all_existing_internal_tracks_can_coexist |
| japanese_manor | japanese_armory_01 | 3 | all_existing_internal_tracks_can_coexist |
| japanese_manor | japanese_brewery_01 | 3 | all_existing_internal_tracks_can_coexist |
| japanese_manor | japanese_fields_01 | 3 | all_existing_internal_tracks_can_coexist |
| japanese_manor | japanese_garden_01 | 3 | all_existing_internal_tracks_can_coexist |
| japanese_manor | japanese_horse_pastures_01 | 3 | all_existing_internal_tracks_can_coexist |
| japanese_manor | japanese_manor_main_01 | 9 | all_existing_internal_tracks_can_coexist |
| japanese_manor | japanese_shrine_01 | 3 | all_existing_internal_tracks_can_coexist |
| japanese_manor | japanese_stables_01 | 3 | all_existing_internal_tracks_can_coexist |
| japanese_manor | japanese_tea_house_01 | 3 | all_existing_internal_tracks_can_coexist |
| japanese_manor | japanese_tea_plantation_01 | 3 | all_existing_internal_tracks_can_coexist |
| japanese_manor | japanese_watch_house_01 | 3 | all_existing_internal_tracks_can_coexist |
| japanese_manor | japanese_workshop_01 | 3 | all_existing_internal_tracks_can_coexist |
| yurt | character_warfare_yurt_01 | 5 | all_existing_internal_tracks_can_coexist |
| yurt | court_yurt_01 | 8 | all_existing_internal_tracks_can_coexist |
| yurt | family_yurt_01 | 8 | all_existing_internal_tracks_can_coexist |
| yurt | herd_welfare_yurt_01 | 9 | all_existing_internal_tracks_can_coexist |
| yurt | mass_warfare_yurt_01 | 6 | all_existing_internal_tracks_can_coexist |
| yurt | mystical_yurt_01 | 7 | all_existing_internal_tracks_can_coexist |
| yurt | trade_yurt_01 | 7 | all_existing_internal_tracks_can_coexist |
| yurt | yurt_main_01 | 15 | all_existing_internal_tracks_can_coexist |

## Внешние развилки, переводимые во внутренние линии

| Тип | Общая внешняя часть | Опорная линия | Внутренних линий | Новая ёмкость | Переводимые здания |
|---|---|---|---:|---:|---|
| estate | garden_03 | garden_01 | 2 | 2 | garden_fruit_04, garden_fruit_05, garden_fruit_06, garden_leisure_04, garden_leisure_05, garden_leisure_06 |
| estate | grazing_land_03 | grazing_land_01 | 4 | 4 | camel_pasture_04, camel_pasture_05, camel_pasture_06, elephant_pasture_04, elephant_pasture_05, elephant_pasture_06, grazing_land_04, grazing_land_05, grazing_land_06, horse_pasture_04, horse_pasture_05, horse_pasture_06 |
| estate | stable_03 | stable_01 | 3 | 3 | stable_chariot_04, stable_chariot_05, stable_chariot_06, stable_grand_04, stable_grand_05, stable_grand_06, stable_kennel_04, stable_kennel_05, stable_kennel_06 |
| estate | storage_02 | storage_01 | 2 | 2 | storage_granary_03, storage_granary_04, storage_warehouse_03, storage_warehouse_04 |
| estate | temple_small_03 | temple_small_01 | 3 | 3 | temple_crypt_04, temple_crypt_05, temple_crypt_06, temple_large_04, temple_large_05, temple_large_06, temple_monastery_04, temple_monastery_05, temple_monastery_06 |
| estate | workshop_02 | workshop_01 | 3 | 3 | workshop_carpenter_03, workshop_carpenter_04, workshop_carpenter_05, workshop_carpenter_06, workshop_mason_03, workshop_mason_04, workshop_mason_05, workshop_mason_06, workshop_textile_03, workshop_textile_04, workshop_textile_05, workshop_textile_06 |
| east_asian_estate | east_asian_estate_garden_03 | east_asian_estate_garden_01 | 2 | 8 | east_asian_estate_garden_fruit_04, east_asian_estate_garden_fruit_05, east_asian_estate_garden_fruit_06, east_asian_estate_garden_leisure_04, east_asian_estate_garden_leisure_05, east_asian_estate_garden_leisure_06 |
| east_asian_estate | east_asian_estate_grazing_land_03 | east_asian_estate_grazing_land_01 | 4 | 9 | east_asian_estate_camel_pasture_04, east_asian_estate_camel_pasture_05, east_asian_estate_camel_pasture_06, east_asian_estate_elephant_pasture_04, east_asian_estate_elephant_pasture_05, east_asian_estate_elephant_pasture_06, east_asian_estate_grazing_land_04, east_asian_estate_grazing_land_05, east_asian_estate_grazing_land_06, east_asian_estate_horse_pasture_04, east_asian_estate_horse_pasture_05, east_asian_estate_horse_pasture_06 |
| east_asian_estate | east_asian_estate_stable_03 | east_asian_estate_stable_01 | 2 | 7 | east_asian_estate_stable_grand_04, east_asian_estate_stable_grand_05, east_asian_estate_stable_grand_06, east_asian_estate_stable_kennel_04, east_asian_estate_stable_kennel_05, east_asian_estate_stable_kennel_06 |
| east_asian_estate | east_asian_estate_storage_02 | east_asian_estate_storage_01 | 2 | 8 | east_asian_estate_storage_granary_03, east_asian_estate_storage_granary_04, east_asian_estate_storage_granary_05, east_asian_estate_storage_granary_06, east_asian_estate_storage_warehouse_03, east_asian_estate_storage_warehouse_04, east_asian_estate_storage_warehouse_05, east_asian_estate_storage_warehouse_06 |
| east_asian_estate | east_asian_estate_workshop_02 | east_asian_estate_workshop_01 | 3 | 8 | east_asian_estate_workshop_carpenter_03, east_asian_estate_workshop_carpenter_04, east_asian_estate_workshop_carpenter_05, east_asian_estate_workshop_carpenter_06, east_asian_estate_workshop_mason_03, east_asian_estate_workshop_mason_04, east_asian_estate_workshop_mason_05, east_asian_estate_workshop_mason_06, east_asian_estate_workshop_textile_03, east_asian_estate_workshop_textile_04, east_asian_estate_workshop_textile_05, east_asian_estate_workshop_textile_06 |

## Внутренняя развилка библиотеки поместья

- Общая линия `library_01 -> library_02` сохраняется отдельной.
- Специализации `library_education_03`` и ``library_observatory_03` привязываются к `estate_main_01`.
- Каждая специализация дополнительно требует уже построенную `library_02`.
- Итоговая ёмкость главной линии: **15** внутренних ячеек.

## Условные ограничения

### Темы лагеря — 23 точечных пар

Для каждой пары снимается только соответствующий `has_realm_law_flag`, а из `ep3_laamps.1021` удаляется только соответствующее удаление здания. Полная ликвидация лагеря и сюжетные удаления сохраняются.

| Флаг | Здание | Очистка |
|---|---|---|
| unlocks_baggage_train_ascetics | baggage_train_ascetics | ep3_laamps.1021 |
| unlocks_baggage_train_negotiators | baggage_train_negotiators | ep3_laamps.1021 |
| unlocks_baggage_train_proof_of_claims | baggage_train_proof_of_claims | ep3_laamps.1021 |
| unlocks_baggage_train_ransom_cages | baggage_train_ransom_cages | ep3_laamps.1021 |
| unlocks_baggage_train_scribes | baggage_train_scribes | ep3_laamps.1021 |
| unlocks_baggage_train_siege_engineers | baggage_train_siege_engineers | ep3_laamps.1021 |
| unlocks_barber_tent_morticians_tools | barber_tent_morticians_tools | ep3_laamps.1021 |
| unlocks_barber_tent_reference_corpus | barber_tent_reference_corpus | ep3_laamps.1021 |
| unlocks_camp_fire_future_dreams | camp_fire_future_dreams | ep3_laamps.1021 |
| unlocks_camp_fire_juicy_rumors | camp_fire_juicy_rumors | ep3_laamps.1021 |
| unlocks_camp_fire_local_hangers_on | camp_fire_local_hangers_on | ep3_laamps.1021 |
| unlocks_camp_fire_nightly_debates | camp_fire_nightly_debates | ep3_laamps.1021 |
| unlocks_camp_perimeter_ditch | camp_perimeter_ditch | ep3_laamps.1021 |
| unlocks_camp_perimeter_extra_watch | camp_perimeter_extra_watch | ep3_laamps.1021 |
| unlocks_camp_perimeter_palisade | camp_perimeter_palisade | ep3_laamps.1021 |
| unlocks_proving_grounds_bodyguard_drills | proving_grounds_bodyguard_drills | ep3_laamps.1021 |
| unlocks_proving_grounds_lockwagon | proving_grounds_lockwagon | ep3_laamps.1021 |
| unlocks_proving_grounds_martial_study | proving_grounds_martial_study | ep3_laamps.1021 |
| unlocks_proving_grounds_the_stick_game | proving_grounds_the_stick_game | ep3_laamps.1021 |
| unlocks_supply_tent_climbing_gear | supply_tent_climbing_gear | ep3_laamps.1021 |
| unlocks_supply_tent_reserve_provisions | supply_tent_reserve_provisions | ep3_laamps.1021 |
| unlocks_supply_tent_reserve_water | supply_tent_reserve_water | ep3_laamps.1021 |
| unlocks_supply_tent_subdued_gear | supply_tent_subdued_gear | ep3_laamps.1021 |

### Культура, территория и специальные способы доступа

| Тип | Линия | Решение | Затронутые здания | Зависимости |
|---|---|---|---|---|
| camp | proving_grounds_camel_run | targeted_remove_specialization_access_gate | proving_grounds_camel_run | Innovations: innovation_war_camels |
| camp | proving_grounds_elephantry_reserve | targeted_remove_specialization_access_gate | proving_grounds_elephantry_reserve | Regions: world_innovation_elephants; CharacterFlags: recently_ate_elephants |
| estate | grazing_land_01 | targeted_remove_specialization_access_gate | camel_pasture_04, camel_pasture_05, camel_pasture_06, elephant_pasture_04, elephant_pasture_05, elephant_pasture_06, grazing_land_04, grazing_land_05, grazing_land_06, horse_pasture_04, horse_pasture_05, horse_pasture_06 | Innovations: innovation_elephantry, innovation_war_camels; RequiredDomicileBuildings: estate_main_03, estate_main_04, estate_main_05; ScriptedTriggers: can_recruit_archer_cavalry_trigger |
| estate | rice_field_01 | targeted_remove_specialization_access_gate | rice_field_01, rice_field_03, rice_field_04, rice_field_05, rice_field_06 | Innovations: innovation_champa_rice; RequiredDomicileBuildings: estate_main_02, estate_main_03, estate_main_04, estate_main_05 |
| estate | silk_01 | targeted_remove_specialization_access_gate | silk_01, silk_02, silk_03, silk_04, silk_05, silk_06 | CulturalParameters: unlocks_silk_buildings_parameter; RequiredDomicileBuildings: estate_main_02, estate_main_03, estate_main_04, estate_main_05 |
| estate | stable_01 | targeted_remove_specialization_access_gate | stable_chariot_04, stable_chariot_05, stable_chariot_06, stable_grand_04, stable_grand_05, stable_grand_06, stable_kennel_04, stable_kennel_05, stable_kennel_06 | CulturalParameters: hosts_chariot_races; RequiredDomicileBuildings: estate_main_03, estate_main_04, estate_main_05 |
| estate | tea_01 | targeted_remove_specialization_access_gate | tea_01, tea_03, tea_04, tea_05, tea_06 | Innovations: innovation_champa_rice; RequiredDomicileBuildings: estate_main_02, estate_main_03, estate_main_04, estate_main_05 |
| estate | estate_main_01 | preserve_entire_vanilla_condition | estate_main_02, estate_main_03, estate_main_04, estate_main_05 | Innovations: innovation_city_planning, innovation_cranes, innovation_development_03, innovation_manorialism |
| yurt | camel_yurt_01 | targeted_remove_specialization_access_gate | camel_yurt_01, camel_yurt_02, camel_yurt_03, camel_yurt_04, camel_yurt_05, camel_yurt_06 | Terrains: desert |
| yurt | forbearing_yurt_01 | targeted_remove_specialization_access_gate | forbearing_yurt_01, forbearing_yurt_02, forbearing_yurt_03, forbearing_yurt_04, forbearing_yurt_05, forbearing_yurt_06 | CulturalParameters: forbearing_internal_yurt_unlock; Traits: patient |
| yurt | goat_yurt_01 | targeted_remove_specialization_access_gate | goat_yurt_01, goat_yurt_02, goat_yurt_03, goat_yurt_04, goat_yurt_05, goat_yurt_06 | Terrains: hills, mountains |
| yurt | horse_breeder_yurt_01 | targeted_remove_specialization_access_gate | horse_breeder_yurt_01, horse_breeder_yurt_02, horse_breeder_yurt_03, horse_breeder_yurt_04, horse_breeder_yurt_05, horse_breeder_yurt_06 | CulturalParameters: horse_breeder_internal_yurt_unlock |
| yurt | language_yurt_01 | targeted_remove_specialization_access_gate | language_yurt_01, language_yurt_02, language_yurt_03, language_yurt_04, language_yurt_05, language_yurt_06 |  |
| yurt | metalworkers_cultrad_yurt_01 | targeted_remove_specialization_access_gate | metalworkers_cultrad_yurt_01, metalworkers_cultrad_yurt_02, metalworkers_cultrad_yurt_03, metalworkers_cultrad_yurt_04, metalworkers_cultrad_yurt_05, metalworkers_cultrad_yurt_06 | CulturalParameters: metalworkers_internal_yurt_unlock |
| yurt | reindeer_yurt_01 | targeted_remove_specialization_access_gate | reindeer_yurt_01, reindeer_yurt_02, reindeer_yurt_03, reindeer_yurt_04, reindeer_yurt_05, reindeer_yurt_06 | Terrains: forest, taiga |
| yurt | sheep_yurt_01 | targeted_remove_specialization_access_gate | sheep_yurt_01, sheep_yurt_02, sheep_yurt_03, sheep_yurt_04, sheep_yurt_05, sheep_yurt_06 | Terrains: plains, steppe |
| yurt | stalwart_defenders_yurt_01 | targeted_remove_specialization_access_gate | stalwart_defenders_yurt_01, stalwart_defenders_yurt_02, stalwart_defenders_yurt_03, stalwart_defenders_yurt_04, stalwart_defenders_yurt_05, stalwart_defenders_yurt_06 | CulturalParameters: stalwart_defenders_internal_yurt_unlock |
| yurt | zealous_people_yurt_01 | targeted_remove_specialization_access_gate | zealous_people_yurt_01, zealous_people_yurt_02, zealous_people_yurt_03, zealous_people_yurt_04, zealous_people_yurt_05, zealous_people_yurt_06 | CulturalParameters: zealous_people_internal_yurt_unlock |
| east_asian_estate | east_asian_estate_grazing_land_01 | targeted_remove_specialization_access_gate | east_asian_estate_camel_pasture_04, east_asian_estate_camel_pasture_05, east_asian_estate_camel_pasture_06, east_asian_estate_elephant_pasture_04, east_asian_estate_elephant_pasture_05, east_asian_estate_elephant_pasture_06, east_asian_estate_grazing_land_03, east_asian_estate_grazing_land_04, east_asian_estate_grazing_land_05, east_asian_estate_grazing_land_06, east_asian_estate_horse_pasture_04, east_asian_estate_horse_pasture_05, east_asian_estate_horse_pasture_06 | Innovations: innovation_elephantry, innovation_war_camels; RequiredDomicileBuildings: east_asian_estate_main_02, east_asian_estate_main_03, east_asian_estate_main_04, east_asian_estate_main_05; ScriptedTriggers: can_recruit_archer_cavalry_trigger |
| east_asian_estate | east_asian_estate_silk_01 | targeted_remove_specialization_access_gate | east_asian_estate_silk_01, east_asian_estate_silk_02, east_asian_estate_silk_03, east_asian_estate_silk_04, east_asian_estate_silk_05, east_asian_estate_silk_06 | CulturalParameters: unlocks_silk_buildings_parameter; RequiredDomicileBuildings: east_asian_estate_main_02, east_asian_estate_main_03, east_asian_estate_main_04, east_asian_estate_main_05 |
| east_asian_estate | east_asian_estate_gunpowder_storage_01 | targeted_remove_specialization_access_gate | east_asian_estate_gunpowder_storage_01, east_asian_estate_gunpowder_storage_03, east_asian_estate_gunpowder_storage_04 | Innovations: innovation_fire_medicine; RequiredDomicileBuildings: east_asian_estate_main_02, east_asian_estate_main_03 |
| east_asian_estate | east_asian_estate_lacquer_studio_01 | targeted_remove_specialization_access_gate | east_asian_estate_lacquer_studio_01, east_asian_estate_lacquer_studio_03, east_asian_estate_lacquer_studio_04 | Innovations: innovation_lacquered_armor; RequiredDomicileBuildings: east_asian_estate_main_02, east_asian_estate_main_03 |
| east_asian_estate | east_asian_estate_main_01 | preserve_entire_vanilla_condition | east_asian_estate_main_02, east_asian_estate_main_03, east_asian_estate_main_04, east_asian_estate_main_05 | Innovations: innovation_city_planning, innovation_cranes, innovation_development_03, innovation_manorialism |
| japanese_manor | japanese_manor_main_01 | preserve_entire_vanilla_condition | japanese_manor_main_02, japanese_manor_main_03, japanese_manor_main_04, japanese_manor_main_05, japanese_manor_main_06 | Innovations: innovation_city_planning, innovation_cranes, innovation_development_03, innovation_manorialism |

Три главные линии (`estate_main_01`, `east_asian_estate_main_01`, `japanese_manor_main_01`) сохраняются без изменений: культура там является только областью проверки универсальных инноваций, а не взаимоисключением.

## Файлы реализации

- `common/domiciles/types/zzz_RB_UD_domicile_types.txt` — пять точечных переопределений типов.
- `common\domiciles\buildings\zzz_RB_UD_camp_buildings.txt` — переопределения соответствующего семейства зданий.
- `common\domiciles\buildings\zzz_RB_UD_estate_buildings.txt` — переопределения соответствующего семейства зданий.
- `common\domiciles\buildings\zzz_RB_UD_yurt_buildings.txt` — переопределения соответствующего семейства зданий.
- `common\domiciles\buildings\zzz_RB_UD_east_asian_estate_buildings.txt` — переопределения соответствующего семейства зданий.
- `common\domiciles\buildings\zzz_RB_UD_japanese_manor_buildings.txt` — переопределения соответствующего семейства зданий.
- `events/zzz_RB_UD_camp_purpose_events.txt` — копия только события `ep3_laamps.1021` без 23 команд удаления тематических построек.
- `replace_path` не используется.

## Покрытие и проверки

- Типы домицилей: 5/5.
- Внешние развилки: 11/11.
- Внутренние развилки: 1/1.
- Флаги тем лагеря: 23/23.
- Ручные условные линии: 24/24; переписать 21, сохранить 3.
- Уникальных затронутых ванильных зданий: 478.
- Неизвестные условия, циклы и потерянные родители: 0.

## Что остаётся перед генерацией кода

- Generate balanced coordinates for the additional external visual slots and visually test all five domicile windows.
- After emitting gameplay overrides, compare every overridden object against the source manifest and reject unrelated drift.
- Run CK3 with error.log and debug.log checks after each domicile family is enabled.
- Regenerate Stage 1 and this plan after every supported CK3 update; signatures must be reviewed before code regeneration.
