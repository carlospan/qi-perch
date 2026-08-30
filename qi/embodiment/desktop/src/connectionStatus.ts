/** P2 · 通道离线文案（§〇.19；与 StatusBar / 状态页同源）。 */

export type OfflineKind = "never" | "reconnecting";

export type OfflineCopy = {
  title: string;
  next: string;
};

export function offlineStatusCopy(kind: OfflineKind): OfflineCopy {
  if (kind === "reconnecting") {
    return { title: "断了一下", next: "正在重连" };
  }
  return { title: "通道还没接上", next: "请确认栖后端在跑" };
}

export function offlineKindFromFlags(
  connected: boolean,
  everConnected: boolean
): OfflineKind | null {
  if (connected) return null;
  return everConnected ? "reconnecting" : "never";
}
