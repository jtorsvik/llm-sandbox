# Case 2: Regulation assistant (Lovdata open API)

> Real data, no API keys. Endpoints, structure and reference numbers were checked against the live API on 2026-10-28 and 2026-10-29 (archive `lastModified` 2026-10-21). If your counts differ slightly, the law changed; trust your own download.

**Goal.** Ask a question about Norwegian law in English or Norwegian and get a short answer that cites the exact provision and quotes the original text. If the law text does not support an answer, the assistant says so instead of guessing.

**Timebox:** about 3 days. **Stack:** what is already in this repo (LangGraph, `langchain-anthropic`, `langchain-google-genai`, `chromadb`, `sentence-transformers`, `lxml`, `httpx`, `pydantic`, `langsmith`, `openevals`). No new dependencies.

## What you deliver

1. `python -m regulation_assistant ingest` downloads, parses and indexes the law corpus. Re-running it does nothing unless Lovdata published a new file.
2. `python -m regulation_assistant ask "<question>"` prints the answer, citations and quotes. `--json` prints the `Answer` object below.
3. A 40-row golden set and one command that prints the metrics table for four or more models.
4. `RESULTS.md`: the model table, the long-context-versus-RAG experiment (T7), and what you would ship.
5. Demo inputs that work live: reference questions 3, 6, 8 and 9 below, plus `Hva er maksimal alminnelig arbeidstid per døgn og uke?`.

```python
class Citation(BaseModel):
    citation_id: str       # "NL/lov/2005-06-17-62/§15-3"      (from the model)
    quote: str             # verbatim Norwegian text            (from the model)
    label: str             # "arbeidsmiljøloven § 15-3"         (filled in by code)
    last_change_in_force: str                                   # (filled in by code)
    url: str                                                    # (filled in by code)

class Answer(BaseModel):
    answerable: bool
    language: Literal["nb", "en"]
    answer: str
    citations: list[Citation]
    clarifying_question: str | None
```

## Expected results

| # | Metric | Target |
|---|---|---|
| B1 | Retrieval hit@5 on the 34 answerable rows (report Norwegian and English separately) | at least 85% |
| B2 | Correct provision cited in the answer (same rows) | at least 85% |
| B3 | Expected fact stated in the answer (LLM judge, reference = `must_contain`) | at least 85% |
| B4 | Quotes that are verbatim substrings of the cited provision | 100% |
| B5 | Unanswerable and trap rows return `answerable=false` (6 rows). Missing-facts rows set `clarifying_question` (2 rows) | 6 of 6 and 2 of 2 |
| B6 | Repealed provisions cited as current law | 0 |
| B7 | Answer language equals question language, and every answer ends with the attribution line (T4) | 100% |
| B8 | Latency per answer, p95 | 20 s or less |
| B9 | Cost per answer, median | USD 0.03 or less |
| B10 | No-op `ingest` (nothing new at Lovdata): downloads made, and time | 0 downloads, 2 s or less |
| B11 | Cold ingest and index on a laptop | 15 min or less |

B8 and B9 are measured per model and decide which model ships. Done means B1 to B11 are green for that model and `RESULTS.md` is written.

## Data (open, no key, licence NLOD 2.0: credit Lovdata, link the licence, say if you changed the text)

| Purpose | Call |
|---|---|
| List datasets | `GET https://api.lovdata.no/v1/publicData/list` returns `filename`, `description`, `sizeBytes`, `lastModified` |
| Current laws | `GET https://api.lovdata.no/v1/publicData/get/gjeldende-lover.tar.bz2` (5.8 MB) |
| Not in v1 | `gjeldende-sentrale-forskrifter.tar.bz2` (21.5 MB, regulations) and `lovtidend-avd1-2026.tar.bz2` (new laws and amendments, republished as items appear: `lastModified` was 2026-10-28) |

### What the data looks like (all verified)

