"""
Convert all .heic/.heif files in a folder to .png.

Setup:
    pip install pillow pillow-heif

Usage:
    python heic_to_png.py "C:\\Users\\pitul\\OneDrive\\Pictures\\imports\\new"
    python heic_to_png.py "C:\\path\\to\\folder" -r              # include subfolders
    python heic_to_png.py "C:\\path\\to\\folder" -o "C:\\out"    # save PNGs elsewhere
    python heic_to_png.py "C:\\path\\to\\folder" --overwrite     # replace existing PNGs
    python heic_to_png.py                                        # prompts for the path
"""

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()

HEIC_EXTENSIONS = {".heic", ".heif"}


def find_heic_files(folder: Path, recursive: bool):
    pattern = "**/*" if recursive else "*"
    return sorted(
        p for p in folder.glob(pattern)
        if p.is_file() and p.suffix.lower() in HEIC_EXTENSIONS
    )


def convert_file(src: Path, folder: Path, out_dir, overwrite: bool) -> str:
    """Convert one file. Returns 'converted' or 'skipped'."""
    if out_dir:
        # Keep subfolder structure when saving to a separate output folder
        dest = out_dir / src.relative_to(folder).with_suffix(".png")
    else:
        dest = src.with_suffix(".png")

    if dest.exists() and not overwrite:
        return "skipped"

    dest.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(src) as img:
        img = ImageOps.exif_transpose(img)  # make sure orientation is correct
        img.save(dest, format="PNG")

    return "converted"


def main():
    parser = argparse.ArgumentParser(description="Convert HEIC files to PNG.")
    parser.add_argument("folder", nargs="?", help="Folder containing .heic files")
    parser.add_argument("-o", "--output", help="Output folder (default: ./converted)")
    parser.add_argument("-r", "--recursive", action="store_true", help="Include subfolders")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing PNGs")
    args = parser.parse_args()

    folder_str = args.folder or input("Path to folder with HEIC files: ")
    folder = Path(folder_str.strip().strip('"').strip("'"))

    if not folder.is_dir():
        sys.exit(f"Error: '{folder}' is not a valid folder.")

    out_dir = Path(args.output.strip().strip('"')) if args.output else folder / "converted"

    files = find_heic_files(folder, args.recursive)
    if not files:
        sys.exit(f"No .heic files found in '{folder}'.")

    print(f"Found {len(files)} HEIC file(s). Converting...\n")

    converted = skipped = failed = 0
    for i, src in enumerate(files, start=1):
        try:
            result = convert_file(src, folder, out_dir, args.overwrite)
            if result == "converted":
                converted += 1
                print(f"[{i}/{len(files)}] OK       {src.name}")
            else:
                skipped += 1
                print(f"[{i}/{len(files)}] SKIPPED  {src.name} (PNG already exists)")
        except Exception as e:
            failed += 1
            print(f"[{i}/{len(files)}] FAILED   {src.name}: {e}")

    print(f"\nDone. Converted: {converted}, skipped: {skipped}, failed: {failed}")


if __name__ == "__main__":
    main()
