/**
 * WS 接线 + 消息 / 历史状态。
 * 「相处」：/history 灌对话与创作·见闻卡；本轮继续 append。
 * 「回顾」：创作 / 见闻归档。
 * 「内在」：/journal 灌独白 / 梦 / 第一次；无则诚实空占位。
 */

import { computed, ref, watch } from "vue";
import { useEmotion } from "./useEmotion";
import type {
  ActionPayload,
  AssistConfirmCard,
  AvatarState,
  CreationCard,
  EmotionSnapshot,
  ExploreCard,
  JournalEntry,
  MessageAckPayload,
  QiView,
  SpeechPayload,
  SpeechStreamDeltaPayload,
  SpeechStreamDonePayload,
  SpeechStreamRetractPayload,
  SystemNoticePayload,
  TalkCardItem,
  TalkItem,
  TalkMessage,
  TimeTracesPayload,
  ReviewMemoriesPayload,
  ReviewMemoryItem,
  ActivityGlancePayload,
  SettingsLlmPayload,
  SettingsLlmSavedPayload,
  SettingsLlmProbePayload,
  TurnInterruptedPayload,
} from "../types";
import { qiWs } from "../ws";

/** 与 HITL：busy 约 60s 强制解锁 */
const TYPING_TIMEOUT_MS = 60_000;
/** 发送回执：约 3s 无 ACK → 可能没送到 */
const ACK_TIMEOUT_MS = 3_000;

const TIMEOUT_NOTICE: SystemNoticePayload = {
  kind: "timeout",
  message: "等太久了，先解开输入。若稍后她仍回了，气泡仍会显示。",
  action: null,
};

const DELIVERY_TIMEOUT_NOTICE: SystemNoticePayload = {
  kind: "delivery_timeout",
  message: "这句可能没送到。气泡还在，你可以再发一次。",
  action: null,
};

function uid(prefix: string) {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
}

const AVATAR_EXPR_PREVIEW = new Set([
  "neutral",
  "soft_smile",
  "happy",
  "quiet",
  "surprised",
  "sleepy",
  "curious",
]);

/** 开发态：?avatar_expr=soft_smile 预览表情，不被 WS 覆盖 */
function devAvatarExprOverride(): string | null {
  if (!import.meta.env.DEV) return null;
  const raw = new URLSearchParams(window.location.search).get("avatar_expr");
  if (!raw || !AVATAR_EXPR_PREVIEW.has(raw)) return null;
  return raw;
}

function applyAvatarState(
  incoming: AvatarState,
  avatar: { value: AvatarState }
) {
  const forced = devAvatarExprOverride();
  if (forced) {
    avatar.value = { ...incoming, expression: forced };
    return;
  }
  avatar.value = incoming;
}

type AnyTalkCard = CreationCard | ExploreCard | AssistConfirmCard;

function cardKey(card: AnyTalkCard): string {
  if (card.type === "creation_card") return `c${card.creation_id}`;
  if (card.type === "explore_drift") return `e${card.action_id}`;
  return `a${card.action_id ?? card.target_path}`;
}

