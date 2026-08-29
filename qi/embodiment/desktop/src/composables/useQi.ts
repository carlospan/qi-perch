/**
 * WS 接线 + 消息 / 历史状态。
 * 「相处」：/history 灌对话与创作·见闻卡；本轮继续 append。
 * 「回顾」：创作 / 见闻归档。
 * 「内在」：/journal 灌独白 / 梦 / 第一次；无则诚实空占位。
 */

import { computed, ref } from "vue";
import { useEmotion } from "./useEmotion";
import type {
  ActionPayload,
  AssistConfirmCard,
  AvatarState,
  CreationCard,
  EmotionSnapshot,
  ExploreCard,
  JournalEntry,
  QiView,
  SpeechPayload,
  SpeechStreamDeltaPayload,
  SpeechStreamDonePayload,
  SpeechStreamRetractPayload,
  SystemNoticePayload,
  TalkCardItem,
  TalkItem,
  TalkMessage,
  TurnInterruptedPayload,
} from "../types";
import { qiWs } from "../ws";

/** 与 HITL：busy 约 60s 强制解锁 */
const TYPING_TIMEOUT_MS = 60_000;

const TIMEOUT_NOTICE: SystemNoticePayload = {
  kind: "timeout",
  message: "等太久了，先解开输入。若稍后她仍回了，气泡仍会显示。",
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
  /** 内在日记（启动后由 /journal 灌入；库空则保持空） */
  const journal = ref<JournalEntry[]>([]);

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

  let emotionPoll: number | null = null;
  let typingTimer: number | null = null;
  let touchConsideredForTurn = false;
  let wired = false;
  /** 进行中的流式气泡 id（WS stream id → talk message id） */
  let activeStreamId: string | null = null;
  let activeStreamTalkId: string | null = null;

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
    requestEmotionSnapshot();
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

  function applyHistory(messages: TalkMessage[]) {
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

    for (const m of pendingMine) {
      const already = talk.value.some(
        (t) => t.role === "me" && t.text === m.text
      );
      if (!already) talk.value.push(m);
    }
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
    qiWs.sendUserMessage(value);
  }

  function requestHistory() {
    qiWs.send({ type: "command", payload: { text: "/history" } });
  }

  function requestJournal() {
    qiWs.send({ type: "command", payload: { text: "/journal" } });
  }

  function requestWake() {
    if (!connected.value) return;
    qiWs.send({ type: "command", payload: { text: "/wake" } });
  }

  function onVis() {
    qiWs.setPresence(document.visibilityState === "visible");
  }

  function connect() {
    if (!wired) {
      wired = true;
      qiWs.on("open", () => {
        connected.value = true;
        requestEmotionSnapshot();
        requestHistory();
        requestJournal();
      });
      qiWs.on("close", () => {
        connected.value = false;
      });
      qiWs.on("typing", () => {
        setTyping(true);
        speaking.value = false;
        noteReplyStart();
      });
      qiWs.on("system_notice", (payload: SystemNoticePayload) => {
        if (!payload?.message?.trim()) return;
        applySystemNotice(payload);
      });
      qiWs.on("turn_interrupted", (payload: TurnInterruptedPayload) => {
        setTyping(false);
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
        requestEmotionSnapshot();
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
          requestEmotionSnapshot();
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
        }) => {
          applyHistory(payload?.messages ?? []);
          applyHistoryCards(payload?.cards ?? []);
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

    if (emotionPoll == null) {
      emotionPoll = window.setInterval(() => {
        if (connected.value) requestEmotionSnapshot();
      }, 8000);
    }
  }

  function disconnect() {
    document.removeEventListener("visibilitychange", onVis);
    clearTypingTimer();
    if (emotionPoll != null) {
      clearInterval(emotionPoll);
      emotionPoll = null;
    }
    qiWs.disconnect();
  }

  async function refreshHistory() {
    requestHistory();
  }

  const inStasis = computed(
    () => mode.value === "stasis" || Boolean(emotion.value.stasis)
  );

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
    talk,
    talkByDay,
    creationCards,
    exploreCards,
    pendingAssist,
    journal,
    historyLoaded,
    send,
    connect,
    disconnect,
    refreshHistory,
    requestWake,
  };
}

/** 单例：App 与子树共享同一会话状态 */
export function useQi() {
  if (!singleton) singleton = createQi();
  return singleton;
}
