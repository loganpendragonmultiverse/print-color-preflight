# Architecture and trust boundaries

```text
PDF + user-selected ICC profile
          |
          v
  non-mutating preflight ----> JSON / HTML findings
          |
          v
  explicit conversion plan
          |
          v
  Ghostscript safer-mode subprocess
          |
          v
  temporary converted PDF
          |
          +--> embed selected output intent
          +--> parse and postflight
          +--> hash result
          |
          v
  atomic-style promotion to requested output path
```

## Components

- `pdf.py` inventories page resources, content operators, print-related graphics state, fonts, and output intents. It also embeds the selected output profile after conversion.
- `profiles.py` validates the ICC header before a profile reaches Ghostscript.
- `ghostscript.py` locates the external engine, builds an argument list without a shell, converts inside a temporary directory, and promotes only a validated result.
- `ink.py` asks Ghostscript for CMYK TIFF proof rasters and computes total area coverage.
- `report.py` serializes JSON and escapes all dynamic content in HTML.
- `cli.py` owns argument validation, exit codes, and user-facing summaries.

## Trust boundaries

PDFs and ICC profiles are untrusted binary inputs. Parsing libraries and Ghostscript should be kept current. The CLI does not use a command shell, accept arbitrary Ghostscript switches, fetch profiles, or transmit files. Profile paths are passed as individual process arguments.

Ghostscript safer mode restricts many file operations but is not a complete sandbox. High-risk documents should be processed in a disposable virtual machine or container.

The conversion record documents software behavior. It is not evidence of a calibrated monitor, characterized press, compliant PDF/X file, or accepted physical proof.

