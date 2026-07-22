<script setup lang="ts">
import { computed } from "vue";
import type { AvatarState } from "../types";

const props = defineProps<{
  state: AvatarState;
}>();

const rootClass = computed(() => [
  "avatar",
  `posture-${props.state.posture}`,
  `expr-${props.state.expression}`,
  `fx-${props.state.effect}`,
]);
</script>

<template>
  <div :class="rootClass" aria-hidden="true">
    <div class="halo" />
    <div class="body">
      <div class="head">
        <div class="eye left" />
        <div class="eye right" />
        <div class="mouth" />
      </div>
    </div>
    <div v-if="state.effect === 'dream_bubbles'" class="bubbles">
      <span /><span /><span />
    </div>
    <div v-if="state.effect === 'thinking_sparkles'" class="sparkles">
      <i /><i /><i />
    </div>
    <div v-if="state.effect === 'season_leaves'" class="leaves">
      <em /><em /><em />
    </div>
    <div v-if="state.effect === 'snow'" class="snow">
      <b /><b /><b /><b />
    </div>
  </div>
</template>

<style scoped>
.avatar {
  position: relative;
  width: 160px;
  height: 180px;
  margin: 0 auto;
}

.halo {
  position: absolute;
  inset: 18% 12% 8%;
  border-radius: 50%;
  background: radial-gradient(circle, var(--glow), transparent 70%);
  opacity: 0.55;
  animation: breathe 4.5s ease-in-out infinite;
}

.body {
  position: absolute;
  left: 50%;
  bottom: 18px;
  width: 72px;
  height: 54px;
  margin-left: -36px;
  border-radius: 40% 40% 45% 45%;
  background: linear-gradient(180deg, #8fb8c8 0%, #5d8496 100%);
  box-shadow: inset 0 -8px 16px rgba(0, 0, 0, 0.18);
  transition: transform 0.45s ease;
}

.head {
  position: absolute;
  left: 50%;
  top: -58px;
  width: 78px;
  height: 78px;
  margin-left: -39px;
  border-radius: 50%;
  background: linear-gradient(160deg, #d8e6ef 0%, #a8c4d4 100%);
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.22);
  transition: transform 0.4s ease;
}

.eye {
  position: absolute;
  top: 34px;
  width: 8px;
  height: 10px;
  border-radius: 50%;
  background: #2a3a4a;
  transition: height 0.3s ease, transform 0.3s ease;
}

.eye.left {
  left: 22px;
}
.eye.right {
  right: 22px;
}

.mouth {
  position: absolute;
  left: 50%;
  bottom: 18px;
  width: 14px;
  height: 4px;
  margin-left: -7px;
  border-radius: 0 0 10px 10px;
  border-bottom: 2px solid #5a7080;
  transition: width 0.25s ease, height 0.25s ease, border-radius 0.25s ease;
}

/* postures */
.posture-talking .mouth {
  width: 10px;
  height: 8px;
  border-radius: 50%;
  border: 2px solid #5a7080;
  border-top: none;
  animation: talk 0.45s ease-in-out infinite;
}

.posture-thinking .head {
  transform: rotate(-6deg) translateY(2px);
}

.posture-happy .body {
  transform: translateY(-4px);
}

.posture-happy .mouth {
  width: 18px;
  height: 6px;
}

.posture-sleeping .eye {
  height: 2px;
  top: 38px;
  border-radius: 2px;
}

.posture-sleeping .mouth {
  width: 8px;
  height: 2px;
  border-radius: 2px;
}

.posture-sleeping .halo {
  opacity: 0.28;
  animation: none;
}

/* expressions */
.expr-soft_smile .mouth,
.expr-happy .mouth {
  width: 16px;
  height: 5px;
}

.expr-quiet .mouth {
  width: 10px;
  height: 1px;
  border-radius: 1px;
}

.expr-surprised .eye {
  height: 12px;
  width: 9px;
}

.expr-surprised .mouth {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 2px solid #5a7080;
}

.expr-sleepy .eye {
  height: 4px;
}

.expr-curious .head {
  transform: rotate(5deg);
}

/* effects */
.bubbles span,
.sparkles i,
.leaves em,
.snow b {
  position: absolute;
  pointer-events: none;
}

.bubbles span {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 1px solid rgba(200, 230, 255, 0.55);
  animation: float 3s ease-in-out infinite;
}
.bubbles span:nth-child(1) {
  left: 28px;
  top: 20px;
}
.bubbles span:nth-child(2) {
  left: 120px;
  top: 40px;
  animation-delay: 0.6s;
}
.bubbles span:nth-child(3) {
  left: 70px;
  top: 8px;
  animation-delay: 1.2s;
}

.sparkles i {
  width: 4px;
  height: 4px;
  background: var(--warm);
  border-radius: 50%;
  animation: twinkle 1.6s ease-in-out infinite;
}
.sparkles i:nth-child(1) {
  left: 24px;
  top: 30px;
}
.sparkles i:nth-child(2) {
  left: 130px;
  top: 50px;
  animation-delay: 0.4s;
}
.sparkles i:nth-child(3) {
  left: 90px;
  top: 12px;
  animation-delay: 0.8s;
}

.leaves em {
  width: 8px;
  height: 12px;
  background: #c48a5a;
  border-radius: 50% 0;
  animation: fall 4s linear infinite;
  opacity: 0.7;
}
.leaves em:nth-child(1) {
  left: 20px;
}
.leaves em:nth-child(2) {
  left: 80px;
  animation-delay: 1s;
}
.leaves em:nth-child(3) {
  left: 130px;
  animation-delay: 2s;
}

.snow b {
  width: 3px;
  height: 3px;
  background: #fff;
  border-radius: 50%;
  opacity: 0.7;
  animation: fall 5s linear infinite;
}
.snow b:nth-child(1) {
  left: 30px;
}
.snow b:nth-child(2) {
  left: 70px;
  animation-delay: 0.8s;
}
.snow b:nth-child(3) {
  left: 110px;
  animation-delay: 1.6s;
}
.snow b:nth-child(4) {
  left: 145px;
  animation-delay: 2.4s;
}

@keyframes breathe {
  0%,
  100% {
    transform: scale(1);
    opacity: 0.45;
  }
  50% {
    transform: scale(1.06);
    opacity: 0.7;
  }
}

@keyframes talk {
  0%,
  100% {
    height: 4px;
  }
  50% {
    height: 10px;
  }
}

@keyframes float {
  0%,
  100% {
    transform: translateY(0);
    opacity: 0.4;
  }
  50% {
    transform: translateY(-14px);
    opacity: 0.9;
  }
}

@keyframes twinkle {
  0%,
  100% {
    opacity: 0.2;
    transform: scale(0.8);
  }
  50% {
    opacity: 1;
    transform: scale(1.3);
  }
}

@keyframes fall {
  0% {
    transform: translateY(-10px) rotate(0deg);
    opacity: 0;
  }
  20% {
    opacity: 0.8;
  }
  100% {
    transform: translateY(160px) rotate(120deg);
    opacity: 0;
  }
}
</style>
