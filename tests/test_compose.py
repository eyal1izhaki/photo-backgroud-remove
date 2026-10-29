"""Run: .venv/bin/python tests/test_compose.py"""
import math
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from background_remover import PADDING, compose


def cutout(draw_shape, size):
    """Transparent photo with one opaque shape off to the side, like a rembg result."""
    image = Image.new("RGBA", (3000, 3000), (0, 0, 0, 0))
    draw_shape(ImageDraw.Draw(image), (400, 300, 400 + size[0], 300 + size[1]))
    return image


def content_bbox(image):
    return image.convert("L").point(lambda v: 255 if v < 250 else 0).getbbox()


coin, kind = compose(cutout(lambda d, box: d.ellipse(box, fill=(120, 80, 40, 255)), (1200, 1200)))
assert kind == "coin" and coin.size == (1500, 1500), (kind, coin.size)

slab, kind = compose(cutout(lambda d, box: d.rounded_rectangle(box, 40, fill=(90, 90, 90, 255)), (1000, 1400)))
assert kind == "slab", kind
assert slab.height == 1500 and slab.width < slab.height, slab.size
assert content_bbox(slab) == (PADDING, PADDING, slab.width - PADDING, slab.height - PADDING), (slab.size, content_bbox(slab))

def tilted_rectangle(draw, box, degrees=7):
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    rad = math.radians(degrees)
    corners = [(box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])]
    draw.polygon([(cx + (x - cx) * math.cos(rad) - (y - cy) * math.sin(rad),
                   cy + (x - cx) * math.sin(rad) + (y - cy) * math.cos(rad)) for x, y in corners], fill=(90, 90, 90, 255))


# A tilted slab is still a slab, and comes out upright: its content fills its bounding box
tilted, kind = compose(cutout(tilted_rectangle, (1000, 1400)))
assert kind == "slab", kind
bbox = content_bbox(tilted)
content = tilted.convert("L").crop(bbox).point(lambda v: 255 if v < 250 else 0)
fill = content.histogram()[255] / (content.width * content.height)
assert fill > 0.98 and tilted.width < tilted.height, (fill, tilted.size)

# A tilt beyond MAX_TILT is a misread outline, not a crooked photo: left as photographed, never swung around
leaning, kind = compose(cutout(lambda d, box: tilted_rectangle(d, box, degrees=30), (1000, 1400)))
content = leaning.convert("L").crop(content_bbox(leaning)).point(lambda v: 255 if v < 250 else 0)
fill = content.histogram()[255] / (content.width * content.height)
assert kind == "slab" and fill < 0.8, (kind, fill)

# The slab's shadow (a half-confident band around it) is not part of the slab: edges stay straight on the slab
def shadowed(draw, box):
    draw.rectangle((box[0] - 20, box[1] - 20, box[2] + 90, box[3] + 90), fill=(200, 200, 200, 120))
    draw.rounded_rectangle(box, 40, fill=(90, 90, 90, 255))


slab_only, _ = compose(cutout(lambda d, box: d.rounded_rectangle(box, 40, fill=(90, 90, 90, 255)), (1000, 1400)))
with_shadow, kind = compose(cutout(shadowed, (1000, 1400)))
assert kind == "slab" and with_shadow.size == slab_only.size, (kind, with_shadow.size, slab_only.size)

# Even a shadow the model is fully confident about, with an edge as dark and crisp as the slab's, is cut away:
# slab plastic is textured, the backdrop and shadow are smooth
def photo_cutout(shadow):
    rng = np.random.default_rng(0)
    gray = 215 + rng.normal(0, 1, (2400, 2400))
    alpha = np.zeros(gray.shape, np.uint8)
    x0, y0, x1, y1 = 400, 300, 1400, 1700
    if shadow:
        gray[y0 + 70:y1 + 70, x0 + 70:x1 + 70] -= 60
        alpha[y0:y1 + 70, x0:x1 + 70] = 255
    gray[y0:y1, x0:x1] = 150 + rng.normal(0, 12, (y1 - y0, x1 - x0))
    alpha[y0:y1, x0:x1] = 255
    image = Image.fromarray(np.clip(gray, 0, 255).astype(np.uint8)).convert("RGBA")
    image.putalpha(Image.fromarray(alpha))
    return image


clean, _ = compose(photo_cutout(shadow=False))
shadow_included, kind = compose(photo_cutout(shadow=True))
assert kind == "slab" and shadow_included.size == clean.size, (kind, shadow_included.size, clean.size)

# A slab the model was unsure about (semi-transparent) comes out solid, not washed out by the white behind it
faint, kind = compose(cutout(lambda d, box: d.rounded_rectangle(box, 40, fill=(90, 90, 90, 120)), (1000, 1400)))
center = faint.getpixel((faint.width // 2, faint.height // 2))
assert kind == "slab" and center == (90, 90, 90), (kind, center)

assert compose(Image.new("RGBA", (100, 100), (0, 0, 0, 0))) is None
print("ok")
