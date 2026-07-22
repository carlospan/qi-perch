<script setup lang="ts">
defineProps<{
  mode: string;
  season: string;
  connected: boolean;
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
};
</script>

<template>
  <div class="status">
    <span class="dot" :class="{ on: connected }" />
    <span>{{ modeLabel[mode] || mode || "……" }}</span>
    <span class="sep">·</span>
    <span>{{ seasonLabel[season] || season || "春" }}</span>
  </div>
</template>

<style scoped>
.status {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-family: var(--mono);
  font-size: 0.72rem;
  color: var(--ink-dim);
  letter-spacing: 0.04em;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--ink-faint);
}

.dot.on {
  background: var(--ember);
  opacity: 0.85;
  box-shadow: 0 0 6px color-mix(in srgb, var(--ember) 55%, transparent);
}

.sep {
  opacity: 0.5;
}
</style>
