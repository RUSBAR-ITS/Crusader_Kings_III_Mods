# Title Capital Changing

Title Capital Changing adds a round button to the de jure capital row of the title window. It relocates the de jure capital of a duchy, kingdom, or empire without changing the ruler's personal realm capital.

The implementation preserves the relevant standard eligibility checks and prestige costs while allowing the player to select any personally held de jure county directly from the title window.

## Rules

- The selected title must be held by the player.
- The ruler must be an adult and at peace.
- The new capital must be a personally held county inside the title's de jure hierarchy.
- The current de jure capital must remain inside the player's realm.
- The prestige cost is 500 for a duchy, 750 for a kingdom, and 1000 for an empire.
- There is no additional cooldown; each title can be changed independently whenever the other requirements are met.
- Moving a duchy capital destroys its existing duchy building, matching vanilla behavior.

## Compatibility

The game does not support appending a widget to `window_title.gui`, so the mod ships a generated copy with one marked insertion. Run `tools/Sync-TCCTitleWindow.ps1` after game updates.

An optional `TCC_HM_RE` compatibility patch is generated from the current Holding Manager: RUSBAR Edition title window.
