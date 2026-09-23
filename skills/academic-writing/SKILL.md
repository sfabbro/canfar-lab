---
name: academic-writing
description: >-
  Improve scientific and academic prose in papers, abstracts, rebuttals, and
  grant text. Use when editing LaTeX/Markdown writing, polishing abstracts,
  reviewer responses, or when the user asks for clearer scholarly writing.
  Pair with academic-humanizer (papers/grants) and unslop (AI tells). Use
  scientific-writing for IMRAD/reporting; manuscript-writing for review-only
  comments. Do not use human-voice on manuscripts (it casualizes).
---

# Academic writing

## Defaults

- Prefer clear, specific claims over hedged filler.
- Preserve the author's technical meaning; do not invent results.
- Match venue tone: AAS/ApJ terse; Nature-style punchy abstract; grant = goals + methods + impact.
- After rewriting paper/grant prose, run **academic-humanizer** then **unslop**.
  Neutral and precise *is* the human voice. Do not inject personality, humor, or
  first-person "I" into a manuscript.
- Keep LaTeX structure: do not flatten `\section`, `\cite`, `\ref`, math, or macros.
- Companion skills: `academic-humanizer` (de-AI without casualizing),
  `scientific-writing` (IMRAD, evidence-bound language), `manuscript-writing`
  (review comments). `human-voice` is for notes/docs, not papers.

## Paper structure checks

| Part | Job |
|------|-----|
| Title | Specific; avoid "A novel study of…" |
| Abstract | Problem → method → main result (with number) → implication. No citations unless required. |
| Intro | Hook, gap, this work, roadmap. End with contribution bullets only if the venue uses them. |
| Methods | Reproducible; define symbols once. |
| Results | Lead with the finding, then the figure. |
| Discussion | Limits + interpretation; no new undeclared results. |
| Conclusions | 3–5 sentences; no copy-paste of abstract. |

## Edit loop

1. Ask what the paragraph must claim (one sentence).
2. Rewrite for that claim; cut throat-clearing ("It is well known that…").
3. Prefer concrete nouns and verbs; demote adjectives.
4. Check tense: methods past; established facts present; this paper's results past or present perfect consistently.
5. Verify every `\cite{}` / number still matches the intended source after edits.
6. Clarity pass (below).
7. Academic-humanizer pass, then unslop.

## Clarity (Gopen: make the sentence easy to parse)

Do not "dumb down" math. Make the *syntax* easy so the science can stay dense.

- **Subject next to verb.** Do not bury the action after a long noun pile.
- **Action in the verb.** "We estimated masses" not "mass estimation was performed".
- **Old then new.** Start with what the reader already knows; put the new finding at the end (stress position).
- **One claim per paragraph.** Lead with that claim.
- Keep evidence-tied hedging (`suggests`, `is consistent with`). Cut vague hedging (`somewhat`, `relatively`, `to some extent`).

## Anti-jargon

Keep field terms that name real objects, methods, or quantities (`redshift`, `PSF`, `halo mass`). Cut inflated English around them.

| Inflated | Plain |
|----------|--------|
| utilize, leverage | use |
| prior to | before |
| in order to | to |
| in the context of | in |
| it is worth noting that | (delete) |
| novel framework / comprehensive pipeline | the actual method name |
| robust | the number, test, or failure mode |

- One term per concept; do not cycle synonyms (`sample` / `dataset` / `catalog` for the same thing).
- Define an acronym once, then use it.
- Unpack stacked nouns: "procedure for estimating the cluster mass function" not "cluster mass function estimation procedure".

## Astronomy / physics specifics

- Units: thin space or `\,` (`$1.2\,\mathrm{kpc}$`); use `siunitx` if the project already does.
- Significance: state the test/statistic, not just "significant".
- Figures: caption = result, not procedure dump; define symbols in caption or nearby text.
- Avoid "utilize", "leverage", "robust framework", "comprehensive pipeline" unless naming a real product.

## Rebuttals / responses

- Quote the reviewer concern briefly, then answer with evidence (figure, table, new test).
- Separate: agree / clarify / disagree-with-data.
- Mark manuscript changes with location (`Sec. 3.2`, line or commit).

## Do not

- Fabricate citations, redshifts, magnitudes, or p-values.
- Expand scope the user did not ask for (new sections, related-work essays).
- Turn dense correct math prose into vague "accessible" copy that loses content.
