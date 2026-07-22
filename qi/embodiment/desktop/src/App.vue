<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import AvatarView from "./components/AvatarView.vue";
import ChatBubble from "./components/ChatBubble.vue";
import InputBox from "./components/InputBox.vue";
import StatusIndicator from "./components/StatusIndicator.vue";
import type { AvatarState, EmotionSnapshot, SpeechPayload } from "./types";
import { qiWs } from "./ws";

const connected = ref(false);
const typing = ref(false);
const speech = ref("");
const season = ref("spring");
const emotion = ref<EmotionSnapshot>({ mode: "awake", description: "" });
const avatar = ref<AvatarState>({
  posture: "idle",
  expression: "neutral",
  effect: "none",
});

function playAudio(data: string, mime = "audio/mpeg") {
  const audio = new Audio(`data:${mime};base64,${data}`);
  void audio.play().catch(() => {});
}

function onSend(text: string) {
  typing.value = true;
  speech.value = "";
  qiWs.sendUserMessage(text);
}

function onVis() {
  qiWs.setPresence(document.visibilityState === "visible");
}

onMounted(() => {
  qiWs.on("open", () => {
    connected.value = true;
  });
  qiWs.on("close", () => {
    connected.value = false;
  });
  qiWs.on("typing", () => {
    typing.value = true;
  });
  qiWs.on("speech", (payload: SpeechPayload) => {
    typing.value = false;
    speech.value = payload.text;
  });
  qiWs.on(
    "state",
    (payload: { avatar_state: AvatarState; season?: string; mode?: string }) => {
      avatar.value = payload.avatar_state;
      if (payload.season) season.value = payload.season;
      if (payload.mode) {
        emotion.value = { ...emotion.value, mode: payload.mode };
      }
    }
  );
  qiWs.on("emotion_update", (payload: EmotionSnapshot) => {
    emotion.value = payload;
  });
  qiWs.on("audio", (payload: { data: string; mime?: string }) => {
    playAudio(payload.data, payload.mime);
  });

  document.addEventListener("visibilitychange", onVis);
  qiWs.connect();
});

onUnmounted(() => {
  document.removeEventListener("visibilitychange", onVis);
  qiWs.disconnect();
});
</script>

<template>
  <div class="shell">
    <header data-tauri-drag-region>
      <h1 data-tauri-drag-region>栖</h1>
      <StatusIndicator
        :mode="emotion.mode || avatar.posture"
        :season="season"
        :connected="connected"
        :description="emotion.description || ''"
      />
    </header>

    <AvatarView :state="avatar" />

    <ChatBubble :text="speech" :typing="typing" />
    <InputBox @send="onSend" />
  </div>
</template>

<style scoped>
.shell {
  max-width: 360px;
  margin: 0 auto;
  min-height: 100%;
  padding: 1.1rem 1rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
  background: radial-gradient(
    ellipse at 30% 20%,
    #2a3a4f 0%,
    var(--bg-deep) 55%,
    #121820 100%
  );
  border-radius: 18px;
  overflow: hidden;
}

header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
  cursor: grab;
  user-select: none;
}

h1 {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 500;
  letter-spacing: 0.28em;
  color: var(--ink);
}
</style>
