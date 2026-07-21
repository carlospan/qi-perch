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
  gap: 0.45rem;
}

input {
  flex: 1;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(0, 0, 0, 0.22);
  color: var(--ink);
  border-radius: 999px;
  padding: 0.55rem 0.9rem;
  outline: none;
  font-size: 0.9rem;
}

input:focus {
  border-color: rgba(126, 184, 201, 0.55);
}

button {
  border: none;
  border-radius: 999px;
  padding: 0.55rem 0.95rem;
  background: linear-gradient(135deg, #6fa3b5, #4d7f91);
  color: #f2f7fb;
  cursor: pointer;
  font-size: 0.88rem;
}

button:hover {
  filter: brightness(1.08);
}
</style>
