/**
 * 输出时钟（口型能量入口）· 无 TTS 文字→viseme
 *
 * 今日：`speech_delta` / 非流式 `speech` 喂入文字（见 useQi → PresenceVrm → pulseSpeak）。
 * 日后 TTS / 音频分析：改接同一 `pulse()` / `clear()`；勿把口型写死在某一 WS 事件名上。
 *
 * 平滑参考：AIRI / wLipSync 的 attack·release + 双口型轻混（无音频时用韵母粗映射）。
 * 观感目标：轻开合、少露齿；大张口只留给语气词。
 * 本模块不发声、不推音频。
 */

export const MOUTH_SHAPES = ["aa", "ih", "ou", "ee", "oh"] as const;
export type MouthShape = (typeof MOUTH_SHAPES)[number];

export type SpeakPulseOpts = {
  /** 本段输出文字（流式 delta 或整段）；驱动韵母粗映射 */
  text?: string;
  /** 0..1，预留给日后 TTS 能量；今日可省略 */
  energy?: number;
};

export type SpeakClockSample = {
  active: boolean;
  /** 平滑后的口型权重 0..1（尚未做全身取景放大） */
  weights: Record<MouthShape, number>;
};

const ATTACK = 14;
const RELEASE = 15;
/** 目标权重上限（再经全身 amp） */
const CAP = 0.52;
const RUNNER_RATIO = 0.32;
/** 每字口型时长（秒） */
const CHAR_HOLD_SEC = 0.13;
const REST_HOLD_SEC = 0.07;
const QUEUE_MAX = 40;

/** 轻唇形轮换（无把握汉字用这个，避免全挤 ee 或乱开 aa） */
const SOFT_CYCLE: MouthShape[] = ["ih", "ee", "ou", "ee", "ih", "ou"];

type VisemeEvent = {
  shape: MouthShape | null;
  remain: number;
  /** 该事件目标强度倍率（语气词可略高） */
  gain: number;
};

function emptyWeights(): Record<MouthShape, number> {
  return { aa: 0, ih: 0, ou: 0, ee: 0, oh: 0 };
}

/** 仅语气词 / 明显开口 → aa/oh；日常字不进此表（防张太大） */
const OPEN_CHARS: Record<string, MouthShape> = {
  啊: "aa",
  阿: "aa",
  呀: "aa",
  哇: "aa",
  哈: "aa",
  哦: "oh",
  喔: "oh",
  噢: "oh",
  哟: "oh",
};

/** 常见闭口/圆唇倾向 */
const ROUND_CHARS: Record<string, MouthShape> = {
  嗯: "ou",
  唔: "ou",
  呜: "ou",
  不: "ou",
  有: "ou",
  无: "ou",
  么: "ou",
  都: "ou",
  口: "ou",
  我: "ou",
};

/** 常见扁唇 / i e */
const FLAT_CHARS: Record<string, MouthShape> = {
  咦: "ih",
  嘻: "ih",
  你: "ih",
  里: "ih",
  意: "ih",
  一: "ih",
  以: "ih",
  己: "ih",
  起: "ih",
  诶: "ee",
  欸: "ee",
  耶: "ee",
  也: "ee",
  夜: "ee",
  些: "ee",
  别: "ee",
  且: "ee",
  的: "ee",
  了: "ee",
  着: "ee",
  呢: "ee",
};

function latinViseme(ch: string): MouthShape | null {
  const c = ch.toLowerCase();
  if ("aáà".includes(c)) return "aa";
  if ("eéè".includes(c)) return "ee";
  if ("iíìy".includes(c)) return "ih";
  if ("oóò".includes(c)) return "oh";
  if ("uúùvü".includes(c)) return "ou";
  return null;
}

function isRestChar(ch: string): boolean {
  return /[\s\p{P}\p{S}\d]/u.test(ch);
}

/**
 * 韵母粗映射：语气词才大开；其余偏轻唇形。
 */
