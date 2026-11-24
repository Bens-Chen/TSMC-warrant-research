"""Convert reports/report_draft.md to reports/report.tex (subset of Markdown used by the draft).

Handles: # title, ## / ### headings (unnumbered; numbers are in the text), the abstract, paragraphs,
pipe tables, images with captions, **bold**, *italic*, `code`, hanging-indent references.
Run: .venv/bin/python reports/md2tex.py && ~/.local/tectonic/tectonic reports/report.tex
"""

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC, OUT = HERE / "report_draft.md", HERE / "report.tex"

PREAMBLE = r"""\documentclass[12pt,a4paper]{article}
\usepackage[margin=2.5cm]{geometry}
\usepackage{fontspec}
\usepackage{xeCJK}
\setmainfont{Times New Roman}
\setCJKmainfont[BoldFont={Heiti TC}]{Songti TC}
\setCJKsansfont{Heiti TC}
\xeCJKsetup{CJKecglue={ }}
\usepackage{graphicx,tabularx,booktabs,caption,float,array,indentfirst}
\usepackage[hidelinks]{hyperref}
\captionsetup{font=small,labelformat=empty,skip=4pt}
\linespread{1.45}
\setlength{\parindent}{2em}
\setlength{\parskip}{0.3em}
\renewcommand{\arraystretch}{1.25}
\newcolumntype{Y}{>{\raggedright\arraybackslash}X}
\begin{document}
"""

SPECIAL = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
           "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}


def esc(t):
    return "".join(SPECIAL.get(ch, ch) for ch in t)


def inline(t):
    t = t.replace(r"\|", "|")
    t = esc(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\\textit{\1}", t)
    t = re.sub(r"`(.+?)`", r"\\texttt{\1}", t)
    return t


def table(rows):
    cells = [[c.strip() for c in re.split(r"(?<!\\)\|", r.strip().strip("|"))] for r in rows]
    head, body = cells[0], [c for c in cells[2:]]
    n = len(head)
    width = [max(len(r[i]) if i < len(r) else 0 for r in [head] + body) for i in range(n)]
    spec = "".join("Y" if w > 14 else "l" for w in width)
    if "Y" not in spec:
        spec = "Y" + spec[1:]
    out = [r"\begin{center}\small", rf"\begin{{tabularx}}{{\linewidth}}{{{spec}}}", r"\toprule",
           " & ".join(rf"\textbf{{{inline(h)}}}" for h in head) + r" \\", r"\midrule"]
    for r in body:
        r = r + [""] * (n - len(r))
        out.append(" & ".join(inline(c) for c in r[:n]) + r" \\")
    out += [r"\bottomrule", r"\end{tabularx}", r"\end{center}"]
    return "\n".join(out)


def convert(md):
    lines = md.splitlines()
    out, i, section = [PREAMBLE], 0, ""
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("# "):
            out.append(r"\begin{center}{\LARGE\bfseries " + inline(ln[2:]) + r"}\end{center}\vspace{1em}")
        elif ln.startswith("## "):
            section = ln[3:].strip()
            if section == "摘要":
                out.append(r"\begin{center}\textbf{摘要}\end{center}\begin{quote}\small")
                i += 1
                while i < len(lines) and not lines[i].startswith("---"):
                    if lines[i].strip():
                        out.append(inline(lines[i]) + "\n")
                    i += 1
                out.append(r"\end{quote}")
                continue
            if section == "附錄":
                out.append(r"\clearpage")
            out.append(r"\section*{" + inline(section) + "}")
        elif ln.startswith("### "):
            out.append(r"\subsection*{" + inline(ln[4:]) + "}")
        elif ln.startswith("---"):
            pass
        elif ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i])
                i += 1
            out.append(table(rows))
            continue
        elif m := re.match(r"!\[(.*)\]\((.*)\)", ln):
            out.append(r"\begin{figure}[H]\centering" + "\n" +
                       rf"\includegraphics[width=0.8\linewidth,height=0.55\textheight,keepaspectratio]{{{m.group(2)}}}" +
                       "\n" + rf"\caption{{{inline(m.group(1))}}}" + "\n" + r"\end{figure}")
        elif re.match(r"\*\*(表|圖) ", ln.strip()):
            out.append(r"\begin{center}" + inline(ln.strip()) + r"\end{center}\vspace{-0.8em}")
        elif ln.startswith("註："):
            out.append(r"{\small\noindent " + inline(ln) + r"\par}")
        elif ln.strip() == "":
            out.append("")
        elif section == "參考文獻":
            out.append(r"\noindent\hangindent=2em\hangafter=1 " + inline(ln) + r"\par")
        else:
            out.append(inline(ln))
        i += 1
    out.append(r"\end{document}")
    return "\n".join(out)


if __name__ == "__main__":
    OUT.write_text(convert(SRC.read_text(encoding="utf-8")), encoding="utf-8")
    print(OUT)
