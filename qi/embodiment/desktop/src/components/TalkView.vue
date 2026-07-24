<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from "vue";
import type { TalkDayGroup } from "../composables/useQi";

const WAITING_LINES = ["……", "嗯……", "我在想。", "稍等……"] as const;

const props = defineProps<{
  groups: TalkDayGroup[];
  typing?: boolean;
}>();

const body = ref<HTMLElement | null>(null);
const waitLine = ref<string>(WAITING_LINES[0]);

function timeLabel(at: number) {
  const d = new Date(at);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${hh}:${mm}`;
}

/** 视口锚定到时间线尾部（最新消息） */
async function scrollBottom() {
  await nextTick();
  // 等 Transition / 布局完成后再滚，避免 scrollHeight 仍是旧值
  await new Promise<void>((r) => requestAnimationFrame(() => r()));
  await new Promise<void>((r) => requestAnimationFrame(() => r()));
  const el = body.value;
  if (el) el.scrollTop = el.scrollHeight;
}

onMounted(() => {
  void scrollBottom();
});

watch(
  () => props.groups.map((g) => g.messages.length).reduce((a, b) => a + b, 0),
  () => {
    void scrollBottom();
  },
  { immediate: true }
);

watch(
  () => props.typing,
  (on) => {
    if (on) {
      waitLine.value =
        WAITING_LINES[Math.floor(Math.random() * WAITING_LINES.length)];
      void scrollBottom();
    }
  }
);
</script>

<template>
  <div class="panel">
    <div class="panel-head">
      <span class="t">谈</span>
      <span class="sub">你们说过的话</span>
    </div>
    <div ref="body" class="panel-body">
      <p v-if="groups.length === 0 && !typing" class="empty">
        还没有说过话。说一句，会留在这里——下次打开也能看见。
      </p>
      <template v-for="g in groups" :key="g.key">
        <div class="day">{{ g.label }}</div>
        <div
          v-for="m in g.messages"
          :key="m.id"
          class="msg"
          :class="m.role"
        >
          <div class="who">{{ m.role === "qi" ? "栖" : "你" }}</div>
          <div class="txt">{{ m.text }}</div>
          <div class="when">{{ timeLabel(m.at) }}</div>
        </div>
      </template>

      <div v-if="typing" class="msg qi pending" aria-live="polite">
        <div class="who">栖</div>
        <div class="txt wait">{{ waitLine }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.panel {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  background: color-mix(in srgb, var(--panel-veil) 62%, transparent);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  pointer-events: auto;
}

.panel-head {
  padding: 8px 4px 10px;
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.panel-head .t {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 4px;
  color: var(--ink);
}

.panel-head .sub {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--ink-faint);
  letter-spacing: 0.5px;
}

.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 6px 2px 18px;
  scrollbar-width: thin;
  scrollbar-color: color-mix(in srgb, var(--ink) 12%, transparent) transparent;
  mask-image: linear-gradient(
    to bottom,
    transparent 0,
    #000 12px,
    #000 calc(100% - 16px),
    transparent 100%
  );
}

.empty {
  margin: 48px 12px;
  text-align: center;
  font-size: 13px;
  line-height: 1.7;
  color: var(--ink-faint);
  font-weight: 300;
}

.day {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--ink-faint);
  letter-spacing: 2px;
  text-align: center;
  margin: 18px 0 14px;
  position: relative;
}

.day::before,
.day::after {
  content: "";
  position: absolute;
  top: 50%;
  width: 26%;
  height: 1px;
  background: color-mix(in srgb, var(--ink) 7%, transparent);
}

.day::before {
  left: 0;
}
.day::after {
  right: 0;
}

.msg {
  max-width: 82%;
  margin-bottom: 14px;
  animation: rise 0.5s ease both;
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(8px);
    filter: blur(2px);
  }
  to {
    opacity: 1;
    transform: none;
    filter: blur(0);
  }
}

.who {
  font-family: var(--mono);
  font-size: 9.5px;
  color: var(--ink-faint);
  letter-spacing: 1px;
  margin-bottom: 4px;
}

.txt {
  font-size: 14px;
  line-height: 1.75;
  padding: 10px 14px;
}

.msg.qi {
  margin-right: auto;
}

.msg.qi .txt {
  background: var(--talk-qi-bg);
  border: 1px solid var(--talk-qi-bd);
  border-radius: 4px 14px 14px 14px;
  color: var(--ink);
}

.msg.me {
  margin-left: auto;
  text-align: right;
}

.msg.me .who {
  text-align: right;
}

.msg.me .txt {
  background: var(--talk-me-bg);
  border: 1px solid var(--talk-me-bd);
  border-radius: 14px 4px 14px 14px;
  color: var(--talk-me-ink);
  display: inline-block;
  text-align: left;
}

.when {
  font-family: var(--mono);
  font-size: 9.5px;
  color: var(--ink-faint);
  letter-spacing: 0.5px;
  margin-top: 4px;
  opacity: 0.85;
}
.msg.me .when {
  text-align: right;
}

.msg.pending .txt.wait {
  color: var(--ink-dim);
  font-weight: 300;
  letter-spacing: 0.6px;
  animation: wait-breathe 3.6s ease-in-out infinite;
}

@keyframes wait-breathe {
  0%,
  100% {
    opacity: 0.55;
  }
  50% {
    opacity: 0.95;
  }
}
</style>