export function vowelVisemeFromChar(ch: string): {
  shape: MouthShape | null;
  gain: number;
} {
  if (!ch || isRestChar(ch)) return { shape: null, gain: 0 };
  if (OPEN_CHARS[ch]) return { shape: OPEN_CHARS[ch]!, gain: 0.85 };
  if (ROUND_CHARS[ch]) return { shape: ROUND_CHARS[ch]!, gain: 0.7 };
  if (FLAT_CHARS[ch]) return { shape: FLAT_CHARS[ch]!, gain: 0.65 };
  const latin = latinViseme(ch);
  if (latin) {
    const gain = latin === "aa" || latin === "oh" ? 0.55 : 0.7;
    return { shape: latin, gain };
  }
  if (/[\u4e00-\u9fff]/.test(ch)) {
    const idx = (ch.codePointAt(0) ?? 0) % SOFT_CYCLE.length;
    return { shape: SOFT_CYCLE[idx]!, gain: 0.68 };
  }
  return { shape: null, gain: 0 };
}

export function createSpeakClock() {
  const smooth = emptyWeights();
  const queue: VisemeEvent[] = [];
  let current: VisemeEvent | null = null;

  function enqueueChar(ch: string) {
    const { shape, gain } = vowelVisemeFromChar(ch);
    if (shape == null) {
      queue.push({ shape: null, remain: REST_HOLD_SEC, gain: 0 });
    } else {
      const hold =
        shape === "aa" || shape === "oh" ? CHAR_HOLD_SEC * 0.9 : CHAR_HOLD_SEC;
      queue.push({ shape, remain: hold, gain });
    }
    while (queue.length > QUEUE_MAX) queue.shift();
  }

  function advanceQueue(dt: number) {
    let left = dt;
    while (left > 1e-6) {
      if (!current) {
        current = queue.shift() ?? null;
        if (!current) break;
      }
      const take = Math.min(left, current.remain);
      current.remain -= take;
      left -= take;
      if (current.remain <= 1e-6) current = null;
    }
  }

  function targetsFromCurrent(): Record<MouthShape, number> {
    const t = emptyWeights();
    if (!current?.shape) return t;
    const winner = current.shape;
    const g = current.gain;
    let main = CAP * g;
    // aa/oh 压一档，但保留可辨认
    if (winner === "aa" || winner === "oh") main *= 0.62;
    t[winner] = main;
    const runner: MouthShape =
      winner === "aa"
        ? "ee"
        : winner === "oh"
          ? "ou"
          : winner === "ee"
            ? "ih"
            : winner === "ih"
              ? "ee"
              : "ee";
    if (runner !== winner) t[runner] = main * RUNNER_RATIO;
    return t;
  }

  return {
    pulse(opts?: SpeakPulseOpts) {
      const text = opts?.text ?? "";
      if (text) {
        for (const ch of text) enqueueChar(ch);
        return;
      }
      const bump = opts?.energy ?? 0.55;
      if (bump > 0.05) {
        queue.push({ shape: "ee", remain: CHAR_HOLD_SEC, gain: bump });
        queue.push({ shape: "ih", remain: CHAR_HOLD_SEC, gain: bump * 0.9 });
        while (queue.length > QUEUE_MAX) queue.shift();
      }
    },

    clear() {
      queue.length = 0;
      current = null;
      for (const k of MOUTH_SHAPES) smooth[k] = 0;
    },

    tick(deltaSec: number): SpeakClockSample {
      const dt = Math.max(0, deltaSec);
      advanceQueue(dt);
      const target = targetsFromCurrent();
      for (const k of MOUTH_SHAPES) {
        const from = smooth[k];
        const to = target[k];
        const rate = 1 - Math.exp(-(to > from ? ATTACK : RELEASE) * dt);
        const next = from + (to - from) * rate;
        smooth[k] = next < 0.008 ? 0 : next;
      }
      const active =
        MOUTH_SHAPES.some((k) => smooth[k] > 0.015) ||
        queue.length > 0 ||
        !!current;
      return { active, weights: { ...smooth } };
    },

    get active() {
      return (
        MOUTH_SHAPES.some((k) => smooth[k] > 0.015) ||
        queue.length > 0 ||
        !!current
      );
    },
  };
}

export type SpeakClock = ReturnType<typeof createSpeakClock>;
