# Pinterest Affiliate Automation — India

Add products to one spreadsheet → run one command → get ready-made pin images
plus a Pinterest bulk-upload CSV, scheduled at Indian peak times.
No Pinterest API needed (it uses Pinterest's own **Bulk create Pins** tool).

```
products.csv ──► generate_pins.py ──► site/pins/*.jpg   (pushed to free GitHub Pages hosting)
                                  └─► output/<date>/pinterest_bulk_1.csv ──► upload in Pinterest
```

Weekly routine once set up (~10 minutes): add 10–20 products → double-click `run.bat`
→ upload the CSV in Pinterest.

---

## 1. Affiliate accounts (one-time)

Your existing Amazon Associates account is the **US** program (amazon.com) — it does
**not** pay on amazon.in sales. For Indian buyers you need one of:

| Option | Link format | Notes |
|---|---|---|
| **Amazon Associates India** — affiliate-program.amazon.in | `https://www.amazon.in/dp/ASIN?tag=yourid-21` | Best commissions on Amazon India. Add your Pinterest profile URL as a website/app in the account. New accounts must make qualifying sales in the first 180 days or the account closes. |
| **EarnKaro** (earnkaro.com) | short EarnKaro links | Easiest start: one account covers Amazon.in, Flipkart, Myntra, Ajio and more. Lower rates than direct programs. |
| **Flipkart Affiliate** | `...?affid=yourid` | Good for fashion/electronics. |

Put whichever link you use into the `affiliate_link` column. Mixing is fine.

**Rules that keep the account safe**
- Every pin description ends with an `#affiliate` disclosure (set in `config.json`). Keep it.
- Don't download product photos from Amazon listings — Amazon's operating agreement
  restricts that. Use your own photos, brand-provided images, or a styled
  photo/mockup you're allowed to use. Empty `image` = a clean text-only placeholder pin.
- Don't change prices on images after they drop; the script shows the price you enter, so
  prefer rounder "under ₹X" style hooks for products whose prices move often.

## 2. Install (one-time, Windows)

1. Install Python 3.10+ from python.org (tick **"Add Python to PATH"**).
2. Unzip this folder anywhere, e.g. `D:\pinterest-india-affiliate`.
3. Double-click `run.bat` once — it installs Pillow and makes a test batch.

## 3. Free image hosting with GitHub Pages (one-time)

Pinterest's bulk tool needs each image at a **public URL**. Free way:

1. Create a free GitHub account and a **public** repo named `pins-site`.
2. In the repo: Settings → Pages → Source: *Deploy from branch*, branch `main`, folder `/root`.
3. Install Git for Windows, then in the project folder:
   ```
   cd site
   git init -b main
   git remote add origin https://github.com/YOUR-USERNAME/pins-site.git
   git add -A && git commit -m "first pins" && git push -u origin main
   ```
4. In `config.json` set
   `"image_base_url": "https://YOUR-USERNAME.github.io/pins-site/pins/"`

From then on `run.bat` pushes new images automatically (`--push`).
Check they're live with `python generate_pins.py --check-urls`.

## 4. Pinterest setup (one-time)

- Business account (you have one). Claim nothing extra; just create the boards named in
  `products.csv` / `default_board` **before** uploading — board names must match exactly.
- Good India-focused board names: *Home Decor Finds India*, *Kitchen Finds India*,
  *Diwali Decoration Ideas*, *Budget Room Makeover India*, *Gift Ideas Under ₹500*.

## 5. Every week

1. Add products to `products.csv`:

   | column | example | required |
   |---|---|---|
   | name | Ceramic Matte Coffee Mug Set of 2 | ✔ |
   | affiliate_link | https://www.amazon.in/dp/B0…?tag=yourid-21 | ✔ |
   | image | `photos/mug.jpg` or a public image URL | – |
   | price | 549 | – |
   | category | Kitchen (small label on the pin) | – |
   | room | kitchen | – |
   | hook | Cafe vibes at home for under 600 (becomes a headline) | – |
   | board | Kitchen Finds India (blank = default board) | – |
   | keywords | coffee mug set, kitchen decor india | – |
   | short_name | Matte coffee mugs | – |
   | product_url | plain amazon.in / flipkart link — paste into EarnKaro to make `affiliate_link` | – |

   Rows with an empty `affiliate_link` are skipped, so a plain store link is never pinned by mistake.

2. Double-click `run.bat`. Only **new** products get pins (history is in `posted_log.csv`).
3. Pinterest → **Create → Create Pin → Bulk create Pins → Upload .csv** and pick
   `output/<newest date>/pinterest_bulk_1.csv`. Pins appear under *Scheduled Pins*.

> **Important:** Pinterest's bulk upload silently skips a row when the same `Link` already
> appears earlier in the same CSV. Upload each product's second design in a **separate CSV**
> (e.g. a week later) so both designs get created.

> **Test first:** upload a CSV with just 2–3 rows the first time and confirm they appear
> correctly before sending a full batch.

## Settings (`config.json`)

| key | default | meaning |
|---|---|---|
| pins_per_day | 5 | Keep 3–10/day; a brand-new account should start at 3–5. |
| variants_per_product | 2 | Two designs per product, posted on different days. |
| post_times_ist | 09:30 … 22:00 | Slots in IST (±12 min random jitter). Converted to UTC for Pinterest. |
| max_days_ahead | 28 | Pinterest only lets you schedule a limited time ahead; extra pins wait for the next run. |
| rows_per_csv | 50 | Splits big batches into several CSV files. |
| colors | 3 palettes | Change to your brand colours. |
| disclosure, cta_text, brand_name | | Text on/under each pin. |

## What grows an India Pinterest account

- Niches that work: home décor, kitchen, festive décor (Diwali/Rakhi/wedding season — pin
  4–6 weeks before), gifts under ₹500/₹999, study desk setups, budget fashion.
- Use search phrases Indians actually type in titles/keywords: "under ₹999",
  "for small Indian homes", "Diwali decoration ideas".
- Fresh images beat repins: the 2-variant setting already gives each link two new designs.
- Mix in some non-affiliate pins (tips, room ideas) so the account isn't 100% links.
