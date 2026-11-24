#!/bin/bash
# Numbers, figures, Markdown -> LaTeX -> PDF. Run from anywhere: bash reports/build_pdf.sh
# Needs the tectonic binary at ~/.local/tectonic/tectonic (official release, aarch64-apple-darwin).
set -euo pipefail
cd "$(dirname "$0")"
PY=../.venv/bin/python
$PY make_numbers.py >/dev/null
$PY make_figures.py >/dev/null
$PY md2tex.py >/dev/null
~/.local/tectonic/tectonic report.tex
echo "built $(pwd)/report.pdf"
