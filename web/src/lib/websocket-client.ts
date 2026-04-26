/**
 * WebSocket客户端服务
 * 用于辩论房间的实时通信
 */

import {
  audioPlaybackDebug,
  shouldDebugAudioMessageType,
} from './utils';

type MessageType =
  | 'join'
  | 'leave'
  | 'user_joined'
  | 'user_left'
  | 'debate_started'
  | 'debate_processing'
  | 'debate_ended'
  | 'speech'
  | 'tts_stream_start'
  | 'tts_stream_chunk'
  | 'tts_stream_end'
  | 'grab_mic'
  | 'mic_grabbed'
  | 'mic_released'
  | 'permission_denied'
  | 'request_recording'
  | 'recording_permission'
  | 'select_speaker'
  | 'speaker_selected'
  | 'start_debate'
  | 'advance_segment'
  | 'end_turn'
  | 'end_debate'
  | 'speech_playback_started'
  | 'speech_playback_finished'
  | 'speech_playback_failed'
  | 'playback_controller_appointed'
  | 'state_update'
  | 'phase_change'
  | 'segment_change'
  | 'timer_update'
  | 'audio'
  | 'audio_processed'
  | 'subtitle'
  | 'ai_speech'
  | 'ping'
  | 'pong'
  | 'error';

interface WebSocketMessage {
  type: MessageType;
  data: any;
  timestamp?: number;
}

type EventHandler = (data: any) => void;

interface WebSocketClientOptions {
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  heartbeatInterval?: number;
}

class WebSocketClient {
  private ws: WebSocket | null = null;
  private url: string = '';
  private token: string = '';
  private roomId: string = '';
  // 用连接代际编号屏蔽过期连接，避免 StrictMode 首次双挂载时旧连接晚到并继续分发消息。
  private connectionGeneration: number = 0;
  // 使用 Set 去重同一处理器，避免组件重复注册后同一条消息被分发多次。
  private eventHandlers: Map<MessageType, Set<EventHandler>> = new Map();
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 5;
  private reconnectInterval: number = 3000;
  private heartbeatInterval: number = 30000;
  private heartbeatTimer: number | null = null;
  private reconnectTimer: number | null = null;
  private isManualClose: boolean = false;

  constructor(options: WebSocketClientOptions = {}) {
    this.maxReconnectAttempts = options.maxReconnectAttempts || 5;
    this.reconnectInterval = options.reconnectInterval || 3000;
    this.heartbeatInterval = options.heartbeatInterval || 30000;
  }


