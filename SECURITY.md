# Security policy

## Supported versions

Security fixes are provided for the latest released version.

## Reporting a vulnerability

Use GitHub private vulnerability reporting for parser bypasses, unsafe file replacement, command execution, path handling, report injection, or dependency vulnerabilities. Do not disclose an exploitable issue publicly before a fix is available.

Include the affected version, platform, a minimal reproducer when safe, expected impact, and any suggested mitigation. You should receive an acknowledgement within seven days.

## Processing untrusted documents

PDFs and ICC profiles are complex binary inputs. Keep Print Color Preflight, pikepdf/qpdf, Pillow/LittleCMS, and Ghostscript updated. Ghostscript runs with safer mode and without a command shell, but safer mode is not an operating-system sandbox. Process hostile files in an isolated disposable environment.

The project never needs network credentials. Do not include proprietary artwork, licensed profiles, customer documents, or secrets in public bug reports.

