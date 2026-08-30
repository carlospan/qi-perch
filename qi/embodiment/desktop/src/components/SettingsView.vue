<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import type { SettingsLlmPayload } from "../types";

const props = defineProps<{
  snapshot: SettingsLlmPayload | null;
  saving?: boolean;
  saveError?: string;
  saveOk?: boolean;
  probing?: boolean;
  probeMessage?: string;
  probeOk?: boolean;
}>();

const emit = defineEmits<{
  close: [];
  save: [
    payload: {
      api_key?: string;
      base_url: string;
      model: string;
    },
  ];
  refresh: [];
  probe: [];
}>();

const apiKey = ref("");
const baseUrl = ref("");
const model = ref("");
const keyDirty = ref(false);
const localProbeHint = ref("");

watch(
  () => props.snapshot,
  (s) => {
    if (!s) return;
    baseUrl.value = s.base_url || "";
    model.value = s.model || "";
    if (!keyDirty.value) apiKey.value = "";
    keyDirty.value = false;
    localProbeHint.value = "";
  },
  { immediate: true }
);

watch(
  () => props.probeMessage,
  () => {
    if (props.probeMessage) localProbeHint.value = "";
  }
);

onMounted(() => {
  emit("refresh");
});

const formDirty = computed(() => {
  const s = props.snapshot;
  if (!s) return keyDirty.value || !!baseUrl.value.trim() || !!model.value.trim();
  if (keyDirty.value) return true;
  if (baseUrl.value.trim() !== (s.base_url || "").trim()) return true;
  if (model.value.trim() !== (s.model || "").trim()) return true;
  return false;
});

function onSave() {
  localProbeHint.value = "";
  const payload: { api_key?: string; base_url: string; model: string } = {
    base_url: baseUrl.value.trim(),
    model: model.value.trim(),
  };
  if (keyDirty.value) {
    payload.api_key = apiKey.value.trim();
  }
  emit("save", payload);
}

function onProbe() {
  if (formDirty.value) {
    localProbeHint.value = "有未保存的改动。请先「保存并生效」，再试连通。";
    return;
  }
  localProbeHint.value = "";
  emit("probe");
}
</script>

<template>
  <div class="desk-page settings">
    <div class="desk-main">
      <header class="page-hero">
        <div class="page-hero-row">
          <h2>设置</h2>
          <button type="button" class="back" @click="emit('close')">返回</button>
        </div>
        <p class="page-hero-sub">给她一把模型钥匙。只存在你这台电脑里。</p>
      </header>

      <div class="desk-scroll form-wrap">
        <label class="field">
          <span class="label">API 密钥</span>
          <input
            v-model="apiKey"
            type="password"
            autocomplete="off"
            :placeholder="
              snapshot?.has_key
                ? `已保存 ${snapshot.api_key_masked}（不改请勿填写；清空并保存可清除）`
                : '粘贴你的 API key'
            "
            @input="keyDirty = true"
          />
        </label>

        <label class="field">
          <span class="label">接口地址（可选）</span>
          <input
            v-model="baseUrl"
            type="url"
            autocomplete="off"
            placeholder="默认沿用配置文件；可填 OpenAI 兼容 base_url"
          />
        </label>

        <label class="field">
          <span class="label">模型名（可选）</span>
          <input
            v-model="model"
            type="text"
            autocomplete="off"
            placeholder="默认沿用配置；填写则 fast/strong 同用此名"
          />
        </label>

        <div class="actions">
          <div class="btn-row">
            <button type="button" class="save" :disabled="saving" @click="onSave">
              {{ saving ? "保存中…" : "保存并生效" }}
            </button>
            <button
              type="button"
              class="probe"
              :disabled="saving || probing"
              @click="onProbe"
            >
              {{ probing ? "在试…" : "试一下" }}
            </button>
          </div>
          <p v-if="saveOk" class="hint ok">已保存，正在用新钥匙。</p>
          <p v-else-if="saveError" class="hint err">{{ saveError }}</p>
          <p v-if="localProbeHint" class="hint err">{{ localProbeHint }}</p>
          <p
            v-else-if="probeMessage"
            class="hint"
            :class="probeOk ? 'ok' : 'err'"
          >
            {{ probeMessage }}
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings.desk-page {
  position: relative;
  flex: 1;
  min-height: 0;
  grid-template-columns: minmax(0, 1fr);
}

.page-hero-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.back {
  border: 1px solid color-mix(in srgb, var(--ink) 14%, transparent);
  background: transparent;
  color: var(--ink-dim);
  font-family: var(--mono);
  font-size: 0.72rem;
  letter-spacing: 0.06em;
  padding: 0.35rem 0.7rem;
  border-radius: 4px;
  cursor: pointer;
}

.back:hover {
  color: var(--ink);
  border-color: color-mix(in srgb, var(--ember) 40%, transparent);
}

.form-wrap {
  max-width: 28rem;
  padding: 8px var(--page-pad-x, 1.5rem) 2rem;
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.label {
  font-family: var(--mono);
  font-size: 0.68rem;
  letter-spacing: 0.08em;
  color: var(--ink-faint);
}

input {
  font-family: var(--serif);
  font-size: 0.95rem;
  padding: 0.65rem 0.75rem;
  border-radius: 6px;
  border: 1px solid color-mix(in srgb, var(--ink) 14%, transparent);
  background: color-mix(in srgb, var(--panel-veil, #121820) 80%, transparent);
  color: var(--ink);
}

input::placeholder {
  color: var(--ink-faint);
  opacity: 0.85;
}

.actions {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.55rem;
  margin-top: 0.4rem;
}

.btn-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  align-items: center;
}

.save {
  font-family: var(--serif);
  font-size: 0.9rem;
  letter-spacing: 0.1em;
  padding: 0.55rem 1.1rem;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  color: #2a2118;
  background: linear-gradient(180deg, #dfc39a 0%, #c49a68 100%);
}

.save:disabled {
  opacity: 0.55;
  cursor: wait;
}

.probe {
  font-family: var(--serif);
  font-size: 0.9rem;
  letter-spacing: 0.1em;
  padding: 0.55rem 1.1rem;
  border-radius: 6px;
  border: 1px solid color-mix(in srgb, var(--ink) 18%, transparent);
  cursor: pointer;
  color: var(--ink-dim);
  background: transparent;
}

.probe:hover:not(:disabled) {
  color: var(--ink);
  border-color: color-mix(in srgb, var(--ember) 40%, transparent);
}

.probe:disabled {
  opacity: 0.55;
  cursor: wait;
}

.hint {
  margin: 0;
  font-size: 0.75rem;
  color: var(--ink-faint);
}

.hint.ok {
  color: color-mix(in srgb, var(--ember) 70%, var(--ink-dim));
}

.hint.err {
  color: #c45a4a;
}
</style>
