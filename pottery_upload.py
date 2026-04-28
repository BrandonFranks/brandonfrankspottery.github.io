#!/usr/bin/env python3
"""
pottery_upload.py — Brandon Franks Pottery
SEO image renaming + Pinterest board management + pin upload.

Commands:
  rename      Rename IMG_*/DSC_*/UUID files to SEO names; update index.html
  boards      Create the 4 Pinterest boards (safe to re-run)
  pin-all     Bulk-pin every gallery image (skips already-pinned)
  pin <file>  Pin a single image by filename (call after a new listing)
  profile     Print instructions to update Pinterest profile (API v5 limitation)
  new-listing Interactive: describe a new piece → stub Etsy listing → auto-pin

Quickstart:
  1. Copy .env.example to .env and add your PINTEREST_ACCESS_TOKEN
  2. python pottery_upload.py rename
  3. git add -A && git commit -m 'SEO image rename' && git push
  4. Wait 2-3 min for GitHub Pages to propagate, then:
  5. python pottery_upload.py boards
  6. python pottery_upload.py pin-all
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("pip install requests")

# ── Paths ─────────────────────────────────────────────────────────────
SITE_DIR  = Path(__file__).parent
PHOTOS    = SITE_DIR / "Pottery 2026 Website Photos"
WEBP_DIR  = PHOTOS / "webp"
THUMBS    = PHOTOS / "thumbs"
HTML_FILE = SITE_DIR / "index.html"
LOG_FILE  = SITE_DIR / "pinterest_log.json"

# ── Pinterest config ──────────────────────────────────────────────────
SITE_URL   = "https://brandonfrankspottery.com"
PHOTO_URL  = f"{SITE_URL}/Pottery%202026%20Website%20Photos/webp"
PIN_TITLE  = "Handmade Crystalline Pottery - Brandon Franks Pottery"
PIN_DESC   = (
    "Handmade crystalline glaze pottery by Brandon Franks, fired at cone 8 in my studio. "
    "Each piece is one of a kind — no two crystals grow the same way. "
    "Available at brandonfrankspottery.com and my Etsy shop. "
    "#crystallineglaze #handmadeceramics #pottery #ceramics #potteryforsale "
    "#handmadepottery #crystalglaze #uniquepottery #ceramicvase #potterygift "
    "#homedecor #studioceramics #crystallineceramics #handmadewithlove #pottersofinstagram"
)
PIN_LINK    = "https://brandonfrankspottery.com"
PROFILE_BIO = (
    "Handmade crystalline glaze pottery by Brandon Franks. "
    "Each piece is one of a kind, thrown and fired at cone 8 in my studio. "
    "Shop at brandonfrankspottery.com"
)

BOARD_DEFAULT   = "Handmade Crystalline Glaze Pottery"
BOARD_MUGS_CUPS = "Crystalline Pottery Mugs and Cups"
BOARD_VASES     = "Unique Ceramic Vases Handmade"
BOARD_GIFTS     = "Pottery Gift Ideas"
BOARD_NAMES     = [BOARD_DEFAULT, BOARD_MUGS_CUPS, BOARD_VASES, BOARD_GIFTS]

PINTEREST_API = "https://api.pinterest.com/v5"
RATE_DELAY    = 1.5  # seconds between API calls (Pinterest rate limit buffer)

# ── Rename map: (old_base, new_base, original_ext) ────────────────────
# Covers all 25 gallery images. Logos and video files are excluded.
RENAME_MAP = [
    ("DSC_7694",                              "crystalline-pottery-mug-001",     "JPG"),
    ("DSC_8920",                              "crystalline-pottery-vase-001",    "jpeg"),
    ("IMG_0025",                              "crystalline-pottery-vase-002",    "JPG"),
    ("IMG_2264",                              "crystalline-pottery-vase-003",    "jpeg"),
    ("IMG_2430",                              "crystalline-pottery-vase-004",    "jpeg"),
    ("IMG_3269",                              "crystalline-pottery-vase-005",    "jpeg"),
    ("IMG_3972",                              "crystalline-pottery-vase-006",    "jpeg"),
    ("IMG_4952",                              "crystalline-pottery-vase-007",    "jpeg"),
    ("00779B48-C1F4-487C-9816-7CE34893B0F3",  "crystalline-pottery-vessel-001",  "jpg"),
    ("0613DADE-2D44-4BD3-A711-7F2908659C21",  "crystalline-pottery-vessel-002",  "jpg"),
    ("0CE20761-83A9-4F1C-9492-3A43A94ECBB3",  "crystalline-pottery-vase-008",    "jpg"),
    ("12E880F9-0F96-4218-8F2E-7066842C3986",  "crystalline-pottery-vase-009",    "jpg"),
    ("IMG_5779",                              "crystalline-pottery-vessel-003",  "jpeg"),
    ("IMG_5784",                              "crystalline-pottery-vessel-004",  "jpeg"),
    ("IMG_5788",                              "crystalline-pottery-vessel-005",  "jpeg"),
    ("IMG_5800",                              "crystalline-pottery-vessel-006",  "jpeg"),
    ("IMG_5808",                              "crystalline-pottery-vessel-007",  "jpeg"),
    ("IMG_6061",                              "crystalline-pottery-cup-001",     "jpeg"),
    ("IMG_6235",                              "crystalline-pottery-vessel-008",  "jpeg"),
    ("IMG_6239",                              "crystalline-pottery-vessel-009",  "jpeg"),
    ("IMG_6248",                              "crystalline-pottery-mug-002",     "jpeg"),
    ("EEBF342A-79FD-4551-BE7E-5382C6F11462",  "crystalline-pottery-vessel-010",  "jpg"),
    ("IMG_2649",                              "crystalline-pottery-vessel-011",  "jpeg"),
    ("IMG_2655",                              "crystalline-pottery-vessel-012",  "jpeg"),
    ("IMG_2755",                              "crystalline-pottery-vessel-013",  "jpeg"),
]

# ── Gallery metadata (mirrors the JS IMAGES array in index.html) ──────
GALLERY = [
    {"base": "crystalline-pottery-mug-001",    "ext": "JPG",
     "alt": "Handmade ceramic mug with olive green crystalline glaze and dark dripping rim by Brandon Franks"},
    {"base": "crystalline-pottery-vase-001",   "ext": "jpeg",
     "alt": "Dark green handmade crystalline pottery vase with speckled glaze, photographed with candlelight by Brandon Franks"},
    {"base": "crystalline-pottery-vase-002",   "ext": "JPG",
     "alt": "Large handmade gourd-shaped ceramic vase covered in tan and blue zinc silicate crystalline glaze by Brandon Franks"},
    {"base": "crystalline-pottery-vase-003",   "ext": "jpeg",
     "alt": "Handmade round ceramic vase with pale blue crystalline glaze held against a garden background by Brandon Franks"},
    {"base": "crystalline-pottery-vase-004",   "ext": "jpeg",
     "alt": "Handmade spherical ceramic vase with amber and silver crystalline glaze by Brandon Franks"},
    {"base": "crystalline-pottery-vase-005",   "ext": "jpeg",
     "alt": "Handmade oval ceramic vase with deep red base glaze and large lavender blue crystalline formations by Brandon Franks"},
    {"base": "crystalline-pottery-vase-006",   "ext": "jpeg",
     "alt": "Handmade ceramic vase with sage green crystalline glaze held over grass by Brandon Franks"},
    {"base": "crystalline-pottery-vase-007",   "ext": "jpeg",
     "alt": "Handmade teardrop-shaped ceramic vase with dense cobalt blue zinc silicate crystalline glaze by Brandon Franks"},
    {"base": "crystalline-pottery-vessel-001", "ext": "jpg",
     "alt": "Handmade red stoneware pottery vessel with bold black brushed glaze held against green grass by Brandon Franks"},
    {"base": "crystalline-pottery-vessel-002", "ext": "jpg",
     "alt": "Two stacked handmade celadon ceramic vessels with vivid blue crystalline glaze formations by Brandon Franks"},
    {"base": "crystalline-pottery-vase-008",   "ext": "jpg",
     "alt": "Handmade dark stoneware ceramic vase with dramatic white glaze splash held against green grass by Brandon Franks"},
    {"base": "crystalline-pottery-vase-009",   "ext": "jpg",
     "alt": "Handmade elongated ceramic vase with emerald green crystalline glaze held against sunlit grass by Brandon Franks"},
    {"base": "crystalline-pottery-vessel-003", "ext": "jpeg",
     "alt": "Handmade gourd-shaped ceramic vessel with vibrant blue crystalline glaze held against sunlit grass by Brandon Franks"},
    {"base": "crystalline-pottery-vessel-004", "ext": "jpeg",
     "alt": "Handmade flat teardrop ceramic vessel with dark matte glaze and subtle crystalline formations held against green grass by Brandon Franks"},
    {"base": "crystalline-pottery-vessel-005", "ext": "jpeg",
     "alt": "Handmade flat teardrop ceramic vessel with celadon green glaze and small circular crystalline formations by Brandon Franks"},
    {"base": "crystalline-pottery-vessel-006", "ext": "jpeg",
     "alt": "Handmade double-bulge gourd ceramic vessel with smooth sage green glaze held against garden foliage by Brandon Franks"},
    {"base": "crystalline-pottery-vessel-007", "ext": "jpeg",
     "alt": "Handmade teardrop ceramic vessel with sandy tan glaze and scattered blue crystalline formations by Brandon Franks"},
    {"base": "crystalline-pottery-cup-001",    "ext": "jpeg",
     "alt": "Handmade ceramic cup with blue and white crystalline stripe glaze photographed inside the kiln by Brandon Franks"},
    {"base": "crystalline-pottery-vessel-008", "ext": "jpeg",
     "alt": "Handmade barrel-shaped ceramic vessel densely covered in vivid blue zinc silicate crystalline formations by Brandon Franks"},
    {"base": "crystalline-pottery-vessel-009", "ext": "jpeg",
     "alt": "Handmade curved ceramic vessel with intense cobalt blue crystalline glaze held outdoors by Brandon Franks"},
    {"base": "crystalline-pottery-mug-002",    "ext": "jpeg",
     "alt": "Handmade ceramic mug with cream glaze and subtle white crystalline patterns and a looped handle by Brandon Franks"},
    {"base": "crystalline-pottery-vessel-010", "ext": "jpg",
     "alt": "Large egg-shaped handmade ceramic vessel with all-white crystalline glaze covered in overlapping circular crystal formations by Brandon Franks"},
    {"base": "crystalline-pottery-vessel-011", "ext": "jpeg",
     "alt": "Flat lens-shaped handmade ceramic vessel with celadon and white crystalline lace formations transitioning to deep green crystals, studio photograph by Brandon Franks"},
    {"base": "crystalline-pottery-vessel-012", "ext": "jpeg",
     "alt": "Flat lens-shaped handmade ceramic vessel with teal and blue-green base glaze and large olive green crystalline formations, studio photograph by Brandon Franks"},
    {"base": "crystalline-pottery-vessel-013", "ext": "jpeg",
     "alt": "Spherical handmade ceramic vessel with deep forest green and teal glaze covered in large white botanical crystalline formations, studio photograph by Brandon Franks"},
]


# ── Env / credentials ─────────────────────────────────────────────────

def _load_dotenv():
    """Parse .env file into os.environ without requiring python-dotenv."""
    env_path = SITE_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def get_token() -> str:
    _load_dotenv()
    token = os.environ.get("PINTEREST_ACCESS_TOKEN", "").strip()
    if not token:
        sys.exit(
            "\nMissing PINTEREST_ACCESS_TOKEN.\n"
            "Copy .env.example to .env and add your token.\n"
            "See .env.example for step-by-step instructions.\n"
        )
    return token


# ── Log helpers ───────────────────────────────────────────────────────

def load_log() -> dict:
    if LOG_FILE.exists():
        return json.loads(LOG_FILE.read_text(encoding="utf-8"))
    return {"pinned": {}, "boards": {}}


def save_log(log: dict):
    LOG_FILE.write_text(json.dumps(log, indent=2, default=str), encoding="utf-8")


# ── Board / pin assignment ────────────────────────────────────────────

def primary_board(filename_base: str) -> str:
    """Primary board determined by keywords in the SEO filename."""
    low = filename_base.lower()
    if "mug" in low or "cup" in low:
        return BOARD_MUGS_CUPS
    if "vase" in low or "vessel" in low:
        return BOARD_VASES
    return BOARD_DEFAULT


# ── Pinterest API calls ───────────────────────────────────────────────

def _ph(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def list_boards(token: str) -> list:
    """Fetch all boards for the authenticated user (handles pagination)."""
    boards, cursor = [], None
    while True:
        params = {"page_size": 25}
        if cursor:
            params["bookmark"] = cursor
        r = requests.get(f"{PINTEREST_API}/boards", headers=_ph(token),
                         params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        boards.extend(data.get("items", []))
        cursor = data.get("bookmark")
        if not cursor:
            break
        time.sleep(RATE_DELAY)
    return boards


def create_board(token: str, name: str) -> dict:
    r = requests.post(
        f"{PINTEREST_API}/boards",
        headers=_ph(token),
        json={"name": name, "privacy": "PUBLIC"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def ensure_boards(token: str, log: dict) -> dict:
    """Create the four boards if they don't already exist. Returns {name: id}."""
    print("Fetching existing Pinterest boards...")
    existing = {b["name"]: b["id"] for b in list_boards(token)}
    board_ids = {}
    for name in BOARD_NAMES:
        if name in existing:
            board_ids[name] = existing[name]
            print(f"  already exists: {name!r}")
        else:
            print(f"  creating: {name!r} ...", end=" ", flush=True)
            b = create_board(token, name)
            board_ids[name] = b["id"]
            print(f"id={b['id']}")
            time.sleep(RATE_DELAY)
    log["boards"] = board_ids
    save_log(log)
    return board_ids


