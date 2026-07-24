/**
 * WS 接线 + 消息 / 历史状态（黄昏的枝 §七）。
 * 「谈」：连接后通过 /history 拉取 SQLite 全量记录，本轮继续 append。
 * 「忆」：连接后通过 /journal 拉取独白 / 梦 / 第一次；无则诚实空占位。
 */

import { computed, ref } from "vue";
import { useEmotion } from "./useEmotion";
import type {
  AvatarState,
  EmotionSnapshot,
  JournalEntry,
  QiView,
  SpeechPayload,
  TalkMessage,
} from "../types";
import { qiWs } from "../ws";

function uid(prefix: string) {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
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
  messages: TalkMessage[];
};

let singleton: ReturnType<typeof createQi> | null = null;

function createQi() {
  const { onEmotionUpdate, requestEmotionSnapshot } = useEmotion();

  const view = ref<QiView>("still");
  const connected = ref(false);
  const typing = ref(false);
  const speech = ref("");
  const speaking = ref(false);
  const replyEpoch = ref(0);
  const season = ref("spring");
  const emotion = ref<EmotionSnapshot>({ mode: "awake", description: "" });
  const avatar = ref<AvatarState>({
    posture: "idle",
    expression: "neutral",
    effect: "none",
  });

  /** 对话历史（启动后由 /history 灌入） */
  const talk = ref<TalkMessage[]>([]);
  const historyLoaded = ref(false);
  /** 内在日记（启动后由 /journal 灌入；库空则保持空） */
  const journal = ref<JournalEntry[]>([]);

  const mode = computed(
    () => emotion.value.mode || avatar.value.posture || "awake"
  );

  const talkByDay = computed<TalkDayGroup[]>(() => {
    const groups = new Map<string, TalkDayGroup>();
    for (const m of talk.value) {
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

  let emotionPoll: number | null = null;
  let touchConsideredForTurn = false;
  let wired = false;

  function noteReplyStart() {
    if (touchConsideredForTurn) return;
    touchConsideredForTurn = true;
    replyEpoch.value += 1;
  }

  function appendTalk(role: "qi" | "me", text: string, tone?: string) {
    const t = text.trim();
    if (!t) return;
    // 避免 history 与本轮 speech 重复叠一条
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
    const value = text.trim();
    if (!value) return;
    touchConsideredForTurn = false;
    typing.value = true;
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
        typing.value = true;
        speaking.value = false;
        noteReplyStart();
      });
      qiWs.on("speech", (payload: SpeechPayload) => {
        noteReplyStart();
        typing.value = false;
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
        }) => {
          avatar.value = payload.avatar_state;
          if (payload.season) season.value = payload.season;
          if (payload.mode) {
            emotion.value = { ...emotion.value, mode: payload.mode };
            if (emotion.value.energy != null) {
              onEmotionUpdate(emotion.value);
            }
          }
        }
      );
      qiWs.on("emotion_update", (payload: EmotionSnapshot) => {
        emotion.value = payload;
        onEmotionUpdate(payload);
      });
      qiWs.on("audio", (payload: { data: string; mime?: string }) => {
        playAudio(payload.data, payload.mime);
      });
      qiWs.on("history", (payload: { messages?: TalkMessage[] }) => {
        applyHistory(payload?.messages ?? []);
      });
      qiWs.on("journal", (payload: { entries?: JournalEntry[] }) => {
        applyJournal(payload?.entries ?? []);
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
    if (emotionPoll != null) {
      clearInterval(emotionPoll);
      emotionPoll = null;
    }
    qiWs.disconnect();
  }

  /** 主动再拉一次全量历史（重连后也会自动拉） */
  async function refreshHistory() {
    requestHistory();
  }

  return {
    view,
    connected,
    typing,
    speech,
    speaking,
    replyEpoch,
    season,
    emotion,
    avatar,
    mode,
    talk,
    talkByDay,
    journal,
    historyLoaded,
    send,
    connect,
    disconnect,
    refreshHistory,
  };
}

/** 单例：App 与子树共享同一会话状态 */
export function useQi() {
  if (!singleton) singleton = createQi();
  return singleton;
}
