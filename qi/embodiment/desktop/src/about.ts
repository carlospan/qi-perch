/** 关于栖 · 常量与检查更新（P3） */

export const QI_RELEASES_URL = "https://github.com/carlospan/qi-perch/releases";

export const QI_LATEST_RELEASE_API =
  "https://api.github.com/repos/carlospan/qi-perch/releases/latest";

export function isTauriShell(): boolean {
  return "__TAURI_INTERNALS__" in window || "__TAURI__" in window;
}

/** Tauri：读壳版本；Vite：package 注入版本 +「开发」 */
export async function resolveAppVersionLabel(): Promise<string> {
  const fallback =
    (typeof import.meta.env.VITE_QI_VERSION === "string" &&
      import.meta.env.VITE_QI_VERSION) ||
    "0.1.2";

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

/** 去掉 v 前缀与「（开发）」等展示后缀，得到可比对的版本串。 */
export function normalizeVersion(label: string): string {
  return label
    .replace(/（开发）/g, "")
    .replace(/\(dev(elopment)?\)/gi, "")
    .replace(/^v/i, "")
    .trim();
}

/**
 * 比较两个版本串（点分数字）。
 * @returns >0 若 a>b；<0 若 a<b；0 相等
 */
export function compareVersions(a: string, b: string): number {
  const pa = normalizeVersion(a)
    .split(".")
    .map((x) => {
      const n = parseInt(x, 10);
      return Number.isFinite(n) ? n : 0;
    });
  const pb = normalizeVersion(b)
    .split(".")
    .map((x) => {
      const n = parseInt(x, 10);
      return Number.isFinite(n) ? n : 0;
    });
  const n = Math.max(pa.length, pb.length);
  for (let i = 0; i < n; i++) {
    const da = pa[i] ?? 0;
    const db = pb[i] ?? 0;
    if (da !== db) return da - db;
  }
  return 0;
}

export type UpdateCheckResult =
  | {
      status: "latest";
      remote: string;
      message: string;
      isDevShell: boolean;
    }
  | {
      status: "newer";
      remote: string;
      message: string;
      isDevShell: boolean;
    }
  | { status: "error"; message: string };

export async function checkForUpdate(
  currentLabel: string,
  fetchImpl: typeof fetch = fetch
): Promise<UpdateCheckResult> {
  const isDevShell = /开发|\(dev/i.test(currentLabel);
  const local = normalizeVersion(currentLabel);
  const fail: UpdateCheckResult = {
    status: "error",
    message: "查更新失败，请检查网络或直接打开 Releases。",
  };

  try {
    const res = await fetchImpl(QI_LATEST_RELEASE_API, {
      headers: {
        Accept: "application/vnd.github+json",
        "User-Agent": "qi-desktop-update-check",
      },
    });
    if (!res.ok) {
      return {
        status: "error",
        message: "查更新失败，请稍后再试或直接打开 Releases。",
      };
    }
    const data = (await res.json()) as { tag_name?: string };
    const remote = normalizeVersion(String(data.tag_name || ""));
    if (!remote) {
      return fail;
    }
    const devNote = isDevShell ? "（当前是开发壳）" : "";
    if (compareVersions(remote, local) > 0) {
      return {
        status: "newer",
        remote,
        isDevShell,
        message: `有新版本 ${remote}。可到 GitHub Releases 下载安装。${devNote}`,
      };
    }
    return {
      status: "latest",
      remote,
      isDevShell,
      message: `已是最新（${local || remote}）。${devNote}`,
    };
  } catch {
    return fail;
  }
}
