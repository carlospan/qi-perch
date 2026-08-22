<script setup lang="ts">
import { computed, ref } from "vue";
import type { CreationCard, ExploreCard, TalkCardItem } from "../types";

export type ReviewFilter = "creation" | "explore";

const props = defineProps<{
  creations: TalkCardItem[];
  explores: TalkCardItem[];
}>();

const filter = ref<ReviewFilter>("creation");

const chips: { id: ReviewFilter; label: string }[] = [
  { id: "creation", label: "创作" },
  { id: "explore", label: "见闻" },
];

const SEASON_ZH: Record<string, string> = {
  spring: "春",
  summer: "夏",
  autumn: "秋",
  winter: "冬",
};

const TYPE_LABEL: Record<string, string> = {
  note: "笔记",
  poem: "小诗",
  essay: "随笔",
  description: "画面",
};

const list = computed(() => {
  const rows =
    filter.value === "creation" ? props.creations : props.explores;
  return [...rows].sort((a, b) => b.at - a.at);
});

function whenLabel(at: number) {
  const d = new Date(at);
  return `${d.getMonth() + 1}月${d.getDate()}日`;
}

function seasonOf(card: CreationCard | ExploreCard) {
  const s = (card.season || "").trim();
  return s ? SEASON_ZH[s] || s : "";
}

function creationTitle(card: CreationCard) {
  const t = (card.creation_type || "").trim().toLowerCase();
  const label = TYPE_LABEL[t];
  return label ? `创作 · ${label}` : "创作";
}

function exploreTitle(card: ExploreCard) {
  const src = (card.source || card.found?.source || "").trim();
  if (src === "web_delegate") return "帮忙 · 查资料";
  const season = seasonOf(card);
  if (season === "秋") return "见闻 · 秋分";
  return season ? `见闻 · ${season}` : "见闻";
}

function exploreBody(card: ExploreCard) {
  const summary = (card.summary || "").trim();
  if (summary) return summary;
  const titles = (card.found?.entries ?? [])
    .map((h) => h.title)
    .filter(Boolean)
    .slice(0, 2);
  return titles.join(" · ") || (card.found?.query || "").trim() || "……";
}
</script>

