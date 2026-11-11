# CPME USA style guide

The one company-wide standard for how CPME USA looks and sounds: name, logo, colours, type, writing, and the
layout of every kind of document CPME sends out. It is harness level (company-wide; Bob, chat, 2026-11-10:
"engineering harness, and system level"), so `harness_sync.py` carries it into every job.

Every new document, page, slide, drawing or email made in any CPME job follows this guide. When a job or
project needs something the guide does not cover, add it here (ask Bob first), not in the job.

| File | What it is |
|---|---|
| `README.md` | This guide (the rules) |
| `brand.yaml` | The same values as data, for scripts (colours, fonts, contact block, logo files) |
| `brand.css` | The same values as CSS custom properties, for HTML pages, portals and data sheets |
| `assets/cpme-logo.png` | The logo, 288 x 216 px, full colour, white background |
| `assets/cpme-logo.svg` | The logo as SVG, 1000 x 743 viewBox (traced from the bitmap, see "Logo") |
| `../cad-lib/cpme-logo.dxf` | The logo as a CAD block (`CPME_LOGO_EMBEDDED`), used by `cpme_titleblock.py` |

## Sources

Everything here was taken from CPME's own material, read on 2026-11-10. Nothing is invented. Where sources
disagree, the guide says which one wins and why.

| Source | What it gave |
|---|---|
| www.cpme-usa.com | Company name, services, products, address, phone, email, social links, the logo on a white tile |
| `Documents\CPME Reference Material\1072-01 Coca Cola Atlantic Bottling Co. Proposal.pdf` (May 6, 2025) | Letterhead, footer band, section bars, quote layout, Arial, Document Blue `#0B5394`, voice of a proposal |
| `Documents\CPME Reference Material\Abarta Coca-Cola CIP Double Skid - rev00.pdf` and `Title Block.pdf` | Drawing sheet format and title block (now in `harness/cad-lib/cpme_titleblock.py`) |
| CPME logo bitmap (from the Abarta set) | Logo colours, measured: navy `#0D1554`, steel grey `#7E849E` |
| Project portals (`portal.css`, CIP-Skid and Hot-Water-Set) | Web fonts, web colour tokens, light and dark themes, the white logo tile, the site footer |
| `CIP-Product-Data-Sheet.html` (CIP-Skid typicals) | One-page data sheet layout, "no makers, tags or job numbers" rule for sales literature |

## 1. Name

| Use | Write | Where |
|---|---|---|
| Legal name | **CPME USA LLC** | Covers, footers, copyright, quotes, purchase-order instructions, contracts |
| Company name | **CPME USA** | Running text, signatures, title blocks, slide footers |
| Short form | **CPME** | After the first mention, and in terms and conditions ("CPME shall...") |

- Always capitals, no full stops: CPME, never Cpme, C.P.M.E. or cpme (except in web and email addresses).
- No comma before LLC. The 2025 proposal wrote "CPME USA, LLC" once; the website and the proposal cover write
  "CPME USA LLC", so that form wins.
- Copyright line: `© CPME USA LLC. All Rights Reserved` (as on the website).
- Products keep their own names and spelling: **ClearTrend** (cleartrend.io), **BeaconLink** (beaconlink.io).

## 2. Contact block

The one current address is the one on the website and on the 2025 proposal:

```
CPME USA LLC
600 Faust Rd., Unit 38
Burlington, WI 53105
414-877-0770
sales@cpme-usa.com · support@cpme-usa.com
www.cpme-usa.com
www.linkedin.com/company/cpme-usa
```

- Phone is written `414-877-0770` (no `1-`, no brackets).
- One-line form, for footers: `CPME USA LLC · 600 Faust Rd., Unit 38, Burlington, WI 53105 · www.cpme-usa.com`
- `sales@` is for quotes and new work, `support@` for existing systems. A person's own address
  (`first.last@cpme-usa.com`) goes in their signature and on documents they prepare.
