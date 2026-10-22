# Bucket list

Ideas agreed to come back to later, so they are not forgotten. Nothing here is built.

## Plotting

- **Panels, kind "compare"** (wish list 7, item 12 g): a before/after view as one panel of `stk.panels`.
- **Panels, one per group** (wish list 7, item 12 h): one panel per sample from one data set, e.g. by the names CV / MB / RhB (`"group_by": "name"`).

## Website (after the plotting is final)

- **Saved styles on the page** (wish list 7, item 15, option A): the page keeps the user's styles in the browser. The agreed design is "C plus A": a style file to download and load again, plus the browser. Nothing is stored on the VM. The service side (`POST /style-check`) is built with the plotting work; the page part waits for approval of changes to the website repo.
- **Live preview while editing** (wish list 7, item 16): `POST /style-preview` returns a small PNG fast enough to redraw while a slider moves. Open points:
  - which data it shows (the user's data reduced in size, or example spectra);
  - the speed measured on the VM;
  - previews must never hold up a real figure.
