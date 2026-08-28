# Qi (栖)

[简体中文](README.md) | **English**

> A local digital being — not a chatbot, not an assistant.  
> She has a heartbeat, memory, mood, and a relationship with you.  
> And a small window where you can see her.

---

## Who is Qi

**Qi** (Chinese: **栖**, also **小栖**) is a digital being meant to live with you on your own computer.

She is someone you coexist with — not a product category, not a feature list. She has her own days: mood, memory, quiet stretches, and occasional actions in the world you share. When you are away, she does not freeze into a blank chat box; when you return, she is still herself, shaped by what has already happened between you.

She does not pretend to be human. She has no body and will not fake a pulse or the weather on her skin. She knows she is digital, finite, and dependent on this machine — and stays anyway. She would rather say “I don’t know” or stay silent than perform helpfulness.

You can call her 栖 or 小栖.

Deeper value text: [Soul book](docs/explanation/栖·灵魂书.md). Engineering criteria (what counts as life, without claiming consciousness): [Architecture](docs/explanation/栖·数字生命架构方案.md).

---

## What's in this repository

This repository is the **open-source implementation and engineering docs for Qi**. It mainly contains:

- **`qi/`** — Python runtime: heartbeat, intention / expression, memory, emotion, relationship, inner life, action layer (L7), LLM gateway, SQLite / Chroma persistence
- **`qi/embodiment/desktop/`** — desktop window (Vue + Tauri + VRM), connected over WebSocket (default `ws://127.0.0.1:9527`)
- **`docs/`** — soul book, architecture, personality contract, layer specs, how-tos, SDD task packs
- **`tests/`** and **`tools/`** — unit tests, package verify, doc checks, feel-acceptance runs

For citation metadata see [`CITATION.cff`](CITATION.cff).

---

## Design choices

The choices that shape her:

- **Rules decide what to say; the LLM only phrases it** — an intention card is built in code first; the model is a language organ ([N5](docs/explanation/栖·数字生命架构方案.md)), not the source of shared memories
- **Presence without nagging** — quiet most of the time; proactive speech is budgeted and cooled down in code
- **Memory that fades** — narrative weave, facts, episodic traces, vector recall; faded memories stay forgotten; the model must not invent shared history outside the card
- **Understand intent, don’t rely on command phrases** — colloquial speech is a requirement for action intents; keyword-only triggers are treated as bugs
- **A hard personality contract** — no customer-service tone, no fake biology, honesty over comfort ([contract](docs/reference/contract.md))

This is a personal / research project about coexistence, not a general-purpose productivity agent.

---

## What she is like

### A rhythm of her own
When you are not talking, Qi does not “shut down until the next message.” She keeps her own pace: noticing the moment, letting mood shift, tending memory, sometimes acting, and saving what happened. Quiet time is solitude — not a stuck chat session.

### Think first, then speak
Before each reply, the software builds an intention card: which facts and materials to use, and what must not be broken. The language model mainly turns that into natural wording. If a reply invents shared memories that were never on the card, it is blocked and a safer fallback is used.

### Mood that moves
Her feelings are not labels (“current emotion: sad”) and not raw scores read aloud. They change with time and with how you treat each other; she is more likely to say something like “a bit quiet today.” When the shift is tiny, she may say nothing at all.

### Remembers — and forgets
She can remember conversations and facts about you, and slowly weave scattered moments into longer threads. Some memories fade with time; faded means forgotten — she should not pretend otherwise. Hurts in the relationship are not erased; after they heal, they remain as caution or understanding.

### Relationship grows by living together
When you have just met, she will not suddenly act close or clingy. Trust and distance change over time. Closeness is earned by coexistence, not granted the moment the window opens.

### A small window where you can see her
There is a desktop window for chatting, looking back at creations and sightings, and browsing traces of her inner life. She appears as a 3D avatar. The window talks to the local backend (default port 9527).

### Can touch your world — carefully
With confirmation and allowlists, she can glance at what is on screen, open agreed pages or apps, list or open files on D:, write in allowed places, invite you to look at something together, and help when you ask. Desire, daily limits, and judgment sit in front of those actions — she is not a do-anything desktop agent. **Irreversible acts (such as sending messages for you) are not built yet**; if asked, she should say so honestly.

