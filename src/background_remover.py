import argparse
import functools
import os
import time
from pathlib import Path
import cv2
import numpy as np
from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver as Observer
from rembg import new_session, remove
from PIL import Image, ImageOps, UnidentifiedImageError

# --- Configuration ---
# Defaults keep everything inside the repo (dev); master-launch.ahk passes the real camera folders.
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "tests" / "fixtures" / "canon-pics"
DEST_DIR = ROOT / "out"
os.environ.setdefault("U2NET_HOME", str(ROOT / ".u2net"))  # rembg model cache, otherwise ~/.u2net
COIN_MODEL = "u2net" # Cuts coins cleanly, but can miss parts of a slab's clear plastic
SLAB_MODEL = "isnet-general-use" # Traces slab outlines completely, but can keep bits of the holder around a coin
SUPPORTED_FORMATS = {'.png', '.jpg', '.jpeg', '.webp'}
IGNORE_PREFIX = "IMG" # Files starting with this will be ignored
ALPHA_THRESHOLD = 32 # Mask alpha at or below this is noise (reflections, shadows); raise it if ghosts remain
SLAB_FILL_RATIO = 0.83 # Objects covering more of their tightest rotated rectangle than this are slabs; round coins cover pi/4 (0.79)
CANVAS_SIZE = 1500
PADDING = int(CANVAS_SIZE * 0.05) # Object fills 90% of the canvas: 75px of white on every side

def is_valid_file(file_path: Path) -> bool:
    """Checks if the file is a supported image and doesn't trigger the ignore prefix."""
    if not file_path.is_file():
        return False
    
    if file_path.suffix.lower() not in SUPPORTED_FORMATS:
        return False
        
    # Check if the filename starts with the ignore prefix
    if IGNORE_PREFIX and file_path.name.startswith(IGNORE_PREFIX):
        return False
        
    return True

from pathlib import Path
from PIL import Image, UnidentifiedImageError
from rembg import remove

from pathlib import Path
from PIL import Image, UnidentifiedImageError
from rembg import remove


def compose(cutout: Image.Image):
    """Centers a background-removed RGBA image on white: round coins on a square canvas, slabs straightened
    on a canvas shaped like the slab. Returns (image, "coin" | "slab"), or None if the cutout is empty."""
    # Drop faint mask noise so it neither shows as a ghost nor stretches the crop off-center
    alpha = cutout.getchannel("A").point(lambda a: a if a > ALPHA_THRESHOLD else 0)
    cutout.putalpha(alpha)
    if not alpha.getbbox():
        return None

    # Slabs (rated coins) fill nearly all of their tightest rotated rectangle, round coins only pi/4 of it
    mask = (np.array(alpha) > 0).astype(np.uint8)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    largest = max(contours, key=cv2.contourArea)
    _, (rect_width, rect_height), angle = cv2.minAreaRect(largest)
    kind = "slab" if cv2.contourArea(largest) / (rect_width * rect_height) > SLAB_FILL_RATIO else "coin"

    if kind == "slab":
        # The model is often unsure about clear plastic and leaves slabs patchy or washed out; a slab is solid,
        # so make everything inside its outline opaque
        solid = np.zeros_like(mask)
        cv2.drawContours(solid, [cv2.convexHull(largest)], -1, 255, cv2.FILLED)
        cutout.putalpha(Image.fromarray(solid))

        # Straighten by the smallest rotation that makes the slab's edges upright
        tilt = (angle + 45) % 90 - 45
        cutout = cutout.rotate(tilt, Image.Resampling.BICUBIC, expand=True)

    trimmed_image = cutout.crop(cutout.getchannel("A").getbbox())
    width, height = trimmed_image.size

    # Resize proportionally so the longest side spans 90% of the canvas
    scale = (CANVAS_SIZE - 2 * PADDING) / max(width, height)
    new_width = int(width * scale)
    new_height = int(height * scale)
    resized_object = trimmed_image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Coins get a square canvas; slabs get one with the same padding on every side
    if kind == "slab":
        canvas = (new_width + 2 * PADDING, new_height + 2 * PADDING)
    else:
        canvas = (CANVAS_SIZE, CANVAS_SIZE)
    background = Image.new("RGB", canvas, (255, 255, 255))

    # Paste the object in the center using its alpha channel as a mask
    paste_x = (canvas[0] - new_width) // 2
    paste_y = (canvas[1] - new_height) // 2
    background.paste(resized_object, (paste_x, paste_y), resized_object)
    return background, kind


