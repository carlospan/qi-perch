<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import InputBox from "./components/InputBox.vue";
import JournalView from "./components/JournalView.vue";
import PresenceVrm from "./components/PresenceVrm.vue";
import ReviewView from "./components/ReviewView.vue";
import SceneView from "./components/SceneView.vue";
import StateView from "./components/StateView.vue";
import StatusBar from "./components/StatusBar.vue";
import TalkView from "./components/TalkView.vue";
import ViewTabs from "./components/ViewTabs.vue";
import WindowControls from "./components/WindowControls.vue";
import { useQi } from "./composables/useQi";

const {
  view,
  connected,
  typing,
  season,
  mode,
  emotion,
  inStasis,
  avatar,
  replyEpoch,
  talkByDay,
  creationCards,
  exploreCards,
  journal,
  send,
  requestWake,
  connect,
  disconnect,
} = useQi();

const booted = ref(false);
const dreaming = computed(
  () => mode.value === "dreaming" || avatar.value.effect === "dream_bubbles"
);
/** 自然语言心境（后端 EmotionState.description，非数值标签） */
const moodText = computed(() => (emotion.value.description || "").trim());

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
  <div class="shell" :class="{ booted, presence: view === 'presence' }">
    <SceneView :entered="booted" :dreaming="dreaming" />
    <div class="vignette" aria-hidden="true" />
    <div class="grain" aria-hidden="true" />

    <div class="content">
      <header data-tauri-drag-region>
        <div class="brand" data-tauri-drag-region>
          <span class="seal">栖</span>
          <h1 data-tauri-drag-region>栖</h1>
        </div>
        <div class="header-right">
          <StatusBar
            :mode="mode"
            :season="season"
            :connected="connected"
            :mood="moodText"
            :replying="typing"
          />
          <WindowControls />
        </div>
      </header>

      <div class="workspace">
        <aside class="nav-rail">
          <ViewTabs v-model="view" layout="vertical" />
        </aside>

        <main class="main">
          <div class="stage">
            <!-- 相处页常驻 DOM：切走时仅隐藏，避免 VRM 每次重载 -->
            <div
              class="presence-layout"
              :class="{ 'is-hidden': view !== 'presence' }"
              :aria-hidden="view !== 'presence'"
            >
              <div class="presence-stage">
                <div class="presence-stage-vignette" aria-hidden="true" />
                <PresenceVrm
                  :active="view === 'presence'"
                  :expression="avatar.expression"
                  :typing="typing"
                  :speech-tick="replyEpoch"
                />
              </div>
              <div class="presence-chat">
                <div class="presence-chat-bg" aria-hidden="true" />
                <div class="presence-chat-vignette" aria-hidden="true" />
                <div class="presence-chat-body">
                  <TalkView
                    v-show="view === 'presence'"
                    layout="desktop"
                    :groups="talkByDay"
                    :typing="typing"
                    @send="send"
                  />
                </div>
                <footer v-show="view === 'presence'" class="composer-inline">
                  <button
                    v-if="inStasis"
                    type="button"
                    class="wake-btn"
                    :disabled="!connected"
                    @click="requestWake"
                  >
                    唤醒
                  </button>
                  <InputBox
                    v-else
                    :disabled="!connected"
                    :busy="typing"
                    @send="send"
                  />
                </footer>
              </div>
            </div>

            <Transition name="view" mode="out-in">
              <div v-if="view === 'review'" key="review" class="page">
                <ReviewView
                  :creations="creationCards"
                  :explores="exploreCards"
                />
              </div>

              <div v-else-if="view === 'inner'" key="inner" class="page">
                <JournalView :entries="journal" />
              </div>

              <div v-else-if="view === 'state'" key="state" class="page">
                <StateView :emotion="emotion" :connected="connected" />
              </div>
            </Transition>
          </div>

          <footer v-if="view !== 'presence'" class="composer-bar">
            <div class="composer-dock">
              <button
                v-if="inStasis"
                type="button"
                class="wake-btn"
                :disabled="!connected"
                @click="requestWake"
              >
                唤醒
              </button>
              <InputBox
                v-else
                :disabled="!connected"
                :busy="typing"
                @send="send"
              />
            </div>
          </footer>
        </main>
      </div>
    </div>
  </div>
</template>

<style scoped>
.shell {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 640px;
  border-radius: var(--shell-radius);
  overflow: hidden;
  isolation: isolate;
  background: var(--night);
  box-shadow:
    0 24px 64px rgba(0, 0, 0, 0.5),
    0 1px 0 rgba(255, 255, 255, 0.04) inset,
    0 0 0 1px rgba(255, 255, 255, 0.05) inset;
}

