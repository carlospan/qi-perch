<script setup lang="ts">
import { computed } from "vue";
import type { ExploreCard } from "../types";

const props = defineProps<{
  card: ExploreCard;
}>();

const emit = defineEmits<{
  together: [url: string, title: string];
}>();

/** 与后端 explore._SEASON_ZH 同构；未知码兜底原样 */
const SEASON_ZH: Record<string, string> = {
  spring: "春",
  summer: "夏",
  autumn: "秋",
  winter: "冬",
};

const hits = computed(() => props.card.found?.entries ?? []);
const query = computed(() => props.card.found?.query?.trim() || "");
const seasonLabel = computed(() => {
  const s = (props.card.season || "").trim();
  return s ? SEASON_ZH[s] || s : "";
});

function onTogether(url: string, title: string) {
  const u = (url || "").trim();
  if (!u) return;
  emit("together", u, (title || "").trim());
}
</script>

<template>
  <article class="paper explore" aria-label="栖的见闻">
    <span class="mark">看</span>
    <p v-if="query" class="query">{{ query }}</p>
    <ul v-if="hits.length" class="hits">
      <li v-for="(h, i) in hits.slice(0, 3)" :key="i" class="hit">
        <span class="title">{{ h.title }}</span>
        <a
          v-if="h.url"
          :href="h.url"
          target="_blank"
          rel="noopener noreferrer"
          class="src"
          >↗</a
        >
        <button
          v-if="h.url"
          type="button"
          class="tog"
          @click="onTogether(h.url, h.title || '')"
        >
          一起看
        </button>
      </li>
    </ul>
    <footer v-if="seasonLabel" class="foot">{{ seasonLabel }}</footer>
  </article>
</template>

<style scoped>
/* N4：实拷 ActionCard 纸感，侧条更淡以区分「看」 */
.paper {
  position: relative;
  padding: 12px 14px 10px;
  background: var(--talk-qi-bg);
  border: 1px solid var(--talk-qi-bd);
  border-radius: 4px 14px 14px 14px;
  color: var(--ink);
}

.paper::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  width: 3px;
  height: 100%;
  border-radius: 4px 0 0 4px;
  background: color-mix(in srgb, var(--ember) 55%, transparent);
}

.paper.explore::before {
  background: color-mix(in srgb, var(--ember) 35%, transparent);
}

.mark {
  display: inline-block;
  font-family: var(--mono);
  font-size: 9.5px;
  letter-spacing: 2px;
  color: var(--ember);
  margin-bottom: 8px;
}

.query {
  font-family: var(--mono);
  font-size: 9.5px;
  color: var(--ink-faint);
  margin: 0 0 6px;
  letter-spacing: 0.5px;
}

.hits {
  list-style: none;
  margin: 0;
  padding: 0;
}

.hit {
  font-size: 11.5px;
  color: var(--ink-faint);
  line-height: 1.6;
}

.hit .title {
  font-family: "Noto Serif SC", "Songti SC", "SimSun", serif;
}

.hit .src {
  margin-left: 4px;
  text-decoration: none;
  color: var(--ink-faint);
}

.hit .src:hover {
  color: var(--ember);
}

.tog {
  margin-left: 6px;
  padding: 0;
  border: none;
  background: none;
  font-family: var(--mono);
  font-size: 9.5px;
  letter-spacing: 0.5px;
  color: var(--ember);
  cursor: pointer;
  opacity: 0.85;
}

.tog:hover {
  opacity: 1;
  text-decoration: underline;
}

.foot {
  margin-top: 10px;
  font-family: var(--mono);
  font-size: 9.5px;
  letter-spacing: 1px;
  color: var(--ink-faint);
}
</style>
