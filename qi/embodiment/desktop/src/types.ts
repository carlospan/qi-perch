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
  | { type: "state"; payload: { avatar_state: AvatarState } }
  | { type: "typing"; payload: Record<string, never> }
  | { type: "emotion_update"; payload: EmotionSnapshot }
  | { type: "ping"; payload: { ts: number } }
  | { type: "audio"; payload: { data: string; mime?: string } };

export type ClientMessage =
  | { type: "user_message"; payload: { text: string } }
  | { type: "presence"; payload: { online: boolean } }
  | { type: "pong"; payload: { ts: number } }
  | { type: "command"; payload: { text: string } };

/** 静 / 谈 / 忆 */
export type QiView = "still" | "talk" | "journal";

/** 「谈」会话消息（第一期：仅内存累积本次会话） */
export type TalkMessage = {
  id: string;
  role: "qi" | "me";
  text: string;
  at: number;
  tone?: string;
};

/** 「忆」日记条目（第二期由后端拉；第一期可为空） */
export type JournalEntry = {
  id: string;
  kind: "梦" | "独白" | "第一次" | string;
  text: string;
  at: number;
};