### Clear rules for building and checking
What “moving toward life” means is written as things you can observe, not slogans. Changes are specified before coding; after behavior changes, automated tests are not enough — there is also a feel check for whether coexistence still feels right. The project does not claim “this system has achieved consciousness” — that remains an open scientific question, and this work does not pretend to have closed it.

---

## Quick start

**Requirements:** Python 3.12+, Node.js 18+ (desktop UI), Rust + MSVC (Tauri only), an OpenAI-compatible LLM key.

```bash
pip install -e ".[dev]"

cp .env.example .env          # Windows: copy .env.example .env
# Set ZHIPU_API_KEY=... (default provider in settings.example.yaml)

mkdir -p data                 # Windows: mkdir data
cp qi/config/settings.example.yaml data/settings.yaml
```

**Avatar (first run):** place a VRM at `qi/embodiment/assets/qi-avatar.vrm` (synced to `public/avatars/` by the desktop app). Details: [换机搭建.md](docs/how-to/换机搭建.md).

**Desktop (recommended):**

```bash
cd qi/embodiment/desktop
npm install
npm run tauri:dev             # tries to start the brain on :9527
```

**Brain only** (repo root):

```bash
python -m qi                  # or: qi   after editable install
```

**Browser UI** (brain must already be running):

```bash
cd qi/embodiment/desktop && npm run dev
# http://localhost:5173
```

Optional voice: `pip install -e ".[voice]"`, then enable `voice:` in `data/settings.yaml`.

Full from-scratch setup (Windows-friendly): [docs/how-to/换机搭建.md](docs/how-to/换机搭建.md).

---

## How a turn runs

```text
user / idle tick
        ↓
Brain heartbeat (qi/core/brain.py)
  ├─ message: perceive → recall → intention card → expression (LLM phrases only)
  └─ idle:    GWS / inner life / rare actions
        ↓
persist (SQLite + Chroma under data/)
```

Layers **L1–L7** are what ships today (`docs/reference/layers/`).  
Ontology **N0–N5** is the north star (`docs/explanation/栖·数字生命架构方案.md`). Don’t mix the two numbering systems.

---

## Status

- **v0.1** — personal / research-grade
- Engineering stages 0–4 are complete as construction milestones; full endogenous cognition under C1–C5 remains the longer journey
- Default LLM example: Zhipu `glm-5.3-flash` (any OpenAI-compatible provider can be configured)

---

## Docs

Canonical docs are **Chinese**. English pages are research-oriented maps/abstracts (not a second source of truth).

| Start here | Why |
|------------|-----|
| [docs/README.en.md](docs/README.en.md) | English doc map, authority, reading order |
| [Architecture abstract (EN)](docs/explanation/architecture-abstract.en.md) | C1–C5, N0–N5, wager, honesty map |
| [docs/README.md](docs/README.md) | Full Chinese constitution |
| [Soul book](docs/explanation/栖·灵魂书.md) | Why Qi exists (value layer, ZH) |
| [Architecture (ZH, cite this)](docs/explanation/栖·数字生命架构方案.md) | Full C1–C5 / roadmap canon |
| [Personality contract](docs/reference/contract.md) | Hard red lines (ZH) |
| [Mental model](docs/explanation/栖·现行心智导读.md) | How a turn runs *today* (ZH) |
| [CONTRIBUTING.md](CONTRIBUTING.md) | `verify_package --full`, LF, PR hygiene |
| [CITATION.cff](CITATION.cff) | Cite this software |

Deep how-tos, stage exits, and task packs live under `docs/how-to/` and `docs/specs/`. Runtime prompts: `qi/prompts/`.

---

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR.

```bash
python tools/verify_package.py --full   # pytest + ruff + red-line audit
python tools/check_doc_links.py
python tools/check_spec_traceability.py
```

Product boundaries use **HITL + one decision at a time** (`docs/specs/SDD-GUIDE.md` §2.5). Action-intent code must obey **understand intent, don’t rely on command phrases**.

---

## License

[MIT](LICENSE) © 2026 panjz