.shell.presence :deep(.scene.entered) {
  animation: none;
  opacity: 0;
  transition: opacity 0.55s var(--ease-view);
}
.shell:not(.presence) :deep(.scene.entered) {
  transition: opacity 0.55s var(--ease-view);
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
.shell.presence .vignette {
  opacity: 0.35;
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
  padding: var(--main-pad-y) var(--main-pad-x);
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  pointer-events: none;
}
.content :deep(header),
.content :deep(aside),
.content :deep(main),
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
  gap: 1rem;
  cursor: grab;
  user-select: none;
  flex-shrink: 0;
  padding-bottom: 2px;
  border-bottom: 1px solid color-mix(in srgb, var(--ink) 6%, transparent);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  min-width: 0;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.seal {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: var(--seal);
  color: var(--seal-ink);
  display: grid;
  place-items: center;
  font-size: 14px;
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
  font-size: 18px;
  font-weight: 600;
  letter-spacing: 8px;
  text-indent: 2px;
  color: var(--ink);
  opacity: 0;
  transform: translateY(6px);
}
.shell.booted h1 {
  animation: brand-in-title 0.5s var(--ease-view) 0.7s forwards;
}

@keyframes brand-in {
  to {
    opacity: 1;
    transform: translateY(0) rotate(-3deg);
  }
}

@keyframes brand-in-title {
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.workspace {
  flex: 1;
  min-height: 0;
  display: flex;
  gap: 0;
  opacity: 0;
}
.shell.booted .workspace {
  animation: brand-in-title 0.45s var(--ease-view) 0.8s forwards;
}

.nav-rail {
  flex: 0 0 var(--nav-rail-w);
  padding: 8px 10px 8px 0;
  border-right: 1px solid color-mix(in srgb, var(--ink) 6%, transparent);
  display: flex;
  flex-direction: column;
}

.main {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding-left: 18px;
}

.stage {
  position: relative;
  flex: 1;
  min-height: 0;
}

.presence-layout {
  position: absolute;
  inset: 0;
  z-index: 2;
  display: grid;
  grid-template-columns: var(--presence-vrm-w) minmax(0, 1fr);
  gap: 0;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--ink) 5%, transparent);
}

.presence-layout.is-hidden {
  visibility: hidden;
  pointer-events: none;
  z-index: 0;
}

.presence-stage {
  position: relative;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  border-right: 1px solid color-mix(in srgb, var(--ink) 6%, transparent);
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--night) 92%, transparent) 0%,
    color-mix(in srgb, var(--night) 98%, transparent) 100%
  );
}

.presence-stage-vignette {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  background:
    radial-gradient(
      90% 80% at 50% 45%,
      transparent 22%,
      rgba(5, 8, 14, 0.42) 68%,
      rgba(5, 8, 14, 0.82) 100%
    ),
    linear-gradient(
      90deg,
      rgba(5, 8, 14, 0.35) 0%,
      transparent 45%
    );
}

.presence-chat {
  position: relative;
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.presence-chat-body {
  position: relative;
  z-index: 2;
  flex: 1;
  min-height: 0;
}

.composer-inline {
  position: relative;
  z-index: 2;
  flex-shrink: 0;
  padding: 12px 14px 14px;
  border-top: 1px solid color-mix(in srgb, var(--ink) 8%, transparent);
  background: linear-gradient(
    180deg,
    transparent 0%,
    color-mix(in srgb, var(--panel-veil) 55%, transparent) 100%
  );
  backdrop-filter: blur(4px);
}

.presence-chat-bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  background: center 42% / cover no-repeat url("/qi-presence-glow.png");
  opacity: 0.58;
  transform: scale(1.03);
}

.presence-chat-vignette {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  background:
    radial-gradient(
      110% 90% at 58% 38%,
      transparent 12%,
      rgba(5, 8, 14, 0.28) 55%,
      rgba(5, 8, 14, 0.72) 100%
    ),
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--panel-veil) 18%, transparent) 0%,
      color-mix(in srgb, var(--panel-veil) 8%, transparent) 42%,
      color-mix(in srgb, var(--panel-veil) 24%, transparent) 100%
    );
}

.presence-chat :deep(.panel) {
  position: absolute;
  inset: 0;
}

.page {
  position: absolute;
  inset: 0;
  z-index: 1;
  min-height: 0;
}

.composer-bar {
  flex-shrink: 0;
  padding: 14px 0 2px;
  border-top: 1px solid color-mix(in srgb, var(--ink) 6%, transparent);
}

.composer-dock {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 14px;
  border: 1px solid color-mix(in srgb, var(--ink) 8%, transparent);
  background: color-mix(in srgb, var(--panel-veil) 72%, transparent);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  box-shadow: inset 0 1px 0 color-mix(in srgb, var(--ink) 5%, transparent);
}

.composer-dock :deep(form) {
  flex: 1;
  min-width: 0;
}

.view-enter-active,
.view-leave-active {
  transition:
    opacity 0.45s var(--ease-view),
    transform 0.45s var(--ease-view);
}
.view-enter-from,
.view-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

.wake-btn {
  width: 100%;
  max-width: 280px;
  padding: 11px 20px;
  border: 1px solid color-mix(in srgb, var(--ink-dim) 35%, transparent);
  border-radius: 10px;
  background: transparent;
  color: var(--ink);
  font-family: var(--serif, Georgia, serif);
  font-size: 0.95rem;
  letter-spacing: 0.12em;
  cursor: pointer;
}
.wake-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.wake-btn:not(:disabled):hover {
  border-color: color-mix(in srgb, var(--ember) 50%, transparent);
  color: var(--ember);
}
</style>
