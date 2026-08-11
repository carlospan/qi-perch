<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { createPetVrm, type PetVrmHandle } from "./usePetVrm";
import { startPetRoam, type PetRoamHandle } from "./usePetRoam";

const host = ref<HTMLElement | null>(null);
const status = ref("加载中…");
let pet: PetVrmHandle | null = null;
let roam: PetRoamHandle | null = null;

onMounted(async () => {
  if (!host.value) return;

  const el = host.value;
  el.addEventListener("mousedown", async (ev) => {
    if (ev.button !== 0) return;
    roam?.pause();
    try {
      await getCurrentWindow().startDragging();
    } catch {
      /* 浏览器预览时无 Tauri */
    } finally {
      // 拖完稍停再继续漫步
      window.setTimeout(() => roam?.resume(), 400);
    }
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
