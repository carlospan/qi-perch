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
