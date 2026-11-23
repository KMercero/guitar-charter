# Guitar Charter

A standalone Windows tool that turns an MP3 into a playable Clone Hero /
Moonscraper guitar chart. Focused on **playability and visual flow**, not
hyper-insane difficulty — for quickly generating a playable draft you refine
in Moonscraper.

## How it works
1. Separate the guitar stem (Demucs `htdemucs_6s`).
2. Detect notes (Basic Pitch).
3. **Fret mapper** (this project's contribution): constraint-based dynamic
   programming scoring ergonomics, visual pattern regularity, and HOPO
   friendliness.
4. Emit `notes.chart` + `song.ini`.

## Usage
1. Run `GuitarCharter.exe`.
2. Pick an MP3, pick an output folder, hit **Chart Guitar**.
3. Add the original audio to the output folder as `song.ogg`, then open the
   folder in Moonscraper to refine.

## Honest scope
Generates a *playable draft*. Expect to fine-tune in Moonscraper.

## Build from source
See BUILD.md.