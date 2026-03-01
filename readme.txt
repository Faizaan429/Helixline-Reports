Task

Build a Python-based command-line tool that converts lab reports from a known diagnostic vendor into a standardized JSON input for our report generation engine. The tool must accept a lab report file in PDF or image format along with a vendor name as an input argument. Based on the selected vendor, the system must use a vendor-specific mapping file that defines how parameter names appearing in that vendor’s reports map to our internal parameter codes. The tool should perform OCR on the report, extract parameter name and value pairs, normalize the extracted parameters strictly to our internal codes using the vendor mapping, ignore any parameters that are not mapped, and generate a clean JSON output containing only the internal parameter codes and their numeric values. The output JSON must follow the agreed schema and be directly consumable by the report generation module, without including units, reference ranges, interpretations, or any extra metadata. The design must ensure that vendor-specific differences in naming or formatting are handled only through external mapping files, so that adding a new lab vendor requires creating a new mapping file and not changing the code.

Duration - 1 week

Desired input foramt - sample_full_input.json

For each vendor create similar files
parameter_map.json
reference_ranges.json

test reports for building -
thyrocare
redcliffe

