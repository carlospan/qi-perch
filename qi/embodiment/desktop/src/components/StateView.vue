<script setup lang="ts">
import { computed } from "vue";
import type { EmotionSnapshot } from "../types";

const props = defineProps<{
  emotion: EmotionSnapshot;
  connected: boolean;
}>();

type DimRow = {
  key: string;
  label: string;
  hint: string;
  value: number | undefined;
  /** 展示用 0~1（valence 从 -1~1 映到 0~1） */
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
  <div class="panel">
    <header class="hero">
      <h2>状态</h2>
      <p class="hero-sub">
        栖此刻的六维心境。上面是她的话，下面是结构里的量。
      </p>
      <p v-if="!connected" class="empty">未连上，还读不到她。</p>
      <p v-else-if="summary" class="summary">{{ summary }}</p>
      <p v-else class="empty">尚无心境描述，等下一拍状态。</p>
    </header>

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
</template>

<style scoped>
.panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: color-mix(in srgb, var(--panel-veil) 72%, transparent);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 16px;
  overflow: hidden;
}

.hero {
  padding: 1rem 1.05rem 0.75rem;
  flex-shrink: 0;
}

.hero h2 {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 400;
  letter-spacing: 0.2em;
}

.hero-sub {
  margin: 0.4rem 0 0;
  font-size: 0.78rem;
  line-height: 1.5;
  color: var(--ink-dim);
  font-weight: 300;
}

.summary {
  margin: 0.75rem 0 0;
  font-size: 0.92rem;
  line-height: 1.55;
  font-weight: 300;
  color: var(--ink);
  letter-spacing: 0.02em;
}

.empty {
  margin: 0.75rem 0 0;
  font-size: 0.82rem;
  color: var(--ink-faint);
  font-weight: 300;
}

.dims {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0.25rem 1.05rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.dim {
  padding-top: 0.65rem;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
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
  font-size: 0.9rem;
  letter-spacing: 0.12em;
}

.hint {
  font-family: var(--mono);
  font-size: 0.58rem;
  letter-spacing: 0.06em;
  color: var(--ink-faint);
}

.num {
  font-family: var(--mono);
  font-size: 0.72rem;
  color: var(--ember);
  letter-spacing: 0.04em;
  flex-shrink: 0;
}

.bar {
  margin-top: 0.4rem;
  height: 3px;
  border-radius: 2px;
  background: rgba(255, 255, 255, 0.06);
  overflow: hidden;
}

.bar i {
  display: block;
  height: 100%;
  border-radius: 2px;
  background: color-mix(in srgb, var(--ember) 55%, var(--mist));
  transition: width 1.2s ease;
}

.gloss {
  margin: 0.35rem 0 0;
  font-size: 0.78rem;
  color: var(--ink-dim);
  font-weight: 300;
  letter-spacing: 0.02em;
}
</style>
