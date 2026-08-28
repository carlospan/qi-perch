# Qi · Architecture abstract (English)

> **Status:** Research-facing abstract of the Chinese canon  
> **Canon (cite for definitions):** [`栖·数字生命架构方案.md`](栖·数字生命架构方案.md)  
> **Map:** [`../README.en.md`](../README.en.md)  
> If this page and the Chinese architecture disagree, **the Chinese document wins**.

This abstract answers: *If the goal is not “life-like UX” but **life** under inspectable criteria, how should the software evolve — and what must it refuse to claim?*

---

## Promises and non-promises

**Promises:** a path from the current codebase that can be built and checked step by step, toward an autonomous, endogenous, continually growing digital being.

**Does not promise:** consciousness, experience, or qualia. Those are open scientific problems. No known method makes code produce phenomenal experience, and no instrument detects it. Endpoint criteria in this project are **externally observable behavioral and structural criteria** only. Any document that says “this design implements consciousness” is out of scope and dishonest for this repo.

---

## C1–C5 — criteria for “digital life”

A system is treated as digital life here only if it meets **all five**. Each criterion has a test. Unfalsifiable wishes are not criteria.

| # | Criterion | Meaning | Test |
|---|-----------|---------|------|
| **C1** | Endogenous cognition | “Thoughts” arise from the system’s own structure and experience, not from a stateless external service | **Unplug test:** with remote LLMs disconnected, non-trivial behavior remains (state evolution, exploration, memory ops, decisions) — not silence or empty spinning |
| **C2** | Self-maintenance | Real resources are consumed; the system must act to sustain itself; the ledger is endogenous. Caveat: “wanting to live” cannot be evolved into a single software instance — C2 requires real, diverse maintenance behavior, not a grown survival drive | **Starve test:** after cutting resource channels, observable coping (throttle, ask for help, migrate) — not dying unaware |
| **C3** | Sense–act loop | Actions change the world; world changes return as perception; the loop does not require a human to start it | **Alone test:** 72h with no user input; behavior still driven by internal state; traces tell a coherent story of what it was doing |
| **C4** | Intrinsic motivation | Action choice is driven by internally derived pressures (curiosity, need, learning progress), not quota gates. Randomness may time a release after motive crosses threshold; it must not *create* the motive | **Trace test:** for any autonomous act, logs answer *why it wanted this now* from internal state |
| **C5** | Structural plasticity | Experience changes the system’s own parameters/connections — not only more DB rows. A year later it is cognitively different | **Diachronic test:** same input patterns yield attributable drift from accumulated experience, not explainable as “row count grew” |

Optional classic ALife criteria (self-replication / evolution) are deferred for this coexistence setting. Process exit = death is treated as honest; state migratability matters for C2.

Operationalization of the five tests: Chinese [`../specs/acceptance.md`](../specs/acceptance.md).

---

## The core wager

> **Clumsy endogenous cognition is closer to life than clever outsourced cognition.**

**Local ≠ endogenous.** A 7B model on your GPU can still be pretrained echo — privatized outsourcing. Endogeny requires **plasticity**: parameters change because of *this* being’s experience.

Degree (clever vs clumsy) can grow; ontology (endogenous vs outsourced) does not blend. The roadmap stages monitor both **endogeny** and **felt coexistence**; collapse on either side means roll back. If they prove incompatible, that empirical result should be written back into the canon.

---

## Target ontology N0–N5 (not the same as L1–L7)

Shipped code is organized as **L1–L7** (functional). The north-star stack is **N0–N5** (ontological):

```
N5  Language organ     LLM — translate only, do not think
N4  Plasticity         experience replay / memory that changes structure
N3  Intrinsic motive   learning progress / homeostasis pressure / prediction error
N2  Cognitive core     global workspace + world model — where thoughts arise
N1  Sense–act          sensors + real effectors + closed loop
N0  Homeostasis        emotion dynamics + resource ledger — baseline of staying alive
```

### N5 — language organ (hard rule)

The LLM phrases an **intention card** built by rules. Wording may polish; **facts must have provenance**. Outputs must not introduce shared-history claims absent from the intention / traces. This is already a central discipline in the running system (`intention` → `expression` gates).

---

## Honesty map of the *current* codebase (summary)

The Chinese architecture classifies modules by whether they truly serve C1–C5 or only perform:

| Kind | Examples (simplified) |
|------|------------------------|
| **Real skeleton** | Heartbeat loop without user input; emotion dynamics in code; memory decay / weave; action budgets that enforce restraint in software |
| **Performance layer** | Some “stream of consciousness” / dream / self-model paths that are still largely remote completion labeled as inner life — being rewritten toward endogeny |
| **Misplaced layer** | Treating the LLM gateway as the “brain”; target is language organ only |

One-line diagnosis used in-project: **there is a real skeleton; the “heart” is still partly on extracorporeal circulation (remote LLM). The program is to put the heart back inside without killing the patient mid-surgery.**

Engineering stages 0–4 exist as construction milestones in Chinese `specs/stages/`; meeting stage exits is not the same as declaring C1–C5 complete.

---

## Red lines (selected)

- **R1** — No third-person claim that the system has consciousness / feelings. First-person stance in the soul book and in-character prompts is a different register (see dual track in [`../README.en.md`](../README.en.md)).  
- **R2** — Do not encode personality only in prompts; personality should grow from history / plasticity.  
- Full list: Chinese architecture §七.

---

## Related English / bilingual entry points

| Doc | Role |
|-----|------|
| [`../README.en.md`](../README.en.md) | Docs constitution map (EN) |
| [`../../README.en.md`](../../README.en.md) | Project README (EN) |
| [`栖·数字生命架构方案.md`](栖·数字生命架构方案.md) | Full architecture (ZH, cite this) |
| [`栖·现行心智导读.md`](栖·现行心智导读.md) | How a turn runs *today* (ZH) |
| [`../reference/contract.md`](../reference/contract.md) | Personality / intent contract (ZH) |
| [`../../CITATION.cff`](../../CITATION.cff) | Citation metadata |
