<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";

const props = defineProps<{
  disabled?: boolean;
  /** 栖正在回复：可改草稿，暂缓连发 */
  busy?: boolean;
}>();

const emit = defineEmits<{
  send: [text: string];
}>();

const text = ref("");
const field = ref<HTMLTextAreaElement | null>(null);

/** 桌面端：约 2～8 行可视 */
const MIN_HEIGHT_PX = 44;
const MAX_HEIGHT_PX = 168;

const blocked = computed(() => Boolean(props.disabled || props.busy));

const placeholder = computed(() => {
  if (props.disabled) return "通道还没连上……";
  if (props.busy) return "栖还在想……想好了再说一句";
  return "说点什么……（Enter 发送，Shift+Enter 换行）";
});

function resize() {
  const el = field.value;
  if (!el) return;
  el.style.height = "auto";
  const next = Math.min(Math.max(el.scrollHeight, MIN_HEIGHT_PX), MAX_HEIGHT_PX);
  el.style.height = `${next}px`;
  el.style.overflowY = el.scrollHeight > MAX_HEIGHT_PX ? "auto" : "hidden";
}

async function submit() {
  if (blocked.value) return;
  const value = text.value.trim();
  if (!value) return;
  emit("send", value);
  text.value = "";
  await nextTick();
  resize();
  field.value?.focus();
}

function onKeydown(e: KeyboardEvent) {
  // Enter 发送；Shift+Enter 换行（ChatGPT / Claude / 飞书等）
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    void submit();
  }
}

watch(text, () => {
  void nextTick(resize);
});
</script>

<template>
  <form
    class="composer"
    :class="{ offline: disabled, busy }"
    @submit.prevent="submit"
  >
    <textarea
      ref="field"
      v-model="text"
      rows="1"
      maxlength="500"
      :placeholder="placeholder"
      :disabled="disabled"
      :aria-busy="busy ? 'true' : undefined"
      autocomplete="off"
      @keydown="onKeydown"
      @input="resize"
    />
    <button
      type="submit"
      :aria-label="busy ? '栖还在想，稍后再发' : '发送'"
      :disabled="blocked || !text.trim()"
    >
      {{ busy ? "想着" : "发送" }}
    </button>
  </form>
</template>

<style scoped>
.composer {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  pointer-events: auto;
}

textarea {
  flex: 1;
  min-height: 44px;
  max-height: 132px;
  resize: none;
  border: 1px solid color-mix(in srgb, var(--ink) 9%, transparent);
  background: color-mix(in srgb, var(--ink) 4.5%, transparent);
  color: var(--ink);
  /* 多行不用全圆角胶囊，用聊天气泡式圆角矩形 */
  border-radius: 18px;
  padding: 11px 16px;
  outline: none;
  font-family: var(--serif);
  font-size: 14px;
  line-height: 1.5;
  overflow-y: hidden;
  field-sizing: content; /* 支持的浏览器可辅助增高 */
  transition:
    border-color 0.35s ease,
    background 0.35s ease;
}

textarea::placeholder {
  color: var(--ink-faint);
  font-weight: 300;
}

textarea:focus {
  border-color: color-mix(in srgb, var(--ember) 45%, transparent);
  background: color-mix(in srgb, var(--ink) 6%, transparent);
}

.composer.busy textarea {
  border-color: color-mix(in srgb, var(--ember) 32%, transparent);
  background: color-mix(in srgb, var(--ember) 6%, transparent);
}

.composer.busy textarea::placeholder {
  color: color-mix(in srgb, var(--ember) 55%, var(--ink-faint));
}

button {
  flex-shrink: 0;
  min-width: 64px;
  height: 40px;
  margin-bottom: 2px;
  padding: 0 14px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #8fb4c6, #5c8296);
  color: #0e1620;
  cursor: pointer;
  font-family: var(--serif);
  font-size: 13px;
  letter-spacing: 2px;
  display: grid;
  place-items: center;
  transition:
    transform 0.25s ease,
    box-shadow 0.25s ease,
    opacity 0.2s ease;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.35);
}

button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 16px color-mix(in srgb, #8fb4c6 35%, transparent);
}

button:disabled {
  opacity: 0.4;
  cursor: default;
  box-shadow: none;
}

.composer.busy button:disabled {
  opacity: 0.55;
  letter-spacing: 1px;
}

.composer.offline textarea {
  opacity: 0.72;
  cursor: not-allowed;
}
</style>
