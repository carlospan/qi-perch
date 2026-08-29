export type AvatarState = {
  posture: string;
  expression: string;
  effect: string;
};

export type EmotionSnapshot = {
  energy?: number;
  valence?: number;
  arousal?: number;
  security?: number;
  curiosity?: number;
  attachment?: number;
  mode?: string;
  stasis?: boolean;
  description?: string;
  stage?: string;
};

export type SpeechPayload = {
  text: string;
  emotion: string;
  tone: string;
};

/** share 递出的创作卡片（对齐 qi/action/share.py） */
export type CreationCard = {
  type: "creation_card";
  creation_id: number;
  creation_type: string;
  content: string;
  emotion_context?: unknown;
  qi_line?: string;
  action_id: number;
  season?: string;
};

export type ExploreHit = { title: string; snippet?: string; url?: string };
export type ExploreFound = {
  entries: ExploreHit[];
  source: string; // "web" | sandbox path
  query?: string;
};

/** 栖外部探索的见闻卡片（对齐 qi/action/explore.py drift 返回） */
export type ExploreCard = {
  type: "explore_drift";
  found: ExploreFound | null;
  summary: string;
  qi_line?: string | null;
  action_id: number;
  season?: string;
  curiosity: number;
  source: string; // "web"
  sandbox: string;
};

/** assist / open：确认请求（对齐 assist/open _confirm_gate） */
export type AssistConfirmCard = {
  type: "assist_confirm_request";
  target_path: string;
  summary: string;
  qi_line?: string | null;
  speak?: boolean;
  outcome?: string;
  needs_confirmation?: boolean;
  action_id?: number;
  kind?: string;
  confirm_mark?: string;
  confirm_label?: string;
};

/** 后端 action payload；回顾区渲染 creation / explore；相处区渲染 assist 确认 */
export type ActionPayload =
  | CreationCard
  | AssistConfirmCard
  | {
      type: "tend_mark";
      occasion: string;
      summary: string;
      action_id: number;
      season?: string;
      speak: boolean;
      qi_line?: string | null;
    }
  | {
      type: "explore_drift";
      found: ExploreFound | null;
      summary: string;
      qi_line?: string | null;
      speak?: boolean;
      action_id: number;
      season?: string;
      curiosity: number;
      source: string; // "web" | "sandbox"
      sandbox: string;
    };

export type SystemNoticePayload = {
  kind:
    | "missing_key"
    | "unreachable"
    | "empty"
    | "timeout"
    | "turn_busy"
    | "queue_full"
    | "delivery_timeout";
  message: string;
  action?: "open_settings" | null;
};

export type MessageAckPayload = {
  client_id: string;
};

export type TurnInterruptedPayload = {
  action: "rephrase" | "stop";
  original_text?: string;
  prefill?: string;
};

export type SpeechStreamDeltaPayload = {
  id: string;
  delta: string;
};

export type SpeechStreamDonePayload = {
  id: string;
  text: string;
  emotion: string;
  tone: string;
};

export type SpeechStreamRetractPayload = {
  id: string;
};

/** 方向 D：时间的痕迹（非 speech） */
export type TimeTracesPayload = {
  line: string;
  remembered?: number;
  fading?: number;
  days_known?: number;
};

/** 方向 D：回顾 · 记忆褪色条目 */
export type ReviewMemoryItem = {
  id: number;
  content: string;
  strength: number;
  opacity: number;
  fading: boolean;
  whisper: string;
  at: number;
};

export type ReviewMemoriesPayload = {
  items: ReviewMemoryItem[];
};

export type ServerMessage =
  | { type: "speech"; payload: SpeechPayload }
  | { type: "speech_delta"; payload: SpeechStreamDeltaPayload }
  | { type: "speech_done"; payload: SpeechStreamDonePayload }
  | { type: "speech_retract"; payload: SpeechStreamRetractPayload }
  | { type: "message_ack"; payload: MessageAckPayload }
  | {
      type: "state";
      payload: {
        avatar_state: AvatarState;
        season?: string;
        mode?: string;
        stasis?: boolean;
      };
    }
  | { type: "typing"; payload: Record<string, never> }
  | { type: "system_notice"; payload: SystemNoticePayload }
  | { type: "turn_interrupted"; payload: TurnInterruptedPayload }
  | { type: "presence"; payload: { online: boolean } }
  | { type: "emotion_update"; payload: EmotionSnapshot }
  | { type: "time_traces"; payload: TimeTracesPayload }
  | { type: "review_memories"; payload: ReviewMemoriesPayload }
  | { type: "ping"; payload: { ts: number } }
  | { type: "audio"; payload: { data: string; mime?: string } }
  | {
      type: "history";
      payload: {
        messages: TalkMessage[];
        /** 创作卡 + 见闻卡回灌（可选；旧后端无此字段） */
        cards?: Array<(CreationCard | ExploreCard | AssistConfirmCard) & { at?: number }>;
        has_more?: boolean;
      };
    }
  | {
      type: "history_page";
      payload: {
        messages: TalkMessage[];
        has_more: boolean;
        before_id?: number;
      };
    }
  | { type: "journal"; payload: { entries: JournalEntry[] } }
  | { type: "journal_entry"; payload: JournalEntry }
  | { type: "wake_result"; payload: { ok: boolean; reason?: string; mode?: string } }
  | { type: "action"; payload: ActionPayload };

/** 回顾时间线条目：文本投影带 kind:"text"；卡片带 kind:"card" */
export type TalkCardItem = {
  id: string;
  kind: "card";
  card: CreationCard | ExploreCard | AssistConfirmCard;
  at: number;
};
export type TalkItem = (TalkMessage & { kind: "text" }) | TalkCardItem;

export type ClientMessage =
  | { type: "user_message"; payload: { text: string; client_id?: string } }
  | { type: "turn_control"; payload: { action: "rephrase" | "stop" } }
  | { type: "presence"; payload: { online: boolean } }
  | { type: "pong"; payload: { ts: number } }
  | {
      type: "command";
      payload: { text: string; before_id?: number };
    };

/** 相处 / 回顾 / 内在 */
export type QiView = "presence" | "review" | "inner" | "state";

/** 「回顾 · 对话」筛选用会话消息（/history 约 200 条 + 本轮追加） */
export type TalkMessage = {
  id: string;
  role: "qi" | "me";
  text: string;
  at: number;
  tone?: string;
};

/** 「内在」日记条目（连上后经 /journal 从后端拉） */
export type JournalEntry = {
  id: string;
  kind: "梦" | "独白" | "第一次" | string;
  text: string;
  at: number;
};
