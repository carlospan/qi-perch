<script setup lang="ts">
import { computed } from "vue";
import type { AssistConfirmCard } from "../types";

const props = defineProps<{
  card: AssistConfirmCard;
}>();

defineEmits<{
  confirm: [];
  cancel: [];
}>();

const fileName = computed(() => {
  const parts = props.card.target_path.split(/[\\/]/);
  return parts[parts.length - 1] || props.card.target_path;
});

const mark = computed(() => props.card.confirm_mark || (props.card.kind === "open" ? "开？" : "看？"));
const confirmLabel = computed(
  () => props.card.confirm_label || (props.card.kind === "open" ? "开吧" : "看吧"),
);
</script>

<template>
  <article class="paper assist-confirm" :aria-label="mark">
    <span class="mark">{{ mark }}</span>
    <div class="filename">{{ fileName }}</div>
    <p class="summary">{{ card.summary }}</p>
    <div class="actions">
      <button type="button" class="confirm" @click="$emit('confirm')">
        {{ confirmLabel }}
      </button>
      <button type="button" class="cancel" @click="$emit('cancel')">
        不用
      </button>
    </div>
  </article>
</template>

<style scoped>
.paper {
  position: relative;
  padding: 12px 14px 10px;
  background: var(--talk-qi-bg);
  border: 1px solid var(--talk-qi-bd);
  border-radius: 4px 14px 14px 14px;
  color: var(--ink);
}

.paper::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  width: 3px;
  height: 100%;
  border-radius: 4px 0 0 4px;
  background: color-mix(in srgb, var(--ember) 45%, transparent);
}

.mark {
  display: inline-block;
  font-family: var(--mono);
  font-size: 9.5px;
  letter-spacing: 2px;
  color: var(--ember);
  margin-bottom: 8px;
}

.filename {
  font-family: var(--mono);
  font-size: 12px;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
  word-break: break-all;
}

.summary {
  margin: 0 0 12px;
  font-family: "Noto Serif SC", "Songti SC", "SimSun", serif;
  font-size: 13px;
  line-height: 1.75;
  color: var(--ink);
}

.actions {
  display: flex;
  gap: 10px;
}

.actions button {
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 1px;
  padding: 5px 12px;
  border-radius: 4px;
  border: 1px solid var(--talk-qi-bd);
  background: color-mix(in srgb, var(--talk-qi-bg) 80%, white);
  color: var(--ink);
  cursor: pointer;
}

.actions button.confirm {
  border-color: color-mix(in srgb, var(--ember) 40%, var(--talk-qi-bd));
  color: var(--ember);
}

.actions button:hover {
  filter: brightness(0.98);
}
</style>