@functools.cache
def rembg_session(model: str):
    """Loads each model once; remove() without a session reloads it for every image."""
    return new_session(model)


def cut_out(photo: Image.Image, model: str) -> Image.Image:
    """The photo with the model's background mask as alpha. Colors stay the photo's own (rembg's cutout
    darkens every pixel the model is unsure about toward black)."""
    cutout = photo.convert("RGBA")
    cutout.putalpha(remove(photo, session=rembg_session(model), only_mask=True))
    return cutout


def process_image(src_path: Path, dest_dir: Path):
    """Removes background, centers the object on a white canvas (see compose), and saves."""
    dest_path = dest_dir / src_path.name
    final_dest_path = dest_path.with_suffix('.jpg')

    # 1. Check if the file already exists in the destination
    if final_dest_path.exists():
        print(f"Skipping: {src_path.name} (Already exists in destination)")
        return

    print(f"Processing: {src_path.name}...")
    
    try:
        # Upright per the camera's EXIF orientation, as rembg does internally, so the mask lines up
        input_image = ImageOps.exif_transpose(Image.open(src_path)).convert("RGB")

        # 2. Remove background and center it on a white canvas shaped for its kind; slabs are redone
        #    with the model that traces their outline completely
        composed = compose(cut_out(input_image, COIN_MODEL))
        if composed and composed[1] == "slab":
            composed = compose(cut_out(input_image, SLAB_MODEL))
        if not composed:
            print(f"Warning: {src_path.name} appears to be completely transparent.")
            return
        background, kind = composed

        # 3. Save final image
        background.save(final_dest_path, format="JPEG", quality=95)  # Pillow's default of 75 shows artifacts on coin edges
        print(f"Successfully saved: {final_dest_path.name} ({kind})")
        
    except UnidentifiedImageError:
        print(f"Error: {src_path.name} is not a valid image file.")
    except Exception as e:
        print(f"Failed to process {src_path.name}: {e}")

def scan_existing_files(src_dir: Path, dest_dir: Path):
    """Scans the source directory on startup to catch files added while offline."""
    print("Scanning existing files...")
    for file_path in src_dir.iterdir():
        if is_valid_file(file_path):
            process_image(file_path, dest_dir)
    print("Initial scan complete. Watching for new files...\n")

class ImageCreationHandler(FileSystemEventHandler):
    """Watches the directory for new file events."""
    def __init__(self, dest_dir: Path):
        self.dest_dir = dest_dir

    def trigger_processing(self, file_path_str):
        src_path = Path(file_path_str)
        if is_valid_file(src_path):
            time.sleep(1) 
            process_image(src_path, self.dest_dir)

    def on_created(self, event):
        if not event.is_directory:
            self.trigger_processing(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self.trigger_processing(event.dest_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--src", type=Path, default=SRC_DIR, help="folder to watch")
    parser.add_argument("--dest", type=Path, default=DEST_DIR, help="output folder")
    args = parser.parse_args()
    src_path_obj = args.src
    dest_path_obj = args.dest

    src_path_obj.mkdir(parents=True, exist_ok=True)
    dest_path_obj.mkdir(parents=True, exist_ok=True)

    # 1. Scan existing files
    scan_existing_files(src_path_obj, dest_path_obj)

    # 2. Set up the watcher
    event_handler = ImageCreationHandler(dest_path_obj)
    observer = Observer()
    observer.schedule(event_handler, path=str(src_path_obj), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping watcher...")
        observer.stop()
    
    observer.join()