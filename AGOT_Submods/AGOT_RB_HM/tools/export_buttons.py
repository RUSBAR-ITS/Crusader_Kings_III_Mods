"""Resize the approved source artwork to 128px RGBA DDS game textures."""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MODES = ("main_upgrade", "regular_build", "regular_upgrade", "duchy", "special", "great")


def main():
    target = ROOT / "gfx/interface/icons/rbhm"
    target.mkdir(parents=True, exist_ok=True)
    for mode in MODES:
        for state in ("active", "inactive"):
            name = f"{mode}_{state}"
            source = ROOT / "assets/buttons" / ("agot_rb_hm_" + name + ".png")
            with Image.open(source) as image:
                image.convert("RGBA").resize((128, 128), Image.Resampling.LANCZOS).save(target / (name + ".dds"))
    print("Exported 12 DDS textures; approved source PNGs unchanged.")


if __name__ == "__main__":
    main()
