# Agent Platform — Spec & Roadmap

> Goal: Build a local‑first agent framework that can orchestrate LLM calls, tools, and memory into reproducible pipelines, with a GUI to design prompts and workflows. First concrete use case: a **book‑writing pipeline**.

---

## 1) Product Vision

* **Local‑first**: works offline with a local LLM; optionally configurable for remote models.
* **Composable**: define pipelines as graphs (DAGs) of steps (LLM/tool/transform).
* **Prompt‑centric**: versioned templates, variables, and guardrails editable via GUI.
* **Reproducible**: deterministic configs, cached artifacts, run metadata, and diff tooling.
* **Extensible**: tool/plugin system (Python callables); schema‑driven pipeline definitions.
* **Human‑in‑the‑loop**: approvals, edits, and reruns at step or graph level.

### Non‑Goals (v1)

* Multi‑tenant SaaS hosting.
* Realtime multi‑cursor collaboration.
* Auto‑learning/autonomous long‑running agents.

---

## 2) Primary Use Case: Book Writing Pipeline

**User story:** As an author, I want to generate an outline, chapters, and revisions from a prompt and research corpus, with the ability to tweak prompts and context selection via the GUI, and persist outputs to disk.

**Core flow:**

1. Collect inputs (title, genre, target audience, tone, references).
2. Generate outline.
3. For each chapter: plan → draft → refine → style pass → save.
4. Optional: research retrieval (RAG) from local notes.
5. Export (Markdown/EPUB/PDF) and artifact bundle.

---

## 3) Functional Requirements

* **Pipelines**: Create/edit/save/load pipeline DAGs (JSON/YAML). Import/export.
* **Steps**: Types include `llm_call`, `tool_call`, `transform`, `store`, `branch`, `foreach`.
* **Prompt system**: Templates (Jinja2), variables, partials, few‑shot exemplars, style guides.
* **Context builder**: pluggable retrieval strategies (keywords, embeddings, RAG).
* **Memory**: project store (JSON/SQLite) + optional vector index (FAISS/Chroma).
* **Artifacts**: versioned outputs per step/run; diffable.
* **Run manager**: execute full graph or a subgraph; retries; caching; resumable runs.
* **GUI**: visual node editor + prompt editor + run viewer + artifact inspector.
* **Meta‑agent**: LLM can propose new pipelines from natural language specs.
* **CLI**: run pipelines headless; export and test prompts.

### Non‑Functional

* Local storage by default; no network calls unless configured.
* Deterministic config (seed, temperature, stop sequences) for reproducibility.
* Clear token budgeting; streaming output; backpressure.
* Logging/trace with run IDs; structured JSON logs.

---

## 4) Architecture Overview

```
[ GUI (React/React Flow) ]
          │
          ▼
[ API (FastAPI) ] — [ Event Bus / Logs ]
          │
          ▼
[ Orchestrator / Runtime ] — [ Tool Plugins ]
          │                     ├─ file_io
          │                     ├─ text_utils (split, score, dedupe)
          │                     ├─ web_fetch (optional)
          │                     └─ exporters (md/epub/pdf)
          ▼
[ LLM Client ] — [ Prompt Service ] — [ Context Builder ]
          │                          └─ Memory (JSON/SQLite + Vector DB)
          ▼
      [ Artifact Store ] (files + metadata)
```

**Key modules:**

* **Orchestrator**: executes DAGs; handles inputs/outputs, retries, caching, timeouts.
* **Prompt service**: loads templates, renders with variables; validates placeholders.
* **Context builder**: chunking, embeddings, retrieval/ranking, context packing.
* **Memory**: SQLite (metadata) + folder of JSON/MD assets; optional FAISS/Chroma index.
* **Artifacts**: content‑addressed files with `run.json` metadata (tokens, timing, config).
* **Tools**: Python callables registered by name and schema.

---

## 5) Data & Schema

### Pipeline (JSON/YAML)

