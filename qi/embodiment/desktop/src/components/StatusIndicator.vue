<script setup lang="ts">
defineProps<{
  mode: string;
  season: string;
  connected: boolean;
  description: string;
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
    <span v-if="description" class="desc">{{ description }}</span>
  </div>
</template>

<style scoped>
.status {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.75rem;
  color: var(--ink-dim);
  letter-spacing: 0.02em;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #6a7a8a;
}

.dot.on {
  background: var(--accent);
  box-shadow: 0 0 8px var(--glow);
}

.sep {
  opacity: 0.5;
}

.desc {
  margin-left: 0.25rem;
  opacity: 0.75;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 10rem;
}
</style>
