<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from "vue";
import type { TalkDayGroup } from "../composables/useQi";
import ActionCard from "./ActionCard.vue";
import AssistConfirmCard from "./AssistConfirmCard.vue";
import ExploreCard from "./ExploreCard.vue";

/** 固定过程态文案：勿用「嗯……」等像成句回话的占位 */
const WAITING_LINE = "在想怎么回你";

const props = withDefaults(
  defineProps<{
    groups: TalkDayGroup[];
    typing?: boolean;
    /** desktop：右栏对话面板，弱化全屏遮罩 */
    layout?: "default" | "desktop";
    historyExhausted?: boolean;
    historyLoading?: boolean;
    /** 递增表示刚 prepend，应保阅读位置 */
    prependTick?: number;
  }>(),
  {
    layout: "default",
    historyExhausted: false,
    historyLoading: false,
    prependTick: 0,
  }
);

const emit = defineEmits<{
  send: [text: string];
  needOlder: [];
}>();

const body = ref<HTMLElement | null>(null);
/** 贴底跟随新消息；上翻阅读时关闭 */
let stickBottom = true;
let savedScrollHeight = 0;
let savedScrollTop = 0;
let expectPrepend = false;

function timeLabel(at: number) {
  const d = new Date(at);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${hh}:${mm}`;
}

/** 视口锚定到时间线尾部（最新消息） */
async function scrollBottom() {
  await nextTick();
  await new Promise<void>((r) => requestAnimationFrame(() => r()));
  await new Promise<void>((r) => requestAnimationFrame(() => r()));
  const el = body.value;
  if (el) el.scrollTop = el.scrollHeight;
}

async function restoreAfterPrepend() {
  await nextTick();
  await new Promise<void>((r) => requestAnimationFrame(() => r()));
  await new Promise<void>((r) => requestAnimationFrame(() => r()));
  const el = body.value;
  if (!el) return;
  const delta = el.scrollHeight - savedScrollHeight;
  el.scrollTop = savedScrollTop + delta;
}

function onScroll() {
  const el = body.value;
  if (!el) return;
  const distBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
  stickBottom = distBottom < 96;
  if (
    el.scrollTop < 72 &&
    !props.historyLoading &&
    !props.historyExhausted
  ) {
    savedScrollHeight = el.scrollHeight;
    savedScrollTop = el.scrollTop;
    expectPrepend = true;
    emit("needOlder");
  }
}

onMounted(() => {
  void scrollBottom();
});

watch(
  () => props.prependTick,
  (n, prev) => {
    if (n && n !== prev) {
      expectPrepend = false;
      void restoreAfterPrepend();
    }
  }
);

watch(
  () =>
    props.groups
      .map((g) =>
        g.messages
          .map((m) =>
            m.kind === "text" ? `${m.id}:${m.text.length}` : m.id
          )
          .join("|")
      )
      .join(";"),
  () => {
    if (expectPrepend) return;
    if (stickBottom) void scrollBottom();
  },
  { immediate: true }
);

watch(
  () => props.typing,
  (on) => {
    if (on && stickBottom) void scrollBottom();
  }
);
</script>

<template>
  <div class="panel" :class="{ desktop: layout === 'desktop' }">
    <div class="panel-head">
      <span class="t">相处</span>
      <span class="sub">此刻的对话</span>
    </div>
    <div ref="body" class="panel-body" @scroll.passive="onScroll">
      <p v-if="historyExhausted" class="history-end" aria-live="polite">
        没有更早的了
      </p>
      <p v-else-if="historyLoading" class="history-loading" aria-live="polite">
        加载更早…
      </p>
      <p v-if="groups.length === 0 && !typing" class="empty">
        还没有说过话。说一句，会留在这里——下次打开也能看见。
      </p>
      <template v-for="g in groups" :key="g.key">
        <div class="day">{{ g.label }}</div>
        <template v-for="m in g.messages" :key="m.id">
          <div v-if="m.kind === 'card'" class="msg qi card">
            <div class="who">栖</div>
            <ActionCard
              v-if="m.card.type === 'creation_card'"
              :card="m.card"
            />
            <ExploreCard
              v-else-if="m.card.type === 'explore_drift'"
              :card="m.card"
              @together="
                (url, title) =>
                  emit(
                    'send',
                    title
                      ? `一起看「${title}」 ${url}`
                      : `一起看 ${url}`,
                  )
              "
            />
            <AssistConfirmCard
              v-else-if="m.card.type === 'assist_confirm_request'"
              :card="m.card"
              @confirm="
                emit(
                  'send',
                  m.card.confirm_label ||
                    (m.card.kind === 'open' ? '开吧' : '看吧'),
                )
              "
              @cancel="emit('send', '不用')"
            />
            <div class="when">{{ timeLabel(m.at) }}</div>
          </div>
          <div v-else class="msg" :class="m.role">
            <div class="who">{{ m.role === "qi" ? "栖" : "你" }}</div>
            <div class="txt">{{ m.text }}</div>
            <div class="when">{{ timeLabel(m.at) }}</div>
          </div>
        </template>
      </template>

      <div v-if="typing" class="msg qi pending" aria-live="polite">
        <div class="who">栖</div>
        <div class="txt wait">
          <span class="wait-words">{{ WAITING_LINE }}</span>
          <span class="wait-dots" aria-hidden="true">
            <i /><i /><i />
          </span>
        </div>
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
  /* 薄纱遮罩，不加 blur，免得把剪影壁纸糊掉 */
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--panel-veil) 38%, transparent) 0%,
      color-mix(in srgb, var(--panel-veil) 12%, transparent) 40%,
      color-mix(in srgb, var(--panel-veil) 22%, transparent) 100%
    );
  pointer-events: auto;
}

.panel.desktop {
  position: relative;
  height: 100%;
  background: transparent;
  border: none;
  border-radius: 0;
}

.panel.desktop .panel-head {
  border-bottom-color: color-mix(in srgb, var(--ink) 8%, transparent);
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--panel-veil) 42%, transparent) 0%,
    transparent 100%
  );
}

.panel-head {
  padding: 10px 14px 12px;
  display: flex;
  align-items: baseline;
  gap: 12px;
  flex-shrink: 0;
  border-bottom: 1px solid color-mix(in srgb, var(--ink) 5%, transparent);
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
  padding: 12px 14px 18px;
  scrollbar-width: thin;
  scrollbar-color: color-mix(in srgb, var(--ink) 12%, transparent) transparent;
  mask-image: linear-gradient(
    to bottom,
    transparent 0,
    #000 10px,
    #000 calc(100% - 14px),
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

.history-end,
.history-loading {
  margin: 8px 12px 4px;
  text-align: center;
  font-size: 11px;
  letter-spacing: 0.5px;
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
  max-width: min(72%, 520px);
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
  background: color-mix(in srgb, var(--talk-qi-bg) 88%, var(--panel-veil));
  border: 1px solid var(--talk-qi-bd);
  border-radius: 4px 14px 14px 14px;
  color: var(--ink);
  backdrop-filter: blur(6px);
}

.panel.desktop .msg.qi .txt {
  background: color-mix(in srgb, var(--panel-veil) 72%, transparent);
  border-color: color-mix(in srgb, var(--talk-qi-bd) 80%, transparent);
}

.msg.qi.card {
  max-width: 88%;
}

.msg.me {
  margin-left: auto;
  text-align: right;
}

.msg.me .who {
  text-align: right;
}

.msg.me .txt {
  background: color-mix(in srgb, var(--talk-me-bg) 88%, var(--panel-veil));
  border: 1px solid var(--talk-me-bd);
  border-radius: 14px 4px 14px 14px;
  color: var(--talk-me-ink);
  display: inline-block;
  text-align: left;
  backdrop-filter: blur(6px);
}

.panel.desktop .msg.me .txt {
  background: color-mix(in srgb, var(--panel-veil) 68%, var(--talk-me-bg));
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
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--ink-dim);
  font-weight: 300;
  letter-spacing: 0.6px;
  border-color: color-mix(in srgb, var(--ember) 28%, var(--talk-qi-bd));
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--ember) 12%, transparent);
  animation: wait-breathe 2.4s ease-in-out infinite;
}

.wait-words {
  flex-shrink: 0;
}

.wait-dots {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-height: 1em;
}

.wait-dots i {
  display: block;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--ember) 75%, var(--ink-dim));
  opacity: 0.35;
  animation: wait-dot 1.2s ease-in-out infinite;
}

.wait-dots i:nth-child(2) {
  animation-delay: 0.2s;
}

.wait-dots i:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes wait-breathe {
  0%,
  100% {
    opacity: 0.72;
  }
  50% {
    opacity: 1;
  }
}

@keyframes wait-dot {
  0%,
  80%,
  100% {
    opacity: 0.28;
    transform: translateY(0);
  }
  40% {
    opacity: 1;
    transform: translateY(-2px);
  }
}
</style>
