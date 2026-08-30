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
  memoryExporting?: boolean;
  memoryWiping?: boolean;
  memoryMessage?: string;
  memoryOk?: boolean;
  allowedRootsSaving?: boolean;
  allowedRootsPicking?: boolean;
  allowedRootsMessage?: string;
  allowedRootsOk?: boolean;
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
  openDataDir: [];
  exportMemory: [];
  wipeMemory: [];
  pickAllowedRoot: [];
  saveAllowedRoots: [roots: string[]];
}>();

const apiKey = ref("");
const baseUrl = ref("");
const model = ref("");
const keyDirty = ref(false);
const localProbeHint = ref("");
/** 删除两步确认：展开后需再点确认 */
const wipeConfirmOpen = ref(false);
const localRoots = ref<string[]>([]);
const devPasteRoot = ref("");
/** Vite 开发壳：允许粘贴路径（产品主路径仍是系统选目录） */
const isDevShell = !("__TAURI_INTERNALS__" in window || "__TAURI__" in window);

watch(
  () => props.snapshot,
  (s) => {
    if (!s) return;
    baseUrl.value = s.base_url || "";
    model.value = s.model || "";
    if (!keyDirty.value) apiKey.value = "";
    keyDirty.value = false;
    localProbeHint.value = "";
    localRoots.value = [...(s.allowed_roots?.roots || [])];
  },
  { immediate: true }
);

watch(
  () => props.probeMessage,
  () => {
    if (props.probeMessage) localProbeHint.value = "";
  }
);

