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
  | { type: "history"; payload: { messages: TalkMessage[] } }
  | { type: "journal"; payload: { entries: JournalEntry[] } }
  | { type: "journal_entry"; payload: JournalEntry }
  | { type: "wake_result"; payload: { ok: boolean; reason?: string; mode?: string } };

export type ClientMessage =
  | { type: "user_message"; payload: { text: string } }
  | { type: "presence"; payload: { online: boolean } }
  | { type: "pong"; payload: { ts: number } }
  | { type: "command"; payload: { text: string } };

/** 静 / 谈 / 忆 */
export type QiView = "still" | "talk" | "journal";

/** 「谈」会话消息（来自 SQLite 全量 + 本轮追加） */
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
