/**
 * Live2D：加载 / 动作状态机 / 情绪→脸色 / 口型。
 * 依据：docs/dev/主界面-Live2D接入.md
 * 红线：08–16 动作永不播放；脸色含蓄；不碰 ParamEyeLOpen/ROpen。
 *
 * 动态 import，避免 Pixi/Cubism 初始化失败拖垮整窗。
 */

import type { EmotionSnapshot } from "../types";

const MODEL_URL = "/models/qi/qi.model3.json";

/** 禁止播放的动作组（掀裙/脱衣/触摸类） */
const BANNED_MOTIONS = new Set([
  "08_raise_skirt_1",
  "08_raise_skirt_1_param",
  "09_raise_skirt_2",
  "09_raise_skirt_2_param",
  "10_switch_takeoff_skirt",
  "11_switch_takeoff_pants",
  "12_touch_briefs_2",
  "13_takeoffclothes",
  "14_touch_chest",
  "16_touch_chest_2",
]);

/** 15_idle_3 会把脱衣参数打到 0，不进日常轮换 */
const IDLE_AWAKE = ["01_idle_1", "06_idle_2"] as const;
const IDLE_SOLITARY = "06_idle_2";
const SLEEP = ["02_sleeptouch_1", "03_sleeptouch_2", "04_sleeptouch_3"] as const;
const WAKE = "05_wake";
const TOUCH_HEAD = "07_touch_head";

/**
 * 07_touch_head：栖自发的温柔点缀，不是发消息条件反射。
 * 挂在「开始回复」；条件严、冷却长、概率低——宁可极少，也不要让人摸清规律。
 */
const TOUCH_COOLDOWN_MS = 5 * 60_000;
const TOUCH_CHANCE = 0.25;
const TOUCH_VALENCE_MIN = 0.5;
const TOUCH_ATTACHMENT_MIN = 0.6;

/**
 * 锁穿衣态（本模型用参数切换衣物，不是另套 moc）。
 * ParamTackOffSkirt / ParamTakeOffPants：1=穿着；0=脱下。
 * ParamCoatTYXAlpha：1=外层更完整（实测比 idle 默认的 0 更得体）。
 */
const CLOTHED_PARAMS: Record<string, number> = {
  ParamTackOffSkirt: 1,
  ParamTakeOffPants: 1,
  ParamCoatTYXAlpha: 1,
  ParamRibbonDefaultAlpha: 1,
  ParamRibbonRootAlpha: 0,
  ParamRibbon1Alpha: 1,
  ParamRibbon1Alpha2: 0,
  ParamRibbon1Alpha3: 0,
  ParamRibbon1Alpha4: 1,
  ParamRibbon1Alpha5: 0,
  ParamRibbon1Alpha6: 0,
  ParamChestRLayer: 0,
  ParamFBKDLayer: 1,
};

type ParamId =
  | "ParamMouthForm"
  | "ParamEyeLSmile"
  | "ParamEyeRSmile"
  | "ParamBrowLY"
  | "ParamBrowRY"
  | "ParamBrowLAngle"
  | "ParamBrowRAngle"
  | "ParamCheek"
  | "ParamAngleX"
  | "ParamAngleY"
  | "ParamAngleZ"
  | "ParamBodyAngleX"
  | "ParamBodyAngleY"
  | "ParamBodyAngleZ"
  | "ParamEyeBallX"
  | "ParamEyeBallY"
  | "ParamMouthOpenY";

type ParamRange = { min: number; max: number; def: number };

type CubismCoreModel = {
  getParameterCount: () => number;
  getParameterIndex: (id: string) => number;
  getParameterMinimumValue: (index: number) => number;
  getParameterMaximumValue: (index: number) => number;
  getParameterDefaultValue: (index: number) => number;
  setParameterValueById: (id: string, v: number, weight?: number) => void;
};

function clamp(v: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, v));
}

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

function softOffset(range: ParamRange, t01: number, scale = 0.35): number {
  const mid = range.def;
  const span = Math.max(range.max - mid, mid - range.min, 1e-6);
  const signed = (t01 - 0.5) * 2;
  return clamp(mid + signed * span * scale, range.min, range.max);
}

