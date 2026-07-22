<script setup lang="ts">
import { onUnmounted, ref, watch } from "vue";

const props = defineProps<{
  text: string;
  typing?: boolean;
}>();

const emit = defineEmits<{
  speaking: [active: boolean];
}>();

const shown = ref("");
let timer: number | null = null;

function clear() {
  if (timer != null) {
    clearInterval(timer);
    timer = null;
  }
}

watch(
  () => [props.text, props.typing] as const,
  ([text, typing]) => {
    clear();
    if (typing) {
      shown.value = "……";
      emit("speaking", false);
      return;
    }
    shown.value = "";
    if (!text) {
      emit("speaking", false);
      return;
    }
    emit("speaking", true);
    let i = 0;
    timer = window.setInterval(() => {
      i += 1;
      shown.value = text.slice(0, i);
      if (i >= text.length) {
        clear();
        emit("speaking", false);
      }
    }, 70);
  },
  { immediate: true }
);

onUnmounted(() => {
  clear();
  emit("speaking", false);
});
</script>

<template>
  <div class="whisper" :class="{ empty: !shown }">
    <span>{{ shown }}</span>
    <span v-if="typing || (text && shown.length < text.length)" class="caret" />
  </div>
</template>

<style scoped>
.whisper {
  min-height: 52px;
  max-width: 280px;
  text-align: center;
  font-family: var(--serif);
  font-size: 15px;
  line-height: 1.8;
  font-weight: 400;
  color: var(--ink);
  text-shadow: 0 1px 12px rgba(8, 12, 20, 0.7);
  padding: 0 24px;
  margin: 0 auto 4px;
  letter-spacing: 0.3px;
}
.whisper.empty {
  opacity: 0.5;
}
.caret {
  display: inline-block;
  width: 1px;
  height: 14px;
  vertical-align: -2px;
  background: var(--ink-dim);
  margin-left: 2px;
  animation: pulse 1s steps(1) infinite;
}
@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.2;
  }
}
</style>