watch(
  () => props.memoryMessage,
  (msg) => {
    if (msg && props.memoryOk) wipeConfirmOpen.value = false;
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

function onExport() {
  wipeConfirmOpen.value = false;
  emit("exportMemory");
}

function onWipeAsk() {
  wipeConfirmOpen.value = true;
}

function onWipeCancel() {
  wipeConfirmOpen.value = false;
}

function onWipeConfirm() {
  emit("wipeMemory");
}

function onPickRoot() {
  emit("pickAllowedRoot");
}

function onRemoveRoot(path: string) {
  const next = localRoots.value.filter((r) => r !== path);
  localRoots.value = next;
  emit("saveAllowedRoots", next);
}

function onDevPasteAdd() {
  const p = devPasteRoot.value.trim();
  if (!p) return;
  if (localRoots.value.includes(p)) {
    devPasteRoot.value = "";
    return;
  }
  const next = [...localRoots.value, p];
  localRoots.value = next;
  devPasteRoot.value = "";
  emit("saveAllowedRoots", next);
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

        <div class="data-dir">
          <p class="label">数据文件夹</p>
          <p class="path" :title="snapshot?.data_dir || ''">
            {{ snapshot?.data_dir || "连接后显示路径" }}
          </p>
          <button type="button" class="open-folder" @click="emit('openDataDir')">
            打开数据文件夹
          </button>
        </div>

        <div class="allowed-roots">
          <p class="label">她能碰的文件夹</p>
          <p class="life-note">
            列盘、读文件、写日记只能在这些顶层目录下。空着就不能碰盘——请先添加。
          </p>
          <ul v-if="localRoots.length" class="root-list">
            <li v-for="r in localRoots" :key="r" class="root-item">
              <span class="root-path" :title="r">{{ r }}</span>
              <button
                type="button"
                class="root-remove"
                :disabled="allowedRootsSaving || allowedRootsPicking"
                @click="onRemoveRoot(r)"
              >
                移除
              </button>
            </li>
          </ul>
          <p v-else class="hint">还没有允许的文件夹。</p>
          <div class="btn-row">
            <button
              type="button"
              class="open-folder"
              :disabled="allowedRootsSaving || allowedRootsPicking"
              @click="onPickRoot"
            >
              {{ allowedRootsPicking ? "选目录中…" : "添加文件夹" }}
            </button>
          </div>
          <div v-if="isDevShell" class="dev-paste">
            <p class="life-note">开发壳：也可粘贴路径添加（产品主路径仍是上面的选目录）。</p>
            <div class="btn-row">
              <input
                v-model="devPasteRoot"
                type="text"
                class="dev-input"
                placeholder="例如 D:\Notes"
                @keydown.enter.prevent="onDevPasteAdd"
              />
              <button
                type="button"
                class="open-folder"
                :disabled="allowedRootsSaving || !devPasteRoot.trim()"
                @click="onDevPasteAdd"
              >
                粘贴添加
              </button>
            </div>
          </div>
          <p
            v-if="allowedRootsMessage"
            class="hint"
            :class="allowedRootsOk ? 'ok' : 'err'"
          >
            {{ allowedRootsMessage }}
          </p>
        </div>

        <div class="memory-life">
          <p class="label">记忆</p>
          <p class="life-note">
            导出只含她记得的事（库与向量），不含钥匙和模型。删除不可恢复。
          </p>
          <div class="btn-row">
            <button
              type="button"
              class="open-folder"
              :disabled="memoryExporting || memoryWiping"
              @click="onExport"
            >
              {{ memoryExporting ? "导出中…" : "导出备份" }}
            </button>
            <button
              v-if="!wipeConfirmOpen"
              type="button"
              class="danger"
              :disabled="memoryExporting || memoryWiping"
              @click="onWipeAsk"
            >
              删除全部记忆
            </button>
          </div>
          <div v-if="wipeConfirmOpen" class="wipe-confirm">
            <p class="wipe-warn">会忘掉往事，钥匙还在。此操作不可恢复。</p>
            <div class="btn-row">
              <button
                type="button"
                class="danger solid"
                :disabled="memoryWiping"
                @click="onWipeConfirm"
              >
                {{ memoryWiping ? "清空中…" : "确认删除" }}
              </button>
              <button
                type="button"
                class="open-folder"
                :disabled="memoryWiping"
                @click="onWipeCancel"
              >
                取消
              </button>
            </div>
          </div>
          <p
            v-if="memoryMessage"
            class="hint"
            :class="memoryOk ? 'ok' : 'err'"
          >
            {{ memoryMessage }}
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

.data-dir,
.memory-life,
.allowed-roots {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.4rem;
  padding-top: 0.6rem;
  border-top: 1px solid color-mix(in srgb, var(--ink) 10%, transparent);
}

.root-list {
  list-style: none;
  margin: 0;
  padding: 0;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.root-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  justify-content: space-between;
}

.root-path {
  flex: 1;
  min-width: 0;
  font-family: var(--mono);
  font-size: 0.68rem;
  color: var(--ink-faint);
  word-break: break-all;
}

.root-remove {
  flex-shrink: 0;
  border: none;
  background: transparent;
  color: #c45a4a;
  cursor: pointer;
  font-family: var(--mono);
  font-size: 0.68rem;
  letter-spacing: 0.04em;
}

.dev-paste {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-top: 0.25rem;
}

.dev-input {
  flex: 1;
  min-width: 8rem;
  font-family: var(--mono);
  font-size: 0.75rem;
  padding: 0.4rem 0.55rem;
  border-radius: 6px;
  border: 1px solid color-mix(in srgb, var(--ink) 14%, transparent);
  background: color-mix(in srgb, var(--panel-veil, #121820) 80%, transparent);
  color: var(--ink);
}

.data-dir .path {
  margin: 0;
  max-width: 100%;
  font-family: var(--mono);
  font-size: 0.68rem;
  color: var(--ink-faint);
  word-break: break-all;
}

.life-note {
  margin: 0;
  font-size: 0.72rem;
  color: var(--ink-faint);
  line-height: 1.45;
}

.wipe-confirm {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  width: 100%;
  padding: 0.55rem 0.6rem;
  border-radius: 6px;
  border: 1px solid color-mix(in srgb, #c45a4a 35%, transparent);
  background: color-mix(in srgb, #c45a4a 8%, transparent);
}

.wipe-warn {
  margin: 0;
  font-size: 0.75rem;
  color: #c45a4a;
  line-height: 1.4;
}

.open-folder {
  font-family: var(--serif);
  font-size: 0.85rem;
  letter-spacing: 0.08em;
  padding: 0.45rem 0.9rem;
  border-radius: 6px;
  border: 1px solid color-mix(in srgb, var(--ink) 18%, transparent);
  cursor: pointer;
  color: var(--ink-dim);
  background: transparent;
}

.open-folder:hover:not(:disabled) {
  color: var(--ink);
  border-color: color-mix(in srgb, var(--ember) 40%, transparent);
}

.open-folder:disabled,
.danger:disabled {
  opacity: 0.55;
  cursor: wait;
}

.danger {
  font-family: var(--serif);
  font-size: 0.85rem;
  letter-spacing: 0.08em;
  padding: 0.45rem 0.9rem;
  border-radius: 6px;
  border: 1px solid color-mix(in srgb, #c45a4a 45%, transparent);
  cursor: pointer;
  color: #c45a4a;
  background: transparent;
}

.danger:hover:not(:disabled) {
  border-color: #c45a4a;
}

.danger.solid {
  color: #fff8f6;
  background: color-mix(in srgb, #c45a4a 88%, #2a2118);
  border-color: transparent;
}
</style>
