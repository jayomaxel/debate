export type MessageType =
  | 'state_update'
  | 'user_joined'
  | 'user_left'
  | 'phase_change'
  | 'segment_change'
  | 'timer_update'
  | 'subtitle'
  | 'speech'
  | 'audio'
  | 'grab_mic'
  | 'request_recording'
  | 'select_speaker'
  | 'recording_permission'
  | 'permission_denied'
  | 'mic_grabbed'
  | 'mic_released'
  | 'speaker_selected'
  | 'start_debate'
  | 'advance_segment'
  | 'end_turn'
  | 'end_debate'
  | 'debate_processing'
  | 'debate_ended'
  | 'speech_playback_started'
  | 'speech_playback_finished'
  | 'speech_playback_failed'
  | 'tts_stream_start'
  | 'tts_stream_chunk'
  | 'tts_stream_end'
  | 'ping'
  | 'pong'
  | 'error';

export type EventHandler = (data: Record<string, unknown>) => void;

interface WebSocketClientOptions {
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  heartbeatInterval?: number;
}

type ImportMetaWithEnv = ImportMeta & {
  env?: {
    VITE_API_BASE_URL?: string;
  };
};

const getWebSocketBaseUrl = () => {
  const envBase = (
    (import.meta as ImportMetaWithEnv).env?.VITE_API_BASE_URL || ''
  ).replace(/\/+$/, '');
  if (envBase) {
    return envBase
      .replace(/^https:/, 'wss:')
      .replace(/^http:/, 'ws:')
      .replace(/\/api$/, '');
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}`;
};

export default class WebSocketClient {
  private socket: WebSocket | null = null;
  private handlers = new Map<MessageType, Set<EventHandler>>();
  private reconnectAttempts = 0;
  private reconnectTimer: number | null = null;
  private heartbeatTimer: number | null = null;
  private closedByUser = false;
  private currentRoomId: string | null = null;
  private currentToken: string | null = null;
  private readonly reconnectInterval: number;
  private readonly maxReconnectAttempts: number;
  private readonly heartbeatInterval: number;

  constructor(options: WebSocketClientOptions = {}) {
    this.reconnectInterval = options.reconnectInterval ?? 3000;
    this.maxReconnectAttempts = options.maxReconnectAttempts ?? 5;
    this.heartbeatInterval = options.heartbeatInterval ?? 30000;
  }

  async connect(roomId: string, token: string): Promise<void> {
    this.disconnect(false);
    this.closedByUser = false;
    this.currentRoomId = roomId;
    this.currentToken = token;

    const url = `${getWebSocketBaseUrl()}/ws/debate/${encodeURIComponent(roomId)}?token=${encodeURIComponent(token)}`;

    await new Promise<void>((resolve, reject) => {
      const socket = new WebSocket(url);
      this.socket = socket;

      socket.onopen = () => {
        this.reconnectAttempts = 0;
        this.startHeartbeat();
        resolve();
      };

      socket.onmessage = (event) => {
        this.handleMessage(event.data);
      };

      socket.onerror = () => {
        reject(new Error('WebSocket connection failed'));
      };

      socket.onclose = () => {
        this.stopHeartbeat();
        if (!this.closedByUser) {
          this.scheduleReconnect();
        }
      };
    });
  }

  disconnect(markClosedByUser = true): void {
    if (markClosedByUser) {
      this.closedByUser = true;
    }

    if (this.reconnectTimer !== null) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    this.stopHeartbeat();
    this.socket?.close();
    this.socket = null;
  }

  isConnected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }

  send(type: MessageType, data: unknown): void {
    if (!this.isConnected()) {
      return;
    }

    this.socket?.send(JSON.stringify({ type, data }));
  }

  on(type: MessageType, handler: EventHandler): void {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, new Set());
    }

    this.handlers.get(type)?.add(handler);
  }

  off(type: MessageType, handler: EventHandler): void {
    this.handlers.get(type)?.delete(handler);
  }

  private handleMessage(raw: string): void {
    try {
      const message = JSON.parse(raw) as {
        type?: MessageType;
        data?: Record<string, unknown>;
      };

      if (!message.type) {
        return;
      }

      const payload = message.data || {};
      this.handlers.get(message.type)?.forEach((handler) => handler(payload));
    } catch (error) {
      console.error('[WebSocketClient] Failed to parse message:', error);
    }
  }

  private scheduleReconnect(): void {
    if (
      !this.currentRoomId ||
      !this.currentToken ||
      this.reconnectAttempts >= this.maxReconnectAttempts
    ) {
      return;
    }

    this.reconnectAttempts += 1;
    this.reconnectTimer = window.setTimeout(() => {
      void this.connect(this.currentRoomId!, this.currentToken!).catch((error) => {
        console.error('[WebSocketClient] Reconnect failed:', error);
      });
    }, this.reconnectInterval);
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = window.setInterval(() => {
      this.send('ping', {});
    }, this.heartbeatInterval);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer !== null) {
      window.clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }
}