def _create_pin(token: str, board_id: str, image_url: str) -> dict:
    r = requests.post(
        f"{PINTEREST_API}/pins",
        headers=_ph(token),
        json={
            "board_id": board_id,
            "title": PIN_TITLE,
            "description": PIN_DESC,
            "link": PIN_LINK,
            "media_source": {"source_type": "image_url", "url": image_url},
        },
        timeout=30,
    )
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    return r.json()


def pin_one(token: str, board_ids: dict, log: dict,
            image_base: str, extra: str = "") -> list:
    """
    Pin image_base to its primary board + Pottery Gift Ideas.
    Returns list of new pin IDs, or empty list if already pinned.
    """
    if image_base in log.get("pinned", {}):
        print(f"  [skip] already pinned: {image_base}")
        return []

    primary = primary_board(image_base)
    # Always pin to primary + gift board (deduplicated in case they're the same)
    boards_to_pin = list(dict.fromkeys([primary, BOARD_GIFTS]))
    image_url = f"{PHOTO_URL}/{image_base}.webp"

    created_ids, used_boards = [], []
    for board_name in boards_to_pin:
        bid = board_ids.get(board_name)
        if not bid:
            print(f"  [error] board not in log: {board_name!r} — run `boards` first")
            continue
        try:
            pin = _create_pin(token, bid, image_url)
            created_ids.append(pin["id"])
            used_boards.append(board_name)
            print(f"  pinned to {board_name!r}: pin {pin['id']}")
        except Exception as exc:
            print(f"  [error] {board_name!r}: {exc}")
        time.sleep(RATE_DELAY)

    if created_ids:
        log.setdefault("pinned", {})[image_base] = {
            "pin_ids": created_ids,
            "boards": used_boards,
            "pinned_at": datetime.now(timezone.utc).isoformat(),
            "note": extra,
        }
        save_log(log)

    return created_ids