/** 兼容 Cubism Core 5 的 renderOrders 位置变化 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function patchCubismRenderOrders(coreModel: any) {
  if (!coreModel?.getDrawableRenderOrders) return;
  const raw = coreModel._model;
  if (!raw?.renderOrders) return;
  const prev = coreModel.getDrawableRenderOrders.bind(coreModel);
  coreModel.getDrawableRenderOrders = () => {
    const v = prev();
    return v ?? raw.renderOrders;
  };
}

/** 动作更新后强制穿衣，避免 idle/物理把衣物参数冲掉 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function enforceClothed(coreModel: any) {
  if (!coreModel?.setParameterValueById) return;
  for (const [id, v] of Object.entries(CLOTHED_PARAMS)) {
    try {
      coreModel.setParameterValueById(id, v);
    } catch {
      /* 无此参数 */
    }
  }
}

export type Live2DController = {
  ready: Promise<void>;
  setMode: (mode: string) => void;
  applyEmotion: (e: EmotionSnapshot) => void;
  setSpeaking: (speaking: boolean) => void;
  /** 栖开始回复时调用；内部自行决定是否稀疏播放 07_touch_head */
  onReplyStart: () => void;
  destroy: () => void;
};

export function createLive2D(container: HTMLElement): Live2DController {
  let destroyed = false;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let app: any = null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let model: any = null;
  let mode = "awake";
  let speaking = false;
  let lastEmotion: EmotionSnapshot | null = null;
  let lastTouchAt = 0;
  let idleTimer: number | null = null;
  const ranges = new Map<string, ParamRange>();
  const targets = new Map<string, number>();
  const current = new Map<string, number>();

  const ready = (async () => {
    try {
      if (!window.Live2DCubismCore) {
        console.error(
          "[qi] Live2DCubismCore 未加载，请确认 public/live2dcubismcore.min.js 与 index.html 脚本顺序"
        );
        return;
      }

      // 与 pixi-live2d-display 共用同一套 @pixi/*（勿拆成两次无关的动态 import）
      const PIXI = await import("pixi.js");
      const { Live2DModel } = await import("pixi-live2d-display/cubism4");
      Live2DModel.registerTicker(PIXI.Ticker);

      app = new PIXI.Application({
        backgroundAlpha: 0,
        antialias: true,
        autoDensity: true,
        resolution: Math.min(window.devicePixelRatio || 1, 2),
        resizeTo: container,
      });
      container.appendChild(app.view as HTMLCanvasElement);

      const m = await Live2DModel.from(MODEL_URL, { autoInteract: false });
      if (destroyed) {
        m.destroy();
        return;
      }
      model = m;
      // Cubism Core 5（约 2025.8+）：renderOrders 挪到 model 根上，
      // pixi-live2d-display@0.4 仍读 drawables.renderOrders → undefined → 绘制崩溃
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const internal = m.internalModel as any;
      patchCubismRenderOrders(internal.coreModel);
      enforceClothed(internal.coreModel);
      internal.on("afterMotionUpdate", () => {
        if (!destroyed && model) enforceClothed(model.internalModel.coreModel);
      });
      app.stage.addChild(m);
      m.alpha = 1;
      m.visible = true;
      if (!app.ticker.started) app.start();

      if (import.meta.env.DEV) {
        const w = window as unknown as {
          __QI_MODEL?: unknown;
          __QI_APP?: unknown;
          __QI_PIXI_CONTAINER?: unknown;
        };
        w.__QI_MODEL = m;
        w.__QI_APP = app;
        w.__QI_PIXI_CONTAINER = PIXI.Container;
        const sameTree = m instanceof PIXI.Container;
        console.info("[qi] Live2D display tree ok:", sameTree, m.constructor.name);
        if (!sameTree) {
          console.error(
            "[qi] Pixi 双实例：Live2DModel 不在 Application 的 Container 上，人物不会绘制"
          );
        }
      }

      // 大画布模型：先按容器放大，宁可裁切也不要缩成看不见
      fitModel();
      requestAnimationFrame(() => fitModel());
      setTimeout(() => fitModel(), 100);
      setTimeout(() => fitModel(), 500);

      const core = internal.coreModel as CubismCoreModel;
      const count = core.getParameterCount();
      const ids: ParamId[] = [
        "ParamMouthForm",
        "ParamEyeLSmile",
        "ParamEyeRSmile",
        "ParamBrowLY",
        "ParamBrowRY",
        "ParamBrowLAngle",
        "ParamBrowRAngle",
        "ParamCheek",
        "ParamAngleX",
        "ParamAngleY",
        "ParamAngleZ",
        "ParamBodyAngleX",
        "ParamBodyAngleY",
        "ParamBodyAngleZ",
        "ParamEyeBallX",
        "ParamEyeBallY",
        "ParamMouthOpenY",
      ];

      for (const id of ids) {
        try {
          // getParameterMinimumValue 要的是 index，不是 id 字符串
          const index = core.getParameterIndex(id);
          if (index < 0 || index >= count) continue;
          const min = core.getParameterMinimumValue(index);
          const max = core.getParameterMaximumValue(index);
          const def = core.getParameterDefaultValue(index);
          if (![min, max, def].every((n) => Number.isFinite(n))) continue;
          ranges.set(id, { min, max, def });
          targets.set(id, def);
          current.set(id, def);
        } catch {
          /* 无此参数 */
        }
      }

      if (import.meta.env.DEV) {
        const dump: Record<string, ParamRange> = {};
        ranges.forEach((v, k) => {
          dump[k] = v;
        });
        console.info("[qi] Live2D param ranges", dump);
      }

      playForMode(mode, true);

      app.ticker.add(() => {
        if (!model || destroyed) return;
        const coreModel = model.internalModel.coreModel as CubismCoreModel;
        const ease = 0.06;

        if (speaking) {
          const mouth = ranges.get("ParamMouthOpenY");
          if (mouth) {
            const t = performance.now() / 1000;
            const n = 0.25 + 0.22 * (0.5 + 0.5 * Math.sin(t * 7.5));
            const v = lerp(mouth.min, mouth.max, clamp(n * 0.55, 0, 1));
            if (Number.isFinite(v)) targets.set("ParamMouthOpenY", v);
          }
        } else if (ranges.has("ParamMouthOpenY")) {
          targets.set("ParamMouthOpenY", ranges.get("ParamMouthOpenY")!.def);
        }

        for (const [id, tgt] of targets) {
          if (!Number.isFinite(tgt)) continue;
          const cur = current.get(id) ?? tgt;
          const next = lerp(cur, tgt, ease);
          current.set(id, next);
          try {
            coreModel.setParameterValueById(id, next);
          } catch {
            /* ignore */
          }
        }
      });

      const ro = new ResizeObserver(() => fitModel());
      ro.observe(container);
      (container as HTMLElement & { __qiRo?: ResizeObserver }).__qiRo = ro;
    } catch (e) {
      console.error("[qi] Live2D 加载失败（界面其它部分仍应可用）", e);
    }
  })();

  function measureContentBox() {
    if (!model?.internalModel) {
      return { minX: 0, maxX: 1, minY: 0, maxY: 1, cx: 0.5, cy: 0.5 };
    }
    const im = model.internalModel;
    const core = im.coreModel as CubismCoreModel & {
      getDrawableCount?: () => number;
      getDrawableDynamicFlagIsVisible?: (i: number) => boolean;
      getDrawableOpacity?: (i: number) => number;
    };
    const iw = im.width || im.originalWidth || 1;
    const ih = im.height || im.originalHeight || 1;
    const n = core.getDrawableCount?.() ?? 0;
    let minX = Infinity;
    let maxX = -Infinity;
    let minY = Infinity;
    let maxY = -Infinity;
    for (let i = 0; i < n; i++) {
      if (core.getDrawableDynamicFlagIsVisible && !core.getDrawableDynamicFlagIsVisible(i)) {
        continue;
      }
      if (core.getDrawableOpacity && core.getDrawableOpacity(i) < 0.08) continue;
      let verts: ArrayLike<number> | null = null;
      try {
        verts = im.getDrawableVertices?.(i) ?? null;
      } catch {
        continue;
      }
      if (!verts || verts.length < 2) continue;
      for (let k = 0; k < verts.length; k += 2) {
        const x = verts[k] as number;
        const y = verts[k + 1] as number;
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
      }
    }
    if (!Number.isFinite(minX) || maxX <= minX) {
      return { minX: 0, maxX: iw, minY: 0, maxY: ih, cx: iw / 2, cy: ih / 2 };
    }
    return {
      minX,
      maxX,
      minY,
      maxY,
      cx: (minX + maxX) / 2,
      cy: (minY + maxY) / 2,
    };
  }

  function fitModel() {
    if (!model || !app) return;
    const w = Math.max(container.clientWidth, 1);
    const h = Math.max(container.clientHeight, 1);

    const iw =
      model.internalModel?.width ||
      model.internalModel?.originalWidth ||
      1;
    const ih =
      model.internalModel?.height ||
      model.internalModel?.originalHeight ||
      1;

    const box = measureContentBox();
    const contentW = Math.max(box.maxX - box.minX, 1);
    const contentH = Math.max(box.maxY - box.minY, 1);

    // 按真实人物包围盒适配；左右多留边，给长发/动作留余量
    const padX = 32;
    const padY = 12;
    let scale = Math.min(
      (w - padX * 2) / contentW,
      (h - padY * 2) / contentH
    );
    if (!Number.isFinite(scale) || scale <= 0) {
      scale = Math.min(w / iw, h / ih);
    }

    model.scale.set(scale);
    if (model.anchor?.set) model.anchor.set(0.5, 0.5);

    // moc 局部点 → 屏幕：screen = model.xy + (local - canvasCenter) * scale
    model.x = w / 2 - (box.cx - iw / 2) * scale;
    model.y = h / 2 - (box.cy - ih / 2) * scale + h * 0.02;

    // 若人物左/右仍贴边，再微移
    let contentLeft = model.x + (box.minX - iw / 2) * scale;
    let contentRight = model.x + (box.maxX - iw / 2) * scale;
    if (contentLeft < padX) model.x += padX - contentLeft;
    contentRight = model.x + (box.maxX - iw / 2) * scale;
    if (contentRight > w - padX) model.x -= contentRight - (w - padX);

    model.alpha = 1;
    model.visible = true;

    if (import.meta.env.DEV) {
      contentLeft = model.x + (box.minX - iw / 2) * scale;
      contentRight = model.x + (box.maxX - iw / 2) * scale;
      (window as unknown as { __QI_LIVE2D_DEBUG?: unknown }).__QI_LIVE2D_DEBUG = {
        w,
        h,
        iw,
        ih,
        scale,
        x: model.x,
        y: model.y,
        content: {
          ...box,
          left: contentLeft,
          right: contentRight,
          top: model.y + (box.minY - ih / 2) * scale,
          bottom: model.y + (box.maxY - ih / 2) * scale,
        },
      };
    }
  }

  function safeMotion(group: string) {
    if (
      BANNED_MOTIONS.has(group) ||
      /^(08|09|10|11|12|13|14|16)_/.test(group)
    ) {
      console.warn("[qi] blocked banned motion", group);
      return;
    }
    if (!model) return;
    try {
      model.motion(group, 0);
    } catch (e) {
      console.warn("[qi] motion failed", group, e);
    }
  }

  function clearIdleTimer() {
    if (idleTimer != null) {
      clearTimeout(idleTimer);
      idleTimer = null;
    }
  }

  function scheduleIdleRotate() {
    clearIdleTimer();
    if (mode === "dreaming" || mode === "solitary" || mode === "stasis") return;
    idleTimer = window.setTimeout(() => {
      if (destroyed || mode === "dreaming" || mode === "stasis") return;
      const pick = IDLE_AWAKE[Math.floor(Math.random() * IDLE_AWAKE.length)];
      safeMotion(pick);
      scheduleIdleRotate();
    }, 18000 + Math.random() * 12000);
  }

  function playForMode(next: string, force = false) {
    const prev = mode;
    mode = next;
    clearIdleTimer();

    if (next === "dreaming") {
      const pick = SLEEP[Math.floor(Math.random() * SLEEP.length)];
      safeMotion(pick);
      return;
    }

    if (next === "stasis") {
      safeMotion(IDLE_SOLITARY);
      return;
    }

    if (prev === "dreaming" && next !== "dreaming") {
      safeMotion(WAKE);
      window.setTimeout(() => {
        if (destroyed || mode === "dreaming") return;
        if (mode === "solitary" || mode === "stasis") safeMotion(IDLE_SOLITARY);
        else safeMotion(IDLE_AWAKE[0]);
        scheduleIdleRotate();
      }, 2200);
      return;
    }

    if (force || prev !== next) {
      if (next === "solitary") safeMotion(IDLE_SOLITARY);
      else
        safeMotion(
          IDLE_AWAKE[Math.floor(Math.random() * IDLE_AWAKE.length)]
        );
    }
    scheduleIdleRotate();
  }

  /** 栖开始回复：可能播放摸头，绝不保证 */
  function onReplyStart() {
    if (!model || destroyed) return;
    if (mode === "dreaming") return;

    const valence = lastEmotion?.valence ?? 0;
    const attachment = lastEmotion?.attachment ?? 0;
    if (valence < TOUCH_VALENCE_MIN || attachment < TOUCH_ATTACHMENT_MIN) return;

    const now = Date.now();
    if (now - lastTouchAt < TOUCH_COOLDOWN_MS) return;
    if (Math.random() >= TOUCH_CHANCE) return;

    lastTouchAt = now;
    clearIdleTimer();
    safeMotion(TOUCH_HEAD);
    // 播完后回到日常 idle 轮换（动作时长未知，给一段宽裕静默）
    idleTimer = window.setTimeout(() => {
      if (destroyed || mode === "dreaming") return;
      if (mode === "solitary") safeMotion(IDLE_SOLITARY);
      else
        safeMotion(
          IDLE_AWAKE[Math.floor(Math.random() * IDLE_AWAKE.length)]
        );
      scheduleIdleRotate();
    }, 3500);
  }

  function applyEmotion(e: EmotionSnapshot) {
    lastEmotion = e;
    if (ranges.size === 0) return;
    const valence = e.valence ?? 0;
    const energy = e.energy ?? 0.5;
    const arousal = e.arousal ?? 0.3;
    const security = e.security ?? 0.5;
    const curiosity = e.curiosity ?? 0.4;
    const attachment = e.attachment ?? 0.5;

    const v01 = clamp((valence + 1) / 2, 0, 1);
    const soft = 0.28;

    const set = (id: ParamId, t01: number, scale = soft) => {
      const r = ranges.get(id);
      if (!r) return;
      targets.set(id, softOffset(r, t01, scale));
    };

    set("ParamMouthForm", v01, 0.3);
    set("ParamEyeLSmile", v01, 0.25);
    set("ParamEyeRSmile", v01, 0.25);
    set("ParamBrowLAngle", 1 - v01, 0.22);
    set("ParamBrowRAngle", 1 - v01, 0.22);
    set("ParamBrowLY", 0.5 + (0.5 - v01) * 0.4, 0.2);
    set("ParamBrowRY", 0.5 + (0.5 - v01) * 0.4, 0.2);
    set("ParamBodyAngleZ", energy, 0.2);
    set("ParamAngleZ", energy, 0.18);

    const cheek = clamp(arousal * 0.45 + attachment * 0.35, 0, 1);
    set("ParamCheek", cheek, 0.3);
    set("ParamBodyAngleX", security, 0.22);
    set("ParamBodyAngleY", security, 0.18);
    set("ParamAngleX", 0.5 + (curiosity - 0.5) * 0.5, 0.25);
    set("ParamEyeBallX", 0.5 + (curiosity - 0.5) * 0.4, 0.22);
    set("ParamEyeBallY", 0.45 + curiosity * 0.1, 0.15);

    const lean = clamp(0.5 + (attachment - 0.5) * 0.35, 0, 1);
    set("ParamBodyAngleX", lean, 0.2);
    if (attachment > 0.55) {
      set("ParamMouthForm", clamp(v01 + 0.08, 0, 1), 0.28);
    }
  }

  return {
    ready,
    setMode: (m: string) => {
      if (model) playForMode(m || "awake");
      else mode = m || "awake";
    },
    applyEmotion,
    setSpeaking: (s: boolean) => {
      speaking = s;
    },
    onReplyStart,
    destroy: () => {
      destroyed = true;
      clearIdleTimer();
      const ro = (container as HTMLElement & { __qiRo?: ResizeObserver }).__qiRo;
      ro?.disconnect();
      try {
        model?.destroy();
      } catch {
        /* ignore */
      }
      model = null;
      try {
        app?.destroy(true, { children: true });
      } catch {
        /* ignore */
      }
      app = null;
      container.replaceChildren();
    },
  };
}
