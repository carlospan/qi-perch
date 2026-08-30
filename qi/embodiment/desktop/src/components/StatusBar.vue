<script setup lang="ts">
import type { SystemNoticePayload } from "../types";
import {
  offlineStatusCopy,
  type OfflineKind,
} from "../connectionStatus";

const props = defineProps<{
  mode: string;
  season: string;
  connected: boolean;
  /** 离线档：从未接上 / 断线重连中 */
  offlineKind?: OfflineKind | null;
  /** 自然语言情绪描述，如「有点安静，感到安稳」 */
  mood?: string;
  /** 栖正在生成回复 */
  replying?: boolean;
  /** 系统态（失败可见，非她的话） */
  notice?: SystemNoticePayload | null;
}>();

const emit = defineEmits<{
  dismissNotice: [];
  openSettings: [];
}>();

const seasonLabel: Record<string, string> = {
  spring: "春",
  summer: "夏",
  autumn: "秋",
  winter: "冬",
};

const modeLabel: Record<string, string> = {
  awake: "醒着",
  ambient: "静静待着",
  solitary: "自己待着",
  dreaming: "在梦里",
  interacting: "在听你",
  stasis: "已封存休息",
};

function offlineCopy() {
  const kind = props.offlineKind ?? "never";
  return offlineStatusCopy(kind);
}
</script>

<template>
  <div class="status" :class="{ replying, hasNotice: !!notice }">
    <div class="row">
      <span class="dot" :class="{ on: connected, pulse: connected && replying }" />
      <template v-if="!connected">
        <span class="offline">{{ offlineCopy().title }}</span>
      </template>
      <template v-else-if="replying">
        <span class="replying-label" aria-live="polite">在回你</span>
        <span class="sep">·</span>
        <span>{{ seasonLabel[season] || season || "春" }}</span>
      </template>
      <template v-else>
        <span>{{ modeLabel[mode] || mode || "……" }}</span>
        <span class="sep">·</span>
        <span>{{ seasonLabel[season] || season || "春" }}</span>
      </template>
    </div>
    <p
      v-if="notice?.message"
      class="notice"
      role="status"
      aria-live="polite"
    >
      <span class="notice-text">{{ notice.message }}</span>
      <button
        v-if="notice.action === 'open_settings'"
        type="button"
        class="notice-go"
        @click="emit('openSettings')"
      >
        去设置
      </button>
      <button type="button" class="notice-x" aria-label="关闭提示" @click="emit('dismissNotice')">
        ×
      </button>
    </p>
    <p
      v-else-if="!connected"
      class="mood offline-next"
      role="status"
      aria-live="polite"
    >
      {{ offlineCopy().next }}
    </p>
    <p
      v-else-if="connected && mood && !replying"
      class="mood"
      :title="mood"
    >
      {{ mood }}
    </p>
    <p v-else-if="connected && replying" class="mood hint" aria-live="polite">
      栖还在想这句话
    </p>
  </div>
</template>

<style scoped>
.status {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.25rem;
  max-width: 22rem;
  font-family: var(--mono);
  font-size: 0.75rem;
  color: var(--ink-dim);
  letter-spacing: 0.04em;
}

.row {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--ink-faint);
  flex-shrink: 0;
}

.dot.on {
  background: var(--ember);
  opacity: 0.85;
  box-shadow: 0 0 6px color-mix(in srgb, var(--ember) 55%, transparent);
}

.dot.pulse {
  animation: reply-dot 1.4s ease-in-out infinite;
}

@keyframes reply-dot {
  0%,
  100% {
    opacity: 0.55;
    transform: scale(1);
    box-shadow: 0 0 4px color-mix(in srgb, var(--ember) 40%, transparent);
  }
  50% {
    opacity: 1;
    transform: scale(1.15);
    box-shadow: 0 0 10px color-mix(in srgb, var(--ember) 70%, transparent);
  }
}

.replying-label {
  color: var(--ember);
  letter-spacing: 0.12em;
  font-weight: 500;
}

.sep {
  opacity: 0.45;
}

.offline {
  color: var(--ink-faint);
}

.mood {
  margin: 0;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.68rem;
  color: var(--ink-faint);
  letter-spacing: 0.02em;
  text-align: right;
}

.mood.offline-next {
  white-space: normal;
  line-height: 1.35;
}

.mood.hint {
  color: color-mix(in srgb, var(--ember) 70%, var(--ink-dim));
  animation: hint-fade 2.4s ease-in-out infinite;
}

@keyframes hint-fade {
  0%,
  100% {
    opacity: 0.65;
  }
  50% {
    opacity: 1;
  }
}

.notice {
  margin: 0;
  display: flex;
  align-items: flex-start;
  gap: 0.35rem;
  max-width: 100%;
  padding: 0.35rem 0.45rem;
  border-radius: 4px;
  background: color-mix(in srgb, var(--ember) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--ember) 28%, transparent);
  font-size: 0.68rem;
  color: var(--ink-dim);
  letter-spacing: 0.02em;
  text-align: left;
  line-height: 1.35;
}

.notice-text {
  flex: 1;
  min-width: 0;
}

.notice-go {
  flex-shrink: 0;
  border: 1px solid color-mix(in srgb, var(--ember) 40%, transparent);
  background: color-mix(in srgb, var(--ember) 16%, transparent);
  color: var(--ink-dim);
  cursor: pointer;
  font-family: var(--mono);
  font-size: 0.65rem;
  letter-spacing: 0.04em;
  padding: 0.15rem 0.4rem;
  border-radius: 3px;
}

.notice-go:hover {
  color: var(--ink);
}

.notice-x {
  flex-shrink: 0;
  border: none;
  background: transparent;
  color: var(--ink-faint);
  cursor: pointer;
  font-size: 0.85rem;
  line-height: 1;
  padding: 0 0.1rem;
}

.notice-x:hover {
  color: var(--ink-dim);
}
</style>
