# Vendor CAD and datasheet downloads (methods that worked on this PC)

Shell downloads (`Invoke-WebRequest`) get 403 from McMaster, ifm and most
CADENAS portals. Don't try to get around that; use the browser methods below.
Sign-ins are Bob's: he signs in in Chrome, the agent drives the signed-in tab.
After any download, compare an in-page `crypto.subtle` sha256 with the file
on disk.

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
