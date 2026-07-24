<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import InputBox from "./components/InputBox.vue";
import JournalView from "./components/JournalView.vue";
import Live2DView from "./components/Live2DView.vue";
import SceneView from "./components/SceneView.vue";
import StatusBar from "./components/StatusBar.vue";
import TalkView from "./components/TalkView.vue";
import ViewTabs from "./components/ViewTabs.vue";
import WhisperView from "./components/WhisperView.vue";
import { useQi } from "./composables/useQi";

/* Step 5：动效收尾 + 验收 */

const {
  view,
  connected,
  typing,
  speech,
  speaking,
  replyEpoch,
  season,
  emotion,
  mode,
  avatar,
  talkByDay,
  journal,
  send,
  connect,
  disconnect,
} = useQi();

const booted = ref(false);
const dreaming = computed(
  () => mode.value === "dreaming" || avatar.value.effect === "dream_bubbles"
);

onMounted(() => {
  connect();
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      booted.value = true;
    });
  });
});
onUnmounted(() => disconnect());
</script>

<template>
  <div class="shell" :class="{ booted }">
    <SceneView :entered="booted" :dreaming="dreaming" />

    <div
      class="figure-layer"
      :class="{ dim: view !== 'still', entered: booted }"
    >
      <Live2DView
        :mode="mode"
        :emotion="emotion"
        :speaking="speaking"
        :reply-epoch="replyEpoch"
        :entered="booted"
      />
    </div>

    <div class="vignette" aria-hidden="true" />
    <div class="grain" aria-hidden="true" />

    <div class="content">
      <header data-tauri-drag-region>
        <div class="brand" data-tauri-drag-region>
          <span class="seal">栖</span>
          <h1 data-tauri-drag-region>栖</h1>
        </div>
        <StatusBar :mode="mode" :season="season" :connected="connected" />
      </header>

      <div class="stage">
        <Transition name="view" mode="out-in">
          <div v-if="view === 'still'" key="still" class="stage-still">
            <div class="stage-spacer" />
            <WhisperView
              :text="speech"
              :typing="typing"
              @speaking="speaking = $event"
            />
          </div>
          <div v-else-if="view === 'talk'" key="talk" class="overlay">
            <TalkView :groups="talkByDay" :typing="typing" />
          </div>
          <div v-else key="journal" class="overlay">
            <JournalView :entries="journal" />
          </div>
        </Transition>
      </div>

      <footer>
        <ViewTabs v-model="view" />
        <InputBox @send="send" />
      </footer>
    </div>
  </div>
</template>

<style scoped>
.shell {
  position: relative;
  width: 100%;
  max-width: 420px;
  height: 100%;
  min-height: 680px;
  margin: 0 auto;
  border-radius: 22px;
  overflow: hidden;
  isolation: isolate;
  background: var(--night);
  box-shadow:
    0 30px 80px rgba(0, 0, 0, 0.55),
    0 2px 0 rgba(255, 255, 255, 0.04) inset,
    0 0 0 1px rgba(255, 255, 255, 0.05) inset;
}

.figure-layer {
  position: absolute;
  left: 0;
  right: 0;
  top: 80px;
  bottom: 120px;
  z-index: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.5s var(--ease-view);
}
.figure-layer.entered {
  opacity: 1;
  transition-delay: 0.35s;
}
.figure-layer.dim {
  opacity: 0.35;
  transition-delay: 0s;
}

.vignette {
  position: absolute;
  inset: 0;
  z-index: 2;
  pointer-events: none;
  background: radial-gradient(
    125% 100% at 50% 58%,
    transparent 42%,
    rgba(5, 8, 14, 0.5) 70%,
    rgba(5, 8, 14, 0.88) 100%
  );
  opacity: var(--vig-a);
  transition: opacity 1.6s ease;
}

.grain {
  position: absolute;
  inset: 0;
  z-index: 3;
  pointer-events: none;
  opacity: 0.05;
  mix-blend-mode: overlay;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='120' height='120' filter='url(%23n)' opacity='0.6'/%3E%3C/svg%3E");
}

.content {
  position: relative;
  z-index: 4;
  height: 100%;
  min-height: 100%;
  padding: 18px 20px 14px;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  pointer-events: none;
}
.content :deep(header),
.content :deep(footer),
.content :deep(form),
.content :deep(input),
.content :deep(textarea),
.content :deep(button),
.content :deep(.panel) {
  pointer-events: auto;
}

header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  cursor: grab;
  user-select: none;
  flex-shrink: 0;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.seal {
  width: 22px;
  height: 22px;
  border-radius: 5px;
  background: var(--seal);
  color: var(--seal-ink);
  display: grid;
  place-items: center;
  font-size: 13px;
  font-weight: 600;
  opacity: 0;
  transform: translateY(6px) rotate(-3deg);
  box-shadow:
    0 1px 4px color-mix(in srgb, var(--seal) 40%, transparent),
    0 0 0 1px rgba(255, 255, 255, 0.06) inset;
}
.shell.booted .seal {
  animation: brand-in 0.5s var(--ease-view) 0.55s forwards;
}

h1 {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  letter-spacing: 6px;
  text-indent: 2px;
  color: var(--ink);
  opacity: 0;
  transform: translateY(6px);
}
.shell.booted h1 {
  animation: brand-in 0.5s var(--ease-view) 0.7s forwards;
}

@keyframes brand-in {
  to {
    opacity: 1;
    transform: translateY(0) rotate(-3deg);
  }
}
.shell.booted h1 {
  animation-name: brand-in-title;
}
@keyframes brand-in-title {
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.stage {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
}

.stage-still {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
}

.stage-spacer {
  flex: 1;
}

.overlay {
  position: absolute;
  inset: 0;
}

.view-enter-active,
.view-leave-active {
  transition:
    opacity 0.5s var(--ease-view),
    transform 0.5s var(--ease-view);
}
.view-enter-from,
.view-leave-to {
  opacity: 0;
  transform: translateY(10px);
}

footer {
  flex-shrink: 0;
  padding-top: 4px;
  opacity: 0;
}
.shell.booted footer {
  animation: brand-in-title 0.45s var(--ease-view) 0.85s forwards;
}
</style>