<template>
  <div class="desk-page review">
    <div class="desk-main">
      <header class="page-hero">
        <div class="page-hero-row">
          <h2>她留下的</h2>
          <svg class="page-hero-mark quill" viewBox="0 0 28 28" aria-hidden="true">
            <path
              fill="none"
              stroke="currentColor"
              stroke-width="1.35"
              stroke-linecap="round"
              d="M5 23c2.2-1.2 5.5-6.5 8.2-12.2C15.5 5.5 18.8 2 23 1.2"
            />
            <path
              fill="currentColor"
              d="M19.8 2.2c2.2 1.4 3.2 3.2 2.8 4.8-2.2-.1-4.6-1.6-6.4-3.4.9-.6 2.1-1 3.6-1.4z"
            />
          </svg>
        </div>
        <p class="page-hero-sub">回顾她的创作与见闻，那些被记得的瞬间。</p>
      </header>

      <div class="chips" role="tablist" aria-label="回顾分类">
      <button
        v-for="c in chips"
        :key="c.id"
        type="button"
        role="tab"
        :aria-selected="filter === c.id"
        :class="{ active: filter === c.id }"
        @click="filter = c.id"
      >
        <svg
          v-if="c.id === 'creation'"
          class="ico"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            fill="none"
            stroke="currentColor"
            stroke-width="1.5"
            stroke-linecap="round"
            d="M5 20c1.5-.8 4-4.5 6-9 1.6-3.6 4-6.2 7-7"
          />
          <path
            fill="currentColor"
            d="M16.5 3.2c1.7 1.1 2.5 2.5 2.2 3.8-1.7 0-3.6-1.2-5-2.6.8-.5 1.7-.9 2.8-1.2z"
          />
        </svg>
        <svg v-else class="ico" viewBox="0 0 24 24" aria-hidden="true">
          <path
            fill="currentColor"
            d="M7.5 13.5c0-3.8 3-7.5 4.5-9.2 1.5 1.7 4.5 5.4 4.5 9.2a4.5 4.5 0 11-9 0z"
          />
        </svg>
        {{ c.label }}
      </button>
      </div>

      <div class="desk-scroll">
        <p v-if="list.length === 0" class="empty">
          <template v-if="filter === 'creation'">还没有递过创作。</template>
          <template v-else>还没有留下见闻。</template>
        </p>

        <div v-else class="card-grid">
          <article
        v-for="(item, idx) in list"
        :key="item.id"
        class="card"
        :class="[filter, idx % 2 ? 'tilt-b' : 'tilt-a']"
      >
        <div class="sheet" aria-hidden="true" />
        <div class="grain" aria-hidden="true" />

        <div
          v-if="item.card.type === 'creation_card'"
          class="bookmark"
          aria-hidden="true"
        >
          <svg viewBox="0 0 28 52" width="20" height="38">
            <defs>
              <linearGradient :id="`rb-${item.id}`" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#d66a55" />
                <stop offset="50%" stop-color="#a83a2c" />
                <stop offset="100%" stop-color="#7a241c" />
              </linearGradient>
            </defs>
            <path
              :fill="`url(#rb-${item.id})`"
              d="M5 0h18v36l-9 11-9-11z"
            />
            <rect x="3" y="0" width="22" height="3.5" fill="#5c1a14" opacity="0.5" />
            <text
              x="14"
              y="19"
              text-anchor="middle"
              fill="#f6ebe3"
              font-size="10"
            >
              ★
            </text>
          </svg>
        </div>

        <svg
          v-else
          class="clip"
          viewBox="0 0 36 56"
          width="26"
          height="42"
          aria-hidden="true"
        >
          <path
            fill="none"
            stroke="#8b97a3"
            stroke-width="3"
            stroke-linecap="round"
            d="M12 20v18a6 6 0 0012 0V14a4.5 4.5 0 00-9 0v22a2.6 2.6 0 005.2 0V20"
          />
        </svg>

        <svg
          v-if="item.card.type === 'explore_drift'"
          class="botany"
          viewBox="0 0 90 100"
          aria-hidden="true"
        >
          <path
            fill="#9aabba"
            opacity="0.2"
            d="M70 10C46 22 28 46 24 70c16-5 36-16 48-34 3 16-4 32-18 44 26-10 40-32 38-54-10 7-14 2-18-16z"
          />
        </svg>

        <div class="inner">
          <template v-if="item.card.type === 'creation_card'">
            <div class="kicker">{{ creationTitle(item.card) }}</div>
            <p class="body">{{ item.card.content }}</p>
            <footer class="foot">
              <span>{{ whenLabel(item.at) }}</span>
              <span class="stamp">栖</span>
            </footer>
          </template>
          <template v-else-if="item.card.type === 'explore_drift'">
            <div class="kicker">{{ exploreTitle(item.card) }}</div>
            <p class="body">{{ exploreBody(item.card) }}</p>
            <footer class="foot">
              <span>{{ whenLabel(item.at) }} · {{ (item.card.source === 'web_delegate' || item.card.found?.source === 'web_delegate') ? '你请她查的' : '来自 她的见闻' }}</span>
            </footer>
          </template>
        </div>
      </article>

          <div class="more">
            <span class="line" />
            <span class="txt">还有更多被收藏的片段</span>
            <span class="line" />
          </div>
        </div>
      </div>
    </div>

    <aside class="desk-aside" aria-hidden="true">
      <div class="desk-aside-bg" />
      <div class="desk-aside-veil" />
      <div class="desk-aside-copy">
        <p class="desk-aside-eyebrow">ARCHIVE</p>
        <p class="desk-aside-quote">
          纸页会泛黄，字句却还在。这里收着她愿意递出来的那一部分。
        </p>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.quill {
  transform: rotate(-12deg);
}

.chips {
  display: flex;
  gap: 10px;
  padding: 20px var(--page-pad-x) 18px;
  flex-shrink: 0;
}

.chips button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border-radius: 999px;
  border: 1px solid color-mix(in srgb, var(--ink) 14%, transparent);
  background: color-mix(in srgb, #070b14 38%, transparent);
  color: var(--ink-faint);
  font-family: var(--serif);
  font-size: 13px;
  letter-spacing: 0.14em;
  padding: 9px 20px;
  cursor: pointer;
  transition:
    background 0.25s ease,
    color 0.25s ease,
    box-shadow 0.25s ease,
    border-color 0.25s ease;
}

