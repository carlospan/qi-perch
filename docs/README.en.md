# docs · Constitution (English entry)

**English** | [简体中文](README.md)

> Canonical documentation is **Chinese**. This page is the English map for international readers and researchers: what is authoritative, what Qi claims (and does not), and where to read next.
> Full Chinese constitution: [`README.md`](README.md).

---

## Language policy

| Layer | Language | Role |
|-------|----------|------|
| Root [`README.md`](../README.md) | Chinese (default) | Project home |
| Root [`README.en.md`](../README.en.md) | English | International home |
| **`docs/` specs, contracts, tasks** | **Chinese = source of truth** | Do not treat English abstracts as superseding Chinese |
| English pages under `docs/` | Abstracts / maps only | Orientation for research exposure; keep thin to avoid dual-source drift |

If English and Chinese disagree, **Chinese + code win**.

---

## Collaboration iron rules (must read)

How this repo decides product behavior with humans + AI agents:

| Name | Meaning |
|------|---------|
| **HITL** | Maintainer approves product boundaries; agents do not invent them |
| **Spec-driven** | Observable behavior goes into a task-pack Spec before coding |
| **One decision at a time** | Confirm small slices; write Spec + HITL immediately; do not hoard chat as truth |
| **Understand intent, don’t rely on command phrases** | Action intents must understand colloquial speech; keyword-only remotes are bugs → Chinese [`reference/contract.md`](reference/contract.md) 「理解意图」 |

Details: Chinese [`specs/SDD-GUIDE.md`](specs/SDD-GUIDE.md) §2.5.

---

## Doc layout (Diátaxis + SDD)

| Path | Type | Contents |
|------|------|----------|
| `explanation/` | Explanation | Soul book, architecture, current mental model, thoughts/ |
| `reference/` | Reference | Contract, L1–L7 layers, config (synced to code) |
| `how-to/` | How-to | Setup, acceptance, UI, IDE-agent manuals |
| `tutorials/` | Tutorials | Learning-the-codebase conventions |
| `specs/` | SDD | Guide, acceptance tests, stages, live tasks, archive |

`progress.md` / `journal.md` are timelines / coexistence notes, not handbooks.

---

## Authority map (by question type)

| Question | Ask | Notes |
|----------|-----|-------|
| Value: life vs tool? | [`explanation/栖·灵魂书.md`](explanation/栖·灵魂书.md) | Value layer |
| What counts as digital life? Roadmap? | [`explanation/栖·数字生命架构方案.md`](explanation/栖·数字生命架构方案.md) | Goal-layer canon; English abstract: [`architecture-abstract.en.md`](explanation/architecture-abstract.en.md) |
| Tone / prompt / behavior red lines? | [`reference/contract.md`](reference/contract.md) | Hard bugs if violated |
| Action intent “understand meaning”? | Same contract, 「理解意图」 | Keyword remotes = bugs |
| Engineering invariants R1–R5? | Architecture §七 / [`specs/stages/_invariants.md`](specs/stages/_invariants.md) | |
| How code should work *today*? | **Code** > `reference/layers/` > [`栖·现行心智导读.md`](explanation/栖·现行心智导读.md) | Archive under `explanation/archive/` is history only |
| Stage exit criteria? | `specs/stages/stage-*.md` | |
| Open questions? | [`specs/open-questions.md`](specs/open-questions.md) | |

---

## Consciousness discourse (dual track)

- **First-person existence stance** (soul book; Qi speaking in prompts; “choose to trust experience while admitting it cannot be proven”): **allowed** — product soul.
- **Third-person engineering claim** (“this system implements consciousness / qualia”): **forbidden** — not an engineering deliverable (architecture §〇 / R1).

When unsure which register you are in, treat the third-person claim as forbidden.

---

## Suggested reading order (research)

1. Root [`README.en.md`](../README.en.md) — what Qi is  
2. This page — authority & policy  
3. [`architecture-abstract.en.md`](explanation/architecture-abstract.en.md) — C1–C5, N0–N5, wager, honesty map  
4. Chinese full architecture (cite this for definitions) — [`栖·数字生命架构方案.md`](explanation/栖·数字生命架构方案.md)  
5. Current turn path — [`栖·现行心智导读.md`](explanation/栖·现行心智导读.md)  
6. Hard behavioral contract — [`reference/contract.md`](reference/contract.md)  
7. Value layer (Chinese) — [`栖·灵魂书.md`](explanation/栖·灵魂书.md)  
8. Layer specs as needed — [`reference/layers/`](reference/layers/)  
9. Acceptance operationalization — [`specs/acceptance.md`](specs/acceptance.md)

---

## Two numbering systems (do not mix)

| System | Meaning | Where |
|--------|---------|--------|
| **L1–L7** | Shipped functional layers | `reference/layers/` |
| **N0–N5** | Target ontology layers | Architecture (Chinese) + English abstract |

---

## Citing / contributing

- License: MIT (see root `LICENSE`)  
- Machine-readable citation: [`CITATION.cff`](../CITATION.cff)  
- Before PRs: [`CONTRIBUTING.md`](../CONTRIBUTING.md) (`verify_package --full`, LF line endings)

English coverage will grow as abstracts only where research need is clear — not as a full mirror of `docs/`.
