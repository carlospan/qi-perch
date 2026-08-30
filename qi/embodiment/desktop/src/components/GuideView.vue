<script setup lang="ts">
import { ADOPT_GUIDE } from "../content/adoptGuide";

const emit = defineEmits<{
  close: [];
  openSettings: [];
}>();
</script>

<template>
  <div class="desk-page guide">
    <div class="desk-main">
      <header class="page-hero">
        <div class="page-hero-row">
          <h2>{{ ADOPT_GUIDE.title }}</h2>
          <button type="button" class="back" @click="emit('close')">返回</button>
        </div>
        <p class="page-hero-sub">{{ ADOPT_GUIDE.lead }}</p>
      </header>

      <div class="desk-scroll form-wrap">
        <ol class="steps">
          <li v-for="(s, i) in ADOPT_GUIDE.steps" :key="i" class="step">
            <span class="step-n">{{ i + 1 }}</span>
            <div class="step-body">
              <h3>{{ s.title }}</h3>
              <p>{{ s.body }}</p>
            </div>
          </li>
        </ol>

        <ul class="notes">
          <li v-for="(n, i) in ADOPT_GUIDE.notes" :key="i">{{ n }}</li>
        </ul>

        <div class="actions">
          <button type="button" class="go-settings" @click="emit('openSettings')">
            去设置贴钥匙
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.guide.desk-page {
  position: relative;
  flex: 1;
  min-height: 0;
  grid-template-columns: minmax(0, 1fr);
}

.page-hero-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.back {
  border: 1px solid color-mix(in srgb, var(--ink) 14%, transparent);
  background: transparent;
  color: var(--ink-dim);
  font-family: var(--mono);
  font-size: 0.72rem;
  letter-spacing: 0.06em;
  padding: 0.35rem 0.7rem;
  border-radius: 4px;
  cursor: pointer;
}

.back:hover {
  color: var(--ink);
  border-color: color-mix(in srgb, var(--ember) 40%, transparent);
}

.form-wrap {
  max-width: 32rem;
  padding: 8px var(--page-pad-x, 1.5rem) 2rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.steps {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.step {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
}

.step-n {
  flex-shrink: 0;
  width: 1.6rem;
  height: 1.6rem;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-family: var(--mono);
  font-size: 0.72rem;
  color: #2a2118;
  background: linear-gradient(180deg, #dfc39a 0%, #c49a68 100%);
  margin-top: 0.15rem;
}

.step-body h3 {
  margin: 0 0 0.35rem;
  font-family: var(--serif);
  font-size: 1rem;
  font-weight: 500;
  letter-spacing: 0.08em;
  color: color-mix(in srgb, var(--ember) 70%, var(--ink));
}

.step-body p {
  margin: 0;
  font-family: var(--serif);
  font-size: 0.9rem;
  line-height: 1.55;
  letter-spacing: 0.03em;
  color: color-mix(in srgb, var(--ink) 88%, transparent);
}

.notes {
  margin: 0;
  padding: 0.75rem 0.9rem;
  list-style: none;
  border-radius: 8px;
  border: 1px solid color-mix(in srgb, var(--ink) 10%, transparent);
  background: color-mix(in srgb, var(--ink) 4%, transparent);
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.notes li {
  font-size: 0.78rem;
  line-height: 1.45;
  color: var(--ink-dim);
  letter-spacing: 0.03em;
}

.notes li::before {
  content: "· ";
  color: var(--ember);
}

.actions {
  margin-top: 0.25rem;
}

.go-settings {
  font-family: var(--serif);
  font-size: 0.9rem;
  letter-spacing: 0.1em;
  padding: 0.55rem 1.1rem;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  color: #2a2118;
  background: linear-gradient(180deg, #dfc39a 0%, #c49a68 100%);
}

.go-settings:hover {
  filter: brightness(1.05);
}
</style>
