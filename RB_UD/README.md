# Unlimited Domiciles

`Unlimited Domiciles` is a clean, vanilla-oriented reimplementation of the
expanded domicile concept.

Internal object prefix: `RB_UD_`.

Current version: `0.0.0` (analysis scaffold; no gameplay changes yet).

## Current implementation stage

Stage 1 is complete: the project has a read-only vanilla domicile analyzer.
It builds the upgrade graph; distinguishes physical external lines from their
terminal specializations; detects external and internal branch groups; records
the exact specialization tails, tiers, icons, and panorama textures needed by
the planned conversion; calculates external and internal slot demand;
classifies construction restrictions and all explicit building-removal paths;
records initial-fill effects; and hashes all relevant vanilla inputs.

The generated schema v2 follows the implementation policy selected for this
mod: keep one external slot per physical building line, then turn each normally
exclusive specialization tail into a separately buildable internal track. A
branch that is already internal is reported separately because it requires
splitting its shared prefix into parallel tracks rather than merely changing
`slot_type`.

- Human-readable audit: `docs/generated/RB_UD_VANILLA_AUDIT.md`
- Machine-readable manifest: `tools/generated/RB_UD_vanilla_manifest.json`
- Analyzer: `../tools/Analyze-RBUDVanillaDomiciles.ps1`

Regenerate both artifacts after a CK3 update:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  tools/Analyze-RBUDVanillaDomiciles.ps1 `
  -GamePath "E:\SteamLibrary\steamapps\common\Crusader Kings III\game" `
  -ModPath "RB_UD"
```

Planned scope:

- allow all compatible external domicile building lines to coexist;
- allow normally exclusive internal building branches to coexist;
- preserve vanilla costs, prerequisites, effects, and progression wherever
  they are unrelated to building exclusivity;
- keep camp buildings when the camp purpose/theme changes;
- do not add a mass "build everything" action;
- do not add another domicile construction-speed modifier.