# ── rename command ────────────────────────────────────────────────────

def cmd_rename():
    """Rename all generic image filenames to SEO-friendly names and update index.html."""
    print("Renaming image files...")
    renamed = skipped = 0

    for old_base, new_base, orig_ext in RENAME_MAP:
        pairs = [
            (PHOTOS / f"{old_base}.{orig_ext}", PHOTOS / f"{new_base}.{orig_ext}"),
            (WEBP_DIR / f"{old_base}.webp",     WEBP_DIR / f"{new_base}.webp"),
            (THUMBS  / f"{old_base}.webp",      THUMBS  / f"{new_base}.webp"),
        ]
        for old_path, new_path in pairs:
            if new_path.exists():
                skipped += 1
            elif old_path.exists():
                old_path.rename(new_path)
                print(f"  {old_path.name}  →  {new_path.name}")
                renamed += 1
            # silently skip if neither exists (shouldn't happen with known filenames)

    print(f"\n  {renamed} files renamed, {skipped} already done.")

    # Patch index.html — replace every old filename string with its SEO equivalent
    print("\nPatching index.html...")
    html = HTML_FILE.read_text(encoding="utf-8")
    original = html

    for old_base, new_base, orig_ext in RENAME_MAP:
        # webp filenames (used in srcset=, webp: JS keys, preload href)
        html = html.replace(f"{old_base}.webp", f"{new_base}.webp")
        # original image filenames with exact extension cases
        html = html.replace(f"{old_base}.{orig_ext}", f"{new_base}.{orig_ext}")
        # CSS background-image and any remaining plain src= references
        for ext in ("JPG", "jpeg", "jpg", "png"):
            if ext.lower() != orig_ext.lower():
                html = html.replace(f"{old_base}.{ext}", f"{new_base}.{ext}")

    if html != original:
        HTML_FILE.write_text(html, encoding="utf-8")
        changed = sum(1 for _, _, _ in RENAME_MAP if True)  # all 25 entries touched
        print(f"  index.html updated ({len(RENAME_MAP)} filename groups replaced).")
    else:
        print("  index.html already up-to-date.")

    print("""
Next steps:
  git add -A && git commit -m 'SEO image rename' && git push
  # Wait 2-3 min for GitHub Pages to deploy, then:
  python pottery_upload.py boards
  python pottery_upload.py pin-all
""")


