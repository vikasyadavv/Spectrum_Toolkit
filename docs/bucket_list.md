# Bucket list

Ideas agreed to come back to later, so they are not forgotten. Nothing here is built.

## Data

- **Several files at once** (raised while discussing groups, 2026-10-22): upload several files in one go on the website, process them in parallel, and give each file its own group by default (the user can rename it). Groups by file already work in Python (`stk.combine(..., groups="file")`); the website needs a several-file upload and `/groups` with `"groups": "file"` for it.

## Website (after the plotting is final)

- **Saved styles on the page** (wish list 7, item 15 A): "My styles" kept in the browser (save, rename, duplicate, delete, set as default, download one or all, load a file), checked by `/style-check` with `"lenient": true`. Nothing is stored on the VM. The service part is built (style files version 1, `"file"`, `"renamed"`, `"skipped"`); the page waits for approval of changes to the website repo. The browser store keeps sections (`styles` now, `recipes` later).
- **Live preview while editing** (wish list 7, item 16): the page asks `/figure` at dpi 60 with the same size in cm, 0.3 s after the last change, one request at a time (a newer change cancels the older one), keeping the last good picture; a 422 is shown next to the setting it names. For the preview only, the page thins each spectrum to about 1000 points, keeping the lowest and highest value of each stretch so sharp bands and spikes still show. Before a file is loaded it uses `GET /example` (built). If the VM is slow: a `"preview": true` answer "busy" so previews never wait in line.
- **Sharing a style by link** (agreed 2026-10-22): the style goes inside the link itself (`...#style=...`), so nothing is stored on the VM; opening the link offers "Add this style?".
- **Journal presets** (agreed 2026-10-22): built-in sizes such as ACS single column 8.25 cm and double column 17.8 cm, RSC and Elsevier, so users do not have to look them up.
