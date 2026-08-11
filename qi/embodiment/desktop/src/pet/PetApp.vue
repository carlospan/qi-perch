<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { createPetVrm, type PetVrmHandle } from "./usePetVrm";
import { startPetRoam, type PetRoamHandle } from "./usePetRoam";

const host = ref<HTMLElement | null>(null);
const status = ref("加载中…");
let pet: PetVrmHandle | null = null;
let roam: PetRoamHandle | null = null;
let resumeTimer = 0;

const DRAG_PX = 7;

onMounted(async () => {
  if (!host.value) return;

  const el = host.value;
  let downX = 0;
  let downY = 0;
  let dragging = false;
  let press = false;

  const clearResumeTimer = () => {
    if (resumeTimer) {
      window.clearTimeout(resumeTimer);
      resumeTimer = 0;
    }
  };

  const scheduleResume = (ms: number) => {
    clearResumeTimer();
    resumeTimer = window.setTimeout(() => {
      resumeTimer = 0;
      roam?.resume();
    }, ms);
  };

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
      scheduleResume(500);
      return;
    }
    // 单击：看你一眼，暂停漫步一会儿
    clearResumeTimer();
    roam?.pause();
    pet?.notice(2600);
    scheduleResume(3000);
  });

  pet = createPetVrm(el);
  try {
    await pet.ready;
    status.value = "";
    roam = startPetRoam(pet);
  } catch (err) {
    console.error(err);
    status.value = "模型加载失败";
  }
});

onBeforeUnmount(() => {
  if (resumeTimer) window.clearTimeout(resumeTimer);
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
