# Unlimited Domiciles

`Unlimited Domiciles` is a clean, vanilla-oriented reimplementation of the
expanded domicile concept.

Internal object prefix: `RB_UD_`.

Current version: `0.0.0` (generated gameplay prototype; in-game layout
validation is still required).

## Current implementation stage

Stages 1-3 are complete. The project now contains a reproducible pipeline that
analyzes the installed vanilla game, builds a signed override plan, validates
that the expected vanilla inputs have not changed, and generates the gameplay
overrides used by the mod.

The analyzer builds the upgrade graph; distinguishes physical external lines
from their terminal specializations; detects external and internal branch
groups; records the exact specialization tails, tiers, icons, and panorama
textures needed by the conversion; calculates external and internal slot
demand; classifies construction restrictions and all explicit building-removal
paths; resolves referenced vanilla scripted triggers; separates compatibility
candidates from prerequisites that should be preserved; records initial-fill
effects; hashes all relevant vanilla inputs; and emits stable fingerprints for
the structure, availability rules, visual assets, and removal logic.

The generated schema v2 follows the implementation policy selected for this
mod: keep one external slot per physical building line, then turn each normally
exclusive specialization tail into a separately buildable internal track. A
branch that is already internal is reported separately because it requires
splitting its shared prefix into parallel tracks rather than merely changing
`slot_type`.

The plan builder names every vanilla type, building, scripted effect, condition
group, capacity change, and target override file; consolidates internal-slot
demand after branch conversion; and explicitly records all 24 reviewed
conditional tracks as preserved vanilla prerequisites.

The generator now mirrors all 1,620 vanilla domicile-building objects into
late-loaded override files and applies the reviewed structural plan. It does
not use `replace_path`. Buildings are split into 62 deterministic files: one
file per vanilla main/external root family together with all descendants.
Vanilla construction time is preserved and routed through generated file-local
`@RB_UD_` constants because the engine rejects global script values in
`construction_time`. Buildings sharing the same vanilla duration reuse the
same RB_UD constant within their generated family file. Direct numeric resource
costs are converted to global generated script values; existing vanilla cost
script values remain intact.

Semantic post-generation checks cover exact 1,620-object coverage, unique
ownership by one root family, valid parent links, capacities, internal slots,
valid branch anchors, preserved vanilla access prerequisites,
bounded initial-fill loops, local constant definitions, UTF-8 BOM encoding,
and disabled camp-purpose cleanup.

- Human-readable audit: `docs/generated/RB_UD_VANILLA_AUDIT.md`
- Machine-readable manifest: `tools/generated/RB_UD_vanilla_manifest.json`
- Analyzer: `../tools/Analyze-RBUDVanillaDomiciles.ps1`
- Human-readable override plan: `docs/generated/RB_UD_OVERRIDE_PLAN.md`
- Machine-readable override plan: `tools/generated/RB_UD_override_plan.json`
- Override-plan builder: `../tools/Build-RBUDOverridePlan.ps1`
- Editable domicile layouts: `tools/RB_UD_layouts.json`
- Generation settings: `tools/RB_UD_generation_settings.json`
- Gameplay generator: `../tools/Generate-RBUDOverrides.ps1`
- Generation manifest: `tools/generated/RB_UD_generation_manifest.json`
- Generation report: `docs/generated/RB_UD_GENERATION_REPORT.md`

Regenerate all artifacts after a CK3 update:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  tools/Analyze-RBUDVanillaDomiciles.ps1 `
  -GamePath "E:\SteamLibrary\steamapps\common\Crusader Kings III\game" `
  -ModPath "RB_UD"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  tools/Build-RBUDOverridePlan.ps1

powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  tools/Generate-RBUDOverrides.ps1 `
  -GamePath "E:\SteamLibrary\steamapps\common\Crusader Kings III\game" `
  -ModPath "RB_UD"
```

The generator deliberately stops when a recorded vanilla hash or structural
signature differs. In that case, rerun and review the analyzer and plan before
accepting new overrides. Files named `zzz_RB_UD_*` are generated output and
must not be edited manually. Visual slot positions belong in
`tools/RB_UD_layouts.json`.

Construction time and other generation-wide scalar policies belong in
`tools/RB_UD_generation_settings.json`. Do not edit the repeated local
constants in generated family files.

## Generated gameplay scope

- five overridden domicile types with expanded external layouts;
- all 1,620 vanilla domicile-building objects reproduced exactly once;
- 62 generated building files, grouped by vanilla root family: camp 8,
  Byzantine estate 17, yurt 8, East Asian estate 16, Japanese manor 13;
- vanilla construction times emitted through generated local `@RB_UD_`
  constants in every family file;
- direct numeric resource costs centralized as generated global script values,
  while existing vanilla script-value costs are reused unchanged;
- external specialization tails converted into independent internal tracks;
- converted roots re-anchored to valid external base buildings while retaining
  their former common tier as an explicit construction prerequisite;
- already-internal estate library specializations split into parallel tracks;
- camp-purpose construction gates removed while unrelated progression remains;
- the 23 vanilla camp-purpose cleanup removals disabled;
- initial estate generation keeps vanilla building counts instead of filling
  all expanded slots, and every generated fill loop has a hard iteration cap;
- the vanilla Japanese manor fill-effect typo is corrected in the override;
- all used vanilla `@` constants are copied into their generated database file;
- culture, territory, terrain, innovation, language, character-state, and
  similar vanilla access requirements preserved unchanged;
- costs, effects, icons, textures, upgrade order, and unrelated vanilla
  prerequisites preserved by copying the current vanilla objects.

The five domicile windows and all split specialization paths still require a
complete manual gameplay pass. Their geometry is data-driven so any overlap
can be corrected without altering the generator. The mod does not add a mass
"build everything" action or another domicile construction-speed modifier.
