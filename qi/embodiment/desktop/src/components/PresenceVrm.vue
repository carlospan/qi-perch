<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { createPetVrm, type PetVrmHandle } from "../pet/usePetVrm";

const props = defineProps<{
  /** 相处页是否在前台；false 时暂停渲染但保持模型常驻 */
  active?: boolean;
  expression?: string;
  typing?: boolean;
  /** 每次 speech / typing 递增，驱动轻 notice */
  speechTick?: number;
}>();

const host = ref<HTMLElement | null>(null);
const status = ref("");

let pet: PetVrmHandle | null = null;

const CLICK_NOTICE_MS = 2600;
const SPEECH_NOTICE_MS = 1000;
const TYPING_NOTICE_MS = 700;

onMounted(async () => {
  if (!host.value) return;
  const el = host.value;

  el.addEventListener("click", () => {
    pet?.notice(CLICK_NOTICE_MS);
  });

  pet = createPetVrm(el, { framing: "presence", loadWalk: false });
  try {
    await pet.ready;
    status.value = "";
    if (props.expression) pet.setExpression(props.expression);
    pet.setActive(props.active !== false);
  } catch (err) {
    console.error(err);
    status.value = "形象加载失败";
  }
});

watch(
  () => props.active,
  (on) => {
    pet?.setActive(on !== false);
  }
);

watch(
  () => props.expression,
  (expr) => {
    if (expr) pet?.setExpression(expr);
  }
);

watch(
  () => props.speechTick,
  (tick, prev) => {
    if (tick && tick !== prev) {
      pet?.notice(SPEECH_NOTICE_MS);
    }
  }
);

watch(
  () => props.typing,
  (on, was) => {
    if (on && !was) {
      pet?.notice(TYPING_NOTICE_MS);
    }
  }
);

onBeforeUnmount(() => {
  pet?.destroy();
  pet = null;
});
</script>

<template>
  <div class="presence-vrm">
    <div ref="host" class="vrm-host" />
    <p v-if="status" class="vrm-status">{{ status }}</p>
  </div>
</template>

<style scoped>
.presence-vrm {
  position: absolute;
  inset: 0;
  z-index: 2;
}

.vrm-host {
  width: 100%;
  height: 100%;
  cursor: pointer;
}

.vrm-host :deep(canvas) {
  display: block;
}

.vrm-status {
  position: absolute;
  left: 50%;
  bottom: 10%;
  transform: translateX(-50%);
  margin: 0;
  font-family: var(--mono);
  font-size: 11px;
  color: var(--ink-faint);
  pointer-events: none;
}
</style>
