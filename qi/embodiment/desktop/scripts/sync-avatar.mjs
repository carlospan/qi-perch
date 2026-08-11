import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const src = join(root, "..", "assets", "qi-avatar.vrm");
const destDir = join(root, "public", "avatars");
const dest = join(destDir, "qi-avatar.vrm");

if (!existsSync(src)) {
  console.warn(`[sync-avatar] 未找到 ${src}，跳过同步`);
  process.exit(0);
}

mkdirSync(destDir, { recursive: true });
copyFileSync(src, dest);
console.log(`[sync-avatar] → ${dest}`);
