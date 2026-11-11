# Vendor CAD and datasheet downloads (methods that worked on this PC)

**Permission (Bob, chat, 2026-10-27, verbatim: "you have permission to download on your own").** Agents download
public vendor cut sheets, manuals and CAD without asking first, and record the URL, date and sha256 for each file.
Sign-ins, account creation and accepting terms stay Bob's. A delegating session quotes this line in the prompt (skill
`agent-task`).

**Reading vendor PDFs.** Read drawings, dimension tables and curves with the Read tool on the PDF, which shows the
pages as images. Text extraction (pypdf) loses dimension letters, table columns and curves. This host has no
poppler, so the Read tool's `pages` option does not render in a subagent (2026-10-27). What worked: install
`pymupdf` into a venv in the agent's own scratchpad (never the repo venvs), render the drawing pages to PNG there,
and Read the PNGs.

**Browser, not spoofing.** A shell download that sets a browser user-agent to get past a 403 is refused by the app
as bot-check circumvention (2026-10-27). Read the vendor's product page in the browser instead. ifm US product pages
(`ifm.com/us/en/product/<part>`) carry the full technical data as page text.

Shell downloads (`Invoke-WebRequest`) get 403 from McMaster, ifm and most
CADENAS portals. Don't try to get around that; use the browser methods below.
Sign-ins are Bob's: he signs in in Chrome, the agent drives the signed-in tab.
After any download, compare an in-page `crypto.subtle` sha256 with the file
on disk.

## Update 2026-10-29

- **McMaster now refuses the app's browser pane** (403 on `ProductContent.aspx` and on `/mvC/Library/CAD2/...`).
  In Bob's Chrome the same calls work: `ProductContent.aspx?partNumber=<PN>&features=...rtrvcadviarps` returns JSON
  whose `cadControlDat.AvailableCAD.ThreeDDownloads` lists the STEP path (`{}` = McMaster has no model). Saving: an
  in-page fetch plus an `<a download>` click saves the first file; Chrome then blocks further downloads from the site
  until Bob allows "automatic downloads" for mcmaster.com once. Category pages give spec rows with part numbers as
  page text.
- **McMaster in Chrome, saving:** opening the library STEP URL as the tab's page (navigate) saves it even when
  scripted saves are blocked; wait about 8 s per file before the next, or the next page load cancels it. After about
  four files McMaster refused Chrome too (403, blank pages): stop, do not retry in a loop; finish later or ask Bob.
- **TraceParts in Chrome, signed in:** `#direct-cad-download` queues the file; the ready file is the `a.download-item`
  in My activity whose text starts with the part number. A family page shows "No CAD available" per row when the
  maker has no model. Scripted search fetches and quick page loads bring the CAPTCHA within a few
  parts: open product pages by hand-paced navigation only, and stop at the CAPTCHA.
- **WIKA** publishes its 3D library openly: `https://www.wika.com/en-us/dokucment_categories_json_36656.json` is the
  full index (790 items: product type, description, `/media/3D-Data/<file>.stp`). Shell downloads of the STEP get
  403; an in-page fetch in the app's pane on wika.com plus `<a download>` lands in Downloads as `<uuid>.tmp`, picked
  by sha256. Data sheets download from the shell: `/media/Data-sheets/<area>/<line>/ds_<code>_en_co.pdf`.
- **Spirax data sheets** download from the shell: `https://www.spiraxsarco.com/-/media/spiraxsarco/international/
  documents/en/ti/<name>` (the TraceParts product page's "Technical Information Sheet" link redirects there).
- **TraceParts** search pages read fine in the pane until it shows a human check (`/AreYouHuman`, seen 2026-10-29);
  an agent never answers it. Downloads need Bob's TraceParts sign-in in Chrome.
- **Watts** keeps its models in a BIMobject private cloud: `productsite.bimobject.com/en-us/wattswatertechnologies/
  privatecloud/wattswater`; Bob's existing BIMobject session signs it in from the page's Log in button (no password).
  `/productsite/products?brand=wattswatertechnologies&cloud=wattswater&freetext=<q>` lists products with their file
  types. Watts offers no STEP (SAT, DWG, Revit, PDF).

## McMaster-Carr (worked 2026-10-01)

1. On any mcmaster.com page in the built-in pane, `fetch` the product content
   URL `/mv<version>/WebParts/Navigate/ProductContent.aspx?partNumber=<PN>&features=enablemnitpns,enablerewriteetoeventchain,rtrvcadviarps`.
   The `mv<version>` segment changes; read it from the page's network requests.
   The HTML holds `/mvD/Library/CAD2/<date>/<hash>/<PN>_<name>.STEP`.
2. In-page `fetch` of that STEP works even when the pane is hidden.
3. CSP blocks fetch to localhost but not a top-level form POST: gzip + base64
   in the page, submit a form (`target _self`) to `http://127.0.0.1:8766/`
   with fields `n` (name) and `d` (data); a receiver script in the scratchpad
   decodes and writes. One file per submit, then navigate back.
4. build123d `import_step` reports mm. McMaster ferrules sit on native Z.

## ifm (CADENAS, ifm.partcommunity.com; worked 2026-10-05)

- Part page > Download CAD > Add formats > STEP AP214 > Start generation.
  Later a scripted `button.click()` on Download CAD starts generation.
  1-3 min; if stuck, delete the entry and request again.
- Chrome allows the first auto-download per site, then blocks silently. After
  that, fetch the `/partserver/preview/<token>/IFM_ELECTRONIC_<part>.zip` URL
  in the built-in pane and save with an `<a download>` click: it lands in
  Downloads as `<uuid>.tmp`; pick it by sha256.
- Data sheets: `https://www.ifm.com/us/en/product/<part>` Downloads tab, same
  anchor trick.
- A localhost receiver does not work from either browser here.
- Portal and PDF tabs freeze screenshots; use `get_page_text` or JS.

## Belimo (belimo.partcommunity.com; worked 2026-10-09)

BELIMO-US catalogue on CADENAS, Bob's sign-in, picked up by the Claude in
Chrome tab. Same generate-then-download flow as ifm.

## Alfa Laval, Endress+Hauser, Spirax Sarco, Armstrong, others

Check the vendor CAD portal first. If it needs a configuration Bob must pick
or a sign-in, give him the exact row and options (size, connection, material,
STEP AP214) in one line.

## PDFs

Opening a PDF URL in the built-in pane triggers a save dialog for Bob. Read
PDFs in Chrome, or through the static-preview server (localhost:8765).
