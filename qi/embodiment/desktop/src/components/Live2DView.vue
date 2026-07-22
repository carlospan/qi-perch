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
  <div class="live2d-wrap" :class="{ entered }">
    <div class="halo cool" aria-hidden="true" />
    <div class="halo warm" aria-hidden="true" />
    <div ref="host" class="live2d-host" />
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
</style>
