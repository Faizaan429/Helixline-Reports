# Lab Report Parameter Extractor

CLI tool that extracts lab test parameters and numeric values from PDF/image lab reports, maps vendor-specific parameter names to Helixline internal codes, and outputs a standardised JSON payload.

## Quick Start

```bash
# Install dependencies
pip install pdfplumber PyMuPDF pytesseract Pillow

# Run extraction
python extract.py --vendor thyrocare --file "thyrocare/Rajat Asati.pdf" --output output.json
python extract.py --vendor redcliffe --file "redcliffe/Sourabh Jain.pdf"
```

## CLI Usage

```
python extract.py --vendor VENDOR --file FILE [--output OUTPUT] [--vendors-dir DIR] [--debug]
```

| Argument | Required | Description |
|---|---|---|
| `--vendor` | Yes | Vendor name (`thyrocare`, `redcliffe`, etc.) |
| `--file` | Yes | Path to lab report (PDF or image) |
| `--output` | No | Output JSON file path (default: stdout) |
| `--vendors-dir` | No | Vendors directory (default: `./vendors`) |
| `--debug` | No | Print extracted text to stderr |

## Output Format

Output follows the `sample_full_input.json` schema. Only internal parameter codes and numeric values are included — no units, reference ranges, flags, or metadata.

```json
{
  "tests": {
    "1001": 101.23,
    "1002": 5.5,
    "2001": 172,
    "5001": 14.3,
    "6001": 1.9
  }
}
```

Codes follow the category scheme defined in `parameter_map.json`:

| Prefix | Category |
|---|---|
| 1XXX | Metabolic / Diabetes |
| 2XXX | Lipid / Cardiovascular |
| 3XXX | Liver Function |
| 4XXX | Kidney Function |
| 5XXX | Hemogram / Blood |
| 6XXX | Thyroid |
| 7XXX | Vitamins & Bone |
| 8XXX | Inflammation |
| 9XXX–12XXX | Hormones, Cancer Markers, Urine, Toxic Elements |

## Project Structure

```
extract.py                          # Main CLI tool
parameter_map.json                  # Master parameter reference (all codes)
reference_ranges.json               # Master reference ranges
sample_full_input.json              # Target output schema
vendors/
  ├── thyrocare/
  │   ├── parameter_map.json        # Thyrocare name → internal code
  │   └── reference_ranges.json     # Reserved for future use
  ├── redcliffe/
  │   ├── parameter_map.json        # Redcliffe name → internal code
  │   └── reference_ranges.json     # Reserved for future use
```

## How to Add a New Vendor

Adding a vendor requires **zero code changes**. Only JSON configuration:

1. Create a directory under `vendors/`:
   ```bash
   mkdir vendors/newvendor
   ```

2. Create `vendors/newvendor/parameter_map.json` mapping vendor-specific parameter names to internal codes:
   ```json
   {
     "Blood Sugar Fasting": 1001,
     "HbA1c (Glycated Hemoglobin)": 1002,
     "Cholesterol Total": 2001
   }
   ```

   **Tips for building the mapping:**
   - Open a sample PDF from the vendor and extract text (`--debug` flag helps).
   - Identify the exact parameter names as they appear in the report text.
   - Map each name to the matching internal code from `parameter_map.json`.
   - Include common naming variants (with/without spaces, parentheses, etc.).
   - Multiple keys can map to the same code to handle different report formats.
   - Matching is case-insensitive; longest match wins when names overlap.

3. Create `vendors/newvendor/reference_ranges.json` (can be an empty placeholder):
   ```json
   {
     "_comment": "Reserved for future use."
   }
   ```

4. Run:
   ```bash
   python extract.py --vendor newvendor --file report.pdf
   ```

## Dependencies

| Package | Purpose |
|---|---|
| `pdfplumber` | Primary PDF text extraction |
| `PyMuPDF` | Fallback PDF extraction + scanned PDF rendering |
| `pytesseract` | OCR for scanned PDFs and images |
| `Pillow` | Image handling for OCR |

For scanned PDFs and images, [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) must be installed on the system and available on PATH.

Native (non-scanned) PDFs only require `pdfplumber` or `PyMuPDF`.

## How It Works

1. **Text extraction**: pdfplumber extracts text from native PDFs. Falls back to PyMuPDF, then OCR for scanned documents.
2. **Line-by-line parsing**: Each line is checked against the vendor's parameter mapping (longest match wins).
3. **Value extraction**: The first standalone numeric value after the matched parameter name is captured.
4. **Multi-line handling**: If no value is found on the matched line, the next line is checked (handles split layouts).
5. **Skip filtering**: Header, footer, interpretation, and methodology lines are filtered out to avoid false matches.

## Assumptions and Limitations

- **Numeric values only**: Qualitative results (e.g. urine colour "Straw Yellow") are not extracted. Only numeric parameters present in the vendor mapping are captured.
- **First match wins**: If a parameter appears on both a summary page and a detail page, the first occurrence's value is used (they should be identical).
- **PDF text quality**: Extraction accuracy depends on the PDF's text layer. Scanned or image-based PDFs rely on OCR quality (Tesseract).
- **Vendor consistency**: The mapping assumes consistent naming within a vendor's reports. If a vendor changes their report format, the mapping JSON may need updating.
- **No unit conversion**: Values are taken as-is from the report. If a vendor reports in different units than expected, manual mapping adjustments may be needed.
- **Parameter overlap**: Short parameter names (e.g. "Iron") can appear in interpretation text. Skip-pattern filtering and boundary checks mitigate this, but edge cases may require mapping refinement.

## Error Handling

| Scenario | Behaviour |
|---|---|
| Vendor folder not found | Exits with error, lists available vendors |
| `parameter_map.json` missing | Exits with error message |
| Input file not found | Exits with error message |
| Unsupported file type | Exits with error message |
| No text extracted | Warns, outputs `{"tests": {}}` |
| No parameters matched | Warns, outputs `{"tests": {}}` |
