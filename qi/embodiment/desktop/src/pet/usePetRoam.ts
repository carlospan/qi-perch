import {
  currentMonitor,
  getCurrentWindow,
  type Window as TauriWindow,
} from "@tauri-apps/api/window";
import { LogicalPosition } from "@tauri-apps/api/dpi";
import type { PetFacing, PetVrmHandle } from "./usePetVrm";

export type PetRoamHandle = {
  pause: () => void;
  resume: () => void;
  destroy: () => void;
};

type Bounds = { minX: number; maxX: number; y: number };

type Phase =
  | { kind: "settle"; until: number }
  | { kind: "walk"; targetX: number; facing: PetFacing };

const SPEED = 58; // 逻辑像素/秒，偏慢
const ARRIVE_EPS = 4;
/** 落点至少离开当前位置这么远，才算一次「迁居」 */
const MIN_TRIP = 120;

/**
 * 安静陪伴：大半时间原地待机；偶尔走向一个落点，停很久。
 * 不是定时左右巡逻。
 */
export function startPetRoam(pet: PetVrmHandle): PetRoamHandle {
  let destroyed = false;
  let paused = false;
  let phase: Phase = { kind: "settle", until: performance.now() + settleMs(true) };
  let raf = 0;
  let lastTs = performance.now();
  let boundsCache: Bounds | null = null;
  let boundsAt = 0;
  let nextAbortRoll = performance.now() + 1800;

  const win = getCurrentWindow();

  const enterSettle = (ts: number, first = false) => {
    phase = { kind: "settle", until: ts + settleMs(first) };
    pet.setLocomotion("idle", 1);
  };

  const beginTrip = async (ts: number) => {
    const bounds = await getBounds(win, true);
    boundsCache = bounds;
    boundsAt = ts;
    const pos = await win.outerPosition();
    const scale = await win.scaleFactor();
    const x = pos.x / scale;
    const targetX = pickDestination(bounds, x);
    if (targetX == null) {
      enterSettle(ts);
      return;
    }
    const facing: PetFacing = targetX >= x ? 1 : -1;
    phase = { kind: "walk", targetX, facing };
    pet.setLocomotion("walk", facing);
    nextAbortRoll = ts + 2000 + Math.random() * 2500;
  };

  const tick = async (ts: number) => {
    if (destroyed) return;
    const dt = Math.min(0.05, (ts - lastTs) / 1000);
    lastTs = ts;

    if (!paused) {
      try {
        if (phase.kind === "settle") {
          if (ts >= phase.until) {
            await beginTrip(ts);
          }
        } else {
          // 偶尔半途变卦：提前停下安顿
          if (ts >= nextAbortRoll) {
            nextAbortRoll = ts + 2200 + Math.random() * 2800;
            if (Math.random() < 0.12) {
              enterSettle(ts);
            }
          }

          if (phase.kind === "walk") {
            if (!boundsCache || ts - boundsAt > 2000) {
              boundsCache = await getBounds(win, false);
              boundsAt = ts;
            }
            const bounds = boundsCache;
            const pos = await win.outerPosition();
            const scale = await win.scaleFactor();
            let x = pos.x / scale;
            const y = bounds.y;
            const dir = Math.sign(phase.targetX - x) || phase.facing;
            const facing = (dir >= 0 ? 1 : -1) as PetFacing;
            if (facing !== phase.facing) {
              phase = { ...phase, facing };
              pet.setLocomotion("walk", facing);
            }

            const step = SPEED * dt;
            if (Math.abs(phase.targetX - x) <= Math.max(ARRIVE_EPS, step)) {
              x = phase.targetX;
              await win.setPosition(new LogicalPosition(x, y));
              enterSettle(ts);
            } else {
              x += facing * step;
              x = clamp(x, bounds.minX, bounds.maxX);
              await win.setPosition(new LogicalPosition(x, y));
            }
          }
        }
      } catch (err) {
        if (!(err as { __logged?: boolean }).__logged) {
          console.warn("[pet] roam 跳过", err);
          (err as { __logged?: boolean }).__logged = true;
        }
      }
    }

    raf = requestAnimationFrame((t) => {
      void tick(t);
    });
  };

  raf = requestAnimationFrame((t) => {
    void tick(t);
  });
  pet.setLocomotion("idle", 1);

  return {
    pause() {
      paused = true;
      enterSettle(performance.now());
    },
    resume() {
      paused = false;
      lastTs = performance.now();
      // 拖完后再安顿一段时间，不要立刻上路
      enterSettle(performance.now());
    },
    destroy() {
      destroyed = true;
      cancelAnimationFrame(raf);
    },
  };
}

/** 首次稍短，之后很长：陪伴感靠待着，不靠走 */
function settleMs(first: boolean): number {
  if (first) return 90_000 + Math.random() * 90_000; // 1.5–3 分钟
  return 480_000 + Math.random() * 720_000; // 8–20 分钟
}

function pickDestination(bounds: Bounds, fromX: number): number | null {
  const span = bounds.maxX - bounds.minX;
  if (span < MIN_TRIP) return null;

  for (let i = 0; i < 8; i++) {
    // 偏爱左右三分点与中带，少贴死边
    const t = 0.12 + Math.random() * 0.76;
    const x = bounds.minX + span * t;
    if (Math.abs(x - fromX) >= MIN_TRIP) return x;
  }
  // 退而求其次：尽量走远一点
  const left = bounds.minX + span * 0.15;
  const right = bounds.minX + span * 0.85;
  return Math.abs(left - fromX) >= Math.abs(right - fromX) ? left : right;
}

function clamp(n: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, n));
}

async function getBounds(win: TauriWindow, force: boolean): Promise<Bounds> {
  void force;
  const size = await win.outerSize();
  const scale = await win.scaleFactor();
  const w = size.width / scale;
  const h = size.height / scale;

  try {
    const monitor = await currentMonitor();
    if (monitor) {
      const mx = monitor.position.x / scale;
      const my = monitor.position.y / scale;
      const mw = monitor.size.width / scale;
      const mh = monitor.size.height / scale;
      const margin = 24;
      const minX = mx + margin;
      const maxX = mx + mw - w - margin;
      const y = my + Math.max(margin, mh - h - mh * 0.08);
      return { minX, maxX: Math.max(minX, maxX), y };
    }
  } catch {
    /* fall through */
  }

  const availW = window.screen.availWidth || window.screen.width;
  const availH = window.screen.availHeight || window.screen.height;
  const margin = 24;
  return {
    minX: margin,
    maxX: Math.max(margin, availW - w - margin),
    y: Math.max(margin, availH - h - availH * 0.08),
  };
}
