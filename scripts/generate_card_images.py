"""One-time script to generate a forehead-card image for every response card.

Usage:
    export OPENAI_API_KEY=sk-...
    python scripts/generate_card_images.py [--force]

Idempotent: skips any card whose image file already exists unless --force is
passed, so it's cheap to re-run after adding new cards. Only needed locally to
(re)populate static/card-images/ -- the deployed app just serves the resulting
static files, no API key needed at runtime.
"""

import argparse
import base64
import io
import sys
from pathlib import Path

from openai import BadRequestError, OpenAI
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from game.cards import RESPONSE_CARDS  # noqa: E402

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "static" / "card-images"
MODEL = "gpt-image-1"
SIZE = "1024x1024"  # smallest square size available
QUALITY = "low"  # cheapest tier

# Cards only ever render on a phone screen, so re-encode the raw 1024x1024
# PNGs down to something web-sized instead of committing ~1.4MB/card.
SAVE_DIMENSIONS = (640, 640)
SAVE_FORMAT = "WEBP"
SAVE_QUALITY = 82

# These two reference real public figures. OpenAI's image models restrict
# photorealistic depictions of real people, especially public figures, so we
# ask for a generic caricature/costume treatment instead of an actual likeness.
SPECIAL_PROMPTS = {
    "r43": (
        "A cartoon caricature of a generic blustery American businessman-politician "
        "in a dark suit and long red tie, exaggerated confident pose, comedic "
        "editorial-cartoon style. Not a real person's likeness."
    ),
    "r44": (
        "A cartoon caricature of a generic composed American politician giving a "
        "speech, dark suit, warm confident smile, comedic editorial-cartoon style. "
        "Not a real person's likeness."
    ),
    # OpenAI's safety system rejected the straightforward "white trash wedding"
    # phrasing outright -- keep the joke (tacky, chaotic backyard wedding) without
    # the classist term that tripped moderation.
    "r36": (
        "A funny, colorful cartoon illustration of a chaotic, tacky backyard "
        "wedding: mismatched folding chairs, a keg next to the cake, string "
        "lights tangled in a tarp canopy, camo-pattern formalwear. Family-friendly, "
        "exaggerated, lighthearted, square composition, bold outlines."
    ),
}


def build_prompt(card) -> str:
    if card.id in SPECIAL_PROMPTS:
        return SPECIAL_PROMPTS[card.id]
    return (
        "A funny, colorful, cartoon/meme-style illustration depicting: "
        f"{card.text}. Family-friendly, exaggerated, lighthearted, square "
        "composition, bold outlines, works well as a small icon."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force", action="store_true", help="Regenerate images that already exist."
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = OpenAI()

    generated, skipped, failed = 0, 0, []
    for card in RESPONSE_CARDS:
        out_path = OUTPUT_DIR / f"{card.id}.{SAVE_FORMAT.lower()}"
        if out_path.exists() and not args.force:
            skipped += 1
            continue

        prompt = build_prompt(card)
        print(f"Generating {card.id} ({card.text!r})...", end=" ", flush=True)
        try:
            result = client.images.generate(
                model=MODEL, prompt=prompt, size=SIZE, quality=QUALITY, n=1
            )
        except BadRequestError as exc:
            print(f"REJECTED ({exc})")
            failed.append(card.id)
            continue
        image_bytes = base64.b64decode(result.data[0].b64_json)
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize(
            SAVE_DIMENSIONS, Image.LANCZOS
        )
        img.save(out_path, SAVE_FORMAT, quality=SAVE_QUALITY)
        tag = " [special-cased likeness]" if card.id in SPECIAL_PROMPTS else ""
        print(f"done{tag}")
        generated += 1

    print(f"\n{generated} image(s) generated, {skipped} already existed and were skipped.")
    if failed:
        print(f"{len(failed)} card(s) rejected by the safety system: {', '.join(failed)}")
        print("Adjust their prompts in SPECIAL_PROMPTS and re-run to retry just those.")
    print(
        "Review the Trump/Obama images (r43, r44) manually -- they were "
        "deliberately generated as generic caricatures, not likenesses, to "
        "stay within OpenAI's usage policy."
    )


if __name__ == "__main__":
    main()
