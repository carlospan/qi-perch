<script setup lang="ts">
defineProps<{
  mode: string;
  season: string;
  connected: boolean;
  /** 自然语言情绪描述，如「有点安静，感到安稳」 */
  mood?: string;
}>();

const seasonLabel: Record<string, string> = {
  spring: "春",
  summer: "夏",
  autumn: "秋",
  winter: "冬",
};

const modeLabel: Record<string, string> = {
  awake: "醒着",
  ambient: "静静待着",
  solitary: "自己待着",
  dreaming: "在梦里",
  interacting: "在听你",
  stasis: "已封存休息",
};
</script>

<template>
  <div class="status">
    <div class="row">
      <span class="dot" :class="{ on: connected }" />
      <span v-if="!connected" class="offline">未连上</span>
      <template v-else>
        <span>{{ modeLabel[mode] || mode || "……" }}</span>
        <span class="sep">·</span>
        <span>{{ seasonLabel[season] || season || "春" }}</span>
      </template>
    </div>
    <p
      v-if="connected && mood"
      class="mood"
      :title="mood"
    >
      {{ mood }}
    </p>
  </div>
</template>

<style scoped>
.status {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.2rem;
  max-width: 11.5rem;
  font-family: var(--mono);
  font-size: 0.72rem;
  color: var(--ink-dim);
  letter-spacing: 0.04em;
}

.row {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--ink-faint);
  flex-shrink: 0;
}

.dot.on {
  background: var(--ember);
  opacity: 0.85;
  box-shadow: 0 0 6px color-mix(in srgb, var(--ember) 55%, transparent);
}

.sep {
  opacity: 0.5;
}

.offline {
  color: color-mix(in srgb, var(--ink-dim) 80%, #c45c5c);
  letter-spacing: 0.06em;
}

.mood {
  margin: 0;
  max-width: 100%;
  font-family: var(--serif);
  font-size: 0.68rem;
  font-weight: 300;
  line-height: 1.35;
  letter-spacing: 0.02em;
  color: var(--ink-dim);
  text-align: right;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  opacity: 0.92;
}
</style>
