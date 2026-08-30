<script setup lang="ts">
import { computed } from "vue";
import type { EmotionSnapshot } from "../types";
import {
  offlineStatusCopy,
  type OfflineKind,
} from "../connectionStatus";

const props = defineProps<{
  emotion: EmotionSnapshot;
  connected: boolean;
  offlineKind?: OfflineKind | null;
}>();

const offlineNote = computed(() => {
  if (props.connected) return "";
  const c = offlineStatusCopy(props.offlineKind ?? "never");
  return `${c.title} · ${c.next}`;
});

type DimRow = {
  key: string;
  label: string;
  hint: string;
  value: number | undefined;
  bar: number;
  gloss: string;
};

function glossEnergy(v: number | undefined): string {
  if (v == null || Number.isNaN(v)) return "尚无";
  if (v < 0.3) return "有些疲惫";
  if (v > 0.7) return "精力充沛";
  if (v >= 0.35 && v <= 0.55) return "精力一般";
  return "平常";
}

function glossValence(v: number | undefined): string {
  if (v == null || Number.isNaN(v)) return "尚无";
  if (v > 0.3) return "心情不错";
  if (v < -0.3) return "有些低落";
  if (v >= -0.15 && v <= 0.15) return "有点安静";
  return "平常";
}

function glossArousal(v: number | undefined): string {
  if (v == null || Number.isNaN(v)) return "尚无";
  if (v > 0.7) return "心里有点躁";
  if (v < 0.25) return "很平静";
  return "平常";
}

function glossSecurity(v: number | undefined): string {
  if (v == null || Number.isNaN(v)) return "尚无";
  if (v < 0.4) return "有点不安";
  if (v > 0.7) return "感到安稳";
  return "平常";
}

function glossCuriosity(v: number | undefined): string {
  if (v == null || Number.isNaN(v)) return "尚无";
  if (v > 0.7) return "有点好奇";
  if (v < 0.35) return "不太想探";
  return "平常";
}

function glossAttachment(v: number | undefined): string {
  if (v == null || Number.isNaN(v)) return "尚无";
  if (v > 0.6) return "有点想你";
  if (v < 0.35) return "有点疏";
  return "平常";
}

function fmt(v: number | undefined, valence = false): string {
  if (v == null || Number.isNaN(v)) return "—";
  const n = valence ? v : Math.min(1, Math.max(0, v));
  return n.toFixed(2);
}

const rows = computed<DimRow[]>(() => {
  const e = props.emotion;
  const valence = e.valence;
  const valenceBar =
    valence == null || Number.isNaN(valence)
      ? 0.5
      : Math.min(1, Math.max(0, (valence + 1) / 2));

  return [
    {
      key: "energy",
      label: "精力",
      hint: "energy",
      value: e.energy,
      bar: e.energy ?? 0,
      gloss: glossEnergy(e.energy),
    },
    {
      key: "valence",
      label: "心境",
      hint: "valence",
      value: e.valence,
      bar: valenceBar,
      gloss: glossValence(e.valence),
    },
    {
      key: "arousal",
      label: "激活",
      hint: "arousal",
      value: e.arousal,
      bar: e.arousal ?? 0,
      gloss: glossArousal(e.arousal),
    },
    {
      key: "security",
      label: "安全感",
      hint: "security",
      value: e.security,
      bar: e.security ?? 0,
      gloss: glossSecurity(e.security),
    },
    {
      key: "curiosity",
      label: "好奇",
      hint: "curiosity",
      value: e.curiosity,
      bar: e.curiosity ?? 0,
      gloss: glossCuriosity(e.curiosity),
    },
    {
      key: "attachment",
      label: "依恋",
      hint: "attachment",
      value: e.attachment,
      bar: e.attachment ?? 0,
      gloss: glossAttachment(e.attachment),
    },
  ];
});

const summary = computed(() => (props.emotion.description || "").trim());
</script>

<template>
  <div class="desk-page state">
    <div class="desk-main">
      <header class="page-hero">
        <div class="page-hero-row">
          <h2>状态</h2>
        </div>
        <p class="page-hero-sub">
          栖此刻的六维心境。上面是她的话，下面是结构里的量。
        </p>
        <p v-if="!connected" class="status-note empty">{{ offlineNote }}</p>
        <p v-else-if="summary" class="status-note summary">{{ summary }}</p>
        <p v-else class="status-note empty">尚无心境描述，等下一拍状态。</p>
      </header>

      <div class="desk-scroll">
        <div class="dims" role="list">
          <article v-for="r in rows" :key="r.key" class="dim" role="listitem">
            <div class="dim-top">
              <div class="names">
                <span class="label">{{ r.label }}</span>
                <span class="hint">{{ r.hint }}</span>
              </div>
              <span class="num" :title="r.hint">{{
                fmt(r.value, r.key === "valence")
              }}</span>
            </div>
            <div class="bar" aria-hidden="true">
              <i :style="{ width: `${Math.round(r.bar * 100)}%` }" />
            </div>
            <p class="gloss">{{ r.gloss }}</p>
          </article>
        </div>
      </div>
    </div>

    <aside class="desk-aside" aria-hidden="true">
      <div class="desk-aside-bg" />
      <div class="desk-aside-veil" />
      <div class="desk-aside-copy">
        <p class="desk-aside-eyebrow">MOOD</p>
        <p class="desk-aside-quote">
          {{ summary || "她还没说清自己，但数值已经在轻轻呼吸。" }}
        </p>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.status-note {
  margin: 16px 0 0;
  max-width: 48ch;
  font-size: 15px;
  line-height: 1.75;
  font-weight: 300;
  letter-spacing: 0.03em;
}

.summary {
  color: color-mix(in srgb, var(--ink) 90%, transparent);
}

.empty {
  color: var(--ink-faint);
}

.dims {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px 16px;
  padding-bottom: 8px;
}

@container desk-main (min-width: 680px) {
  .dims {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

.dim {
  padding: 18px 18px 16px;
  border-radius: 14px;
  background: color-mix(in srgb, var(--ink) 4%, transparent);
  border: 1px solid color-mix(in srgb, var(--ink) 8%, transparent);
  box-shadow: inset 0 1px 0 color-mix(in srgb, var(--ink) 5%, transparent);
}

.dim-top {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
}

.names {
  display: flex;
  align-items: baseline;
  gap: 0.45rem;
  min-width: 0;
}

.label {
  font-size: 0.95rem;
  letter-spacing: 0.14em;
}

.hint {
  font-family: var(--mono);
  font-size: 0.58rem;
  letter-spacing: 0.06em;
  color: var(--ink-faint);
}

.num {
  font-family: var(--mono);
  font-size: 0.76rem;
  color: var(--ember);
  letter-spacing: 0.04em;
  flex-shrink: 0;
}

.bar {
  margin-top: 0.55rem;
  height: 4px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--ink) 8%, transparent);
  overflow: hidden;
}

.bar i {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(
    90deg,
    color-mix(in srgb, var(--mist) 70%, transparent),
    color-mix(in srgb, var(--ember) 75%, transparent)
  );
  transition: width 1.2s ease;
}

.gloss {
  margin: 0.5rem 0 0;
  font-size: 0.8rem;
  color: var(--ink-dim);
  font-weight: 300;
  letter-spacing: 0.02em;
}

@media (max-width: 1100px) {
  .dims {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