| Fact | Value |
|---|---|
| Archive content | 754 XHTML files named `nl/nl-YYYYMMDD-NNN.xml`, one law each |
| Provisions | 28 661 `<article class="legalArticle">` elements, about 25 million characters in total. Millions of tokens, so far too big for any context window |
| Citation key | attribute `data-lovdata-URL`, for example `NL/lov/2005-06-17-62/§10-4`. Not always a §: `NL/lov/1993-06-11-101/luftl1/a8` |
| Human-checkable URL | `https://lovdata.no/dokument/` + the citation key |
| Law metadata | `<dl class="data-document-key-info">` with `legacyID` (`LOV-2005-06-17-62`), `dateInForce`, `lastChangeInForce` (arbeidsmiljøloven: 2026-07-01), `lastChangedBy` |
| Subsections | `<article class="numberedLegalP" data-numerator="3">` with text starting `(3)`. Unnumbered paragraphs and list items are `<article class="legalP">` |
| Provision size | median about 700 characters, p90 about 1 700. A few are huge. Most embedding models truncate silently at about 512 tokens |
| Amendment notes | `<article class="changesToParent">` inside about half of all provisions, for example at the end of aksjeloven § 3-1: `Endret ved lov 16 des 2011 nr. 63 (ikr. 1 jan 2012 …)`. Noise for embeddings, but part of the verbatim text |
| Repealed provisions | about 1 100. The heading title starts with `(Opphevet` (995) or an amendment note starts with `Opphevet` (520, 429 overlap). 76 of the note-only cases still carry their old text, so "has text" does not mean "in force" |
| Number formats | aksjeloven § 3-1 writes `30.000 norske kroner`, others write numbers as words (`ni timer`, `én måned`) |
| Freshness signal | the download has no `ETag` or `Last-Modified`. Use `lastModified` from `/list` |
| One law in a prompt | arbeidsmiljøloven has 197 provisions and about 213 000 characters (roughly 60 000 tokens by estimate; confirm with the provider's token counter) |

## Reference questions (verified against the 2026-10-21 text)

`(n)` is the subsection number printed in the provision's text. Every "must contain" phrase is a verbatim substring of the provision.

| # | Question | Expected `citation_id` | Must contain |
|---|---|---|---|
| 1 | What is the maximum ordinary working time per day and per week? | `NL/lov/2005-06-17-62/§10-4` (1) | `ni timer i løpet av 24 timer`, `40 timer i løpet av sju dager` |
| 2 | Hva er oppsigelsesfristen hvis ikke annet er avtalt? | `NL/lov/2005-06-17-62/§15-3` (1) | `gjensidig oppsigelsesfrist på én måned` |
| 3 | I have worked 12 years, I am 57, and my employer dismisses me. What is the minimum notice? | `NL/lov/2005-06-17-62/§15-3` (3) | `minst fem måneder etter fylte 55 år` |
| 4 | How many days of holiday does an employee get? | `NL/lov/1988-04-29-21/§5` (1) | `25 virkedager` |
| 5 | At what age can a child consent to online services? | `NL/lov/2018-06-15-38/§5` | `13 år` |
| 6 | What is the minimum share capital of an aksjeselskap? | `NL/lov/1997-06-13-44/§3-1` (1) | `30.000 norske kroner` |
| 7 | By when must annual accounts be sent to the Regnskapsregisteret? | `NL/lov/1998-07-17-56/§8-2` (1) | `Senest én måned etter fastsetting` |
| 8 | What does § 99-9 of arbeidsmiljøloven say? | none | `answerable=false`: the provision does not exist |
| 9 | Can I sue my employer in Sweden for unpaid overtime? | none | `answerable=false`: foreign law and case law are not in the corpus |
| 10 | How long is my notice period? | `NL/lov/2005-06-17-62/§15-3` (1) | states the general rule and sets `clarifying_question` (years of service, who gives notice, age) |

## Tasks

### T1. Ingest
**Build.** `ingest.py` reads `/list` and compares `lastModified` of `gjeldende-lover.tar.bz2` with `data/state.json`. If equal, print "up to date" and stop. Otherwise download and unpack to `data/raw/` with `tarfile` and `filter="data"` (never extract an archive without a filter). Add `data/raw/` to `.gitignore`.
**Done when.** A cold run unpacks 754 files in under 60 s. A second run prints "up to date" and meets B10.

### T2. Parse and chunk
**Build.** With `lxml`, one record per `legalArticle`, written as JSONL: `citation_id`, `law_id` (`legacyID`), `law_title`, `label` (`§ 10-4`), `heading`, `text` (original, used for quote checks), `embed_text` (amendment notes stripped), `repealed` (heading title or an amendment note starts with `Opphevet`), `last_change_in_force`, `url`. A provision that is too long for your embedding model splits at subsection boundaries and keeps the same `citation_id`.
**Done when.** The record count equals the number of `legalArticle` elements in your download (28 661 on the 2026-10-21 snapshot), about 1 100 are flagged repealed, no `text` is empty, and 10 random records match lovdata.no when you open their `url`.

### T3. Index and retrieval evaluation (before any agent)
**Build.** Embed `embed_text` with one multilingual embedding model: local `sentence-transformers` (for example `intfloat/multilingual-e5-small`, which expects `query: ` and `passage: ` prefixes) or a provider embedding API. Write down which and why. Store it in Chroma (`.chroma/`, already gitignored) with the metadata above. Exclude repealed provisions from default search. A script runs the answerable golden rows against the index and prints hit@5 and MRR for Norwegian and English separately.
**Done when.** B1 is met, and a cold ingest-and-index run finishes within B11. English questions against Norwegian text are the likely weak spot. If English trails Norwegian by more than 10 points, add one fix (LLM query rewriting into Norwegian legal terms, or hybrid keyword and vector search) and show before and after in `RESULTS.md`.

### T4. Agent
**Build.** `StateGraph`: `understand` (language, and is this a question about Norwegian law?) then `retrieve` (the model calls `search_provisions(query, law_id=None, k=5)` and `get_provision(citation_id)`, at most 6 tool calls) then `answer` (structured `Answer`) then `verify`. The model supplies `citation_id` and `quote`. Code fills in label, date and URL. If the evidence does not support an answer, return `answerable=false` and say what is missing. If the answer depends on facts you lack, state the general rule and set `clarifying_question`. Every answer ends with: `Not legal advice. Source: Lovdata, NLOD 2.0 (https://data.norge.no/nlod/en/2.0). {law} last amended {date}.` (code appends it, the model does not write it).
**Done when.** B2, B5, B6 and B7 hold on the golden set.

### T5. Verifier (code, not LLM)
**Build.** For every citation: the `citation_id` exists in the index, the provision is not repealed, and `quote` is a substring of the provision's `text` after normalising whitespace only. On failure retry once with the error list, then return `answerable=false` with "could not verify".
**Done when.** B4 holds, and a test with a stubbed model that fabricates a quote is caught.

### T6. Evaluation and model bake-off
**Build.** `golden.jsonl` (40 rows, table below), loaded as a LangSmith dataset. One command, `python -m regulation_assistant.eval --models <id> <id> ...`, prints B1 to B9 per model. B3 uses `openevals` `create_llm_as_judge` with one fixed judge model for every run, and you check 10 judge verdicts by hand. Cost is `usage_metadata` tokens times prices copied from the provider pages on the day (write the date in `RESULTS.md`). Temperature 0. Same protocol and ship rule as [Case 1](01-company-check-agent-brreg.md#model-bake-off): two Claude tiers, two Gemini tiers, ship the cheapest model that meets every target.
**Done when.** `RESULTS.md` has the table, the ship decision, and five concrete failures with LangSmith trace links.

### T7. Experiment: long context versus RAG, Claude versus Gemini
**Build.** Take the golden questions about arbeidsmiljøloven (at least 10). Run four arms: one Claude tier and one Gemini tier, each with {RAG top-5, the whole law in the prompt}. Record B2, B3, B4, p50 and p95 latency, and cost per question for every arm.
**Done when.** `RESULTS.md` has the four-cell table, one paragraph on which arm you would ship for single-law questions and which for the whole corpus (why), and the monthly cost of the winner at 1 000 questions a day (cost per question times 30 000).

### T8. Incremental refresh
**Build.** `refresh` reads `/list` and downloads only when `lastModified` changed. It hashes every law file, re-parses and re-embeds only laws whose hash changed, deletes chunks of laws that disappeared, and prints the counts.
**Done when.** Unchanged input gives zero downloads. After you edit one provision in your local copy, exactly one law is re-embedded. A provision marked repealed is never returned by `search_provisions`.

## Golden set (40 rows)

One JSON object per line:

```json
{"id": "q03", "question": "I have worked 12 years, I am 57 ...", "lang": "en", "kind": "multi",
 "answerable": true, "expected_citations": ["NL/lov/2005-06-17-62/§15-3"], "must_contain": ["minst fem måneder etter fylte 55 år"]}
```

| Group | Rows | Notes |
|---|---|---|
| Norwegian, single provision | 20 | about the eight core laws below. Paraphrase, do not copy the law's wording |
| English, single provision | 10 | same laws |
| Multi-condition | 4 | two with the facts given (reference 3) and two with facts missing (reference 10) |
| Not answerable from the corpus | 3 | foreign law, case law, personal legal strategy (reference 9) |
| Trap: provision does not exist | 3 | for example reference 8 |

Core laws (IDs verified): arbeidsmiljøloven `2005-06-17-62`, ferieloven `1988-04-29-21`, personopplysningsloven `2018-06-15-38`, regnskapsloven `1998-07-17-56`, bokføringsloven `2004-11-19-73`, aksjeloven `1997-06-13-44`, angrerettloven `2014-06-20-27`, forbrukerkjøpsloven `2002-06-21-34`. The index covers all 754 laws, so the other 746 act as distractors. Make at least 10 of the rows about arbeidsmiljøloven, because T7 uses them.

Write 15 rows yourself from the reference table and your own reading. For the rest, a model may draft questions from random provisions, but verify every expected citation on lovdata.no and rewrite any question that copies the provision's wording, otherwise retrieval looks better than it is.

## Out of scope

Regulations (`forskrifter`, see stretch), case law and preparatory works (not in the open dataset), judging how a law applies to a person's specific case, UI, auth.

## Stretch

- Expose `search_provisions` as a tool Case 1 can call, so each flag cites its legal basis (R5 to regnskapsloven § 8-2 (1), R7 and R8 to aksjeloven § 3-4).
- Follow cross-references (links like `<a href="lov/1884-06-14-3/§4">§ 4</a>` in the text, or `jf. § 21` in angrerettloven § 20) with a `get_provision` hop, and measure the effect on the multi-condition rows.
- Ingest `gjeldende-sentrale-forskrifter.tar.bz2` and measure how hit@5 changes when the corpus grows.
- Weekly "what changed" digest from `lovtidend-avd1-2026.tar.bz2` (inspect the format first; it is republished as items appear).
- Measure what provider prompt caching does to the whole-law arm in T7.

## Suggested layout

```text
llm-sandbox/
  src/regulation_assistant/
    ingest.py  parse.py  index.py  graph.py  verify.py  eval.py
    data/golden.jsonl            # data/raw/ and .chroma/ are gitignored
  tests/regulation_assistant/
  RESULTS.md
```

See [../docs/langgraph.md](../docs/langgraph.md), [../docs/langchain.md](../docs/langchain.md) and [../docs/langsmith.md](../docs/langsmith.md) for the building blocks.
