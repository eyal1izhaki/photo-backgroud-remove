import argparse
import os
import time
from pathlib import Path
from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver as Observer
from rembg import remove
from PIL import Image, UnidentifiedImageError

# --- Configuration ---
# Defaults keep everything inside the repo (dev); master-launch.ahk passes the real camera folders.
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "tests" / "fixtures" / "canon-pics"
DEST_DIR = ROOT / "out"
os.environ.setdefault("U2NET_HOME", str(ROOT / ".u2net"))  # rembg model cache, otherwise ~/.u2net
SUPPORTED_FORMATS = {'.png', '.jpg', '.jpeg', '.webp'}
IGNORE_PREFIX = "IMG" # Files starting with this will be ignored

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


def process_image(src_path: Path, dest_dir: Path):
    """Removes background, trims transparent padding, scales the coin to 80% of a 1500x1500 white canvas, and saves."""
    dest_path = dest_dir / src_path.name
    final_dest_path = dest_path.with_suffix('.png')

    # 1. Check if the file already exists in the destination
    if final_dest_path.exists():
        print(f"Skipping: {src_path.name} (Already exists in destination)")
        return

    print(f"Processing: {src_path.name}...")
    
    try:
        input_image = Image.open(src_path)
        
        # 2. Remove background (returns an RGBA image with transparent padding)
        output_image = remove(input_image)
        
        # 3. Crop out all surrounding transparent pixels to isolate the actual coin
        bbox = output_image.getbbox()
        if not bbox:
            print(f"Warning: {src_path.name} appears to be completely transparent.")
            return
        
        trimmed_image = output_image.crop(bbox)
        
        # 4. Setup canvas dimensions and target object size (80% of 1500 = 1200px)
        canvas_size = 1500
        max_object_size = int(canvas_size * 0.9)
        
        # 5. Resize the trimmed coin proportionally to fit within 1200x1200
        orig_width, orig_height = trimmed_image.size
        scale = min(max_object_size / orig_width, max_object_size / orig_height)
        new_width = int(orig_width * scale)
        new_height = int(orig_height * scale)
        
        resized_object = trimmed_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # 6. Create a clean 1500x1500 white background (RGB)
        background = Image.new("RGB", (canvas_size, canvas_size), (255, 255, 255))
        
        # 7. Calculate coordinates to paste the coin right in the center
        paste_x = (canvas_size - new_width) // 2
        paste_y = (canvas_size - new_height) // 2
        
        # 8. Paste the resized coin onto the white background using its alpha channel as a mask
        background.paste(resized_object, (paste_x, paste_y), resized_object)
        
        # 9. Save final image
        background.save(final_dest_path, format="PNG")
        print(f"Successfully saved: {final_dest_path.name}")
        
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