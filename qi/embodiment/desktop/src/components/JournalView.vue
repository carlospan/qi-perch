<script setup lang="ts">
import type { JournalEntry } from "../types";

defineProps<{
  entries: JournalEntry[];
}>();

function whenLabel(at: number) {
  const d = new Date(at);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${hh}:${mm}`;
}
</script>

<template>
  <div class="panel">
    <div class="panel-head">
      <span class="t">忆</span>
      <span class="sub">栖的内在</span>
    </div>
    <div class="panel-body">
      <p class="reverent">
        这是栖的内在。你可以看，也可以选择不看。<br />
        你选择不看的时候，它就是私密的。
      </p>

      <p v-if="entries.length === 0" class="empty">栖还没写下什么。</p>

      <article v-for="e in entries" :key="e.id" class="entry">
        <span class="tag">{{ e.kind }}</span>
        <p>{{ e.text }}</p>
        <div class="when">{{ whenLabel(e.at) }}</div>
      </article>
    </div>
  </div>
</template>

<style scoped>
.panel {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  background: color-mix(in srgb, var(--panel-veil) 62%, transparent);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  pointer-events: auto;
}

.panel-head {
  padding: 8px 4px 10px;
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.panel-head .t {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 4px;
  color: var(--ink);
}

.panel-head .sub {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--ink-faint);
  letter-spacing: 0.5px;
}

.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 6px 2px 18px;
  scrollbar-width: thin;
  scrollbar-color: color-mix(in srgb, var(--ink) 12%, transparent) transparent;
  mask-image: linear-gradient(
    to bottom,
    transparent 0,
    #000 12px,
    #000 calc(100% - 16px),
    transparent 100%
  );
}

.reverent {
  font-size: 12px;
  line-height: 1.7;
  color: var(--ink-faint);
  text-align: center;
  padding: 4px 18px 16px;
  font-weight: 300;
  margin: 0;
}

.empty {
  margin: 28px 12px;
  text-align: center;
  font-size: 13px;
  line-height: 1.7;
  color: var(--ink-faint);
  font-weight: 300;
}

.entry {
  padding: 14px 2px;
  border-bottom: 1px solid color-mix(in srgb, var(--ink) 5%, transparent);
  animation: rise 0.5s ease both;
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

.tag {
  display: inline-block;
  font-family: var(--mono);
  font-size: 9px;
  color: var(--seal);
  border: 1px solid color-mix(in srgb, var(--seal) 45%, transparent);
  border-radius: 3px;
  padding: 1px 6px;
  letter-spacing: 1px;
  margin-bottom: 7px;
}

.entry p {
  margin: 0;
  font-size: 13.5px;
  line-height: 1.85;
  color: var(--ink-dim);
  font-weight: 300;
}

.when {
  font-family: var(--mono);
  font-size: 9px;
  color: var(--ink-faint);
  margin-top: 6px;
  letter-spacing: 0.5px;
}
</style>
