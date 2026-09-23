---
name: latex-debug
description: >-
  Debug LaTeX builds and log errors with latexmk/chktex/latexindent, then verify
  PDF output. Use when .tex/.bib fails to compile, Overleaf shows a build error,
  citations/refs break, or the user asks to fix LaTeX, BibTeX, or paper layout.
---

# LaTeX debug

## Tools (prefer local MacTeX)

| Job | Command |
|-----|---------|
| Build | `latexmk -pdf -interaction=nonstopmode -file-line-error main.tex` |
| Lint | `chktex -q -n1 -n3 -n8 -n18 -n24 -n34 main.tex` |
| Format | `latexindent -w -s -c=/tmp/latexindent main.tex` (backup `.bak` created) |
| PDF pages | `pdftoppm -png -r 150 main.pdf /tmp/latex-preview/page` then Read PNGs |
| LSP | `texlab` if installed; Cursor: LaTeX Workshop + LTeX |

## Loop

1. Reproduce with `latexmk` from the project root (or the dir that has `main.tex`).
2. Read the **first** error in `.log` (`! ` lines, `l.<n>`, `Emergency stop`). Ignore later cascade.
3. Fix the root cause in `.tex`/`.bib`/inputs. Common cases below.
4. Rebuild. If PDF exists, render 1–2 pages and visually check.
5. Run `chktex` for leftover style issues; do not chase every warning.

## Common failures

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `Undefined control sequence` | Missing `\usepackage` or typo | Add package or correct command |
| `Missing $` / `Extra }` | Math mode / brace mismatch | Balance `$`/`\( \)`/`{ }` near reported line |
| `Citation undefined` | Bib not run / wrong key | Rebuild full cycle; fix `.bib` key; check `biblatex` vs `natbib` |
| `File not found` | Wrong `\input`/`\includegraphics` path | Paths relative to main file; check extension |
| `Float too large` / overfull | Figure/table width | `width=\linewidth`, rewrite caption |
| Overleaf OK, local fail | Engine/TeX Live drift | Match Overleaf engine (`pdflatex`/`xelatex`/`lualatex`) in `.latexmkrc` |
| Unicode / fancy quotes | Curly quotes, nbsp | Use ASCII `'`/`"`; avoid U+2011 |

## `.latexmkrc` (optional, project root)

```perl
$pdf_mode = 1;  # pdflatex
$bibtex_use = 2;
$pdflatex = 'pdflatex -interaction=nonstopmode -file-line-error %O %S';
```

## Visual check

Use the `pdf` skill: `pdftoppm`, then inspect PNGs for clipped text, overlapping floats, bad tables. Do not claim the paper looks fine from the log alone.

## Self-check

```bash
latexmk -pdf -interaction=nonstopmode -file-line-error main.tex && chktex -q main.tex | head
```
