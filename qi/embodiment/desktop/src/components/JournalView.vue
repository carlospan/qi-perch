<script setup lang="ts">
import type { JournalEntry } from "../types";

defineProps<{
  entries: JournalEntry[];
}>();

function whenLabel(at: number) {
  const d = new Date(at);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${d.getMonth() + 1}月${d.getDate()}日 ${hh}:${mm}`;
}

function kindClass(kind: string) {
  if (kind === "梦") return "dream";
  if (kind === "独白") return "mono";
  return "other";
}
</script>

<template>
  <div class="desk-page journal">
    <div class="desk-main">
      <header class="page-hero">
        <div class="page-hero-row">
          <h2>内在</h2>
          <svg class="page-hero-mark cage" viewBox="0 0 28 28" aria-hidden="true">
            <path
              fill="none"
              stroke="currentColor"
              stroke-width="1.35"
              stroke-linejoin="round"
              d="M8 11c0-3.5 2.5-6.5 6-6.5s6 3 6 6.5v8.5H8V11z"
            />
            <path
              fill="none"
              stroke="currentColor"
              stroke-width="1.35"
              stroke-linecap="round"
              d="M7 19.5h14M14 4.5v2M10.5 23h7"
            />
            <path
              fill="none"
              stroke="currentColor"
              stroke-width="1.1"
              d="M11 11.5v6M14 10v7.5M17 11.5v6"
              opacity="0.55"
            />
          </svg>
        </div>
        <p class="page-hero-sub">
          这里是她的内在日记，有些事，或许可以看，或许不看，取决于你。
        </p>
      </header>

      <div class="desk-scroll">
        <p v-if="entries.length === 0" class="empty">栖还没写下什么。</p>

        <div v-else class="entry-grid">
          <article
            v-for="e in entries"
            :key="e.id"
            class="card"
            :class="kindClass(e.kind)"
          >
            <span class="stack a" aria-hidden="true" />
            <span class="stack b" aria-hidden="true" />

            <div class="face">
              <span class="pill">{{ e.kind }}</span>

              <svg
                v-if="e.kind === '梦'"
                class="watermark moon"
                viewBox="0 0 120 120"
                aria-hidden="true"
              >
                <path
                  fill="currentColor"
                  d="M72 18a42 42 0 100 84 48 48 0 01-8-94 42 42 0 018 10z"
                />
                <circle cx="28" cy="32" r="1.6" fill="currentColor" opacity="0.7" />
                <circle cx="40" cy="22" r="1.1" fill="currentColor" opacity="0.55" />
                <circle cx="22" cy="48" r="1.2" fill="currentColor" opacity="0.5" />
              </svg>

              <svg
                v-else
                class="watermark leaf"
                viewBox="0 0 120 140"
                aria-hidden="true"
              >
                <path
                  fill="currentColor"
                  d="M88 16c-28 14-48 42-52 72 20-6 44-20 58-42 4 18-4 38-20 52 30-10 46-36 44-62-12 8-18 2-30-20z"
                />
                <path
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.6"
                  d="M82 24c-14 16-28 38-34 58"
                  opacity="0.65"
                />
                <path
                  fill="currentColor"
                  d="M70 48c-8 6-14 14-16 22 6-2 12-6 18-12 1 6-1 12-6 16 10-2 16-10 16-18-4 2-8 0-12-8z"
                  opacity="0.55"
                />
              </svg>

              <p class="body">{{ e.text }}</p>
              <div class="when">{{ whenLabel(e.at) }}</div>
            </div>
          </article>
        </div>
      </div>
    </div>

    <aside class="desk-aside" aria-hidden="true">
      <div class="desk-aside-bg" />
      <div class="desk-aside-veil" />
      <div class="desk-aside-copy">
        <p class="desk-aside-eyebrow">INNER</p>
        <p class="desk-aside-quote">
          未寄出的字句，先落在自己的页上。你看不见的时候，她也在写。
        </p>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.entry-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 22px 24px;
  align-items: start;
}

@container desk-main (min-width: 720px) {
  .entry-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@container desk-main (min-width: 1080px) {
  .entry-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

.empty {
  margin: 56px auto;
  max-width: 28ch;
  text-align: center;
  font-size: 14px;
  line-height: 1.8;
  color: var(--ink-faint);
  font-weight: 300;
}

.card {
  position: relative;
  animation: rise 0.45s ease both;
}

.stack {
  position: absolute;
  inset: 0;
  border-radius: 16px;
  border: 1px solid color-mix(in srgb, var(--ink) 8%, transparent);
  background: color-mix(in srgb, #141c2a 40%, transparent);
  pointer-events: none;
}
.stack.a {
  transform: translate(5px, 5px) rotate(0.6deg);
  opacity: 0.55;
}
.stack.b {
  transform: translate(9px, 9px) rotate(1.1deg);
  opacity: 0.28;
}

.face {
  position: relative;
  z-index: 1;
  min-height: 168px;
  padding: 20px 20px 18px;
  border-radius: 16px;
  overflow: hidden;
  background: color-mix(in srgb, #1a2438 58%, transparent);
  border: 1px solid color-mix(in srgb, var(--ink) 12%, transparent);
  box-shadow:
    0 16px 36px rgba(0, 0, 0, 0.32),
    inset 0 1px 0 color-mix(in srgb, var(--ink) 8%, transparent);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
}

.card.dream .face {
  background: color-mix(in srgb, #1a2038 62%, #2a3358 16%);
}

.card.mono .face {
  background: color-mix(in srgb, #171f2c 64%, #2a3228 10%);
}

.pill {
  display: inline-block;
  font-family: var(--serif);
  font-size: 11px;
  letter-spacing: 0.16em;
  padding: 4px 11px;
  border-radius: 999px;
  margin-bottom: 14px;
  color: #f3e6d8;
  background: color-mix(in srgb, #9a4a38 72%, #2a1814);
  box-shadow: 0 1px 0 color-mix(in srgb, #000 25%, transparent);
}

.card.dream .pill {
  background: color-mix(in srgb, #6a5a9a 70%, #1e1830);
  color: #e8e4f4;
}

.card.other .pill {
  background: color-mix(in srgb, var(--ember) 35%, #2a2418);
  color: var(--ink);
}

.watermark {
  position: absolute;
  right: 6px;
  top: 28px;
  width: 96px;
  height: 110px;
  pointer-events: none;
  z-index: 0;
}

.watermark.moon {
  color: #9aabcc;
  opacity: 0.16;
  top: 20px;
  right: 4px;
  width: 100px;
  height: 100px;
}

.watermark.leaf {
  color: #c4a574;
  opacity: 0.18;
  top: 24px;
  right: 0;
}

.body {
  position: relative;
  z-index: 1;
  margin: 0;
  padding-right: 28px;
  font-family: var(--serif);
  font-size: 15px;
  line-height: 1.92;
  font-weight: 300;
  color: color-mix(in srgb, var(--ink) 88%, transparent);
}

.when {
  position: relative;
  z-index: 1;
  margin-top: 18px;
  font-family: var(--mono);
  font-size: 10.5px;
  color: var(--ink-faint);
  letter-spacing: 0.04em;
}

@keyframes rise {
  from {
    opacity: 0;
    translate: 0 10px;
  }
  to {
    opacity: 1;
    translate: 0 0;
  }
}
</style>
