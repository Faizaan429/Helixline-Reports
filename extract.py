#!/usr/bin/env python3
"""
extract.py — Lab Report Parameter Extractor

Extracts lab test parameters and numeric values from PDF/image lab reports,
maps vendor-specific parameter names to Helixline internal parameter codes,
and outputs a clean, standardized JSON payload.

Usage:
    python extract.py --vendor thyrocare --file report.pdf --output output.json
    python extract.py --vendor redcliffe --file "Sourabh Jain.pdf"
"""

import argparse
import json
import os
import re
import sys


# ---------------------------------------------------------------------------
# Vendor configuration loading
# ---------------------------------------------------------------------------

def list_vendors(vendors_dir):
    """Return list of available vendor names (subdirectories of vendors_dir)."""
    if not os.path.isdir(vendors_dir):
        return []
    return sorted(
        d for d in os.listdir(vendors_dir)
        if os.path.isdir(os.path.join(vendors_dir, d))
    )


def load_vendor_mapping(vendor_name, vendors_dir):
    """
    Load the vendor-specific parameter_map.json.

    Returns a dict: {vendor_param_name: internal_code, ...}
    Exits with a clear error if the vendor or file is missing.
    """
    vendor_path = os.path.join(vendors_dir, vendor_name)

    if not os.path.isdir(vendor_path):
        available = list_vendors(vendors_dir)
        print(
            f"Error: Vendor '{vendor_name}' not found in {vendors_dir}/\n"
            f"Available vendors: {', '.join(available) if available else '(none)'}",
            file=sys.stderr,
        )
        sys.exit(1)

    map_path = os.path.join(vendor_path, "parameter_map.json")
    if not os.path.isfile(map_path):
        print(f"Error: Parameter map not found: {map_path}", file=sys.stderr)
        sys.exit(1)

    with open(map_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Strip the _comment key (metadata) if present
    mapping = {k: v for k, v in raw.items() if not k.startswith("_")}
    return mapping


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def extract_text_from_pdf(file_path):
    """
    Extract text from a native (non-scanned) PDF.

    Tries pdfplumber first, then falls back to PyMuPDF.
    Returns the concatenated text from all pages.
    """
    text = ""

    # --- pdfplumber ---
    try:
        import pdfplumber

        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        if text.strip():
            return text
    except Exception as e:
        print(f"[info] pdfplumber extraction failed ({e}), trying PyMuPDF...", file=sys.stderr)

    # --- PyMuPDF fallback ---
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(file_path)
        for page in doc:
            page_text = page.get_text()
            if page_text:
                text += page_text + "\n"
        doc.close()
        if text.strip():
            return text
    except Exception as e:
        print(f"[info] PyMuPDF extraction failed ({e})", file=sys.stderr)

    return text


def extract_text_from_scanned_pdf(file_path):
    """OCR a scanned PDF by rendering each page to an image."""
    import io

    text = ""
    try:
        import fitz
        import pytesseract
        from PIL import Image

        doc = fitz.open(file_path)
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            page_text = pytesseract.image_to_string(img)
            if page_text:
                text += page_text + "\n"
        doc.close()
    except ImportError as e:
        print(f"[warn] OCR dependencies missing ({e}). Install pytesseract + Pillow.", file=sys.stderr)
    except Exception as e:
        print(f"[warn] Scanned PDF OCR failed: {e}", file=sys.stderr)
    return text


def extract_text_from_image(file_path):
    """OCR a standalone image file (PNG, JPG, TIFF, etc.)."""
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(file_path)
        return pytesseract.image_to_string(img)
    except ImportError as e:
        print(f"Error: OCR dependencies missing ({e}). Install pytesseract + Pillow.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: Image OCR failed: {e}", file=sys.stderr)
        return ""


def extract_text(file_path):
    """
    Route text extraction based on file type.

    - PDF  -> native extraction, falls back to OCR if very little text found
    - Image -> OCR
    """
    if not os.path.isfile(file_path):
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        text = extract_text_from_pdf(file_path)
        # If native extraction yields almost nothing, try OCR
        if len(text.strip()) < 50:
            print("[info] Very little text from native extraction; attempting OCR...", file=sys.stderr)
            text = extract_text_from_scanned_pdf(file_path)
    elif ext in (".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".gif", ".webp"):
        text = extract_text_from_image(file_path)
    else:
        print(f"Error: Unsupported file type '{ext}'. Use PDF or image files.", file=sys.stderr)
        sys.exit(1)

    return text


# ---------------------------------------------------------------------------
# Parameter parsing
# ---------------------------------------------------------------------------

# Lines matching any of these patterns are *not* data rows. They contain
# reference ranges, interpretation text, methodology notes, etc.
# Patterns checked against the START of a line (first 40 chars).
# These mark non-data lines: interpretation text, methodology notes, etc.
_START_SKIP = [
    "bio. ref. interval",
    "reference range",
    "reference :",
    "interpretation",
    "clinical significance",
    "clinical use",
    "method :",
    "method:",
    "disclaimer",
    "note:",
    "comments :",
    "comments:",
    "kit validation",
    "specification",
    "conditions of reporting",
    "national lipid",
    "risk category",
    "risk group",
    "treatment goals",
    "ncep",
    "desirable",
    "borderline high",
    "causes of",
    "low values",
    "high values",
    "goal of therapy",
    "therapeutic",
    "pregnancy reference",
    "1st trimester",
    "2nd trimester",
    "3rd trimester",
]

# Patterns checked ANYWHERE in the line. These are structural/footer lines
# that never carry parameter data.
_ANYWHERE_SKIP = [
    "sample collected",
    "sample received",
    "report released",
    "booking centre",
    "processing lab",
    "conditions of reporting",
    "barcode",
    "labcode",
    "scan qr",
    "patient name",
    "patient id",
    "referred by",
    "report status",
    "test description",
    "dob/age",
    "end of report",
    "how was your experience",
]


def _is_skip_line(line_lower):
    """Return True if this line is not a data row."""
    # Check start-of-line patterns (first 40 chars)
    start = line_lower[:40]
    if any(pat in start for pat in _START_SKIP):
        return True
    # Check anywhere patterns
    if any(pat in line_lower for pat in _ANYWHERE_SKIP):
        return True
    return False


def _extract_first_number(text):
    """
    Extract the first standalone numeric value from *text*.

    Handles integers, decimals, and comma-separated thousands.
    Ignores numbers embedded inside words (e.g. dates, barcodes).
    Returns float/int or None.
    """
    # Match a number preceded by start-of-string or whitespace/punctuation
    match = re.search(r'(?:^|[\s\*\)\]\,\:]+)(\d[\d,]*\.?\d*)', text)
    if match:
        raw = match.group(1).replace(",", "")
        try:
            val = float(raw)
            # Sanity: skip impossibly large values (barcodes, IDs, dates)
            if val > 999999:
                return None
            # Preserve int when the original had no decimal point
            if "." not in raw:
                return int(val)
            return val
        except ValueError:
            return None
    return None


def extract_parameters(text, vendor_mapping):
    """
    Parse extracted report text and return {internal_code_str: value}.

    Algorithm:
      1. Normalise the vendor mapping to lowercase.
      2. Process text line-by-line.
      3. For each line, find the *longest* matching vendor parameter name.
      4. Extract the first numeric value after that name.
      5. If no value on the current line, peek at the next line (handles
         Thyrocare's multi-line layout where name and value are split).
      6. First match per internal code wins; duplicates are ignored.
    """
    results = {}

    # Build normalised lookup: lowered_name -> internal_code
    norm_map = {}
    for name, code in vendor_mapping.items():
        norm_map[name.lower().strip()] = code

    # Pre-sort names longest-first for efficient matching
    sorted_names = sorted(norm_map.keys(), key=len, reverse=True)

    lines = text.split("\n")

    for line_idx, raw_line in enumerate(lines):
        line_stripped = raw_line.strip()
        if not line_stripped or len(line_stripped) < 3:
            continue

        line_lower = line_stripped.lower()

        # Quick reject non-data lines
        if _is_skip_line(line_lower):
            continue

        # --- Find the best (longest) parameter name in this line ---
        best_name = None
        best_code = None
        best_end = 0

        for name in sorted_names:
            idx = line_lower.find(name)
            if idx == -1:
                continue

            # Left-boundary: must be at start or preceded by non-alnum
            if idx > 0 and line_lower[idx - 1].isalnum():
                continue

            # Right-boundary: must end at end-of-line or be followed by
            # whitespace / punctuation (avoids partial-word matches)
            end = idx + len(name)
            if end < len(line_lower):
                ch = line_lower[end]
                # Allow: space, tab, common trailing chars
                if ch.isalpha():
                    continue  # middle of a longer word

            if best_name is None or len(name) > len(best_name):
                best_name = name
                best_code = norm_map[name]
                best_end = end

        if best_name is None:
            continue

        code_str = str(best_code)

        # Already captured this code? Skip.
        if code_str in results:
            continue

        # --- Extract numeric value ---
        after = line_stripped[best_end:]
        value = _extract_first_number(after)

        # Peek at the next line when the value isn't on the current one
        # (e.g. Thyrocare HbA1c where name and value are on separate lines)
        if value is None and line_idx + 1 < len(lines):
            next_line = lines[line_idx + 1].strip()
            if next_line and len(next_line) < 200 and not _is_skip_line(next_line.lower()):
                value = _extract_first_number(next_line)

        if value is not None:
            results[code_str] = value

    return results


# ---------------------------------------------------------------------------
# Output generation
# ---------------------------------------------------------------------------

def build_output(parameters):
    """Wrap extracted parameters in the expected output schema."""
    return {"tests": parameters}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Extract lab parameters from PDF/image reports and output standardised JSON.",
        epilog=(
            "Examples:\n"
            '  python extract.py --vendor thyrocare --file "Rajat Asati.pdf"\n'
            '  python extract.py --vendor redcliffe --file "Sourabh Jain.pdf" --output out.json\n'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--vendor", required=True, help="Vendor name (e.g. thyrocare, redcliffe)")
    parser.add_argument("--file", required=True, help="Path to the lab report (PDF or image)")
    parser.add_argument("--output", default=None, help="Write JSON to this file (default: stdout)")
    parser.add_argument("--vendors-dir", default="vendors", help="Path to the vendors directory")
    parser.add_argument("--debug", action="store_true", help="Print extracted text to stderr")

    args = parser.parse_args()

    # 1. Load vendor mapping
    mapping = load_vendor_mapping(args.vendor, args.vendors_dir)
    print(f"[info] Loaded {len(mapping)} parameter entries for vendor '{args.vendor}'", file=sys.stderr)

    # 2. Extract text
    text = extract_text(args.file)
    if args.debug:
        print("=== EXTRACTED TEXT (first 5000 chars) ===", file=sys.stderr)
        print(text[:5000], file=sys.stderr)
        print("=== END ===\n", file=sys.stderr)

    if not text.strip():
        print("[warn] No text could be extracted from the file.", file=sys.stderr)

    # 3. Parse parameters
    parameters = extract_parameters(text, mapping)

    if not parameters:
        print("[warn] No mapped parameters found in the report.", file=sys.stderr)

    # 4. Build and write output
    output = build_output(parameters)
    output_json = json.dumps(output, indent=2, ensure_ascii=False)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json + "\n")
        print(f"[info] Output written to {args.output}", file=sys.stderr)
    else:
        print(output_json)

    print(f"[info] Extracted {len(parameters)} parameters.", file=sys.stderr)


if __name__ == "__main__":
    main()
