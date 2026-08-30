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
  openSettings: [];
  openGuide: [];
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
    <div class="tab-list">
      <button
        v-for="t in tabs"
        :key="t.id"
        type="button"
        :class="{ active: modelValue === t.id }"
        @click="emit('update:modelValue', t.id)"
      >
        {{ t.label }}
      </button>
    </div>
    <div v-if="layout === 'vertical'" class="rail-footer">
      <button
        type="button"
        class="guide"
        aria-label="领养指引"
        title="领养指引"
        @click="emit('openGuide')"
      >
        指引
      </button>
      <button
        type="button"
        class="gear"
        aria-label="设置"
        title="设置"
        @click="emit('openSettings')"
      >
        <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
          <path
            fill="currentColor"
            d="M19.14 12.94c.04-.31.06-.63.06-.94s-.02-.63-.06-.94l2.03-1.58a.5.5 0 00.12-.64l-1.92-3.32a.5.5 0 00-.6-.22l-2.39.96a7.1 7.1 0 00-1.63-.94l-.36-2.54a.5.5 0 00-.49-.42h-3.84a.5.5 0 00-.49.42l-.36 2.54c-.59.24-1.13.55-1.63.94l-2.39-.96a.5.5 0 00-.6.22L2.77 8.84a.5.5 0 00.12.64l2.03 1.58c-.04.31-.06.63-.06.94s.02.63.06.94L2.89 14.5a.5.5 0 00-.12.64l1.92 3.32c.13.22.4.31.64.22l2.39-.96c.5.39 1.04.71 1.63.94l.36 2.54c.05.24.25.42.49.42h3.84c.24 0 .44-.18.49-.42l.36-2.54c.59-.24 1.13-.55 1.63-.94l2.39.96c.24.09.51 0 .64-.22l1.92-3.32a.5.5 0 00-.12-.64l-2.03-1.58zM12 15.5A3.5 3.5 0 1112 8a3.5 3.5 0 010 7.5z"
          />
        </svg>
      </button>
    </div>
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
  height: 100%;
  min-height: 0;
}

.tab-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
  min-height: 0;
}

.tabs.horizontal .tab-list {
  flex-direction: row;
  gap: 22px;
  flex: 0;
}

.rail-footer {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 4px;
  width: 100%;
}

.guide {
  align-self: stretch;
  text-align: left;
  padding: 8px 14px;
  border-radius: 11px;
  border: none;
  background: none;
  cursor: pointer;
  font-family: var(--serif);
  font-size: 12px;
  letter-spacing: 0.18em;
  color: var(--ink-faint);
  transition:
    color 0.25s ease,
    background 0.25s ease;
}

.guide:hover {
  color: var(--ink-dim);
  background: color-mix(in srgb, var(--ink) 6%, transparent);
}

.gear {
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 11px;
  border: none;
  background: none;
  color: var(--ink-faint);
  cursor: pointer;
  transition:
    color 0.25s ease,
    background 0.25s ease;
}

.gear:hover {
  color: var(--ink-dim);
  background: color-mix(in srgb, var(--ink) 6%, transparent);
}

.tab-list button {
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

.tabs.vertical .tab-list button {
  text-align: left;
  padding: 11px 14px;
  border-radius: 11px;
  letter-spacing: 0.22em;
  font-size: 13px;
}

.tab-list button::after {
  content: "";
  position: absolute;
  background: var(--seal);
  transition:
    width 0.35s ease,
    height 0.35s ease,
    opacity 0.35s ease;
}

.tabs.horizontal .tab-list button::after {
  left: 50%;
  bottom: -4px;
  width: 0;
  height: 2px;
  border-radius: 1px;
  transform: translateX(-50%);
}

.tabs.vertical .tab-list button::after {
  left: 0;
  top: 50%;
  width: 3px;
  height: 0;
  border-radius: 0 2px 2px 0;
  transform: translateY(-50%);
  opacity: 0;
}

.tab-list button.active {
  color: var(--ink);
}

.tabs.vertical .tab-list button.active {
  background: color-mix(in srgb, var(--ink) 7%, transparent);
  box-shadow: inset 0 1px 0 color-mix(in srgb, var(--ink) 6%, transparent);
}

.tab-list button.active::after {
  opacity: 1;
}

.tabs.horizontal .tab-list button.active::after {
  width: 14px;
}

.tabs.vertical .tab-list button.active::after {
  height: 18px;
}

.tab-list button:hover {
  color: var(--ink-dim);
}

.tabs.vertical .tab-list button:hover:not(.active) {
  background: color-mix(in srgb, var(--ink) 3%, transparent);
}
</style>
