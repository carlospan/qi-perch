<script setup lang="ts">
import type { QiView } from "../types";

withDefaults(
  defineProps<{
    modelValue: QiView;
    layout?: "horizontal" | "vertical";
  }>(),
  { layout: "vertical" }
);

const emit = defineEmits<{
  "update:modelValue": [v: QiView];
}>();

const tabs: { id: QiView; label: string }[] = [
  { id: "presence", label: "相处" },
  { id: "review", label: "回顾" },
  { id: "inner", label: "内在" },
  { id: "state", label: "状态" },
];
</script>

<template>
  <nav class="tabs" :class="layout" aria-label="相处方式">
    <button
      v-for="t in tabs"
      :key="t.id"
      type="button"
      :class="{ active: modelValue === t.id }"
      @click="emit('update:modelValue', t.id)"
    >
      {{ t.label }}
    </button>
  </nav>
</template>

<style scoped>
.tabs {
  display: flex;
  pointer-events: auto;
}

.tabs.horizontal {
  justify-content: center;
  gap: 22px;
}

.tabs.vertical {
  flex-direction: column;
  align-items: stretch;
  gap: 6px;
  width: 100%;
}

button {
  background: none;
  border: none;
  cursor: pointer;
  font-family: var(--serif);
  font-size: 14px;
  color: var(--ink-faint);
  letter-spacing: 2px;
  padding: 2px 4px;
  position: relative;
  transition:
    color 0.35s ease,
    background 0.35s ease;
}

.tabs.vertical button {
  text-align: left;
  padding: 11px 14px;
  border-radius: 11px;
  letter-spacing: 0.22em;
  font-size: 13px;
}

button::after {
  content: "";
  position: absolute;
  background: var(--seal);
  transition:
    width 0.35s ease,
    height 0.35s ease,
    opacity 0.35s ease;
}

.tabs.horizontal button::after {
  left: 50%;
  bottom: -4px;
  width: 0;
  height: 2px;
  border-radius: 1px;
  transform: translateX(-50%);
}

.tabs.vertical button::after {
  left: 0;
  top: 50%;
  width: 3px;
  height: 0;
  border-radius: 0 2px 2px 0;
  transform: translateY(-50%);
  opacity: 0;
}

button.active {
  color: var(--ink);
}

.tabs.vertical button.active {
  background: color-mix(in srgb, var(--ink) 7%, transparent);
  box-shadow: inset 0 1px 0 color-mix(in srgb, var(--ink) 6%, transparent);
}

button.active::after {
  opacity: 1;
}

.tabs.horizontal button.active::after {
  width: 14px;
}

.tabs.vertical button.active::after {
  height: 18px;
}

button:hover {
  color: var(--ink-dim);
}

.tabs.vertical button:hover:not(.active) {
  background: color-mix(in srgb, var(--ink) 3%, transparent);
}
</style>
