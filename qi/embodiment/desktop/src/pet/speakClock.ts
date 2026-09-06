/**
 * 输出时钟（口型能量入口）
 *
 * 今日：由 `speech_delta` / 非流式 `speech` 脉冲驱动（见 useQi → PresenceVrm → pulseSpeak）。
 * 日后 TTS 句级分片：不要新造口型通道，改接到同一 `pulse()` / `clear()`；
 * 勿把口型逻辑写死在某一类 WS 事件名上。
 *
 * 本模块不发声、不推音频。
 */

export const MOUTH_SHAPES = ["aa", "ih", "ou", "ee", "oh"] as const;
export type MouthShape = (typeof MOUTH_SHAPES)[number];

export type SpeakPulseOpts = {
  /** 0..1，默认约 0.85 */
  energy?: number;
};

export type SpeakClockSample = {
  energy: number;
  shape: MouthShape;
  active: boolean;
};

/** 能量衰减（每秒）；略快于常见出字间隔，间隙会合嘴 */
const DECAY_PER_SEC = 2.8;
const ACTIVE_EPS = 0.04;

export function createSpeakClock() {
  let energy = 0;
  let shapeIdx = 0;

  return {
    /**
     * 有「输出片段」到达时调用（文字 delta 或未来音频分片）。
     */
    pulse(opts?: SpeakPulseOpts) {
      const bump = opts?.energy ?? 0.85;
      energy = Math.min(1, Math.max(energy, bump));
      shapeIdx = (shapeIdx + 1) % MOUTH_SHAPES.length;
    },

    /** 打断 / 收回：立刻闭嘴 */
    clear() {
      energy = 0;
    },

    /**
     * 每帧调用；返回当前口型采样。
     */
    tick(deltaSec: number): SpeakClockSample {
      const dt = Math.max(0, deltaSec);
      energy = Math.max(0, energy - DECAY_PER_SEC * dt);
      const active = energy > ACTIVE_EPS;
      return {
        energy,
        shape: MOUTH_SHAPES[shapeIdx]!,
        active,
      };
    },

    get energy() {
      return energy;
    },

    get active() {
      return energy > ACTIVE_EPS;
    },
  };
}

export type SpeakClock = ReturnType<typeof createSpeakClock>;
