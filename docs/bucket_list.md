# Bucket list

Ideas agreed to come back to later, so they are not forgotten. Nothing here is built.

## Data

- **Several files at once** (raised while discussing groups, 2026-10-22): upload several files in one go on the website, process them in parallel, and give each file its own group by default (the user can rename it). Groups by file already work in Python (`stk.combine(..., groups="file")`); the website needs a several-file upload and `/groups` with `"groups": "file"` for it.

## Website (after the plotting is final)

- **Saved styles on the page** (wish list 7, item 15, option A): the page keeps the user's styles in the browser. The agreed design is "C plus A": a style file to download and load again, plus the browser. Nothing is stored on the VM. The service side (`POST /style-check`) is built with the plotting work; the page part waits for approval of changes to the website repo.
- **Live preview while editing** (wish list 7, item 16): `POST /style-preview` returns a small PNG fast enough to redraw while a slider moves. Open points:
  - which data it shows (the user's data reduced in size, or example spectra);
  - the speed measured on the VM;
  - previews must never hold up a real figure.
