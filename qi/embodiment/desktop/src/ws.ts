import type { ClientMessage, ServerMessage } from "./types";

const WS_URL = "ws://127.0.0.1:9527";
const RECONNECT_MAX_DELAY = 30000;

type Handler = (payload: any) => void;

export type QiWebSocketOptions = {
  /**
   * 是否上报在场（默认 true）。
   * 桌宠窗只听广播，勿抢聊天壳的 presence，否则关掉宠窗会误标离线。
   */
  managePresence?: boolean;
};

export class QiWebSocket {
  private ws: WebSocket | null = null;
  private reconnectDelay = 1000;
  private handlers = new Map<string, Handler[]>();
  private reconnectTimer: number | null = null;
  private closedByUser = false;
  private managePresence: boolean;

  constructor(options: QiWebSocketOptions = {}) {
    this.managePresence = options.managePresence !== false;
  }

  connect() {
    this.closedByUser = false;
    this.ws = new WebSocket(WS_URL);
    this.ws.onopen = () => {
      this.reconnectDelay = 1000;
      if (this.managePresence) {
        this.send({ type: "presence", payload: { online: true } });
      }
      this.emit("open", {});
    };
    this.ws.onmessage = (event) => {
      const msg = JSON.parse(event.data as string) as ServerMessage;
      if (msg.type === "ping") {
        this.send({ type: "pong", payload: { ts: msg.payload.ts } });
      }
      this.emit(msg.type, msg.payload);
    };
    this.ws.onclose = () => {
      this.emit("close", {});
      if (!this.closedByUser) this.scheduleReconnect();
    };
    this.ws.onerror = () => this.ws?.close();
  }

  private scheduleReconnect() {
    if (this.reconnectTimer != null) return;
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, this.reconnectDelay);
    this.reconnectDelay = Math.min(this.reconnectDelay * 2, RECONNECT_MAX_DELAY);
  }

  send(msg: ClientMessage) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }

  sendUserMessage(text: string) {
    this.send({ type: "user_message", payload: { text } });
  }

  setPresence(online: boolean) {
    this.send({ type: "presence", payload: { online } });
  }

  on(type: string, handler: Handler) {
    if (!this.handlers.has(type)) this.handlers.set(type, []);
    this.handlers.get(type)!.push(handler);
  }

  private emit(type: string, payload: any) {
    this.handlers.get(type)?.forEach((h) => h(payload));
  }

  disconnect() {
    this.closedByUser = true;
    if (this.reconnectTimer != null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.managePresence) {
      this.setPresence(false);
    }
    this.ws?.close();
  }
}

export const qiWs = new QiWebSocket();
