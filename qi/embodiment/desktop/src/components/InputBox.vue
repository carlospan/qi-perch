<script setup lang="ts">
import { ref } from "vue";

const emit = defineEmits<{
  send: [text: string];
}>();

const text = ref("");

function submit() {
  const value = text.value.trim();
  if (!value) return;
  emit("send", value);
  text.value = "";
}
</script>

<template>
  <form class="input" @submit.prevent="submit">
    <input
      v-model="text"
      type="text"
      maxlength="500"
      placeholder="说点什么……"
      autocomplete="off"
    />
    <button type="submit">说</button>
  </form>
</template>

<style scoped>
.input {
  display: flex;
  align-items: center;
  gap: 10px;
  pointer-events: auto;
}

input {
  flex: 1;
  border: 1px solid color-mix(in srgb, var(--ink) 9%, transparent);
  background: color-mix(in srgb, var(--ink) 4.5%, transparent);
  color: var(--ink);
  border-radius: 999px;
  padding: 11px 18px;
  outline: none;
  font-family: var(--serif);
  font-size: 14px;
  transition:
    border-color 0.35s ease,
    background 0.35s ease;
}

input::placeholder {
  color: var(--ink-faint);
  font-weight: 300;
}

input:focus {
  border-color: color-mix(in srgb, var(--ember) 45%, transparent);
  background: color-mix(in srgb, var(--ink) 6%, transparent);
}

button {
  width: 38px;
  height: 38px;
  border: none;
  border-radius: 50%;
  padding: 0;
  background: linear-gradient(135deg, #8fb4c6, #5c8296);
  color: #0e1620;
  cursor: pointer;
  font-family: var(--serif);
  font-size: 15px;
  display: grid;
  place-items: center;
  transition:
    transform 0.25s ease,
    box-shadow 0.25s ease;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.35);
}

button:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 16px color-mix(in srgb, #8fb4c6 35%, transparent);
}
</style>
