<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { QiWebSocket } from "../ws";
import { createPetVrm, type PetVrmHandle } from "./usePetVrm";
import { startPetRoam, type PetRoamHandle } from "./usePetRoam";

const host = ref<HTMLElement | null>(null);
const status = ref("加载中…");
let pet: PetVrmHandle | null = null;
let roam: PetRoamHandle | null = null;
let resumeTimer = 0;
let resumeDeadline = 0;
let roamLocked = false;
let petWs: QiWebSocket | null = null;

const DRAG_PX = 7;
const CLICK_NOTICE_MS = 2600;
const CLICK_HOLD_MS = 3000;
const SPEECH_NOTICE_MS = 1000;
const SPEECH_HOLD_MS = 1400;
const DRAG_HOLD_MS = 500;

function clearResumeTimer() {
  if (resumeTimer) {
    window.clearTimeout(resumeTimer);
    resumeTimer = 0;
  }
}

/** 暂停漫步；多次触发取最晚截止，避免说话打断点击后的安顿 */
function pauseRoamFor(ms: number) {
  roam?.pause();
  resumeDeadline = Math.max(resumeDeadline, Date.now() + ms);
  clearResumeTimer();
  const arm = () => {
    if (roamLocked) {
      resumeTimer = window.setTimeout(arm, 200);
      return;
    }
    const left = resumeDeadline - Date.now();
    if (left > 16) {
      resumeTimer = window.setTimeout(arm, left);
      return;
    }
    resumeTimer = 0;
    roam?.resume();
  };
  arm();
}

onMounted(async () => {
  if (!host.value) return;

  const el = host.value;
  let downX = 0;
  let downY = 0;
  let dragging = false;
  let press = false;

  el.addEventListener("mousedown", (ev) => {
    if (ev.button !== 0) return;
    press = true;
    dragging = false;
    downX = ev.clientX;
    downY = ev.clientY;
  });

  window.addEventListener("mousemove", async (ev) => {
    if (!press || dragging) return;
    const dx = ev.clientX - downX;
    const dy = ev.clientY - downY;
    if (dx * dx + dy * dy < DRAG_PX * DRAG_PX) return;
    dragging = true;
    roamLocked = true;
    clearResumeTimer();
    roam?.pause();
    try {
      await getCurrentWindow().startDragging();
    } catch {
      /* 浏览器预览 */
    }
  });

  window.addEventListener("mouseup", () => {
    if (!press) return;
    press = false;
    if (dragging) {
      dragging = false;
      roamLocked = false;
      pauseRoamFor(DRAG_HOLD_MS);
      return;
    }
    pet?.notice(CLICK_NOTICE_MS);
    pauseRoamFor(CLICK_HOLD_MS);
  });

  pet = createPetVrm(el);
  try {
    await pet.ready;
    status.value = "";
    roam = startPetRoam(pet);

    // 只听广播，不改 presence（聊天壳管在场）
    petWs = new QiWebSocket({ managePresence: false });
    petWs.on("speech", () => {
      pet?.notice(SPEECH_NOTICE_MS);
      pauseRoamFor(SPEECH_HOLD_MS);
    });
    petWs.connect();
  } catch (err) {
    console.error(err);
    status.value = "模型加载失败";
  }
});

onBeforeUnmount(() => {
  clearResumeTimer();
  petWs?.disconnect();
  petWs = null;
  roam?.destroy();
  roam = null;
  pet?.destroy();
  pet = null;
});
</script>

<template>
  <div id="host" ref="host" />
  <p v-if="status" id="status">{{ status }}</p>
</template>