# ── boards command ────────────────────────────────────────────────────

def cmd_boards():
    token = get_token()
    log = load_log()
    board_ids = ensure_boards(token, log)
    print(f"\nBoards ready ({len(board_ids)}):")
    for name, bid in board_ids.items():
        print(f"  {name}: {bid}")


# ── pin-all command ───────────────────────────────────────────────────

def cmd_pin_all():
    token = get_token()
    log = load_log()
    board_ids = log.get("boards")
    if not board_ids:
        sys.exit("No boards recorded. Run `python pottery_upload.py boards` first.")

    already_pinned = set(log.get("pinned", {}).keys())
    to_pin = [img for img in GALLERY if img["base"] not in already_pinned]

    print(f"{len(GALLERY)} total images, {len(already_pinned)} already pinned, "
          f"{len(to_pin)} to pin this run.\n")

    total_new_pins = 0
    for img in to_pin:
        print(f"→ {img['base']}")
        new_pins = pin_one(token, board_ids, log, img["base"])
        total_new_pins += len(new_pins)

    pinned_now = len(log.get("pinned", {}))
    print(f"\nDone. {total_new_pins} new pins created. "
          f"{pinned_now}/{len(GALLERY)} images pinned total.")


# ── pin <file> command ────────────────────────────────────────────────

