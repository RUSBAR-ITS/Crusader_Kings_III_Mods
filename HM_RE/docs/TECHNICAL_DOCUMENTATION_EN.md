# Holding Manager (RUSBAR Edition) — Technical Documentation

Version `1.0.0` · Crusader Kings III `1.19.0.6`

This document describes the current vanilla-focused implementation of Holding Manager (RUSBAR Edition), its file layout, data flow, maintenance procedure, and the integration contract for compatibility patches.

<a id="en-toc"></a>
## Table of contents

1. [Purpose and scope](#en-purpose)
2. [Runtime architecture](#en-architecture)
3. [Game rules and player-facing systems](#en-rules)
4. [Complete file reference](#en-files)
5. [Adding support for buildings from another mod](#en-modding)
6. [Updating HM_RE after a CK3 patch](#en-updating)
7. [GUI and load-order compatibility](#en-gui)
8. [Localization and encoding](#en-localization)
9. [Coding rules](#en-coding)
10. [Testing checklist](#en-testing)
11. [Known boundaries](#en-boundaries)
12. [Credits and permissions](#en-credits)

<a id="en-purpose"></a>
## 1. Purpose and scope

HM_RE provides immediate holding-management actions in the county interface and mass decisions for the personal domain or the entire sub-realm. It can construct, upgrade, replace, and remove supported regular buildings; add building slots; convert holding types; and feudalize eligible holdings.

The base package targets the unmodified vanilla game. Its central design rule is to preserve vanilla availability logic rather than invent a parallel ruleset. Building eligibility therefore mirrors the current vanilla building definitions, while thin adapters translate scopes where the Holding Manager action starts from a province instead of vanilla's normal construction context.

The base catalogs intentionally exclude duchy buildings in `1.0.0`. Non-vanilla buildings and GUI overhauls require explicit compatibility patches.

[Back to contents](#en-toc)

<a id="en-architecture"></a>
## 2. Runtime architecture

### 2.1 Single-holding actions

1. `gui/window_county_view.gui` exposes HM_RE buttons.
2. A button calls an object from `common/scripted_guis/`.
3. The scripted GUI checks ownership, game rules, holding state, construction state, costs, cooldowns, and building eligibility.
4. `common/scripted_triggers/` decides whether the requested building or conversion is legal.
5. `common/script_values/` calculates building, slot, conversion, gold, prestige, treasury, and instant-construction costs.
6. `common/scripted_effects/` performs the actual change and resolves the holder/government where necessary.

### 2.2 Mass actions

Personal-domain decisions iterate `every_directly_owned_province`. Realm-wide decisions iterate `every_realm_province` and are shown only when the vassal-scope replacement rule is enabled.

Construction, upgrade, and removal decisions use the same effect twice:

- `show_as_tooltip` renders the exact preview grouped by county and holding;
- `hidden_effect` performs the changes after confirmation.

Consequently, a compatibility effect must be deterministic and must expose the same `add_building` or `remove_building` operations used by the real execution. Cost predicates, preview predicates, and execution predicates must remain identical.

Construction effects add a first-tier building if it is legal. If no free slot exists, they may add `extra_building_slot` first when the configured slot trigger permits it. Upgrade effects advance one tier per invocation. Removal effects remove the currently installed supported tier.

### 2.3 Building eligibility

The large `HM_RE_triggers_*_buildings.txt` files reproduce four vanilla blocks for each tier:

- `is_enabled`;
- `can_construct_potential`;
- `can_construct_showing_failures_only`;
- `can_construct`.

The synchronization tool changes only the scope-sensitive pieces required by HM_RE, most importantly `scope:holder` to `province_owner`, and maps a small set of helper requirements to HM_RE wrappers. There is no `debug_only = no` bypass in building availability.

### 2.4 Initialization

`on_game_start` initializes `HM_RE_is_loaded` and the global decision-visibility variable `HM_RE_show_decisions`. The latter lets the player hide the long list of mass decisions without disabling the mod.

[Back to contents](#en-toc)

<a id="en-rules"></a>
## 3. Game rules and player-facing systems

`common/game_rules/HM_RE_controls.txt` currently defines 20 rules:

- free player functions;
- holding-type conversion cost and cooldown;
- building replacement scope: domain only or the whole sub-realm;
- feudalization scope: domain only or the whole sub-realm;
- mass-construction gold cap;
- player slot policy, base cost, and incremental cost;
- instant-construction time surcharge;
- visibility of Build All and Upgrade All;
- optional Nomad and Temple Citadel conversion buttons;
- visibility and base cost of the player Add Slots decision;
- whether player slot costs use gold or treasury;
- AI slot policy, base cost, and incremental cost.

The rules are campaign settings. Changing their definitions or removing option IDs is safest to test in a new campaign because saves serialize selected rule identifiers.

Player-facing systems include:

- county-view buttons for holding conversion, building management, slot addition, and special-building removal;
- a title-view interaction for eligible feudalization;
- six detailed personal/realm mass decisions for construct, upgrade, and clear;
- a selected-barony decision for adding a slot;
- an AI-only periodic slot decision;
- show/hide decisions that control the mass-decision list.

[Back to contents](#en-toc)

<a id="en-files"></a>
## 4. Complete file reference

### 4.1 Package root and repository support

- `descriptor.mod` — packaged mod metadata: name, version, tag, and supported CK3 version.
- `README.md` — bilingual project overview, compatibility notice, credits, and documentation links.
- `thumbnail.png` — Steam Workshop and launcher cover image.
- `docs/TECHNICAL_DOCUMENTATION_EN.md` — this English technical reference.
- `docs/TECHNICAL_DOCUMENTATION_RU.md` — Russian technical reference.
- `docs/STEAM_WORKSHOP_DESCRIPTION_EN.txt` — English Workshop-ready BBCode text, kept below Steam's 8000-character limit.
- `docs/STEAM_WORKSHOP_DESCRIPTION_RU.txt` — Russian Workshop-ready BBCode text, kept below Steam's 8000-character limit.
- `../HM_RE.mod` — local launcher descriptor pointing to `mod/HM_RE`; it mirrors package version metadata.
- `../tools/Sync-HMREBuildingTriggers.ps1` — maintenance utility that rebuilds HM_RE tier eligibility triggers from a selected CK3 installation.

### 4.2 Character interactions

- `common/character_interactions/HM_RE_interactions.txt` — `HM_RE_feudalize_vassal_holding_interaction`; validates the selected barony, government, culture, ownership, and configured scope, then applies vanilla-style tribal-to-castle feudalization effects.

### 4.3 Decisions

- `common/decisions/HM_RE_decisions_add_slot.txt` — player decision with a barony selector; adds an extra slot to an eligible directly owned holding and charges the calculated cost.
- `common/decisions/HM_RE_decisions_ai_add_slot.txt` — AI-only periodic decision; selects one eligible owned or leased church province and purchases a slot under AI rules.
- `common/decisions/HM_RE_decisions_buildings_construction.txt` — personal-domain and realm-wide Build All decisions, costs, availability, exact previews, and execution loops.
- `common/decisions/HM_RE_decisions_buildings_upgrade.txt` — personal-domain and realm-wide Upgrade All decisions with matching calculation, preview, and execution scopes.
- `common/decisions/HM_RE_decisions_hide_show.txt` — toggles the global variable controlling visibility of HM_RE decisions.
- `common/decisions/HM_RE_decisions_holdings_clear.txt` — personal-domain and realm-wide Clear All Building Slots decisions and previews.

### 4.4 Defines, rules, modifiers, and initialization

- `common/defines/zzz_HM_RE_holdings_defines.txt` — raises `NProvince.MAX_BUILDINGS`, allowing the mod's configurable extra-slot system to exceed the vanilla hard limit.
- `common/game_rules/HM_RE_controls.txt` — all 20 campaign rules and their selectable setting IDs.
- `common/modifiers/HM_RE_province_modifiers.txt` — temporary post-conversion province penalty used as the holding-type conversion cooldown marker.
- `common/on_action/HM_RE_on_actions.txt` — game-start initialization of HM_RE global variables.

### 4.5 Script values

- `common/script_values/HM_RE_values.txt` — master construction/upgrade gold and prestige totals, cost cap, dynamic cap, and combined slot-plus-construction total.
- `common/script_values/HM_RE_values_admin_buildings.txt` — per-tier and aggregate costs for Capital Bureau buildings.
- `common/script_values/HM_RE_values_buildings_slots.txt` — player/AI slot prices, default and potential slot counts, holding/development policies, event-building count, and maximum slot costs.
- `common/script_values/HM_RE_values_castle_buildings.txt` — castle holding-level upgrade prices.
- `common/script_values/HM_RE_values_change_holding_type.txt` — configured holding conversion cost and cooldown values.
- `common/script_values/HM_RE_values_city_buildings.txt` — city holding-level and Guild Halls prices.
- `common/script_values/HM_RE_values_common_buildings.txt` — Hospices prices.
- `common/script_values/HM_RE_values_construction_time_cost.txt` — quick, standard, and slow instant-construction surcharge multipliers selected by game rule.
- `common/script_values/HM_RE_values_standard_economy_buildings.txt` — tier and aggregate prices for standard economic building families.
- `common/script_values/HM_RE_values_standard_fortification_buildings.txt` — tier and aggregate prices for standard fortification families.
- `common/script_values/HM_RE_values_standard_military_buildings.txt` — tier and aggregate prices for standard military families.
- `common/script_values/HM_RE_values_temple_buildings.txt` — temple holding-level and temple-specific building prices.
- `common/script_values/HM_RE_values_temple_citadel_buildings.txt` — Temple Citadel holding-level and family prices.
- `common/script_values/HM_RE_values_tribal_buildings.txt` — tribal holding-level costs, prestige costs, and tribal-family prices.

### 4.6 Scripted effects

- `common/scripted_effects/HM_RE_effects.txt` — master construct, upgrade, remove, and remove-special aggregators used by GUI controls and mass decisions.
- `common/scripted_effects/HM_RE_effects_ach_buildings.txt` — construct/upgrade/remove effects for the three oath building families.
- `common/scripted_effects/HM_RE_effects_admin_buildings.txt` — Capital Bureau effects.
- `common/scripted_effects/HM_RE_effects_auxiliary.txt` — post-conversion title-holder, lease, and government resolution.
- `common/scripted_effects/HM_RE_effects_castle_buildings.txt` — castle holding-level upgrade effect.
- `common/scripted_effects/HM_RE_effects_city_buildings.txt` — city holding-level and Guild Halls effects.
- `common/scripted_effects/HM_RE_effects_common_buildings.txt` — Hospices effects.
- `common/scripted_effects/HM_RE_effects_standard_economy_buildings.txt` — construct/upgrade/remove effects for all supported standard economic families.
- `common/scripted_effects/HM_RE_effects_standard_fortification_buildings.txt` — equivalent effects for standard fortification families.
- `common/scripted_effects/HM_RE_effects_standard_military_buildings.txt` — equivalent effects for standard military families.
- `common/scripted_effects/HM_RE_effects_temple_buildings.txt` — temple holding-level and temple-family effects.
- `common/scripted_effects/HM_RE_effects_temple_citadel_buildings.txt` — Temple Citadel holding-level and family effects.
- `common/scripted_effects/HM_RE_effects_tribal_buildings.txt` — tribal holding-level and tribal-family effects.

### 4.7 Scripted GUIs

- `common/scripted_guis/HM_RE_guis_buildings_slots.txt` — county-view Build All, Upgrade All, Clear, Remove Special, and Add Slot button logic.
- `common/scripted_guis/HM_RE_guis_change_holding_type.txt` — Castle, Temple, City, Nomad, and Temple Citadel conversion buttons, costs, cooldowns, and post-conversion resolution.
- `common/scripted_guis/HM_RE_guis_replace_holder.txt` — internal debug-only holder replacement helper; intentionally not part of normal gameplay.

### 4.8 Scripted triggers

- `common/scripted_triggers/HM_RE_building_slot_triggers.txt` — validates a selected barony for the player Add Slot decision.
- `common/scripted_triggers/HM_RE_triggers.txt` — master build/upgrade/remove eligibility, mass-action filters, and supported-building removal catalog.
- `common/scripted_triggers/HM_RE_triggers_auxiliary.txt` — manual scope adapters for tribal/Wanua and terrain requirements not copied verbatim from vanilla.
- `common/scripted_triggers/HM_RE_triggers_slots.txt` — player/AI slot-policy dispatch and final add-slot eligibility.
- `common/scripted_triggers/HM_RE_triggers_ach_buildings.txt` — generated tier eligibility for oath building families.
- `common/scripted_triggers/HM_RE_triggers_admin_buildings.txt` — generated Capital Bureau tier eligibility.
- `common/scripted_triggers/HM_RE_triggers_castle_buildings.txt` — generated castle holding-level eligibility.
- `common/scripted_triggers/HM_RE_triggers_city_buildings.txt` — generated city holding-level and Guild Halls eligibility.
- `common/scripted_triggers/HM_RE_triggers_common_buildings.txt` — generated Hospices eligibility.
- `common/scripted_triggers/HM_RE_triggers_standard_economy_buildings.txt` — generated eligibility for standard economic families.
- `common/scripted_triggers/HM_RE_triggers_standard_fortification_buildings.txt` — generated eligibility for standard fortification families.
- `common/scripted_triggers/HM_RE_triggers_standard_military_buildings.txt` — generated eligibility for standard military families.
- `common/scripted_triggers/HM_RE_triggers_temple_buildings.txt` — generated temple holding-level and family eligibility.
- `common/scripted_triggers/HM_RE_triggers_temple_citadel_buildings.txt` — generated Temple Citadel holding-level and family eligibility.
- `common/scripted_triggers/HM_RE_triggers_tribal_buildings.txt` — generated tribal holding-level and family eligibility.

### 4.9 GUI and graphics

- `gui/window_county_view.gui` — current vanilla county window plus the HM_RE control strip and expanded building-grid support. This is a full vanilla-file override.
- `gui/window_title.gui` — current vanilla title window plus the HM_RE feudalization button. This is a full vanilla-file override.
- `gui/decision_view_widgets/HM_RE_decision_view_widget_building_special.gui` — selected-barony widget used by the Add Slot decision.
- `gui/preload/HM_RE_basis_textformatting.gui` — shared player, AI, enabled, disabled, default, and neutral text colors.
- `gui/preload/HM_RE_textformatting.gui` — HM_RE rule, positive, and negative text colors.
- `gfx/interface/buttons/HM_RE_upgrade.dds` — custom upgrade-all button texture.

### 4.10 Localization

Every supported language has the same three-file/key layout:

- `localization/english/HM_RE_basis_l_english.yml` — seven reusable formatting/role fragments.
- `localization/english/HM_RE_decisions_l_english.yml` — ten mass-decision names.
- `localization/english/HM_RE_localization_l_english.yml` — 224 core UI, rule, option, interaction, message, and tooltip keys.
- `localization/russian/HM_RE_basis_l_russian.yml` — Russian basis fragments.
- `localization/russian/HM_RE_decisions_l_russian.yml` — Russian decision names.
- `localization/russian/HM_RE_localization_l_russian.yml` — Russian core localization.
- `localization/french/HM_RE_basis_l_french.yml` — French basis fragments.
- `localization/french/HM_RE_decisions_l_french.yml` — French decision names.
- `localization/french/HM_RE_localization_l_french.yml` — French core localization.
- `localization/german/HM_RE_basis_l_german.yml` — German basis fragments.
- `localization/german/HM_RE_decisions_l_german.yml` — German decision names.
- `localization/german/HM_RE_localization_l_german.yml` — German core localization.
- `localization/spanish/HM_RE_basis_l_spanish.yml` — Spanish basis fragments.
- `localization/spanish/HM_RE_decisions_l_spanish.yml` — Spanish decision names.
- `localization/spanish/HM_RE_localization_l_spanish.yml` — Spanish core localization.
- `localization/korean/HM_RE_basis_l_korean.yml` — Korean basis fragments.
- `localization/korean/HM_RE_decisions_l_korean.yml` — Korean decision names.
- `localization/korean/HM_RE_localization_l_korean.yml` — Korean core localization.
- `localization/simp_chinese/HM_RE_basis_l_simp_chinese.yml` — Simplified Chinese basis fragments.
- `localization/simp_chinese/HM_RE_decisions_l_simp_chinese.yml` — Simplified Chinese decision names.
- `localization/simp_chinese/HM_RE_localization_l_simp_chinese.yml` — Simplified Chinese core localization.

[Back to contents](#en-toc)

<a id="en-modding"></a>
## 5. Adding support for buildings from another mod

The recommended delivery format is a separate compatibility patch that depends on and loads after both HM_RE and the building mod. Do not put optional third-party checks into the vanilla-focused base package.

### 5.1 Required data for each building family

For a family such as `example_building_01` through `example_building_04`, provide:

1. **Tier triggers** — `YOUR_PREFIX_can_construct_example_building_01`, etc. Copy all relevant source-building eligibility blocks and adapt only scopes that differ. The first tier must reject an existing equal-or-higher building; higher tiers must require the exact previous tier.
2. **Family triggers** — one construct wrapper for tier 1 and one upgrade wrapper containing legal higher tiers.
3. **Cost values** — per-tier values, a first-tier construct total, and an ordered next-tier upgrade total. Reuse the correct quick/standard/slow instant-time multiplier.
4. **Effects** — construct, upgrade, and remove effects. Construction must add a slot through the existing HM_RE slot trigger when permitted. Upgrade and removal should use ordered `if`/`else_if` branches.
5. **Potential-slot accounting** — add the family to `HM_RE_value_potential_buildings` so Build All reserves the correct number of slots.
6. **Master integration** — extend construct/upgrade/remove effects, construct/upgrade/remove triggers, gold/prestige totals where relevant, and `HM_RE_trigger_remove_buildings`.
7. **Localization** — add only new HM_RE UI keys; CK3 already localizes the building itself if the source mod does so.

Current master objects that normally need extension are:

- `HM_RE_effect_construct_buildings`;
- `HM_RE_effect_upgrade_buildings`;
- `HM_RE_effect_remove_buildings`;
- `HM_RE_can_construct_buildings`;
- `HM_RE_can_upgrade_buildings`;
- `HM_RE_trigger_remove_buildings`;
- `HM_RE_value_construct_buildings_gold_cost`;
- `HM_RE_value_upgrade_buildings_gold_cost`;
- `HM_RE_value_potential_buildings`.

If the added family spends prestige, changes holding levels, is special/duchy-only, or has mutually exclusive county-wide limits, extend the corresponding totals and filters as well.

### 5.2 Important patch limitation

Paradox top-level scripted objects do not merge. A later file defining `HM_RE_effect_construct_buildings` replaces the earlier object. A compatibility patch that overrides a master aggregator must therefore copy the current HM_RE body and add its calls, then be reviewed after every HM_RE update. Use your own prefix for all non-overridden patch objects.

### 5.3 Vanilla synchronization tool and mod buildings

`Sync-HMREBuildingTriggers.ps1` reads only the `common/buildings` directory below the supplied `GamePath`. It rebuilds IDs already present in HM_RE's eleven generated trigger files and fails if an ID is absent from that source tree. Therefore:

- use it directly for supported vanilla buildings;
- do not add a third-party ID to the base generated files unless the supplied source tree actually contains that definition;
- for an external compatibility patch, maintain separate trigger files or adapt the tool in the patch repository to read both vanilla and mod building sources.

### 5.4 What to preserve from the source building

Check every tier for terrain, holding type, government, culture, innovation, era, county-capital, county-wide count, prerequisite building, faith, parameter, DLC/feature, and mutual-exclusion conditions. A cultural parameter may unlock a tier earlier than the ordinary innovation path, so replacing these blocks with a simplified era check is not acceptable.

[Back to contents](#en-toc)

<a id="en-updating"></a>
## 6. Updating HM_RE after a CK3 patch

1. Update both `descriptor.mod` and `../HM_RE.mod` version metadata.
2. Diff vanilla `gui/window_county_view.gui` and `gui/window_title.gui` against the HM_RE copies; rebase vanilla changes while preserving only the marked HM_RE additions.
3. Run:

   ```powershell
   .\tools\Sync-HMREBuildingTriggers.ps1 -GamePath "C:\Path\To\Crusader Kings III\game"
   ```

4. Review the generated diff. The tool overwrites the eleven generated trigger files and writes UTF-8 BOM with CRLF.
5. Compare vanilla building IDs with the HM_RE effect/value catalogs. The generator updates requirements for known IDs; it does not automatically add a newly introduced building family to effects, costs, slot accounting, or master aggregators.
6. Review renamed/removed building tiers, holding types, helper triggers, scripted values, GUI datamodel calls, and localization keys.
7. Validate every language has the same key set and all CK3 `.yml` files retain UTF-8 BOM.
8. Test a new campaign and inspect `error.log`, `debug.log`, `game.log`, and `gui_warnings.log`.

[Back to contents](#en-toc)

<a id="en-gui"></a>
## 7. GUI and load-order compatibility

The two full vanilla GUI overrides are the highest-risk compatibility surface. A patch must start from the version that should win load order, then reinsert the HM_RE blocks identified by `HM_RE_` names. Loading two independent replacements does not merge them.

The decision widget uses CK3's `create_holy_order` controller as a reusable barony selector. Preserve its expected saved scopes (`barony`, `barony.title_province`, and ruler context) when changing it.

Scripted building compatibility usually does not require editing the GUI. New controls, new holding types, or different title/county windows do.

[Back to contents](#en-toc)

<a id="en-localization"></a>
## 8. Localization and encoding

- CK3 localization files must be UTF-8 with BOM.
- Keep the exact `l_<language>:` header and standard language directory.
- Preserve `$KEY$`, `[Concept|E]`, `[Scope.Get...]`, formatting tags, and icon tokens.
- Add the same key to all seven languages; a placeholder English value is preferable to a missing key during development.
- English and Russian are the reviewed reference localizations. French, German, Spanish, Korean, and Simplified Chinese were completed with AI assistance and require human review.
- Documentation Markdown and Workshop `.txt` files use ordinary UTF-8 and are not parsed by CK3.

[Back to contents](#en-toc)

<a id="en-coding"></a>
## 9. Coding rules

- Prefix fork-owned objects and files with `HM_RE_`. Compatibility patches should use their own unique prefix.
- Preserve vanilla logic and reuse vanilla scripted requirements where their scope is valid.
- Write explicit scope comments for public scripted effects, triggers, and values.
- Keep trigger, cost, preview, and execution ordering synchronized.
- Do not use `debug_only = no` to bypass construction requirements.
- Do not silently add non-vanilla integrations to the base package.
- Treat generated trigger files as generated sources: change vanilla adapters or the generator, then regenerate.
- Preserve unrelated user changes when rebasing the two vanilla GUI files.
- Avoid duplicate localization keys and duplicate top-level script object IDs.

[Back to contents](#en-toc)

<a id="en-testing"></a>
## 10. Testing checklist

- Start a new campaign with intended game rules.
- Test Castle, City, Temple, Tribal, Administrative, Temple Citadel, and enabled Nomad paths where available.
- Test one personal and one vassal holding for build, upgrade, replace, clear, add-slot, conversion, and feudalization actions.
- Confirm disabled buttons explain the same vanilla requirement that blocks ordinary construction.
- Compare displayed cost with the resource actually removed.
- Verify treasury-versus-gold behavior and free-functions behavior.
- Fill all ordinary slots, then confirm Build All adds only the slots permitted by player/AI policy.
- Test all six mass decisions and compare preview with the result holding by holding.
- Confirm realm decisions appear only under the vassal-scope rule.
- Verify special and duchy buildings are not accidentally removed by ordinary Clear All.
- Inspect logs after closing the game. Search for `HM_RE`, source filenames, unknown effects/triggers/values, missing localization, GUI parse errors, and duplicate objects.
- Expect removed historical game-rule IDs to remain in old save metadata; use a new campaign for a clean rule-loading test.

[Back to contents](#en-toc)

<a id="en-boundaries"></a>
## 11. Known boundaries

- Version `1.0.0` supports the vanilla building set except duchy buildings in mass catalogs.
- External building mods are not discovered dynamically.
- Full GUI overrides can conflict with any mod replacing the same county or title window.
- Game-rule settings are serialized into saves.
- The mod raises the global maximum building count; another mod changing the same define requires an explicit compatibility choice.
- Instant HM_RE actions reproduce vanilla eligibility, not vanilla construction queues or elapsed time. The configured surcharge compensates for skipped time.

[Back to contents](#en-toc)

<a id="en-credits"></a>
## 12. Credits and permissions

Thanks to the authors of [Holding Manager Continued](https://steamcommunity.com/sharedfiles/filedetails/?id=3473706726) and the [original Holding Manager](https://steamcommunity.com/sharedfiles/filedetails/?id=2633505646) for the idea and implementation on which this fork is based.

RUSBAR Edition may be used, copied, modified, redistributed, forked, translated, re-uploaded, incorporated into other projects, or supported by arbitrary compatibility patches. Attribution and links to the predecessors are appreciated.

[Repository](https://github.com/RUSBAR-ITS/Crusader_Kings_III_Mods) · [Russian documentation](TECHNICAL_DOCUMENTATION_RU.md) · [Back to contents](#en-toc)