  /**
   * 连接到WebSocket服务器
   * @param roomId 辩论房间ID
   * @param token JWT认证令牌
   */
  connect(roomId: string, token: string): Promise<void> {
    return new Promise((resolve, reject) => {
      this.roomId = roomId;
      this.token = token;
      this.isManualClose = false;
      const currentGeneration = ++this.connectionGeneration;

      // 构建WebSocket URL
      const wsBaseURL = (import.meta as any).env?.VITE_WS_BASE_URL as string | undefined;
      if (wsBaseURL) {
        const base = wsBaseURL.replace(/\/$/, '');
        this.url = `${base}/ws/debate/${roomId}?token=${encodeURIComponent(token)}`;
      } else {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        this.url = `${protocol}//${host}/ws/debate/${roomId}?token=${encodeURIComponent(token)}`;
      }

      try {
        // 新连接开始前先主动关闭旧连接，避免同一客户端短时间内持有两条房间连接。
        if (this.ws) {
          try {
            this.ws.close(1000, 'Superseded by newer connection');
          } catch {
            // 旧连接可能已经处于关闭中，这里忽略关闭异常即可。
          }
        }

        const socket = new WebSocket(this.url);
        this.ws = socket;
        let isResolved = false;
        // 记录连接参数，便于确认当前房间是否建立了重复连接。
        audioPlaybackDebug('WebSocketClient', '准备建立 websocket 连接', {
          roomId,
          url: this.url,
          generation: currentGeneration,
        });

        const isStaleConnection = (): boolean => {
          return currentGeneration !== this.connectionGeneration || this.ws !== socket;
        };

        socket.onopen = () => {
          if (isStaleConnection()) {
            audioPlaybackDebug('WebSocketClient', '忽略过期 websocket 连接的 onopen', {
              roomId: this.roomId,
              generation: currentGeneration,
            });
            try {
              socket.close(1000, 'Stale connection');
            } catch {
              // 过期连接已不可用时无需继续处理。
            }
            if (!isResolved) {
              isResolved = true;
              reject(new Error('Connection cancelled'));
            }
            return;
          }
          console.log('WebSocket connected');
          audioPlaybackDebug('WebSocketClient', 'websocket 连接已建立', {
            roomId: this.roomId,
            generation: currentGeneration,
          });
          this.reconnectAttempts = 0;
          this.startHeartbeat();
          isResolved = true;
          resolve();
        };

        socket.onmessage = (event) => {
          if (isStaleConnection()) {
            audioPlaybackDebug('WebSocketClient', '忽略过期 websocket 连接的消息', {
              roomId: this.roomId,
              generation: currentGeneration,
            });
            return;
          }
          this.handleMessage(event.data);
        };

        socket.onerror = (error) => {
          if (isStaleConnection()) {
            if (!isResolved) {
              isResolved = true;
              reject(new Error('Connection cancelled'));
            }
            return;
          }
          console.error('WebSocket error:', error);
          audioPlaybackDebug('WebSocketClient', 'websocket 发生错误', {
            roomId: this.roomId,
            error: String((error as any)?.message || error),
            generation: currentGeneration,
          });
          if (!isResolved) {
            isResolved = true;
            reject(error);
          }
        };

        socket.onclose = (event) => {
          const staleConnection = isStaleConnection();
          console.log('WebSocket closed:', event.code, event.reason);
          audioPlaybackDebug('WebSocketClient', 'websocket 已关闭', {
            roomId: this.roomId,
            code: event.code,
            reason: event.reason,
            manualClose: this.isManualClose,
            generation: currentGeneration,
            staleConnection,
          });
          if (!staleConnection) {
            this.stopHeartbeat();
          }

          // 如果连接从未成功建立，不要重连（让Promise reject处理）
          if (!isResolved) {
            isResolved = true;
            reject(
              new Error(
                staleConnection
                  ? 'Connection cancelled'
                  : `WebSocket closed before connection established: ${event.reason || event.code}`
              )
            );
            return;
          }

          if (staleConnection) {
            return;
          }

          // 如果不是手动关闭，尝试重连
          if (!this.isManualClose && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.scheduleReconnect();
          } else if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnect attempts reached');
          }
        };
      } catch (error) {
        reject(error);
      }
    });
  }

  /**
   * 断开WebSocket连接
   */
  disconnect(): void {
    this.isManualClose = true;
    this.stopHeartbeat();
    // 断开时推进连接代际，确保还在路上的旧连接回调全部失效。
    this.connectionGeneration += 1;
    audioPlaybackDebug('WebSocketClient', '手动断开 websocket', {
      roomId: this.roomId,
      generation: this.connectionGeneration,
    });
    
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
  }

  /**
   * 发送消息
   * @param type 消息类型
   * @param data 消息数据
   */
  send(type: MessageType, data: any): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.error('WebSocket is not connected');
      audioPlaybackDebug('WebSocketClient', '发送消息失败，websocket 未连接', {
        roomId: this.roomId,
        type,
      });
      return;
    }

    const message: WebSocketMessage = {
      type,
      data,
      timestamp: Date.now(),
    };

    this.ws.send(JSON.stringify(message));
    if (shouldDebugAudioMessageType(type)) {
      // 只记录音频链路相关消息，避免把所有业务消息都打进控制台。
      audioPlaybackDebug('WebSocketClient', '发送音频相关 websocket 消息', {
        roomId: this.roomId,
        type,
        timestamp: message.timestamp,
      });
    }
  }


  /**
   * 注册事件监听器
   * @param type 消息类型
   * @param handler 处理函数
   */
  on(type: MessageType, handler: EventHandler): void {
    if (!this.eventHandlers.has(type)) {
      this.eventHandlers.set(type, new Set());
    }
    this.eventHandlers.get(type)!.add(handler);
    if (shouldDebugAudioMessageType(type)) {
      audioPlaybackDebug('WebSocketClient', '注册音频相关事件处理器', {
        roomId: this.roomId,
        type,
        handlerCount: this.eventHandlers.get(type)!.size,
      });
    }
  }

  /**
   * 移除事件监听器
   * @param type 消息类型
   * @param handler 处理函数
   */
  off(type: MessageType, handler: EventHandler): void {
    const handlers = this.eventHandlers.get(type);
    if (handlers) {
      handlers.delete(handler);
      if (shouldDebugAudioMessageType(type)) {
        audioPlaybackDebug('WebSocketClient', '移除音频相关事件处理器', {
          roomId: this.roomId,
          type,
          handlerCount: handlers.size,
        });
      }
      if (handlers.size === 0) {
        this.eventHandlers.delete(type);
      }
    }
  }

  /**
   * 处理接收到的消息
   * @param data 消息数据
   */
  private handleMessage(data: string): void {
    try {
      const message: WebSocketMessage = JSON.parse(data);
      const handlers = this.eventHandlers.get(message.type);
      if (shouldDebugAudioMessageType(message.type)) {
        audioPlaybackDebug('WebSocketClient', '收到音频相关 websocket 消息', {
          roomId: this.roomId,
          type: message.type,
          handlerCount: handlers?.size || 0,
          speechId: String(message.data?.speech_id || message.data?.message_id || ''),
        });
      }

      if (handlers) {
        handlers.forEach((handler) => {
          try {
            handler(message.data);
          } catch (error) {
            console.error('Error in message handler:', error);
          }
        });
      }
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
    }
  }

  /**
   * 启动心跳
   */
  private startHeartbeat(): void {
    this.stopHeartbeat();
    
    this.heartbeatTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.send('ping', {});
      }
    }, this.heartbeatInterval);
  }

  /**
   * 停止心跳
   */
  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  /**
   * 安排重连
   */
  private scheduleReconnect(): void {
    if (this.reconnectTimer) {
      return;
    }

    this.reconnectAttempts++;
    console.log(`Reconnecting... Attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect(this.roomId, this.token).catch((error) => {
        console.error('Reconnect failed:', error);
      });
    }, this.reconnectInterval);
  }

  /**
   * 获取连接状态
   */
  getReadyState(): number {
    return this.ws ? this.ws.readyState : WebSocket.CLOSED;
  }

  /**
   * 是否已连接
   */
  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }
}

export default WebSocketClient;
export type { WebSocketMessage, MessageType, EventHandler };
