/** 关于栖 · 常量（P3） */

export const QI_RELEASES_URL = "https://github.com/carlospan/qi-perch/releases";

export function isTauriShell(): boolean {
  return "__TAURI_INTERNALS__" in window || "__TAURI__" in window;
}

/** Tauri：读壳版本；Vite：package 注入版本 +「开发」 */
export async function resolveAppVersionLabel(): Promise<string> {
  const fallback =
    (typeof import.meta.env.VITE_QI_VERSION === "string" &&
      import.meta.env.VITE_QI_VERSION) ||
    "0.1.0";

  if (!isTauriShell()) {
    return `${fallback}（开发）`;
  }

  try {
    const { getVersion } = await import("@tauri-apps/api/app");
    return await getVersion();
  } catch {
    return fallback;
  }
}
