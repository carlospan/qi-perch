<script setup lang="ts">
import { onUnmounted, ref, watch } from "vue";

const props = defineProps<{
  text: string;
  typing?: boolean;
}>();

const shown = ref("");
let timer: number | null = null;

watch(
  () => [props.text, props.typing] as const,
  ([text, typing]) => {
    if (timer != null) {
      clearInterval(timer);
      timer = null;
    }
    if (typing) {
      shown.value = "……";
      return;
    }
    shown.value = "";
    if (!text) return;
    let i = 0;
    timer = window.setInterval(() => {
      i += 1;
      shown.value = text.slice(0, i);
      if (i >= text.length && timer != null) {
        clearInterval(timer);
        timer = null;
      }
    }, 28);
  },
  { immediate: true }
);

onUnmounted(() => {
  if (timer != null) clearInterval(timer);
});
</script>

<template>
  <div class="bubble" :class="{ empty: !shown }">
    <p>{{ shown || " " }}</p>
  </div>
</template>

<style scoped>
.bubble {
  min-height: 3.2rem;
  padding: 0.65rem 0.85rem;
  border-radius: 14px 14px 14px 4px;
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: var(--ink);
  font-size: 0.92rem;
  line-height: 1.55;
  backdrop-filter: blur(6px);
}

.bubble.empty {
  opacity: 0.45;
}

p {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
