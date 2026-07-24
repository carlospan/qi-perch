<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

/**
 * 氛围场景：天空冷暖 / 雾 / 水墨枝 / 光尘 / 梦泡。
 * 氛围变量来自 :root（useEmotion）；入场由 App 的 .booted 编排。
 */

const props = defineProps<{
  /** 入场编排已启动 */
  entered?: boolean;
  /** dreaming 或 dream_bubbles 效果 */
  dreaming?: boolean;
}>();

const moteEls = ref<{ style: Record<string, string>; cls?: string }[]>([]);
const bubbleEls = ref<{ style: Record<string, string> }[]>([]);

onMounted(() => {
  const motes: { style: Record<string, string>; cls: string }[] = [];
  for (let i = 0; i < 14; i++) {
    const tumble = i < 3;
    let width: number;
    let height: number;
    let cls = "";
    if (tumble) {
      // 近处浮粒：微椭圆，在光里轻轻翻
      width = 3.8 + Math.random() * 1.6;
      height = width * (0.5 + Math.random() * 0.28);
      cls = "tumble";
    } else if (i < 7) {
      // 远处微尘
      width = height = 1 + Math.random() * 0.9;
      cls = "far";
    } else {
      // 中景
      width = height = 2.2 + Math.random() * 1.6;
    }
    motes.push({
      cls,
      style: {
        left: `${5 + Math.random() * 90}%`,
        top: `${18 + Math.random() * 62}%`,
        animationDuration: `${6 + Math.random() * 8}s`,
        animationDelay: `${-Math.random() * 8}s`,
        width: `${width}px`,
        height: `${height}px`,
      },
    });
  }
  moteEls.value = motes;

  const bubbles = [];
  for (let i = 0; i < 7; i++) {
    const size = `${10 + Math.random() * 18}px`;
    bubbles.push({
      style: {
        left: `${12 + Math.random() * 76}%`,
        bottom: `${8 + Math.random() * 40}%`,
        width: size,
        height: size,
        animationDuration: `${9 + Math.random() * 7}s`,
        animationDelay: `${-Math.random() * 6}s`,
      },
    });
  }
  bubbleEls.value = bubbles;
});

const sceneClass = computed(() => ({
  entered: !!props.entered,
  dreaming: !!props.dreaming,
}));
</script>

<template>
  <div class="scene" :class="sceneClass" aria-hidden="true">
    <div class="sky cool" />
    <div class="sky warm" />
    <div class="horizon cool" />
    <div class="horizon warm" />
    <div class="mist a" />
    <div class="mist b" />

    <div class="branch">
      <svg viewBox="0 0 420 170" preserveAspectRatio="none">
        <defs>
          <linearGradient id="qi-branch-fade" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stop-color="var(--branch)" stop-opacity="0.12" />
            <stop offset="12%" stop-color="var(--branch)" stop-opacity="0.92" />
            <stop offset="88%" stop-color="var(--branch)" stop-opacity="0.88" />
            <stop offset="100%" stop-color="var(--branch)" stop-opacity="0.18" />
          </linearGradient>
          <linearGradient id="qi-branch-twig" x1="0" y1="1" x2="0" y2="0">
            <stop offset="0%" stop-color="var(--branch)" stop-opacity="0.85" />
            <stop offset="100%" stop-color="var(--branch)" stop-opacity="0.15" />
          </linearGradient>
        </defs>
        <!-- 月光勾边：略宽、极淡冷色 -->
        <path
          class="glow"
          d="M -10 128 C 70 104, 150 122, 232 96 C 300 76, 352 84, 432 62"
          stroke="color-mix(in srgb, var(--mist) 55%, transparent)"
          stroke-width="10"
          fill="none"
          stroke-linecap="round"
          opacity="0.22"
        />
        <path
          d="M -10 128 C 70 104, 150 122, 232 96 C 300 76, 352 84, 432 62"
          stroke="url(#qi-branch-fade)"
          stroke-width="7"
          fill="none"
          stroke-linecap="round"
        />
        <path
          class="glow"
          d="M 232 96 C 252 78, 268 70, 288 58"
          stroke="color-mix(in srgb, var(--mist) 50%, transparent)"
          stroke-width="6"
          fill="none"
          stroke-linecap="round"
          opacity="0.18"
        />
        <path
          d="M 232 96 C 252 78, 268 70, 288 58"
          stroke="url(#qi-branch-twig)"
          stroke-width="4"
          fill="none"
          stroke-linecap="round"
        />
        <path
          class="glow"
          d="M 150 116 C 162 104, 172 98, 186 90"
          stroke="color-mix(in srgb, var(--mist) 50%, transparent)"
          stroke-width="5.5"
          fill="none"
          stroke-linecap="round"
          opacity="0.16"
        />
        <path
          d="M 150 116 C 162 104, 172 98, 186 90"
          stroke="url(#qi-branch-twig)"
          stroke-width="3.5"
          fill="none"
          stroke-linecap="round"
        />
        <circle cx="288" cy="56" r="3" fill="var(--branch)" opacity=".45" />
        <circle cx="187" cy="88" r="2.6" fill="var(--branch)" opacity=".38" />
      </svg>
    </div>

    <div class="motes">
      <i
        v-for="(m, idx) in moteEls"
        :key="idx"
        :class="m.cls"
        :style="m.style"
      />
    </div>
    <div v-show="dreaming" class="dream-bubbles">
      <i v-for="(b, idx) in bubbleEls" :key="'b' + idx" :style="b.style" />
    </div>
  </div>