- Social: LinkedIn `linkedin.com/company/cpme-usa`, Facebook `facebook.com/CPMEUSA`, X `@cpme_usa`.
- **Open item:** the drawing title block (`cpme_titleblock.py`, from the older `Title Block.pdf`) still prints
  `441 MILWAUKEE AVE STE 6, BURLINGTON WI 53105`. It changes to the address above only when Bob says so.

## 3. Logo

The logo is a navy crescent "C" around a steel-grey "C", with "CPME" in navy inside it.

**Files.** Use only the files in this folder and `cad-lib/cpme-logo.dxf`. Never redraw, retrace or AI-generate
the logo. The PNG is the original bitmap. The SVG was traced from that bitmap for web use; it is not CPME's
original vector artwork. **Open item:** ask whoever made the logo for the original vector file (AI, EPS, PDF or
SVG); when it arrives it replaces the SVG here, with a note of where it came from.

**Rules.**
- Keep the proportions (about 4 : 3). Never stretch, rotate, recolour, outline, shadow or crop it.
- Clear space on every side: at least one quarter of the logo's height.
- Smallest size: 0.5 in wide in print, 48 px wide on screen. The PNG is 288 x 216 px, so in print it stays at
  or under about 1.5 in wide (about 200 dpi); larger print needs the SVG or the original vector.
- Background: white or very light only. On navy or a photo, put the logo on a white tile with rounded corners
  (as on the website and the portal top bar). Never place it straight on a dark colour.
- One colour: black only where colour is not possible (CAD title blocks on layer `P-ANNO-LOGO`, fax, stamps).
- The logo goes with the name: top of a cover, a letterhead, a title block, the bottom right of a slide or a
  footer band. Not as a pattern or a watermark.

## 4. Colour

Two colours come from the logo; the rest support them. Hex values are sRGB. Contrast is against white.

| Name | Hex | From | Use | Contrast |
|---|---|---|---|---|
| **CPME Navy** | `#0D1554` | Logo (measured) | Headings, footer band, web top bar, title text, the main brand colour | 16.8 : 1 |
| **CPME Steel** | `#7E849E` | Logo (measured) | Rules, borders, logo-matched accents, large text only | 3.7 : 1 |
| **Document Blue** | `#0B5394` | 2025 proposal | Section bars (white text), header rule, links in documents | 7.8 : 1 |
| Ink | `#0F1733` | Portal | Body text on screen | 17.6 : 1 |
| Ink 2 | `#3A4466` | Portal | Secondary text | 9.6 : 1 |
| Muted | `#6B7394` | Portal | Captions, notes, table headers | 4.7 : 1 |
| Rule | `#CFD5E6` | Portal | Table lines, dividers | n/a |
| Tint | `#EEF2FB` | Portal | Table header fill, label cells | n/a |
| Page | `#F4F6FB` | Portal | Web page background (paper stays white) | n/a |

Status colours (checks, gates, registers only, never decoration): OK `#138A5A`, Warning `#B7791F`,
Fail `#C53030`. Always pair a status colour with a word (PASS, HOLD, FAIL), never colour alone.

- Body text is never Steel (3.7 : 1 is too light for small text).
- White text goes on Navy or Document Blue only.
- The website's green button (`#51BD55`) is the website's own. Do not use it in documents or portals.
- Dark theme (web only): the values in `brand.css` `[data-theme="dark"]`, the same as the portals.
- Drawings stay black on white (CAD layers set the colour); the brand colours are not used on drawings.

## 5. Type

