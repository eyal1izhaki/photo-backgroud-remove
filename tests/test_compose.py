"""Run: .venv/bin/python tests/test_compose.py"""
import math
import sys
from pathlib import Path
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

# A slab the model was unsure about (semi-transparent) comes out solid, not washed out by the white behind it
faint, kind = compose(cutout(lambda d, box: d.rounded_rectangle(box, 40, fill=(90, 90, 90, 120)), (1000, 1400)))
center = faint.getpixel((faint.width // 2, faint.height // 2))
assert kind == "slab" and center == (90, 90, 90), (kind, center)

assert compose(Image.new("RGBA", (100, 100), (0, 0, 0, 0))) is None
print("ok")