```yaml
version: 1
name: Book Writer
inputs:
  title: string
  genre: string
  audience: string
  tone: string
  references_dir: path
steps:
  - id: outline
    type: llm_call
    prompt: templates/outline.j2
    params: {temperature: 0.5, max_tokens: 1500}
    outputs: {outline_md: text}

  - id: plan_chapters
    type: transform
    code: python:utils.plan_chapters
    inputs: {outline_md: outline.outline_md}
    outputs: {chapters: list}

  - id: draft_chapters
    type: foreach
    foreach: plan_chapters.chapters
    body:
      - id: draft
        type: llm_call
        prompt: templates/chapter_draft.j2
        inputs: {chapter_plan: item, outline_md: outline.outline_md}
        params: {temperature: 0.7, max_tokens: 3500}
        outputs: {draft_md: text}
      - id: style
        type: llm_call
        prompt: templates/style_pass.j2
        inputs: {draft_md: draft.draft_md, tone: $.tone}
        params: {temperature: 0.4}
        outputs: {chapter_md: text}

  - id: save
    type: store
    target: artifacts/book.md
    inputs: {outline: outline.outline_md, chapters: draft_chapters[*].style.chapter_md}
```

### Step Result Metadata (per run)

```json
{
  "run_id": "2025-10-08-091530-utc",
  "pipeline": "book-writer",
  "step": "outline",
  "inputs": {"title": "…"},
  "outputs": {"outline_md": "# …"},
  "llm_stats": {"prompt_tokens": 1200, "completion_tokens": 900, "latency_ms": 4200},
  "artifacts": ["artifacts/outline.md"],
  "cache_key": "…",
  "params": {"temperature": 0.5}
}
```

### Memory Records

```json
{
  "id": "doc_8f93…",
  "kind": "note|source|draft|chapter",
  "path": "memory/notes/research-x.md",
  "embedding": "vector-ref (optional)",
  "metadata": {"title": "Research X", "tags": ["character-A"], "chunk_id": 3}
}
```

---

## 6) Prompt Assets

* **Structure**: `templates/` with `system/`, `partials/`, `styles/`, `pipelines/`.
* **Conventions**: front‑matter for metadata (style, stop words, constraints).
* **Validation**: CI check ensures all `{{ variables }}` are supplied by the pipeline.

**Example** — `templates/chapter_draft.j2`

```jinja2
[system]
You are a professional novelist. Write vivid, coherent prose with strong pacing.

[user]
Title: {{ title }}
Chapter Plan:
{{ chapter_plan }}

Outline context (for continuity):
{{ outline_md | truncate(4000) }}

Constraints:
- Tone: {{ tone }}
- Keep continuity with prior chapters if referenced.
- Return Markdown only.
```

---

## 7) Context & Retrieval Strategy

* **Chunking**: Markdown‑aware, ~800–1200 tokens with overlap.
* **Embeddings**: local model if available; otherwise fall back.
* **Retrieval**: hybrid (BM25 + cosine) with max‑marginal relevance (MMR) de‑dupe.
* **Packing**: budget‑aware selection; include citations/IDs to enable traceability.
* **Guards**: context size hard limits; truncation with clear boundaries.

---

## 8) Execution Model & Reliability

* **Scheduler**: topological order; supports parallel branches; `foreach` batch.
* **Caching**: content‑addressed by (step id + rendered prompt + params + context hash).
* **Retries**: exponential backoff; classify transient vs. fatal errors.
* **Idempotency**: store and step writes use temp paths + atomic rename.
* **Timeouts/quotas**: per step and per run.

---

## 9) Observability

* **Run log**: structured JSON + pretty console.
* **Artifacts**: tree view with diffs (Markdown diff).
* **Metrics**: tokens, latency, cache hit rate, retrieval quality stats.
* **Traces**: parent/child spans per step.

---

## 10) Security & Privacy

* All data on local disk by default.
* Secrets via `.env` only if remote endpoints are enabled.
* Allowlist tools; sandbox untrusted tools (process isolation optional).

---

## 11) Testing & Evaluation

* **Unit tests**: template rendering, step adapters, tool IO contracts.
* **Golden tests**: snapshot expected structure (headings, outline shape, style heuristics).
* **Eval harness**: readability (FK score), repetition checks, style constraint adherence.
* **Manual review loop**: markups that feed a `revise` step.

---

## 12) Exporters

* **Markdown** (primary), **EPUB** (Calibre/`ebooklib`), **PDF** (wkhtmltopdf).
* **Bundle**: `artifacts/run-<id>/` with `book.md`, `book.epub`, prompts, and logs.

---

## 13) Tech Stack (proposed)

