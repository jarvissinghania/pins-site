"""
Pinterest affiliate pin generator (India)
-----------------------------------------
Reads products.csv  ->  makes 1000x1500 pin images  ->  writes Pinterest
"Bulk create Pins" CSV files with titles, descriptions, keywords, boards and
publish times spread across the day in IST.

Usage:
    python generate_pins.py              # new products only
    python generate_pins.py --all        # redo every product
    python generate_pins.py --push       # also git-push images to your GitHub Pages repo
    python generate_pins.py --check-urls # after pushing, confirm every image URL is live
"""

import argparse
import csv
import io
import json
import os
import random
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = os.path.dirname(os.path.abspath(__file__))
IST = timezone(timedelta(hours=5, minutes=30))
W, H = 1000, 1500

# ----------------------------------------------------------------- helpers

def load_config():
    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
        return json.load(f)


def slugify(text, n=50):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:n].strip("-") or "pin"


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


FONT_CANDIDATES = {
    "bold": [
        "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf",
        "/Library/Fonts/Arial Bold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ],
    "regular": [
        "C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf",
        "/Library/Fonts/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ],
}
_font_cache = {}


def font(weight, size):
    key = (weight, size)
    if key not in _font_cache:
        for path in FONT_CANDIDATES[weight]:
            if os.path.exists(path):
                _font_cache[key] = ImageFont.truetype(path, size)
                break
        else:
            _font_cache[key] = ImageFont.load_default(size=size)
    return _font_cache[key]


def rupee_ok(f):
    """True if the font really has a ₹ glyph (not the empty 'missing' box)."""
    try:
        return f.getmask("₹").getbbox() != f.getmask("\uffff").getbbox()
    except Exception:
        return False


def fmt_price(price, f):
    if not price:
        return ""
    try:
        n = int(float(str(price).replace(",", "").replace("₹", "").strip()))
        # Indian digit grouping: 1,49,999
        s = str(n)
        if len(s) > 3:
            head, tail = s[:-3], s[-3:]
            head = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", head)
            s = f"{head},{tail}"
    except ValueError:
        s = str(price)
    return ("₹" if rupee_ok(f) else "Rs. ") + s


def wrap(draw, text, f, max_w, max_lines):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=f) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        while draw.textlength(lines[-1] + "…", font=f) > max_w and " " in lines[-1]:
            lines[-1] = lines[-1].rsplit(" ", 1)[0]
        lines[-1] += "…"
    return lines


def load_product_image(src):
    if not src:
        return None
    try:
        if src.lower().startswith(("http://", "https://")):
            req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=20).read()
            img = Image.open(io.BytesIO(data))
        else:
            path = src if os.path.isabs(src) else os.path.join(ROOT, src)
            img = Image.open(path)
        return ImageOps.exif_transpose(img).convert("RGBA")
    except Exception as e:
        print(f"   ! could not load image '{src}': {e}")
        return None

# ----------------------------------------------------------------- pin design