.chips button .ico {
  width: 14px;
  height: 14px;
}

.chips button.active {
  color: #2a2118;
  border-color: transparent;
  background: linear-gradient(180deg, #dfc39a 0%, #c49a68 100%);
  box-shadow:
    0 0 0 1px color-mix(in srgb, #b88855 40%, transparent),
    0 8px 22px color-mix(in srgb, var(--ember) 28%, transparent);
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 22px 24px;
  align-items: start;
}

.empty {
  margin: 56px auto;
  max-width: 28ch;
  text-align: center;
  font-size: 14px;
  line-height: 1.8;
  color: var(--ink-faint);
  font-weight: 300;
}

.card {
  position: relative;
  animation: up 0.45s ease both;
}

.card.tilt-a {
  transform: rotate(-0.35deg);
}
.card.tilt-b {
  transform: rotate(0.45deg);
}

.sheet,
.grain {
  position: absolute;
  inset: 0;
  pointer-events: none;
  border-radius: 10px;
}

.sheet {
  box-shadow: 0 14px 28px rgba(0, 0, 0, 0.4);
}

.card.creation .sheet {
  background: linear-gradient(165deg, #f7efe3 0%, #ebe0cf 55%, #e2d4c0 100%);
}

.card.explore .sheet {
  background: linear-gradient(165deg, #eef3f6 0%, #dde6ec 55%, #d0dae3 100%);
}

.grain {
  opacity: 0.32;
  mix-blend-mode: multiply;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='160' height='160' filter='url(%23n)' opacity='0.55'/%3E%3C/svg%3E");
}

.card.explore .grain {
  opacity: 0.2;
  mix-blend-mode: soft-light;
}

.card.creation {
  color: #2a221a;
}
.card.explore {
  color: #1d2831;
}

.bookmark {
  position: absolute;
  top: -1px;
  right: 20px;
  z-index: 3;
  filter: drop-shadow(0 3px 4px rgba(60, 15, 10, 0.4));
  pointer-events: none;
}

.clip {
  position: absolute;
  top: -10px;
  right: 16px;
  z-index: 3;
  filter: drop-shadow(1px 2px 2px rgba(0, 0, 0, 0.28));
  transform: rotate(8deg);
  pointer-events: none;
}

.botany {
  position: absolute;
  right: 8px;
  bottom: 22px;
  width: 76px;
  height: 84px;
  z-index: 1;
  pointer-events: none;
}

.inner {
  position: relative;
  z-index: 2;
  padding: 18px 20px 16px;
}

.kicker {
  font-family: var(--serif);
  font-size: 11px;
  letter-spacing: 2px;
  color: #9a4a38;
  margin-bottom: 12px;
}

.card.explore .kicker {
  color: #5a7080;
}

.body {
  margin: 0;
  font-family: var(--serif);
  font-size: 14px;
  line-height: 1.95;
  font-weight: 400;
  white-space: pre-wrap;
  word-break: break-word;
}

.foot {
  margin-top: 18px;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 10px;
  font-family: var(--mono);
  font-size: 10.5px;
  letter-spacing: 0.4px;
  color: color-mix(in srgb, currentColor 40%, transparent);
}

.stamp {
  width: 32px;
  height: 32px;
  border: 1.7px solid #b0432f;
  color: #b0432f;
  border-radius: 2px;
  display: grid;
  place-items: center;
  font-family: var(--serif);
  font-size: 14px;
  transform: rotate(-8deg);
  opacity: 0.9;
  box-shadow: inset 0 0 0 1px color-mix(in srgb, #b0432f 25%, transparent);
}

.more {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 28px 2px 8px;
  grid-column: 1 / -1;
}

.more .line {
  flex: 1;
  height: 1px;
  background: color-mix(in srgb, var(--ink) 14%, transparent);
}

.more .txt {
  font-size: 11px;
  color: var(--ink-faint);
  letter-spacing: 1px;
  font-weight: 300;
  white-space: nowrap;
}

@keyframes up {
  from {
    opacity: 0;
    translate: 0 10px;
  }
  to {
    opacity: 1;
    translate: 0 0;
  }
}
</style>