* **Backend**: Python 3.11, FastAPI, Pydantic, Uvicorn.
* **Runtime**: networkx (DAG), asyncio, Jinja2, sqlite3, FAISS/Chroma.
* **LLM**: local client wrapper (your model) with a simple provider interface.
* **GUI**: React + Vite, Tailwind, **React Flow** (graph), Monaco (prompt editor).
* **Packaging**: uv/poetry, pre‑commit (ruff, black, mypy), pytest.

---

## 14) Roadmap (Step‑by‑Step)

### Phase 0 — Scaffolding (1–2 days)

* [ ] Repo layout: `core/`, `server/`, `ui/`, `pipelines/`, `templates/`, `tools/`, `artifacts/`, `memory/`.
* [ ] Python project setup (uv/poetry), lint/format/mypy, test harness.
* [ ] Define provider interface for LLM + minimal local client.
* [ ] `orchestrator` skeleton: load pipeline JSON, run linear sequence, log outputs.
* **Exit criteria:** CLI runs a toy pipeline with a single `llm_call` and writes an artifact.

### Phase 1 — MVP Pipeline (Book v0) (3–5 days)

* [ ] Implement step types: `llm_call`, `transform(py)`, `store`.
* [ ] Implement `foreach` iterator.
* [ ] Prompt service (Jinja2) + template validation.
* [ ] Artifact store + run metadata.
* [ ] Basic caching (hash of prompt+params+context).
* [ ] Example pipeline: outline → chapter draft → save Markdown.
* **Exit criteria:** From CLI, generate a 3‑chapter booklet with configurable inputs.

### Phase 2 — GUI Alpha (1–2 weeks)

* [ ] FastAPI endpoints: run/list pipelines, get artifacts, logs, templates.
* [ ] React Flow editor: add/edit nodes, connect edges, edit step params.
* [ ] Prompt editor with live variable preview.
* [ ] Run viewer: status, logs, artifacts; re‑run from a node.
* **Exit criteria:** Design a pipeline in UI, run it, inspect outputs without the CLI.

### Phase 3 — Memory & Retrieval (1 week)

* [ ] SQLite metadata + file‑backed memory records.
* [ ] Embeddings index (FAISS/Chroma) + ingest job.
* [ ] Context builder: BM25 + vector hybrid, MMR, packing.
* [ ] Add retrieval into chapter prompts (RAG option toggle).
* **Exit criteria:** Chapters incorporate top‑k retrieved notes with citations.

### Phase 4 — Reliability & Quality (1 week)

* [ ] Parallel branches; timeouts; retries; better error surfaces.
* [ ] Token budgeting + streaming; partial saves; resume runs.
* [ ] Diff viewer; golden tests; basic eval metrics.
* **Exit criteria:** Stable long runs with diagnosable failures and measurable quality.

### Phase 5 — Meta‑Agent & Templates (1 week)

* [ ] Spec‑to‑pipeline generator: LLM produces a valid pipeline JSON/YAML.
* [ ] Template packs: outline styles, character sheets, genre presets.
* [ ] One‑click scaffold from preset in GUI.
* **Exit criteria:** Describe a new flow in natural language → runnable pipeline stub.

---

## 15) Acceptance Criteria (MVP)

* Run the book pipeline end‑to‑end locally via GUI and CLI.
* Pipelines are saved as JSON/YAML; re‑runnable with same outputs when cached.
* Prompts editable in GUI; validation prevents missing variables.
* Artifacts and run logs accessible and exportable.

---

## 16) Risks & Mitigations

* **LLM drift/instability** → stronger constraints, lower temperature, golden tests.
* **Token limits** → incremental generation, context packing, per‑chapter runs.
* **Prompt debt** → templates + style guides; CI validation.
* **Complexity creep** → start with 3–5 essential step types; plugin later.

---

## 17) Open Questions

* Which local embedding model to standardize on?
* Need a sandbox for tools (process isolation) in v1?
* Preference for JSON vs YAML for pipelines in the GUI?
* Do we want a project‑level config (e.g., `project.yml`) to set defaults?

---

## 18) Quick Start (target state)

```
# CLI
agent run pipelines/book_writer.yaml \
  --title "Voyagers" --genre "Sci‑Fi" --tone "Optimistic" --audience "Adult"

# GUI
1) Open http://localhost:5173
2) Load template “Book Writer”
3) Edit prompts, set inputs, Run
4) Download artifacts/run-<id>/book.md
```