def is_plain_backdrop(img):
    """True when the photo's border is near-white or transparent (a studio product shot)."""
    rgba = img.convert("RGBA")
    w, h = rgba.size
    px = [rgba.getpixel((x, y)) for x in range(0, w, max(1, w // 40)) for y in (0, h - 1)]
    px += [rgba.getpixel((x, y)) for y in range(0, h, max(1, h // 40)) for x in (0, w - 1)]
    plain = sum(1 for r, g, b, a in px if a < 20 or min(r, g, b) > 235)
    return plain / len(px) > 0.8

def make_photo_pin(product, img, headline, palette, cfg):
    """Realistic, photo-first pin: the product photo fills the pin, text sits on a soft fade."""
    panel, accent = hex_rgb(palette["panel"]), hex_rgb(palette["accent"])
    white = (255, 255, 255)
    pin = Image.new("RGB", (W, H), white)
    studio = img is not None and is_plain_backdrop(img)

    if img is None:
        pin = Image.new("RGB", (W, H), panel)
    elif studio:
        # white studio shot: keep the whole product visible above the text
        img.thumbnail((W - 80, H - 470), Image.LANCZOS)
        pin.paste(img, ((W - img.width) // 2, 60 + (H - 470 - 60 - img.height) // 2), img)
    else:
        pin.paste(ImageOps.fit(img.convert("RGB"), (W, H), Image.LANCZOS,
                               centering=(0.5, 0.4)), (0, 0))
        # dark fade at the bottom so white text stays readable on any photo
        fade = Image.new("L", (1, H))
        for y in range(H):
            t = (y - H * 0.52) / (H * 0.48)
            fade.putpixel((0, y), int(225 * max(0.0, min(1.0, t)) ** 1.15))
        shade = Image.new("RGB", (W, H), (12, 12, 14))
        pin = Image.composite(shade, pin, fade.resize((W, H)))

    d = ImageDraw.Draw(pin)
    txt = (25, 25, 28) if studio else white
    pad = 70
    hf = font("bold", 72)
    lines = wrap(d, headline, hf, W - 2 * pad, 3)
    y = H - 140 - len(lines) * 86
    kicker = (product.get("category") or "Smart find").upper()
    d.text((pad, y - 58), kicker, font=font("bold", 32), fill=accent if not studio else panel)
    for line in lines:
        d.text((pad, y), line, font=hf, fill=txt)
        y += 86
    d.text((pad, H - 95), cfg["cta_text"].format(store=store_name(product)) + "  →",
           font=font("regular", 38), fill=txt)

    bf = font("bold", 28)
    bw = d.textlength(cfg["brand_name"], font=bf)
    d.rounded_rectangle((W // 2 - bw / 2 - 24, 30, W // 2 + bw / 2 + 24, 80), radius=25,
                        fill=(20, 20, 22) if not studio else panel)
    d.text((W // 2, 55), cfg["brand_name"], font=bf, fill=white, anchor="mm")
    return pin


def make_pin(product, headline, palette, layout, cfg):
    bg, panel = hex_rgb(palette["bg"]), hex_rgb(palette["panel"])
    txt, accent = hex_rgb(palette["text"]), hex_rgb(palette["accent"])
    pin = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(pin)

    photo_h = 930 if layout == 0 else 880
    panel_top = photo_h if layout == 0 else 0
    photo_top = 0 if layout == 0 else H - photo_h

    # product photo, centred on the light background
    img = load_product_image(product.get("image", ""))
    if img and is_plain_backdrop(img):
        # studio shot on white: white area, product as large as possible
        d.rectangle((0, photo_top, W, photo_top + photo_h), fill=(255, 255, 255))
        img.thumbnail((W - 60, photo_h - 60), Image.LANCZOS)
        pin.paste(img, ((W - img.width) // 2, photo_top + (photo_h - img.height) // 2), img)
    elif img:
        # lifestyle shot: fill the whole photo area (centre crop)
        fitted = ImageOps.fit(img.convert("RGB"), (W, photo_h), Image.LANCZOS, centering=(0.5, 0.45))
        pin.paste(fitted, (0, photo_top))
    else:  # placeholder so the pipeline still runs
        d.rounded_rectangle((90, photo_top + 90, W - 90, photo_top + photo_h - 90),
                            radius=40, outline=panel, width=6)
        f = font("bold", 46)
        for i, line in enumerate(wrap(d, product["name"], f, W - 260, 4)):
            d.text((W // 2, photo_top + photo_h // 2 - 80 + i * 60), line,
                   font=f, fill=panel, anchor="mm")

    # text panel
    panel_h = H - photo_h
    d.rectangle((0, panel_top, W, panel_top + panel_h), fill=panel)
    pad = 70
    y = panel_top + 60

    kicker = (product.get("category") or "Smart find").upper()
    d.text((pad, y), kicker, font=font("bold", 30), fill=accent)
    y += 60

    hf = font("bold", 66)
    lines = wrap(d, headline, hf, W - 2 * pad, 3)
    for line in lines:
        d.text((pad, y), line, font=hf, fill=txt)
        y += 80

    # price + CTA row
    pf = font("bold", 52)
    price = fmt_price(product.get("price", ""), pf)
    row_y = panel_top + panel_h - 150
    x = pad
    if price:
        tw = d.textlength(price, font=pf)
        d.rounded_rectangle((x, row_y, x + tw + 60, row_y + 90), radius=45, fill=accent)
        d.text((x + 30 + tw / 2, row_y + 45), price, font=pf, fill=panel, anchor="mm")
        x += tw + 90
    cf = font("regular", 36)
    d.text((x, row_y + 45), cfg["cta_text"].format(store=store_name(product)) + "  →", font=cf, fill=txt, anchor="lm")

    # brand footer (small, on the photo side so it never collides with text)
    bf = font("bold", 28)
    by = 45 if layout == 0 else H - 45
    bw = d.textlength(cfg["brand_name"], font=bf)
    d.rounded_rectangle((W // 2 - bw / 2 - 22, by - 24, W // 2 + bw / 2 + 22, by + 24),
                        radius=24, fill=panel)
    d.text((W // 2, by), cfg["brand_name"], font=bf, fill=txt, anchor="mm")
    return pin

# ----------------------------------------------------------------- copy

STORES = [("flipkart", "Flipkart"), ("fktr.in", "Flipkart"), ("myntra", "Myntra"),
          ("ajio", "Ajio"), ("amazon", "Amazon"), ("amzn", "Amazon")]


def store_name(p):
    """Store shown on the pin, worked out from the product/affiliate link."""
    if p.get("store"):
        return p["store"]
    urls = ((p.get("product_url") or "") + " " + (p.get("affiliate_link") or "")).lower()
    return next((name for key, name in STORES if key in urls), "the store")


HEADLINES = [
    "{name}",
    "{hook}",
    "Budget {cat_l} find under {price_round}",
    "Easy festive upgrade: {short}",
    "{short} for a cosy {room}",
    "{store} find: {short}",
]

DESC_TEMPLATES = [
    "{hook}. {name} is one of my favourite {cat_l} picks on {store} right now{price_part}. "
    "Great for {room} upgrades on a budget. Tap to check today's price and reviews.",
    "Looking for easy {room} upgrade ideas? {name}{price_part} is a simple, affordable upgrade. "
    "{hook}. Save this pin for later and tap to see the latest deal.",
]


def price_round(price):
    try:
        n = int(float(str(price).replace(",", "")))
        for step in (199, 299, 499, 699, 999, 1499, 1999, 2999, 4999, 9999, 14999, 19999):
            if n <= step:
                return f"₹{step:,}"
        return f"₹{n:,}"
    except ValueError:
        return "a budget"


def build_copy(p, variant, cfg):
    name = p["name"].strip()
    short = p.get("short_name") or " ".join(name.split()[:3])
    cat = p.get("category") or "home"
    hook = p.get("hook") or f"A must-have {cat.lower()} pick"
    room = p.get("room") or "home"
    vals = dict(store=store_name(p), name=name, short=short, cat_l=cat.lower(), hook=hook, room=room,
                price_round=price_round(p.get("price", "")))
    show_price = cfg.get("show_price", True) and p.get("price")
    pool = HEADLINES if show_price else [h for h in HEADLINES if "{price_round}" not in h]
    if not show_price and p.get("hook"):
        pool = ["{hook}"] + [h for h in pool if h not in ("{hook}", "{name}")]
    rnd = random.Random(f"{name}-{variant}")
    headline = (pool[0] if variant == 0 else rnd.choice(pool[1:])).format(**vals)

    title = headline if len(headline) <= 100 else headline[:97] + "..."
    price_part = f" (around {fmt_price(p['price'], font('bold', 20))})" if show_price else ""
    desc = rnd.choice(DESC_TEMPLATES).format(price_part=price_part, **vals)
    kws = [k.strip() for k in (p.get("keywords") or "").split(",") if k.strip()]
    if kws:
        desc += " " + " ".join("#" + re.sub(r"\s+", "", k.title()) for k in kws[:4])
    desc += " " + cfg["disclosure"]
    if len(desc) > 500:
        desc = desc[:497 - len(cfg["disclosure"])].rsplit(" ", 1)[0] + "… " + cfg["disclosure"]
    return headline, title, desc, ", ".join(kws)

# ----------------------------------------------------------------- scheduling

def schedule_slots(cfg, count, start):
    times = cfg["post_times_ist"][: cfg["pins_per_day"]]
    slots, day = [], start
    while len(slots) < count:
        for t in times:
            hh, mm = map(int, t.split(":"))
            local = datetime(day.year, day.month, day.day, hh, mm, tzinfo=IST)
            local += timedelta(minutes=random.randint(-12, 12))  # look less robotic
            slots.append(local)
            if len(slots) == count:
                break
        day += timedelta(days=1)
    return slots

# ----------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="regenerate every product, not just new ones")
    ap.add_argument("--push", action="store_true", help="git add/commit/push the site/ folder")
    ap.add_argument("--check-urls", action="store_true", help="check image URLs in the latest batch")
    args = ap.parse_args()
    cfg = load_config()

    if args.check_urls:
        return check_urls()

    if "YOUR-GITHUB-USERNAME" in cfg["image_base_url"]:
        print("! Set image_base_url in config.json first (see README, step 3).")

    log_path = os.path.join(ROOT, "posted_log.csv")
    done = set()
    if os.path.exists(log_path) and not args.all:
        with open(log_path, encoding="utf-8") as f:
            done = {(r["link"], r["variant"]) for r in csv.DictReader(f)}

    with open(os.path.join(ROOT, "products.csv"), encoding="utf-8-sig") as f:
        all_rows = [r for r in csv.DictReader(f) if r.get("name")]
    products = [r for r in all_rows if (r.get("affiliate_link") or "").strip()]
    waiting = [r["name"] for r in all_rows if not (r.get("affiliate_link") or "").strip()]
    if waiting:
        print(f"Skipping {len(waiting)} product(s) with no affiliate_link yet "
              f"(make an EarnKaro link from product_url): " + "; ".join(waiting))

    # all variant-0 pins first, then variant-1 ... so the same product
    # never appears twice on one day
    jobs = [(p, v) for v in range(cfg["variants_per_product"]) for p in products
            if (p["affiliate_link"], str(v)) not in done]
    if not jobs:
        print("Nothing new to generate. Add rows to products.csv (or use --all).")
        return

    max_pins = cfg["pins_per_day"] * cfg["max_days_ahead"]
    if len(jobs) > max_pins:
        print(f"Only scheduling {max_pins} pins (max_days_ahead limit); run again later for the rest.")
        jobs = jobs[:max_pins]

    start = datetime.now(IST).date() + timedelta(days=1 if cfg["start_date"] == "tomorrow" else 0)
    # never double up with pins already scheduled by an earlier batch
    if os.path.exists(log_path):
        with open(log_path, encoding="utf-8") as f:
            last = max((r["publish_ist"][:10] for r in csv.DictReader(f) if r.get("publish_ist")), default="")
        if last:
            start = max(start, datetime.strptime(last, "%Y-%m-%d").date() + timedelta(days=1))
    slots = schedule_slots(cfg, len(jobs), start)

    site_dir = os.path.join(ROOT, cfg.get("pins_dir", "site/pins"))
    os.makedirs(site_dir, exist_ok=True)
    batch = datetime.now(IST).strftime("%Y-%m-%d_%H%M")
    out_dir = os.path.join(ROOT, "output", batch)
    os.makedirs(out_dir, exist_ok=True)

    rows, log_rows = [], []
    for i, ((p, v), when) in enumerate(zip(jobs, slots), 1):
        headline, title, desc, kws = build_copy(p, v, cfg)
        palette = cfg["colors"][(i + v) % len(cfg["colors"])]
        if cfg.get("style", "photo") == "photo":
            imgs = [x.strip() for x in (p.get("image") or "").split("|") if x.strip()]
            img = load_product_image(imgs[v % len(imgs)]) if imgs else None
            pin = make_photo_pin(p, img, headline, palette, cfg)
        else:
            pin = make_pin(p, headline, palette, v % 2, cfg)
        fname = f"{slugify(p['name'])}-v{v + 1}.jpg"
        pin.save(os.path.join(site_dir, fname), "JPEG", quality=88, optimize=True)
        print(f" [{i}/{len(jobs)}] {fname}  ->  {when:%d %b %H:%M} IST")
        rows.append({
            "Title": title,
            "Media URL": cfg["image_base_url"].rstrip("/") + "/" + fname,
            "Pinterest board": p.get("board") or cfg["default_board"],
            "Thumbnail": "",
            "Description": desc,
            "Link": p["affiliate_link"].strip(),
            "Publish date": when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
            "Keywords": kws,
        })
        log_rows.append({"link": p["affiliate_link"], "variant": v, "file": fname,
                         "publish_ist": when.strftime("%Y-%m-%d %H:%M"), "batch": batch})

    fields = list(rows[0].keys())
    n = cfg["rows_per_csv"]
    # Pinterest skips a row whose Link already appeared in the same CSV, so every
    # file gets at most one pin per product link (each design goes in its own file).
    files, cur, links = [], [], set()
    for r in rows:
        if r["Link"] in links or len(cur) >= n:
            files.append(cur)
            cur, links = [], set()
        cur.append(r)
        links.add(r["Link"])
    if cur:
        files.append(cur)
    for i, chunk in enumerate(files, 1):
        path = os.path.join(out_dir, f"pinterest_bulk_{i}.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(chunk)
        print(f"CSV -> {os.path.relpath(path, ROOT)}  ({len(chunk)} pins - upload each file separately)")

    new_log = not os.path.exists(log_path)
    with open(log_path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(log_rows[0].keys()))
        if new_log:
            w.writeheader()
        w.writerows(log_rows)

    if args.push:
        push_site(batch)
    print(f"\nDone: {len(rows)} pins. Next: push site/ (if you didn't use --push), "
          f"run --check-urls, then upload the CSV in Pinterest.")


def push_site(batch):
    site = os.path.join(ROOT, "site")
    if not os.path.isdir(os.path.join(site, ".git")):
        print("! site/ is not a git repo yet - see README step 3.")
        return
    for cmd in (["git", "add", "-A"], ["git", "commit", "-m", f"pins {batch}"], ["git", "push"]):
        r = subprocess.run(cmd, cwd=site, capture_output=True, text=True)
        print(" ".join(cmd), "->", "ok" if r.returncode == 0 else r.stderr.strip()[:200])


def check_urls():
    outs = sorted(os.listdir(os.path.join(ROOT, "output")))
    if not outs:
        print("No batches yet.")
        return
    latest = os.path.join(ROOT, "output", outs[-1])
    bad = 0
    for name in sorted(os.listdir(latest)):
        with open(os.path.join(latest, name), encoding="utf-8") as f:
            for r in csv.DictReader(f):
                url = r["Media URL"]
                try:
                    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
                    code = urllib.request.urlopen(req, timeout=15).status
                except Exception as e:
                    code = getattr(e, "code", str(e))
                if code != 200:
                    bad += 1
                    print(f" ✗ {code}  {url}")
    print("All image URLs are live ✓" if not bad else f"{bad} URL(s) not live yet - "
          "GitHub Pages can take 1-2 minutes after a push.")


if __name__ == "__main__":
    sys.exit(main())
