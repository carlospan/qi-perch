<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";

const visible = ref(false);
/** 窗口是否已最大化（系统窗控「方框」语义，非独占全屏） */
const expanded = ref(false);

let unlisten: (() => void) | null = null;
let resizeSyncTimer = 0;
let settleTimer = 0;
let toggling = false;

function syncExpandedClass(on: boolean) {
  document.documentElement.classList.toggle("qi-maximized", on);
}

function beginResizeUi() {
  document.documentElement.classList.add("qi-resizing");
  window.dispatchEvent(new Event("qi-window-resizing"));
}

function scheduleResizeEnd(extraMs = 0) {
  window.clearTimeout(settleTimer);
  settleTimer = window.setTimeout(() => {
    document.documentElement.classList.remove("qi-resizing");
    toggling = false;
    void readExpandedState();
    window.dispatchEvent(new Event("qi-layout-settled"));
  }, 72 + extraMs);
}

function applyExpandedState(on: boolean) {
  if (expanded.value === on) {
    syncExpandedClass(on);
    return;
  }
  expanded.value = on;
  syncExpandedClass(on);
}

async function readExpandedState() {
  try {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    applyExpandedState(await getCurrentWindow().isMaximized());
  } catch {
    applyExpandedState(false);
  }
}

function scheduleExpandedSync() {
  window.clearTimeout(resizeSyncTimer);
  resizeSyncTimer = window.setTimeout(() => {
    if (!toggling) void readExpandedState();
  }, 80);
}

onMounted(async () => {
  visible.value =
    typeof window !== "undefined" &&
    ("__TAURI_INTERNALS__" in window || "__TAURI__" in window);

  await readExpandedState();

  if (!visible.value) return;

  try {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    const win = getCurrentWindow();
    unlisten = await win.onResized(async () => {
      try {
        if (await win.isMinimized()) return;
        const size = await win.innerSize();
        if (size.width < 120 || size.height < 120) return;
      } catch {
        /* 尺寸读失败时仍走缩放优化 */
      }
      beginResizeUi();
      scheduleResizeEnd();
      scheduleExpandedSync();
    });
  } catch (e) {
    console.warn("[qi] 窗口尺寸监听失败", e);
  }
});

onBeforeUnmount(() => {
  window.clearTimeout(resizeSyncTimer);
  window.clearTimeout(settleTimer);
  unlisten?.();
  document.documentElement.classList.remove("qi-resizing");
  syncExpandedClass(false);
});

async function minimize() {
  try {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    await getCurrentWindow().minimize();
  } catch (e) {
    console.warn("[qi] 最小化失败", e);
  }
}

async function toggleExpanded() {
  if (toggling) return;
  toggling = true;

  try {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    await getCurrentWindow().toggleMaximize();
    scheduleResizeEnd(48);
  } catch (e) {
    toggling = false;
    document.documentElement.classList.remove("qi-resizing");
    console.warn("[qi] 最大化切换失败", e);
    await readExpandedState();
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
    <button type="button" class="ctrl" aria-label="最小化" title="最小化" @click="minimize">
      <svg class="ico" viewBox="0 0 10 10" aria-hidden="true">
        <path d="M1.5 8.25h7" stroke="currentColor" stroke-width="1.15" stroke-linecap="round" />
      </svg>
    </button>
    <button
      type="button"
      class="ctrl"
      :aria-label="expanded ? '还原' : '最大化'"
      :title="expanded ? '还原' : '最大化'"
      @click="toggleExpanded"
    >
      <svg v-if="!expanded" class="ico" viewBox="0 0 10 10" aria-hidden="true">
        <rect
          x="1.35"
          y="1.35"
          width="7.3"
          height="7.3"
          rx="1.1"
          fill="none"
          stroke="currentColor"
          stroke-width="1.15"
        />
      </svg>
      <svg v-else class="ico" viewBox="0 0 10 10" aria-hidden="true">
        <rect
          x="2.55"
          y="0.85"
          width="6.35"
          height="6.35"
          rx="0.95"
          fill="none"
          stroke="currentColor"
          stroke-width="1.05"
        />
        <rect
          x="0.85"
          y="2.75"
          width="6.35"
          height="6.35"
          rx="0.95"
          fill="none"
          stroke="currentColor"
          stroke-width="1.05"
        />
      </svg>
    </button>
    <button
      type="button"
      class="ctrl close"
      aria-label="关闭到托盘"
      title="关闭到托盘"
      @click="closeWin"
    >
      <svg class="ico" viewBox="0 0 10 10" aria-hidden="true">
        <path
          d="M2.4 2.4l5.2 5.2M7.6 2.4L2.4 7.6"
          stroke="currentColor"
          stroke-width="1.15"
          stroke-linecap="round"
        />
      </svg>
    </button>
  </div>
</template>

<style scoped>
.win-ctrls {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
  pointer-events: auto;
  -webkit-app-region: no-drag;
}

.ctrl {
  width: 32px;
  height: 28px;
  border: none;
  border-radius: 6px;
  padding: 0;
  background: transparent;
  color: color-mix(in srgb, var(--ink) 78%, var(--ink-dim));
  cursor: pointer;
  display: grid;
  place-items: center;
  transition: background 0.18s ease, color 0.18s ease;
}

.ico {
  width: 10px;
  height: 10px;
  display: block;
}

.ctrl:hover {
  background: color-mix(in srgb, var(--ink) 8%, transparent);
  color: var(--ink);
}

.ctrl.close:hover {
  background: color-mix(in srgb, #c45c5c 72%, transparent);
  color: #fff;
}
</style>
