---
name: brothers-keeper
description: Build the Brother's Keeper top-down Phaser rescue game module for Groundwork (find, rescue, escort the brother home across four biomes; belt and book bag combat).
---
# Brother's Keeper (game module)

**Status:** Spec v2, 2026-10-29, from Brann's dictation. No code yet.

## Platform
- Built with Phaser inside the Groundwork web app, planned at `packages/brothers-keeper/`.
- Top-down view (preferred for thumb control). Isometric is under consideration because it makes small hops easier.
- Art is sleek modern-retro, cel-shaded or hand-painted, not basic 8-bit.

## Story
The hero has gotten clean. His brother was supposed to come with him, but the villain **The Man** drugged him, kidnapped him and enslaved him. The hero follows clues across four biomes (forest, jungle, desert, mountains), rescues his brother and escorts him home.

**Win condition:** the game counts as beaten only when both brothers make it home. Rescuing the brother alone does not end it.

## Hero tools
- **Book bag (ranged):** the hero throws books, and each book breaks on impact. Two books defeat a regular enemy. Books are found at libraries, schools and offices.
- **Belt (unlimited):** grabs onto things, swings across gaps and fights at close range.
- The hero loses health when enemies hit him.

## Escort
The brother walks on his own during the escort.

## Enemies
- **Old drunk:** throws a bottle.
- **Young party drunks:** throw things.
- **The lady:** suggestive but non-explicit. She slowly drains stamina as the hero gets close, so the player has to walk around her. She can't be fought.
- **Smoker:** nearly on fire, and touching the fire does damage. The player has to go around him.
- **Fret Bros:** fitter enemies on hard levels. They take three hits: two books plus one belt hit.
- **The Man:** the final villain.

## Clues
- Clues are hidden in searchable props such as under a milk carton, in a mailbox or in a garbage can.
- The player searches these locations while dodging attacks: bars and a toned-down strip club that is suggestive but non-explicit and still playable.

## Controls (mobile)
- An analog thumbstick for movement, with no on-screen D-pad.
- One tap throws a book.
- Holding grabs with the belt.

## Sound
Music and sound effects, each of which can be turned off separately.

## Still open
- Brother's behavior in the escort: can he get hurt, and is it game over if he is caught?
- Health amount, lives and save points.
- The final choice between top-down and isometric.
- What the stamina drain does when stamina runs out.
- Number of levels per biome, plus bosses (does The Man appear at each biome?).
- Book carry limit.
- Keyboard and desktop controls.
- Free or paid tier.
- Content rating. The suggestive enemies and settings need a rating check, because the Groundwork app serves people in recovery.