function sameDay(a: Date, b: Date) {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

export function dayKey(ts: number) {
  const d = new Date(ts);
  return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
}

/** 「今天 · 7月22日」一类分组标题 */
export function dayLabel(ts: number) {
  const d = new Date(ts);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  const md = `${d.getMonth() + 1}月${d.getDate()}日`;
  if (sameDay(d, today)) return `今天 · ${md}`;
  if (sameDay(d, yesterday)) return `昨天 · ${md}`;
  return md;
}

export type TalkDayGroup = {
  key: string;
  label: string;
  messages: TalkItem[];
};

let singleton: ReturnType<typeof createQi> | null = null;

function createQi() {
  const { onEmotionUpdate, requestEmotionSnapshot } = useEmotion();

  const view = ref<QiView>("presence");
  const connected = ref(false);
  const typing = ref(false);
  const speech = ref("");
  const speaking = ref(false);
  const replyEpoch = ref(0);
  const systemNotice = ref<SystemNoticePayload | null>(null);
  const composerPrefill = ref("");
  const season = ref("spring");
  const emotion = ref<EmotionSnapshot>({ mode: "awake", description: "" });
  const avatar = ref<AvatarState>({
    posture: "idle",
    expression: devAvatarExprOverride() || "neutral",
    effect: "none",
  });

  /** 对话历史（启动后由 /history 灌入） */
  const talk = ref<TalkMessage[]>([]);
  /** 创作 / 见闻 / assist 确认卡（随 /history.cards 回灌） */
  const cards = ref<TalkCardItem[]>([]);
  const historyLoaded = ref(false);
  /** 是否还有更早文本可上翻 */
  const historyHasMore = ref(true);
  const historyLoadingOlder = ref(false);
  /** 到头轻提示（谈区顶） */
  const historyExhausted = ref(false);
  /** 通知 TalkView：刚完成一次 prepend，请保位置 */
  const historyPrependTick = ref(0);
  /** 内在日记（启动后由 /journal 灌入；库空则保持空） */
  const journal = ref<JournalEntry[]>([]);
  /** 方向 D：存在页底部时间痕迹旁白 */
  const timeTraceLine = ref("");
  /** 方向 D：回顾「记忆」列表 */
  const reviewMemories = ref<ReviewMemoryItem[]>([]);
  /** 方向 D：存在页一行动向旁白（无近事则空） */
  const activityGlanceLine = ref("");
  /** P2：设置页（整页，非 tab） */
  const settingsOpen = ref(false);
  const settingsLlm = ref<SettingsLlmPayload | null>(null);
  const settingsSaving = ref(false);
  const settingsSaveError = ref("");
  const settingsSaveOk = ref(false);
  const settingsProbing = ref(false);
  const settingsProbeMessage = ref("");
  const settingsProbeOk = ref(false);

  const mode = computed(() => {
    if (emotion.value.stasis || emotion.value.mode === "stasis") {
      return "stasis";
    }
    return emotion.value.mode || avatar.value.posture || "awake";
  });

  function appendCard(card: AnyTalkCard, at?: number) {
    const key = cardKey(card);
    if (cards.value.some((c) => cardKey(c.card) === key)) return;
    cards.value.push({
      id: uid("card"),
      kind: "card",
      card,
      at: typeof at === "number" ? at : Date.now(),
    });
  }

  function applyHistoryCards(
    raw: Array<(CreationCard | ExploreCard | AssistConfirmCard) & { at?: number }>
  ) {
    const hydrated: TalkCardItem[] = [];
    const seen = new Set<string>();
    for (const row of raw ?? []) {
      if (row?.type === "creation_card") {
        if (!row.content?.trim()) continue;
        const card: CreationCard = {
          type: "creation_card",
          creation_id: Number(row.creation_id),
          creation_type: String(row.creation_type || "note"),
          content: String(row.content).trim(),
          emotion_context: row.emotion_context,
          qi_line: row.qi_line,
          action_id: Number(row.action_id) || 0,
          season: row.season,
        };
        if (!Number.isFinite(card.creation_id)) continue;
        const key = cardKey(card);
        if (seen.has(key)) continue;
        seen.add(key);
        hydrated.push({
          id: uid("card"),
          kind: "card",
          card,
          at: typeof row.at === "number" ? row.at : Date.now(),
        });
        continue;
      }
      if (row?.type === "explore_drift") {
        const entries = row.found?.entries;
        const okSource =
          row.source === "web" ||
          row.source === "journal" ||
          row.source === "web_delegate";
        if (!okSource || !Array.isArray(entries) || entries.length === 0) continue;
        const card: ExploreCard = {
          type: "explore_drift",
          found: row.found,
          summary: String(row.summary || "").trim(),
          qi_line: row.qi_line,
          action_id: Number(row.action_id) || 0,
          season: row.season,
          curiosity: Number(row.curiosity) || 0,
          source: row.source,
          sandbox: String(row.sandbox || ""),
        };
        if (!Number.isFinite(card.action_id) || card.action_id <= 0) continue;
        const key = cardKey(card);
        if (seen.has(key)) continue;
        seen.add(key);
        hydrated.push({
          id: uid("card"),
          kind: "card",
          card,
          at: typeof row.at === "number" ? row.at : Date.now(),
        });
        continue;
      }
      if (row?.type === "assist_confirm_request") {
        const path = String(row.target_path || "").trim();
        if (!path) continue;
        const card: AssistConfirmCard = {
          type: "assist_confirm_request",
          target_path: path,
          summary: String(row.summary || "").trim(),
          qi_line: row.qi_line,
          action_id: row.action_id,
          kind: row.kind,
          confirm_mark: row.confirm_mark,
          confirm_label: row.confirm_label,
        };
        const key = cardKey(card);
        if (seen.has(key)) continue;
        seen.add(key);
        hydrated.push({
          id: uid("card"),
          kind: "card",
          card,
          at: typeof row.at === "number" ? row.at : Date.now(),
        });
      }
    }
    cards.value = hydrated;
  }

  const talkByDay = computed<TalkDayGroup[]>(() => {
    const items: TalkItem[] = [
      ...talk.value.map((m) => ({ ...m, kind: "text" as const })),
      ...cards.value,
    ].sort((a, b) => a.at - b.at);
    const groups = new Map<string, TalkDayGroup>();
    for (const m of items) {
      const key = dayKey(m.at);
      let g = groups.get(key);
      if (!g) {
        g = { key, label: dayLabel(m.at), messages: [] };
        groups.set(key, g);
      }
      g.messages.push(m);
    }
    return [...groups.values()];
  });

  const creationCards = computed(() =>
    cards.value.filter((c) => c.card.type === "creation_card")
  );
  const exploreCards = computed(() =>
    cards.value.filter((c) => c.card.type === "explore_drift")
  );
  /** 相处页：最近一条协助确认 */
  const pendingAssist = computed((): AssistConfirmCard | null => {
    for (let i = cards.value.length - 1; i >= 0; i--) {
      const item = cards.value[i];
      if (item.card.type === "assist_confirm_request") return item.card;
    }
    return null;
  });

  let typingTimer: number | null = null;
  let touchConsideredForTurn = false;
  let wired = false;
  /** 进行中的流式气泡 id（WS stream id → talk message id） */
  let activeStreamId: string | null = null;
  let activeStreamTalkId: string | null = null;
  /** client_id → 等待 ACK 的 timer */
  const pendingAckTimers = new Map<string, number>();

  function clearTypingTimer() {
    if (typingTimer != null) {
      window.clearTimeout(typingTimer);
      typingTimer = null;
    }
  }

  function armTypingTimeout() {
    clearTypingTimer();
    typingTimer = window.setTimeout(() => {
      typingTimer = null;
      if (!typing.value) return;
      typing.value = false;
      systemNotice.value = TIMEOUT_NOTICE;
    }, TYPING_TIMEOUT_MS);
  }

  function clearAckTimer(clientId: string) {
    const t = pendingAckTimers.get(clientId);
    if (t != null) {
      window.clearTimeout(t);
      pendingAckTimers.delete(clientId);
    }
  }

  function clearAllAckTimers() {
    for (const t of pendingAckTimers.values()) {
      window.clearTimeout(t);
    }
    pendingAckTimers.clear();
  }

  function armAckTimeout(clientId: string) {
    clearAckTimer(clientId);
    const timer = window.setTimeout(() => {
      pendingAckTimers.delete(clientId);
      applySystemNotice(DELIVERY_TIMEOUT_NOTICE);
    }, ACK_TIMEOUT_MS);
    pendingAckTimers.set(clientId, timer);
  }

  function applyMessageAck(payload: MessageAckPayload) {
    const id = String(payload?.client_id || "").trim();
    if (id) clearAckTimer(id);
    else clearAllAckTimers();
  }

  function setTyping(on: boolean) {
    typing.value = on;
    if (on) armTypingTimeout();
    else clearTypingTimer();
  }

  function applySystemNotice(payload: SystemNoticePayload) {
    systemNotice.value = payload;
    setTyping(false);
  }

  function dismissSystemNotice() {
    systemNotice.value = null;
  }

  function popLastMineIfMatch(original?: string) {
    const last = talk.value[talk.value.length - 1];
    if (!last || last.role !== "me") return;
    const orig = (original || "").trim();
    if (orig && last.text.trim() !== orig) return;
    talk.value = talk.value.slice(0, -1);
  }

  function requestRephrase() {
    if (!connected.value || !typing.value) return;
    systemNotice.value = null;
    qiWs.send({ type: "turn_control", payload: { action: "rephrase" } });
  }

  function requestStopSpeaking() {
    if (!connected.value || !typing.value) return;
    systemNotice.value = null;
    qiWs.send({ type: "turn_control", payload: { action: "stop" } });
  }

  function noteReplyStart() {
    if (touchConsideredForTurn) return;
    touchConsideredForTurn = true;
    replyEpoch.value += 1;
  }

  function appendTalk(role: "qi" | "me", text: string, tone?: string) {
    const t = text.trim();
    if (!t) return;
    const last = talk.value[talk.value.length - 1];
    if (
      last &&
      last.role === role &&
      last.text === t &&
      Date.now() - last.at < 5000
    ) {
      return;
    }
    talk.value.push({
      id: uid(role),
      role,
      text: t,
      at: Date.now(),
      tone,
    });
  }

  function applySpeechDelta(payload: SpeechStreamDeltaPayload) {
    const sid = String(payload?.id || "").trim();
    const delta = String(payload?.delta || "");
    if (!sid || !delta) return;
    noteReplyStart();
    setTyping(false);
    if (activeStreamId === sid && activeStreamTalkId) {
      const idx = talk.value.findIndex((m) => m.id === activeStreamTalkId);
      if (idx >= 0) {
        const cur = talk.value[idx];
        talk.value[idx] = { ...cur, text: cur.text + delta };
        speech.value = talk.value[idx].text;
        return;
      }
    }
    activeStreamId = sid;
    const mid = uid("qi");
    activeStreamTalkId = mid;
    talk.value.push({
      id: mid,
      role: "qi",
      text: delta,
      at: Date.now(),
    });
    speech.value = delta;
    speaking.value = true;
  }

  function applySpeechDone(payload: SpeechStreamDonePayload) {
    const sid = String(payload?.id || "").trim();
    const text = String(payload?.text || "").trim();
    noteReplyStart();
    setTyping(false);
    if (sid && activeStreamId === sid && activeStreamTalkId) {
      const idx = talk.value.findIndex((m) => m.id === activeStreamTalkId);
      if (idx >= 0) {
        const cur = talk.value[idx];
        talk.value[idx] = {
          ...cur,
          text: text || cur.text,
          tone: payload.tone || cur.tone,
        };
        speech.value = talk.value[idx].text;
      }
    } else if (text) {
      appendTalk("qi", text, payload.tone);
      speech.value = text;
    }
    activeStreamId = null;
    activeStreamTalkId = null;
    speaking.value = false;
  }

  function applySpeechRetract(payload: SpeechStreamRetractPayload) {
    const sid = String(payload?.id || "").trim();
    if (sid && activeStreamId === sid && activeStreamTalkId) {
      talk.value = talk.value.filter((m) => m.id !== activeStreamTalkId);
    } else if (activeStreamTalkId) {
      talk.value = talk.value.filter((m) => m.id !== activeStreamTalkId);
    }
    activeStreamId = null;
    activeStreamTalkId = null;
    speech.value = "";
    speaking.value = false;
  }

  function retractActiveStreamBubble() {
    if (!activeStreamTalkId) return;
    talk.value = talk.value.filter((m) => m.id !== activeStreamTalkId);
    activeStreamId = null;
    activeStreamTalkId = null;
    speech.value = "";
    speaking.value = false;
  }

  function applyHistory(messages: TalkMessage[], hasMore?: boolean) {
    const pendingMine =
      typing.value && talk.value.length
        ? talk.value.filter((m) => m.role === "me").slice(-1)
        : [];

    talk.value = messages
      .filter((m) => m.text?.trim())
      .map((m) => ({
        id: m.id || uid(m.role),
        role: m.role === "me" ? "me" : "qi",
        text: m.text.trim(),
        at: typeof m.at === "number" ? m.at : Date.now(),
        tone: m.tone,
      }));

    historyLoaded.value = true;
    if (typeof hasMore === "boolean") {
      historyHasMore.value = hasMore;
      historyExhausted.value = !hasMore;
    } else {
      historyHasMore.value = true;
      historyExhausted.value = false;
    }

    for (const m of pendingMine) {
      const already = talk.value.some(
        (t) => t.role === "me" && t.text === m.text
      );
      if (!already) talk.value.push(m);
    }
  }

  function applyHistoryPage(messages: TalkMessage[], hasMore: boolean) {
    historyLoadingOlder.value = false;
    historyHasMore.value = hasMore;
    if (!hasMore) historyExhausted.value = true;

    const incoming = (messages ?? [])
      .filter((m) => m.text?.trim())
      .map((m) => ({
        id: m.id || uid(m.role),
        role: (m.role === "me" ? "me" : "qi") as "qi" | "me",
        text: m.text.trim(),
        at: typeof m.at === "number" ? m.at : Date.now(),
        tone: m.tone,
      }));
    if (!incoming.length) {
      if (!hasMore) historyExhausted.value = true;
      historyPrependTick.value += 1;
      return;
    }
    const seen = new Set(talk.value.map((m) => m.id));
    const fresh = incoming.filter((m) => !seen.has(m.id));
    if (!fresh.length) {
      if (!hasMore) historyExhausted.value = true;
      historyPrependTick.value += 1;
      return;
    }
    talk.value = [...fresh, ...talk.value];
    historyPrependTick.value += 1;
  }

  function oldestDbMessageId(): number | null {
    for (const m of talk.value) {
      const match = /^db-(\d+)$/.exec(m.id);
      if (match) return Number(match[1]);
    }
    return null;
  }

  function requestHistoryOlder() {
    if (!connected.value || historyLoadingOlder.value || !historyHasMore.value) {
      return;
    }
    const beforeId = oldestDbMessageId();
    if (beforeId == null) {
      historyHasMore.value = false;
      historyExhausted.value = true;
      return;
    }
    historyLoadingOlder.value = true;
    qiWs.send({
      type: "command",
      payload: { text: "/history_before", before_id: beforeId },
    });
  }

  function applyJournal(entries: JournalEntry[]) {
    journal.value = (entries ?? [])
      .filter((e) => e.text?.trim())
      .map((e) => ({
        id: e.id || uid("j"),
        kind: e.kind || "独白",
        text: e.text.trim(),
        at: typeof e.at === "number" ? e.at : Date.now(),
      }));
  }

  function playAudio(data: string, mime = "audio/mpeg") {
    const audio = new Audio(`data:${mime};base64,${data}`);
    void audio.play().catch(() => {});
  }

  function send(text: string) {
    if (!connected.value) return;
    const value = text.trim();
    if (!value) return;
    touchConsideredForTurn = false;
    systemNotice.value = null;
    setTyping(true);
    speech.value = "";
    speaking.value = false;
    appendTalk("me", value);
    const clientId = uid("msg");
    armAckTimeout(clientId);
    qiWs.sendUserMessage(value, clientId);
  }

  function requestHistory() {
    qiWs.send({ type: "command", payload: { text: "/history" } });
  }

  function requestJournal() {
    qiWs.send({ type: "command", payload: { text: "/journal" } });
  }

  function requestTimeTraces() {
    qiWs.send({ type: "command", payload: { text: "/time_traces" } });
  }

  function requestReviewMemories() {
    qiWs.send({ type: "command", payload: { text: "/review_memories" } });
  }

  function requestActivityGlance() {
    qiWs.send({ type: "command", payload: { text: "/activity_glance" } });
  }

  function openSettings() {
    settingsOpen.value = true;
    settingsSaveOk.value = false;
    settingsSaveError.value = "";
    settingsProbeMessage.value = "";
    settingsProbeOk.value = false;
    requestSettingsLlm();
  }

  function closeSettings() {
    settingsOpen.value = false;
    settingsSaveOk.value = false;
    settingsSaveError.value = "";
    settingsProbeMessage.value = "";
    settingsProbeOk.value = false;
    settingsProbing.value = false;
  }

  function requestSettingsLlm() {
    qiWs.send({ type: "command", payload: { text: "/settings_llm" } });
  }

  function saveSettingsLlm(payload: {
    api_key?: string;
    base_url: string;
    model: string;
  }) {
    settingsSaving.value = true;
    settingsSaveOk.value = false;
    settingsSaveError.value = "";
    settingsProbeMessage.value = "";
    const body: {
      text: string;
      api_key?: string;
      base_url: string;
      model: string;
    } = {
      text: "/settings_llm_save",
      base_url: payload.base_url,
      model: payload.model,
    };
    if (payload.api_key !== undefined) {
      body.api_key = payload.api_key;
    }
    qiWs.send({ type: "command", payload: body });
  }

  function probeSettingsLlm() {
    settingsProbing.value = true;
    settingsProbeMessage.value = "";
    settingsProbeOk.value = false;
    qiWs.send({ type: "command", payload: { text: "/settings_llm_probe" } });
  }

  function requestWake() {
    if (!connected.value) return;
    qiWs.send({ type: "command", payload: { text: "/wake" } });
  }

  function onVis() {
    qiWs.setPresence(document.visibilityState === "visible");
  }

  watch(view, (next, prev) => {
    if (!connected.value) return;
    if (next === "presence" && prev !== "presence") {
      requestTimeTraces();
      requestActivityGlance();
    }
    if (next === "review" && prev !== "review") {
      requestReviewMemories();
    }
  });

  function connect() {
    if (!wired) {
      wired = true;
      qiWs.on("open", () => {
        connected.value = true;
        requestEmotionSnapshot();
        requestHistory();
        requestJournal();
        requestTimeTraces();
        requestReviewMemories();
        requestActivityGlance();
      });
      qiWs.on("close", () => {
        connected.value = false;
      });
      qiWs.on("typing", () => {
        setTyping(true);
        speaking.value = false;
        noteReplyStart();
      });
      qiWs.on("time_traces", (payload: TimeTracesPayload) => {
        const line = String(payload?.line || "").trim();
        timeTraceLine.value = line;
      });
      qiWs.on("activity_glance", (payload: ActivityGlancePayload) => {
        activityGlanceLine.value = String(payload?.line || "").trim();
      });
      qiWs.on("settings_llm", (payload: SettingsLlmPayload) => {
        settingsLlm.value = {
          has_key: Boolean(payload?.has_key),
          api_key_masked: String(payload?.api_key_masked || ""),
          base_url: String(payload?.base_url || ""),
          model: String(payload?.model || ""),
        };
      });
      qiWs.on("settings_llm_saved", (payload: SettingsLlmSavedPayload) => {
        settingsSaving.value = false;
        settingsLlm.value = {
          has_key: Boolean(payload?.has_key),
          api_key_masked: String(payload?.api_key_masked || ""),
          base_url: String(payload?.base_url || ""),
          model: String(payload?.model || ""),
        };
        if (payload?.ok) {
          settingsSaveOk.value = true;
          settingsSaveError.value = "";
          dismissSystemNotice();
        } else {
          settingsSaveOk.value = false;
          settingsSaveError.value =
            String(payload?.error || "").trim() || "保存失败，请再试一次。";
        }
      });
      qiWs.on("settings_llm_probe", (payload: SettingsLlmProbePayload) => {
        settingsProbing.value = false;
        settingsProbeOk.value = Boolean(payload?.ok);
        settingsProbeMessage.value =
          String(payload?.message || "").trim() ||
          (payload?.ok ? "通了。" : "没通，请再试一次。");
      });
      qiWs.on("review_memories", (payload: ReviewMemoriesPayload) => {
        const rows = Array.isArray(payload?.items) ? payload.items : [];
        reviewMemories.value = rows
          .map((r) => ({
            id: Number(r.id) || 0,
            content: String(r.content || "").trim(),
            strength: Number(r.strength) || 0,
            opacity: Number(r.opacity) || 0.32,
            fading: Boolean(r.fading),
            whisper: String(r.whisper || "").trim(),
            at: typeof r.at === "number" ? r.at : 0,
          }))
          .filter((r) => r.id && r.content);
      });
      qiWs.on("system_notice", (payload: SystemNoticePayload) => {
        if (!payload?.message?.trim()) return;
        clearAllAckTimers();
        applySystemNotice(payload);
      });
      qiWs.on("message_ack", (payload: MessageAckPayload) => {
        applyMessageAck(payload);
      });
      qiWs.on("turn_interrupted", (payload: TurnInterruptedPayload) => {
        setTyping(false);
        clearAllAckTimers();
        retractActiveStreamBubble();
        const orig = (payload?.original_text || "").trim();
        // 若刚发了打断白话，先拿掉那条；再拿掉原句气泡
        const last = talk.value[talk.value.length - 1];
        if (last?.role === "me") {
          talk.value = talk.value.slice(0, -1);
        }
        popLastMineIfMatch(orig);
        const pre = (payload?.prefill || "").trim();
        composerPrefill.value = pre;
      });
      qiWs.on("speech_delta", (payload: SpeechStreamDeltaPayload) => {
        applySpeechDelta(payload);
      });
      qiWs.on("speech_done", (payload: SpeechStreamDonePayload) => {
        applySpeechDone(payload);
      });
      qiWs.on("speech_retract", (payload: SpeechStreamRetractPayload) => {
        applySpeechRetract(payload);
      });
      qiWs.on("speech", (payload: SpeechPayload) => {
        noteReplyStart();
        setTyping(false);
        // 非流式整段到达时，清掉可能残留的流式半截
        if (activeStreamTalkId) {
          retractActiveStreamBubble();
        }
        speech.value = payload.text;
        appendTalk("qi", payload.text, payload.tone);
      });
      qiWs.on(
        "state",
        (payload: {
          avatar_state: AvatarState;
          season?: string;
          mode?: string;
          stasis?: boolean;
        }) => {
          applyAvatarState(payload.avatar_state, avatar);
          if (payload.season) season.value = payload.season;
          const stasis = Boolean(payload.stasis) || payload.mode === "stasis";
          if (payload.mode || stasis) {
            emotion.value = {
              ...emotion.value,
              mode: stasis ? "stasis" : payload.mode,
              stasis,
            };
            if (emotion.value.energy != null) {
              onEmotionUpdate(emotion.value);
            }
          }
        }
      );
      qiWs.on("emotion_update", (payload: EmotionSnapshot) => {
        const stasis =
          Boolean(payload.stasis) || payload.mode === "stasis" || false;
        emotion.value = {
          ...payload,
          mode: stasis ? "stasis" : payload.mode,
          stasis,
        };
        onEmotionUpdate(emotion.value);
      });
      qiWs.on(
        "wake_result",
        (payload: { ok?: boolean; mode?: string; reason?: string }) => {
          if (!payload?.ok) return;
          emotion.value = {
            ...emotion.value,
            stasis: false,
            mode: payload.mode || "ambient",
          };
        }
      );
      qiWs.on("audio", (payload: { data: string; mime?: string }) => {
        playAudio(payload.data, payload.mime);
      });
      qiWs.on(
        "history",
        (payload: {
          messages?: TalkMessage[];
          cards?: Array<(CreationCard | ExploreCard) & { at?: number }>;
          has_more?: boolean;
        }) => {
          applyHistory(payload?.messages ?? [], payload?.has_more);
          applyHistoryCards(payload?.cards ?? []);
        }
      );
      qiWs.on(
        "history_page",
        (payload: { messages?: TalkMessage[]; has_more?: boolean }) => {
          applyHistoryPage(
            payload?.messages ?? [],
            payload?.has_more !== false
          );
        }
      );
      qiWs.on("journal", (payload: { entries?: JournalEntry[] }) => {
        applyJournal(payload?.entries ?? []);
      });
      qiWs.on("journal_entry", (entry: JournalEntry) => {
        if (!entry?.text?.trim()) return;
        journal.value.unshift({
          id: entry.id || uid("j"),
          kind: entry.kind || "独白",
          text: entry.text.trim(),
          at: typeof entry.at === "number" ? entry.at : Date.now(),
        });
      });
      qiWs.on("action", (payload: ActionPayload) => {
        if (payload?.type === "creation_card") {
          appendCard(payload);
          return;
        }
        if (payload?.type === "explore_drift") {
          const entries = payload.found?.entries;
          const okSource =
            payload.source === "web" ||
            payload.source === "journal" ||
            payload.source === "web_delegate";
          if (okSource && Array.isArray(entries) && entries.length > 0) {
            appendCard(payload);
          }
          return;
        }
        if (payload?.type === "assist_confirm_request") {
          // open/disk/write：确认只走谈区正文 + 口头，不叠卡（与 brain_delivery 一致）
          if (
            payload.kind === "open" ||
            payload.kind === "disk" ||
            payload.kind === "write" ||
            payload.kind === "together"
          )
            return;
          if (String(payload.target_path || "").trim()) {
            appendCard(payload);
          }
        }
      });
    }

    document.addEventListener("visibilitychange", onVis);
    qiWs.connect();
  }

  function disconnect() {
    document.removeEventListener("visibilitychange", onVis);
    clearTypingTimer();
    clearAllAckTimers();
    qiWs.disconnect();
  }

  async function refreshHistory() {
    requestHistory();
  }

  const inStasis = computed(
    () => mode.value === "stasis" || Boolean(emotion.value.stasis)
  );

  /** 形象旁真状态短旁白（非 speech） */
  const presenceStatus = computed(() => {
    if (typing.value) return "正在回你";
    if (avatar.value.posture === "thinking") return "在想";
    if (inStasis.value || mode.value === "stasis") return "睡着了";
    if (mode.value === "dreaming") return "在做梦";
    if (mode.value === "solitary") return "自己待着";
    return "在这儿";
  });

  return {
    view,
    connected,
    typing,
    speech,
    speaking,
    replyEpoch,
    systemNotice,
    dismissSystemNotice,
    composerPrefill,
    requestRephrase,
    requestStopSpeaking,
    season,
    emotion,
    avatar,
    mode,
    inStasis,
    presenceStatus,
    timeTraceLine,
    activityGlanceLine,
    settingsOpen,
    settingsLlm,
    settingsSaving,
    settingsSaveError,
    settingsSaveOk,
    settingsProbing,
    settingsProbeMessage,
    settingsProbeOk,
    openSettings,
    closeSettings,
    requestSettingsLlm,
    saveSettingsLlm,
    probeSettingsLlm,
    reviewMemories,
    talk,
    talkByDay,
    creationCards,
    exploreCards,
    pendingAssist,
    journal,
    historyLoaded,
    historyExhausted,
    historyLoadingOlder,
    historyPrependTick,
    requestHistoryOlder,
    send,
    connect,
    disconnect,
    refreshHistory,
    requestWake,
    requestTimeTraces,
    requestReviewMemories,
    requestActivityGlance,
  };
}

/** 单例：App 与子树共享同一会话状态 */
export function useQi() {
  if (!singleton) singleton = createQi();
  return singleton;
}