</template>

<style scoped>
.scene {
  position: absolute;
  inset: 0;
  z-index: 0;
  opacity: 0;
  filter: saturate(var(--sat)) brightness(var(--bright));
  transition: filter 1.6s ease;
}
.scene.dreaming {
  filter: saturate(calc(var(--sat) * 0.85)) brightness(calc(var(--bright) * 0.78));
}
.scene.entered {
  animation: scene-in 0.55s ease forwards;
}

@keyframes scene-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.sky {
  position: absolute;
  inset: 0;
  transition: opacity 2.2s ease;
}
.sky.cool {
  background: linear-gradient(
    180deg,
    var(--sky-cool-0) 0%,
    var(--sky-cool-1) 52%,
    var(--sky-cool-2) 100%
  );
  opacity: calc(1 - var(--warm-t));
}
.sky.warm {
  background: linear-gradient(
    180deg,
    var(--sky-warm-0) 0%,
    var(--sky-warm-1) 52%,
    var(--sky-warm-2) 100%
  );
  opacity: var(--warm-t);
}

.horizon {
  position: absolute;
  left: -20%;
  right: -20%;
  bottom: -18%;
  height: 62%;
  border-radius: 50%;
  filter: blur(30px);
  transition: opacity 2.2s ease;
}
.horizon.cool {
  background: radial-gradient(
    closest-side,
    color-mix(in srgb, var(--horizon-cool) 20%, transparent),
    transparent 72%
  );
  opacity: calc(1 - var(--warm-t));
}
.horizon.warm {
  background: radial-gradient(
    closest-side,
    color-mix(in srgb, var(--horizon-warm) 26%, transparent),
    transparent 72%
  );
  opacity: var(--warm-t);
}

.mist {
  position: absolute;
  width: 220%;
  height: 200px;
  filter: blur(26px);
  opacity: 0;
  transition: opacity 0.8s ease 0.15s;
}
.scene.entered .mist {
  opacity: 0.8;
}
.mist.a {
  bottom: 120px;
  left: -60%;
  background: radial-gradient(
    closest-side,
    color-mix(in srgb, var(--mist) 10%, transparent),
    transparent 70%
  );
  animation: drift var(--mist-dur) linear infinite;
}
.mist.b {
  bottom: 40px;
  left: -30%;
  background: radial-gradient(
    closest-side,
    color-mix(in srgb, var(--mist) 8%, transparent),
    transparent 70%
  );
  animation: drift calc(var(--mist-dur) * 1.5) linear infinite reverse;
}

@keyframes drift {
  from {
    transform: translateX(0);
  }
  to {
    transform: translateX(28%);
  }
}

.branch {
  position: absolute;
  left: -4%;
  right: -4%;
  top: 72px;
  height: 140px;
  z-index: 1;
  opacity: 0;
  pointer-events: none;
}
.scene.entered .branch {
  animation: fade-soft 0.7s ease 0.2s forwards;
  opacity: 0;
}
.branch svg {
  width: 100%;
  height: 100%;
  display: block;
}

.motes {
  position: absolute;
  inset: 0;
  z-index: 1;
  opacity: 0;
  transition: opacity 1.6s ease 0.35s;
}
.scene.entered .motes {
  opacity: var(--mote-a);
}
.motes i {
  position: absolute;
  border-radius: 50%;
  background: color-mix(in srgb, var(--ember) 55%, var(--ink) 45%);
  filter: blur(0.4px);
  animation: mote 9s ease-in-out infinite;
}
.motes i.far {
  filter: blur(0.6px);
  opacity: 0.7;
}
.motes i.tumble {
  border-radius: 50%;
  filter: blur(0.35px);
  animation-name: mote-tumble;
}

@keyframes mote {
  0%,
  100% {
    transform: translateY(0);
    opacity: 0.15;
  }
  50% {
    transform: translateY(-26px);
    opacity: 0.85;
  }
}

@keyframes mote-tumble {
  0%,
  100% {
    transform: translateY(0) rotate(-12deg);
    opacity: 0.2;
  }
  50% {
    transform: translateY(-22px) rotate(18deg);
    opacity: 0.9;
  }
}
@keyframes fade-soft {
  to {
    opacity: 0.38;
  }
}

/* 梦泡：克制、慢、少 */
.dream-bubbles {
  position: absolute;
  inset: 0;
  z-index: 2;
  pointer-events: none;
  opacity: 0;
  transition: opacity 1.8s ease;
}
.scene.dreaming .dream-bubbles {
  opacity: 0.55;
}
.dream-bubbles i {
  position: absolute;
  border-radius: 50%;
  border: 1px solid color-mix(in srgb, var(--ink) 18%, transparent);
  background: color-mix(in srgb, var(--ink) 4%, transparent);
  box-shadow: inset 0 0 8px color-mix(in srgb, var(--ink) 8%, transparent);
  animation: bubble-rise ease-in-out infinite;
}
@keyframes bubble-rise {
  0%,
  100% {
    transform: translateY(0) scale(1);
    opacity: 0.2;
  }
  50% {
    transform: translateY(-36px) scale(1.06);
    opacity: 0.55;
  }
}
</style>
