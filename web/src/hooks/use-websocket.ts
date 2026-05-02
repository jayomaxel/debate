/**
 * useWebSocket Hook
 * 封装WebSocket客户端，提供React Hook接口
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import WebSocketClient from '../lib/websocket-client';
import type { MessageType, EventHandler } from '../lib/websocket-client';
import { audioPlaybackDebug, shouldDebugAudioMessageType } from '../lib/utils';
import TokenManager from '../lib/token-manager';

interface UseWebSocketOptions {
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: any) => void;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  heartbeatInterval?: number;
}

interface UseWebSocketReturn {
  isConnected: boolean;
  send: (type: MessageType, data: any) => void;
  on: (type: MessageType, handler: EventHandler) => void;
  off: (type: MessageType, handler: EventHandler) => void;
  connect: () => Promise<void>;
  disconnect: () => void;
}

/**
 * useWebSocket Hook
 * 
 * @param roomId 辩论房间ID
 * @param options 配置选项
 * @returns WebSocket操作接口
 * 
 * @example
 * ```tsx
 * const { isConnected, send, on, off } = useWebSocket('room-123', {
 *   onConnect: () => console.log('Connected'),
 *   onDisconnect: () => console.log('Disconnected')
 * });
 * 
 * useEffect(() => {
 *   const handler = (data) => console.log('Speech:', data);
 *   on('speech', handler);
 *   return () => off('speech', handler);
 * }, [on, off]);
 * ```
 */
export function useWebSocket(
  roomId: string | null,
  options: UseWebSocketOptions = {}
): UseWebSocketReturn {
  const {
    onConnect,
    onDisconnect,
    onError,
    reconnectInterval,
    maxReconnectAttempts,
    heartbeatInterval,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const clientRef = useRef<WebSocketClient | null>(null);
  const handlersRef = useRef<Map<MessageType, Set<EventHandler>>>(new Map());
  const onConnectRef = useRef(onConnect);
  const onDisconnectRef = useRef(onDisconnect);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    onConnectRef.current = onConnect;
    onDisconnectRef.current = onDisconnect;
    onErrorRef.current = onError;
  }, [onConnect, onDisconnect, onError]);

  /**
   * 初始化WebSocket客户端
   */
  useEffect(() => {
    if (!clientRef.current) {
      clientRef.current = new WebSocketClient({
        reconnectInterval,
        maxReconnectAttempts,
        heartbeatInterval,
        onOpen: () => {
          setIsConnected(true);
          onConnectRef.current?.();
        },
        onClose: (event) => {
          setIsConnected(false);
          console.warn('[useWebSocket] Debate websocket disconnected', {
            roomId,
            code: event?.code,
            reason: event?.reason,
            wasClean: event?.wasClean,
          });
          onDisconnectRef.current?.();
        },
        onError: (error) => {
          onErrorRef.current?.(error);
        },
      });
    }
  }, [reconnectInterval, maxReconnectAttempts, heartbeatInterval]);

  /**
   * 连接到WebSocket服务器
   */
  const connect = useCallback(async () => {
    if (!roomId || !clientRef.current) {
      return;
    }

    try {
      audioPlaybackDebug('useWebSocket', '开始连接房间 websocket', { roomId });
      const token = TokenManager.getAccessToken();
      if (!token) {
        throw new Error('No access token available');
      }
      console.debug('[useWebSocket] Preparing debate websocket connection', {
        roomId,
        hasToken: !!token,
        origin: typeof window !== 'undefined' ? window.location.origin : '',
      });

      await clientRef.current.connect(roomId, token);
      audioPlaybackDebug('useWebSocket', '房间 websocket 连接成功', { roomId });
    } catch (error) {
      console.error('[useWebSocket] Connect failed:', error);
      audioPlaybackDebug('useWebSocket', '房间 websocket 连接失败', {
        roomId,
        error: String((error as any)?.message || error),
      });
      setIsConnected(false);
      onErrorRef.current?.(error);
      throw error;
    }
  }, [roomId]);

  /**
   * 断开WebSocket连接
   */
  const disconnect = useCallback(() => {
    if (clientRef.current) {
      audioPlaybackDebug('useWebSocket', '开始断开房间 websocket', { roomId });
      clientRef.current.disconnect();
      setIsConnected(false);
    }
  }, [roomId]);

  /**
   * 发送消息
   */
  const send = useCallback((type: MessageType, data: any) => {
    if (clientRef.current && clientRef.current.isConnected()) {
      clientRef.current.send(type, data);
    } else {
      console.warn('[useWebSocket] Cannot send message: not connected');
    }
  }, []);

  /**
   * 注册事件监听器
   */
  const on = useCallback((type: MessageType, handler: EventHandler) => {
    if (!clientRef.current) {
      return;
    }

    // 跟踪处理器以便清理
    if (!handlersRef.current.has(type)) {
      handlersRef.current.set(type, new Set());
    }
    handlersRef.current.get(type)!.add(handler);
    if (shouldDebugAudioMessageType(type)) {
      // 记录 Hook 层监听数，便于确认页面组件是否重复订阅了音频事件。
      audioPlaybackDebug('useWebSocket', 'Hook 注册音频相关监听', {
        roomId,
        type,
        handlerCount: handlersRef.current.get(type)!.size,
      });
    }

    // 注册到WebSocket客户端
    clientRef.current.on(type, handler);
  }, [roomId]);

  /**
   * 移除事件监听器
   */
  const off = useCallback((type: MessageType, handler: EventHandler) => {
    if (!clientRef.current) {
      return;
    }

    // 从跟踪中移除
    const handlers = handlersRef.current.get(type);
    if (handlers) {
      handlers.delete(handler);
      if (shouldDebugAudioMessageType(type)) {
        audioPlaybackDebug('useWebSocket', 'Hook 移除音频相关监听', {
          roomId,
          type,
          handlerCount: handlers.size,
        });
      }
    }

    // 从WebSocket客户端移除
    clientRef.current.off(type, handler);
  }, [roomId]);

  /**
   * 自动连接（如果提供了roomId）
   */
  useEffect(() => {
    if (roomId) {
      connect().catch((error) => {
        // 只在非取消错误时打印日志
        if (error?.message !== 'Connection cancelled') {
          console.error('[useWebSocket] Auto-connect failed:', error);
        }
      });
    }

    // 清理函数
    return () => {
      disconnect();
    };
  }, [roomId]); // 只依赖roomId，避免无限重连

  /**
   * 组件卸载时清理所有事件监听器
   */
  useEffect(() => {
    return () => {
      if (clientRef.current) {
        // 移除所有注册的处理器
        handlersRef.current.forEach((handlers, type) => {
          handlers.forEach((handler) => {
            clientRef.current!.off(type, handler);
          });
        });
        handlersRef.current.clear();
      }
    };
  }, []);

  return {
    isConnected,
    send,
    on,
    off,
    connect,
    disconnect,
  };
}

export default useWebSocket;
