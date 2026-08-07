<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from "vue";
import { createLive2D, type Live2DController } from "../composables/useLive2D";
import type { EmotionSnapshot } from "../types";

const props = defineProps<{
  mode: string;
  emotion: EmotionSnapshot;
  speaking: boolean;
  /** 栖开始回复时递增，用于触发稀疏 07_touch_head */
  replyEpoch?: number;
  /** 入场编排：光晕稍后亮起 */
  entered?: boolean;
}>();

const host = ref<HTMLElement | null>(null);
const loadError = ref<string | null>(null);
let ctrl: Live2DController | null = null;

onMounted(async () => {
  if (!host.value) return;
  try {
    ctrl = createLive2D(host.value);
    await ctrl.ready;
    ctrl.setMode(props.mode || "awake");
    ctrl.applyEmotion(props.emotion);
    ctrl.setSpeaking(props.speaking);
  } catch (e) {
    console.error("[qi] Live2D 初始化失败", e);
    loadError.value =
      e instanceof Error ? e.message : "形象加载失败，其它界面仍可用";
    ctrl?.destroy();
    ctrl = null;
  }
});

watch(
  () => props.mode,
  (m) => ctrl?.setMode(m || "awake")
);
watch(
  () => props.emotion,
  (e) => ctrl?.applyEmotion(e),
  { deep: true }
);
watch(
  () => props.speaking,
  (s) => ctrl?.setSpeaking(s)
);
watch(
  () => props.replyEpoch,
  (n, prev) => {
    if (n != null && n > 0 && n !== prev) ctrl?.onReplyStart();
  }
);

onUnmounted(() => {
  ctrl?.destroy();
  ctrl = null;
});
</script>

<template>
  <div class="live2d-wrap" :class="{ entered, failed: !!loadError }">
    <div class="halo cool" aria-hidden="true" />
    <div class="halo warm" aria-hidden="true" />
    <div ref="host" class="live2d-host" :hidden="!!loadError" />
    <div v-if="loadError" class="placeholder" role="status">
      <span class="mark">栖</span>
      <p class="title">形象没能出现</p>
      <p class="hint">{{ loadError }}</p>
      <p class="hint soft">对话与状态栏仍可用；换机时请按文档放入 Cubism Core 与模型。</p>
    </div>
  </div>
</template>

<style scoped>
.live2d-wrap {
  position: relative;
  width: 100%;
  max-width: none;
  height: 100%;
  min-height: 340px;
  margin: 0 auto;
  display: grid;
  place-items: center;
  overflow: visible;
}

.halo {
  position: absolute;
  width: 200px;
  height: 200px;
  border-radius: 50%;
  filter: blur(8px);
  top: 12%;
  left: 50%;
  transform: translateX(-50%) scale(0.92);
  pointer-events: none;
  z-index: 0;
  opacity: 0;
  transition:
    opacity 1.6s ease 0.4s,
    transform 0.7s var(--ease-view) 0.4s;
}
.live2d-wrap.entered .halo {
  transform: translateX(-50%) scale(1);
  animation: breathe 5.5s ease-in-out 0.6s infinite;
}
.halo.cool {
  background: radial-gradient(
    circle,
    color-mix(in srgb, var(--horizon-cool) 55%, transparent),
    transparent 68%
  );
}
.live2d-wrap.entered .halo.cool {
  opacity: calc((1 - var(--warm-t)) * var(--glow-a));
}
.halo.warm {
  background: radial-gradient(
    circle,
    color-mix(in srgb, var(--horizon-warm) 60%, transparent),
    transparent 68%
  );
}
.live2d-wrap.entered .halo.warm {
  opacity: calc(var(--warm-t) * var(--glow-a));
}
.live2d-wrap.failed .halo {
  opacity: 0.35;
  animation: none;
}

@keyframes breathe {
  0%,
  100% {
    transform: translateX(-50%) scale(1);
  }
  50% {
    transform: translateX(-50%) scale(1.07);
  }
}

.live2d-host {
  position: relative;
  z-index: 1;
  width: 100%;
  height: 100%;
  overflow: visible;
}
.live2d-host :deep(canvas) {
  display: block;
  width: 100% !important;
  height: 100% !important;
}

.placeholder {
  position: relative;
  z-index: 2;
  max-width: 16rem;
  padding: 1.25rem 1rem;
  text-align: center;
  color: var(--ink-muted, var(--ink-dim));
}
.placeholder .mark {
  display: inline-grid;
  place-items: center;
  width: 2.75rem;
  height: 2.75rem;
  margin-bottom: 0.75rem;
  border-radius: 50%;
  font-family: var(--display, inherit);
  font-size: 1.25rem;
  letter-spacing: 0.08em;
  color: var(--ink);
  background: color-mix(in srgb, var(--ink) 8%, transparent);
}
.placeholder .title {
  margin: 0 0 0.4rem;
  font-size: 0.95rem;
  color: var(--ink);
  letter-spacing: 0.06em;
}
.placeholder .hint {
  margin: 0.25rem 0 0;
  font-size: 0.72rem;
  line-height: 1.55;
  word-break: break-word;
}
.placeholder .hint.soft {
  opacity: 0.75;
}
</style>
