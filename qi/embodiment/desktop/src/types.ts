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

/** 后端 action 三种 payload；谈区渲染 creation_card + 外部 explore_drift */
export type ActionPayload =
  | CreationCard
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

export type ServerMessage =
  | { type: "speech"; payload: SpeechPayload }
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
  | { type: "emotion_update"; payload: EmotionSnapshot }
  | { type: "ping"; payload: { ts: number } }
  | { type: "audio"; payload: { data: string; mime?: string } }
  | {
      type: "history";
      payload: {
        messages: TalkMessage[];
        /** 已分享创作卡回灌（可选；旧后端无此字段） */
        cards?: Array<CreationCard & { at?: number }>;
      };
    }
  | { type: "journal"; payload: { entries: JournalEntry[] } }
  | { type: "journal_entry"; payload: JournalEntry }
  | { type: "wake_result"; payload: { ok: boolean; reason?: string; mode?: string } }
  | { type: "action"; payload: ActionPayload };

/** 谈区时间线条目：文本投影带 kind:"text"；卡片带 kind:"card" */
export type TalkCardItem = {
  id: string;
  kind: "card";
  card: CreationCard | ExploreCard;
  at: number;
};
export type TalkItem = (TalkMessage & { kind: "text" }) | TalkCardItem;

export type ClientMessage =
  | { type: "user_message"; payload: { text: string } }
  | { type: "presence"; payload: { online: boolean } }
  | { type: "pong"; payload: { ts: number } }
  | { type: "command"; payload: { text: string } };

/** 静 / 谈 / 忆 */
export type QiView = "still" | "talk" | "journal";

/** 「谈」会话消息（来自 /history 最近约 200 条 + 本轮追加） */
export type TalkMessage = {
  id: string;
  role: "qi" | "me";
  text: string;
  at: number;
  tone?: string;
};

/** 「忆」日记条目（连上后经 /journal 从后端拉） */
export type JournalEntry = {
  id: string;
  kind: "梦" | "独白" | "第一次" | string;
  text: string;
  at: number;
};
