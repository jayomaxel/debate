import { getWebSocketBaseUrl as getRuntimeWebSocketBaseUrl } from './runtime-url';

export type MessageType =
  | 'room_joined'
  | 'state_update'
  | 'user_joined'
  | 'user_left'
  | 'phase_change'
  | 'phase_timeout'
  | 'segment_change'
  | 'segment_timeout'
  | 'timer_update'
  | 'subtitle'
  | 'speech'
  | 'audio'
  | 'grab_mic'
  | 'request_recording'
  | 'select_speaker'
  | 'waiting_checklist_update'
  | 'recording_permission'
  | 'audio_processed'
  | 'permission_denied'
  | 'mic_grabbed'
  | 'mic_released'
  | 'speaker_selected'
  | 'start_debate'
  | 'advance_segment'
  | 'end_turn'
  | 'end_debate'
  | 'debate_processing'
  | 'debate_started'
  | 'debate_ended'
  | 'debate_end_failed'
  | 'advance_blocked'
  | 'advance_deferred'
  | 'moderator_transferred'
  | 'moderator_missing'
  | 'ai_turn_failed'
  | 'ai_turn_skipped'
  | 'playback_controller_appointed'
  | 'speech_playback_started'
  | 'speech_playback_finished'
  | 'speech_playback_failed'
  | 'speech_playback_skipped'
  | 'tts_stream_start'
  | 'tts_stream_chunk'
  | 'tts_stream_end'
  | 'ping'
  | 'pong'
  | 'error';

export type EventHandler = (data: Record<string, unknown>) => void;

export const getWebSocketBaseUrl = getRuntimeWebSocketBaseUrl;

interface WebSocketClientOptions {
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  heartbeatInterval?: number;
  onOpen?: () => void;
  onClose?: (event?: CloseEvent) => void;
  onError?: (error: Event) => void;
}

export const buildDebateWebSocketUrl = (roomId: string, token?: string) => {
  const baseUrl = getWebSocketBaseUrl();
  const roomPath = `/ws/debate/${encodeURIComponent(roomId)}`;
  if (!token) {
    return `${baseUrl}${roomPath}`;
  }
  return `${baseUrl}${roomPath}?token=${encodeURIComponent(token)}`;
};

export default class WebSocketClient {
  private socket: WebSocket | null = null;
  private handlers = new Map<MessageType, Set<EventHandler>>();
  private reconnectAttempts = 0;
  private reconnectTimer: number | null = null;
  private heartbeatTimer: number | null = null;
  private closedByUser = false;
  private hasConnected = false;
  private currentRoomId: string | null = null;
  private currentToken: string | null = null;
  private readonly reconnectInterval: number;
  private readonly maxReconnectAttempts: number;
  private readonly heartbeatInterval: number;
  private readonly onOpen?: () => void;
  private readonly onClose?: (event?: CloseEvent) => void;
  private readonly onError?: (error: Event) => void;

  constructor(options: WebSocketClientOptions = {}) {
    this.reconnectInterval = options.reconnectInterval ?? 3000;
    this.maxReconnectAttempts = options.maxReconnectAttempts ?? 5;
    this.heartbeatInterval = options.heartbeatInterval ?? 30000;
    this.onOpen = options.onOpen;
    this.onClose = options.onClose;
    this.onError = options.onError;
  }

  async connect(roomId: string, token: string): Promise<void> {
    this.disconnect(false);
    this.closedByUser = false;
    this.currentRoomId = roomId;
    this.currentToken = token;

    const url = buildDebateWebSocketUrl(roomId, token);
    const debugUrl = buildDebateWebSocketUrl(roomId);
    console.debug('[WebSocketClient] Connecting to debate websocket', {
      roomId,
      url: debugUrl,
    });

    await new Promise<void>((resolve, reject) => {
      const socket = new WebSocket(url);
      this.socket = socket;

      socket.onopen = () => {
        this.reconnectAttempts = 0;
        this.hasConnected = true;
        this.startHeartbeat();
        console.debug('[WebSocketClient] Debate websocket connected', {
          roomId,
          url: debugUrl,
        });
        this.onOpen?.();
        resolve();
      };

      socket.onmessage = (event) => {
        this.handleMessage(event.data);
      };

      socket.onerror = (event) => {
        console.error('[WebSocketClient] Debate websocket error', {
          roomId,
          url: debugUrl,
        });
        this.onError?.(event);
        reject(new Error('WebSocket connection failed'));
      };

      socket.onclose = (event) => {
        this.stopHeartbeat();
        this.socket = null;
        console.warn('[WebSocketClient] Debate websocket closed', {
          roomId,
          url: debugUrl,
          code: event.code,
          reason: event.reason,
          wasClean: event.wasClean,
          closedByUser: this.closedByUser,
        });
        this.onClose?.(event);
        if (!this.closedByUser && this.hasConnected) {
          this.scheduleReconnect();
        }
      };
    });
  }

  disconnect(markClosedByUser = true): void {
    if (markClosedByUser) {
      this.closedByUser = true;
      this.hasConnected = false;
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
