<script setup lang="ts">
import { computed } from "vue";
import type { CreationCard } from "../types";

const props = defineProps<{
  card: CreationCard;
}>();

/** 类型标：对齐 _infer_type 四码；推断偶发不准可接受；未知省略 */
const TYPE_LABEL: Record<string, string> = {
  note: "笔记",
  poem: "诗",
  essay: "随笔",
  description: "画面",
};

const typeLabel = computed(() => {
  const t = (props.card.creation_type || "").trim().toLowerCase();
  if (!t || t === "unknown") return "";
  return TYPE_LABEL[t] || "";
});

const seasonLabel = computed(() => (props.card.season || "").trim());
</script>

<template>
  <article class="paper" aria-label="栖递来的创作">
    <span v-if="typeLabel" class="mark">{{ typeLabel }}</span>
    <div class="body">{{ card.content }}</div>
    <footer v-if="seasonLabel" class="foot">{{ seasonLabel }}</footer>
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
  background: color-mix(in srgb, var(--ember) 55%, transparent);
}

.mark {
  display: inline-block;
  font-family: var(--mono);
  font-size: 9.5px;
  letter-spacing: 2px;
  color: var(--ember);
  margin-bottom: 8px;
}

.body {
  font-family: "Noto Serif SC", "Songti SC", "SimSun", serif;
  font-size: 13.5px;
  line-height: 1.85;
  font-weight: 400;
  white-space: pre-wrap;
  word-break: break-word;
}

.foot {
  margin-top: 10px;
  font-family: var(--mono);
  font-size: 9.5px;
  letter-spacing: 1px;
  color: var(--ink-faint);
}
</style>
