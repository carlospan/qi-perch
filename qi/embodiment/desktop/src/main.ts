import { createApp } from "vue";
import App from "./App.vue";

/* 字体打包进应用，不依赖运行时 CDN */
import "@fontsource/noto-serif-sc/300.css";
import "@fontsource/noto-serif-sc/400.css";
import "@fontsource/noto-serif-sc/600.css";
import "@fontsource/ibm-plex-mono/300.css";
import "@fontsource/ibm-plex-mono/400.css";

import "./style.css";

createApp(App).mount("#app");
