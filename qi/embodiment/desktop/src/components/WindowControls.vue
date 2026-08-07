<script setup lang="ts">
import { onMounted, ref } from "vue";

const visible = ref(false);

onMounted(() => {
  // 仅桌面壳显示；纯浏览器预览不渲染窗控
  visible.value =
    typeof window !== "undefined" &&
    ("__TAURI_INTERNALS__" in window || "__TAURI__" in window);
});

async function minimize() {
  try {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    await getCurrentWindow().minimize();
  } catch (e) {
    console.warn("[qi] 最小化失败", e);
  }
}

async function closeWin() {
  try {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    await getCurrentWindow().close();
  } catch (e) {
    console.warn("[qi] 关闭窗口失败", e);
  }
}
</script>

<template>
  <div v-if="visible" class="win-ctrls" data-tauri-drag-region="false">
    <button type="button" class="ctrl" aria-label="最小化" @click="minimize">
      −
    </button>
    <button type="button" class="ctrl close" aria-label="关闭" @click="closeWin">
      ×
    </button>
  </div>
</template>

<style scoped>
.win-ctrls {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
  pointer-events: auto;
  -webkit-app-region: no-drag;
}

.ctrl {
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 8px;
  padding: 0;
  background: color-mix(in srgb, var(--ink) 6%, transparent);
  color: var(--ink-muted, var(--ink));
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
  display: grid;
  place-items: center;
  transition: background 0.2s ease, color 0.2s ease;
}

.ctrl:hover {
  background: color-mix(in srgb, var(--ink) 12%, transparent);
}

.ctrl.close:hover {
  background: color-mix(in srgb, #c45c5c 55%, transparent);
  color: #fff;
}
</style>