def cmd_pin(filename: str):
    """Pin a single image by base filename (with or without extension)."""
    token = get_token()
    log = load_log()
    board_ids = log.get("boards")
    if not board_ids:
        sys.exit("No boards recorded. Run `python pottery_upload.py boards` first.")

    base = Path(filename).stem
    print(f"Pinning: {base}")
    new_pins = pin_one(token, board_ids, log, base)
    if new_pins:
        print(f"Created {len(new_pins)} pin(s): {new_pins}")
    else:
        print("No new pins (already pinned, or error above).")


# ── profile command ───────────────────────────────────────────────────

def cmd_profile():
    """
    Pinterest API v5 does not expose a writable profile-description endpoint.
    This command prints the bio text and links to the settings page.
    """
    print("Pinterest API v5 does not support updating the profile bio via API.")
    print("Update it manually at: https://www.pinterest.com/settings/profile\n")
    print("Suggested bio:")
    print(f"  {PROFILE_BIO}")


# ── new-listing command ───────────────────────────────────────────────

def cmd_new_listing():
    """
    Interactive workflow for a new piece:
      1. Enter the SEO image filename
      2. (Etsy stub — wire up ETSY_API_KEY when ready)
      3. Auto-pin to the appropriate Pinterest boards
    """
    print("=" * 60)
    print("New Pottery Listing")
    print("=" * 60)

    image_file = input("SEO image filename (e.g. crystalline-pottery-vase-010.jpeg): ").strip()
    if not image_file:
        sys.exit("No filename provided.")
    base = Path(image_file).stem

    # ── Etsy stub ──────────────────────────────────────────────────────
    # Uncomment and implement once you have ETSY_API_KEY in .env
    # _load_dotenv()
    # etsy_key = os.environ.get("ETSY_API_KEY", "")
    # if etsy_key:
    #     title   = input("Listing title: ").strip()
    #     price   = input("Price (USD): ").strip()
    #     qty     = input("Quantity: ").strip()
    #     # POST to https://openapi.etsy.com/v3/application/shops/{shop_id}/listings
    #     # with title, description, price, quantity, taxonomy_id, etc.
    #     print("[Etsy] Listing created.")
    # else:
    print("[Etsy] ETSY_API_KEY not set — skipping Etsy listing.")
    print("       See .env.example to configure Etsy integration.")

    # ── Pinterest ──────────────────────────────────────────────────────
    print("\n[Pinterest] Pinning...")
    token = get_token()
    log = load_log()
    board_ids = log.get("boards")
    if not board_ids:
        print("No boards found in log. Setting up boards now...")
        board_ids = ensure_boards(token, log)

    new_pins = pin_one(token, board_ids, log, base, extra="via new-listing")
    if new_pins:
        print(f"\n{len(new_pins)} pin(s) created successfully.")
    else:
        print("\nNo new pins created (already pinned or error above).")


# ── Entry point ───────────────────────────────────────────────────────

def main():
    CMDS = {
        "rename":      cmd_rename,
        "boards":      cmd_boards,
        "pin-all":     cmd_pin_all,
        "profile":     cmd_profile,
        "new-listing": cmd_new_listing,
    }

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "pin":
        if len(sys.argv) < 3:
            sys.exit("Usage: python pottery_upload.py pin <filename>")
        cmd_pin(sys.argv[2])
    elif cmd in CMDS:
        CMDS[cmd]()
    else:
        print(f"Unknown command: {cmd!r}")
        print(f"Available: {', '.join(list(CMDS) + ['pin <file>'])}")
        sys.exit(1)


if __name__ == "__main__":
    main()