| Medium | Headings | Body | Numbers, tags, part numbers |
|---|---|---|---|
| Word, Google Docs, PDF proposals, quotes, letters | Arial Bold | Arial | Arial |
| Web pages, portals, HTML data sheets, HTML slides | Archivo 600-800 | IBM Plex Sans 400-600 | IBM Plex Mono |
| PowerPoint and Google Slides | Arial Bold | Arial | Arial |
| Drawings (DWG, DXF, PDF from DWG) | CAD text styles in `cpme_titleblock.py` | same | same |
| Email | Arial (the mail program's default sans) | same | same |

Arial is what the 2025 proposal uses and is on every PC. Archivo and IBM Plex are what the portals already
load (Google Fonts, free); fall back to `system-ui, "Segoe UI", Arial, sans-serif`.

**Sizes for documents** (from the 2025 proposal):

| Element | Size |
|---|---|
| Cover title (customer, project) | 20-22 pt bold |
| Cover "CPME USA LLC" | 22 pt bold |
| Section bar text | 12-14 pt bold, white on Document Blue |
| Sub-heading | 11-12 pt bold |
| Body | 10-11 pt |
| Tables, notes | 9 pt |
| Footer | 8-9 pt |

Sentence case for headings ("Scope of work"), except the cover and the words QUOTATION and DRAFT. Line
spacing 1.15 to 1.3. Left-aligned text, never justified.

## 6. Writing

CPME's voice, from the website and the proposal: direct, practical and client-focused. Say what CPME will
do and what the customer gets.

- Plain technical English: short sentences, one idea each, active voice ("CPME supplies the skid", not "the
  skid will be supplied").
- Lead with the result, then the detail.
- Every value has its unit (`110 in x 50 in`, `1,115,000 Btu/h`, `14-16 weeks`). US customary units first.
- Quantities in commercial text as word and digit: `Two (2) chemical pumps` (as in the proposal).
- Customer and site names exactly as the customer writes them. Check spelling on every cover and header (the
  2025 proposal has "Atlantic Cola Cola Bottling Co" in one place).
- Tags, line numbers and part numbers exactly as on the P&ID or the maker's sheet (CLAUDE.md "Units and naming").
- Dates: `May 6, 2025` in customer letters and quotes; `2025-05-06` (ISO) in drawings, registers and file names.
- No hype ("world-class", "cutting-edge", "best-in-class"). Name the capability instead.
- Sales literature (website data sheets, brochures): no maker names, tag numbers or job numbers.
- Never invent a figure, approval, signature or date (CLAUDE.md hard rule 1).

**Proven phrases from CPME's own text** (use as a model, not word for word):
- "Every client has different needs." / "...tailored to your specific application."
- "Technical Services with a Focus on Client Success."
- "Please contact me if you have any questions or need clarification on the proposed solution."

**What CPME does** (the website's list, in this order): process design (CIP, batching, blending, thermal
processing, skid-based systems); PLC programming and support (Allen-Bradley); HMI / SCADA / OIT
(FactoryTalk View, Ignition, iFix, Wonderware); communications and networks; instrument calibration;
web reporting; ClearTrend; BeaconLink.

## 7. Documents

### 7.1 Customer documents: proposals, quotes, letters (Word or Google Docs, sent as PDF)

From the 2025 proposal:

- **Header (every page):** the logo centred at the top, about 0.75 in tall, then a full-width 2 pt rule in
  Document Blue.
- **Footer (every page):** a full-width CPME Navy band, white text: address with a map-pin icon, web site and
  LinkedIn with icons, sales email and phone with icons, and the logo on a white tile at the right.
- **Cover:** "Proposal Prepared for:", customer name, project name, "For Services, Materials, and Equipment
  from:", CPME USA LLC, the logo, project number, date. Centred.
- **Quote box:** a two-cell bordered row `Quote No: <nnnn-nn>` | `Date: <Month D, YYYY>`, then "Prepared for"
  (left) and "Prepared by" (right) with name, company and email.
- **Section bars:** full-width Document Blue bar, white bold heading, left-aligned (for example "Executive
  Summary").
- **Order of sections:** Cover, Executive summary (project overview, scope of work), drawings (P&ID), Quotation
  (bill of materials by area, total, quotation notes, payment terms), General conditions of work.
- **Quotation table:** columns Catalog # | Description | Qty/Unit; one table per area (control panel, skid).
- **Sign-off:** "Best Regards," then the signer's name (bold), signature, title (bold) and *CPME USA*.
- **Page size:** US Letter for new documents. **Open item:** the 2025 proposal PDF is US Legal (8.5 x 14 in);
  confirm with Bob whether proposals stay Legal.
- File name: `<Project No> <Customer> Proposal.pdf` (as `1072-01 Coca Cola Atlantic Bottling Co. Proposal.pdf`).

### 7.2 Data sheets and product literature (HTML printed to PDF)

- US Letter, one page where possible, `@page { margin: 0 }` with the page's own margins.
- Header: logo left, kicker in small caps (Document Blue), title in Navy, a document-info table at the right
  (document ID, revision, date).
- Section headings: white text on a Navy band. Tables: Tint header row, Rule lines.
- Footer: a Navy rule, then the one-line contact block left and `<DOC-ID> Rev <X> · Page n of m` right.
- Link `brand.css` (or copy its `:root` block) instead of new colour values. Existing filed revisions are
  never changed (TR-08); a sheet moves to these tokens on its next revision.

### 7.3 Project portals and web pages

- Use `brand.css` tokens and the portal pattern already in use: Navy top bar, the logo on a white rounded
  tile, light and dark themes, the one-line contact block in the footer.
- Archivo headings, IBM Plex Sans body, IBM Plex Mono for tags and numbers.
- Customer-facing pages follow the writing rules above; internal working pages may use job shorthand.

### 7.4 Drawings

- Every drawing carries the CPME sheet format from `harness/cad-lib/cpme_titleblock.py`: border with zone
  numbers and letters, header band, DRAFT stamp until approved, title block with the logo, revision block.
- Revision letters, filing and clouds follow CLAUDE.md "Drawing and design revisions". This guide adds nothing
  to them.
- Black on white. No brand colours on drawings.

### 7.5 Slides (customer and sales)

- 16 : 9 (1920 x 1080 for HTML, widescreen in PowerPoint).
- White background, Navy titles, Document Blue for one accent, the logo bottom right on every slide, the
  cover with the logo and the customer and project names.
- Arial in PowerPoint, Archivo / IBM Plex in HTML.
- The weekly dev meeting decks are internal and keep their own comedy themes; this section is for slides a
  customer or partner sees.

### 7.6 Email signature

```
<First Last>
<Title>
CPME USA
<direct phone> · 414-877-0770
<first.last>@cpme-usa.com · www.cpme-usa.com
600 Faust Rd., Unit 38, Burlington, WI 53105
```

- Name in bold Navy, the rest in Ink or Muted, Arial 10-11 pt.
- The logo (PNG, shown at about 72 px wide) at the left or above the name, linked to www.cpme-usa.com.
- No quotes, banners or extra images.

## 8. Checklist before anything goes out

- [ ] Name written as in section 1; legal name on the cover and the footer.
- [ ] Contact block exactly as in section 2.
- [ ] Logo from this folder, not stretched, clear space kept, on white.
- [ ] Only the colours in section 4; body text is Ink or Navy; status colours paired with a word.
- [ ] Fonts as in section 5 for the medium.
- [ ] Customer name, project number and date checked against the customer's own documents.
- [ ] Every value has its unit; nothing invented.
- [ ] Sales literature has no makers, tags or job numbers.

## Open items for Bob

1. Drawing title block address: change `cpme_titleblock.py` from 441 Milwaukee Ave Ste 6 to 600 Faust Rd.,
   Unit 38?
2. The original vector logo file, from whoever made it.
3. Proposal page size: keep US Legal, or US Letter like everything else?

## Changes to this guide

A change to this guide is asked of Bob first, like a harness design rule, and cites his answer here.

| Date | Change | Basis |
|---|---|---|
| 2026-11-10 | First issue, from the sources listed above | Bob, chat, 2026-11-10 |
