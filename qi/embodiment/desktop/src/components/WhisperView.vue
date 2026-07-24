<script setup lang="ts">
import { onUnmounted, ref, watch } from "vue";

/**
 * 低语区。等待态文案取自灵魂书气质：在场、克制，不是「正在思考」式工具腔。
 */

const WAITING_LINES = ["……", "嗯……", "我在想。", "稍等……"] as const;

const props = defineProps<{
  text: string;
  typing?: boolean;
}>();

const emit = defineEmits<{
  speaking: [active: boolean];
}>();

const shown = ref("");
const waiting = ref(false);
let timer: number | null = null;
let waitTimer: number | null = null;
let waitIdx = 0;

function clearType() {
  if (timer != null) {
    clearInterval(timer);
    timer = null;
  }
}

function clearWait() {
  if (waitTimer != null) {
    clearInterval(waitTimer);
    waitTimer = null;
  }
}

function startWaiting() {
  waiting.value = true;
  waitIdx = Math.floor(Math.random() * WAITING_LINES.length);
  shown.value = WAITING_LINES[waitIdx];
  clearWait();
  // 极慢换一句，像念头轻轻换，不抢注意力
  waitTimer = window.setInterval(() => {
    waitIdx = (waitIdx + 1) % WAITING_LINES.length;
    shown.value = WAITING_LINES[waitIdx];
  }, 4200);
}

watch(
  () => [props.text, props.typing] as const,
  ([text, typing]) => {
    clearType();
    clearWait();
    if (typing) {
      startWaiting();
      emit("speaking", false);
      return;
    }
    waiting.value = false;
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
        clearType();
        emit("speaking", false);
      }
    }, 70);
  },
  { immediate: true }
);

onUnmounted(() => {
  clearType();
  clearWait();
  emit("speaking", false);
});
</script>

<template>
  <div class="whisper" :class="{ empty: !shown, waiting }">
    <span>{{ shown }}</span>
    <span
      v-if="waiting || (text && shown.length < text.length)"
      class="caret"
    />
  </div>
</template>

<style scoped>
.whisper {
  min-height: 52px;
  max-width: 280px;
  text-align: center;
  font-family: var(--serif);
  font-size: 16px;
  line-height: 1.75;
  font-weight: 300;
  color: var(--ink);
  text-shadow: 0 1px 12px rgba(8, 12, 20, 0.7);
  padding: 0 24px;
  margin: 0 auto 4px;
  letter-spacing: 0.3px;
}
.whisper.empty {
  opacity: 0.5;
}
.whisper.waiting {
  color: var(--ink-dim);
  opacity: 0.85;
  animation: wait-breathe 3.6s ease-in-out infinite;
}

@keyframes wait-breathe {
  0%,
  100% {
    opacity: 0.55;
  }
  50% {
    opacity: 0.92;
  }
}

.caret {
  display: inline-block;
  width: 1px;
  height: 0.95em;
  margin-left: 2px;
  vertical-align: -0.1em;
  background: var(--ink-dim);
  animation: blink 1.1s steps(1) infinite;
}
@keyframes blink {
  0%,
  49% {
    opacity: 1;
  }
  50%,
  100% {
    opacity: 0;
  }
}
</style>
