<script setup lang="ts">
import type { QiView } from "../types";

defineProps<{
  modelValue: QiView;
}>();

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
  <nav class="tabs" aria-label="相处方式">
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
  justify-content: center;
  gap: 22px;
  margin-bottom: 12px;
  pointer-events: auto;
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
  transition: color 0.35s ease;
}

button::after {
  content: "";
  position: absolute;
  left: 50%;
  bottom: -4px;
  width: 0;
  height: 2px;
  border-radius: 1px;
  background: var(--seal);
  transform: translateX(-50%);
  transition: width 0.35s ease;
}

button.active {
  color: var(--ink);
}

button.active::after {
  width: 14px;
}

button:hover {
  color: var(--ink-dim);
}
</style>
