import type { EmotionSnapshot } from "../types";
import { qiWs } from "../ws";

/** 情绪 → 氛围 CSS 变量。公式见 docs/dev/主界面设计-黄昏的枝.md §五，照抄勿改。 */

function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v));
}

export type AtmosphereVars = {
  warmT: number;
  glowA: number;
  moteA: number;
  vigA: number;
  sat: number;
  bright: number;
  mistDurSec: number;
};

export function emotionToAtmosphere(e: EmotionSnapshot): AtmosphereVars {
  const energy = e.energy ?? 0.5;
  const valence = e.valence ?? 0;
  const arousal = e.arousal ?? 0.3;
  const security = e.security ?? 0.5;
  const curiosity = e.curiosity ?? 0.4;
  const attachment = e.attachment ?? 0.5;

  // valence → 冷暖；依恋并入光晕暖度（高依恋略偏暖）
  const valenceWarm = clamp((valence + 1) / 2, 0, 1);
  const warmT = clamp(valenceWarm + (attachment - 0.5) * 0.2, 0, 1);

  let bright = 0.86 + energy * 0.28;
  // dreaming：场景再压暗一档
  if (e.mode === "dreaming") {
    bright *= 0.82;
  }

  return {
    warmT,
    glowA: 0.3 + energy * 0.45,
    moteA: 0.12 + curiosity * 0.6,
    vigA: 0.55 - security * 0.25,
    sat: 0.8 + arousal * 0.5,
    bright,
    mistDurSec: 58 - arousal * 32,
  };
}

/** 写入 :root；SceneView 内 transition 1.5~2.2s。 */
export function applyAtmosphere(vars: AtmosphereVars): void {
  const r = document.documentElement.style;
  r.setProperty("--warm-t", vars.warmT.toFixed(3));
  r.setProperty("--glow-a", vars.glowA.toFixed(3));
  r.setProperty("--mote-a", vars.moteA.toFixed(3));
  r.setProperty("--vig-a", vars.vigA.toFixed(3));
  r.setProperty("--sat", vars.sat.toFixed(3));
  r.setProperty("--bright", vars.bright.toFixed(3));
  r.setProperty("--mist-dur", `${vars.mistDurSec.toFixed(1)}s`);
}

export function applyEmotionSnapshot(e: EmotionSnapshot): AtmosphereVars {
  const vars = emotionToAtmosphere(e);
  applyAtmosphere(vars);
  return vars;
}

/**
 * emotion_update → 氛围。
 * 连上拉一次 /state；其后靠后端事件推送（P0 情绪事件推送）。
 */
export function useEmotion() {
  function onEmotionUpdate(payload: EmotionSnapshot) {
    applyEmotionSnapshot(payload);
  }

  function requestEmotionSnapshot() {
    qiWs.send({ type: "command", payload: { text: "/state" } });
  }

  return { onEmotionUpdate, applyEmotionSnapshot, requestEmotionSnapshot };
}
