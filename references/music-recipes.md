# Music Recipes

## Built-In Styles

- `uk-bassline`: 138 BPM, F minor, drum/sub/donk/reese/stab workflow.
- `trap`: 140 BPM, A minor, drums/808/lead workflow.
- `deep-house`: 124 BPM, C minor, drums/bass/chord workflow.

Use `list_style_recipes` for summaries and `style_recipe(style)` for structured track, scene, pattern, and mixer hints.

## Pattern Names

- Drums: `four-on-floor`, `breakbeat`, `amen`, `trap`, `ukg-shuffle`
- Bass: `reese`, `bassline-house`, `garage-bass`, `speed-garage`
- Harmony and lead: `arp`, `chord-stab`, `chords`
- UK bassline: `donk`

## Drum Rack Map

- `36` C1: kick
- `38` D1: snare
- `42` F#1: closed hat
- `46` A#1: open hat

If a kit uses different pads, write notes manually with `add_notes_to_clip`.

## Prompt To Tool Mapping

- "make a beat": find drum track, then `make_pattern(..., style="four-on-floor" or "trap")`
- "make it bouncier": use `variation` into a new slot, then compare.
- "add harmony": use `harmonize` into a separate track.
- "build a full session": use `style_recipe`, create tracks/scenes, then fill cells.
