import { describe, expect, it, vi } from 'vitest';
import WebSocketClient from './websocket-client';

describe('WebSocketClient', () => {
  it('should dispatch a message only once when the same handler is registered repeatedly', () => {
    const client = new WebSocketClient();
    const handler = vi.fn();

    // 同一个处理器被重复注册时，底层应自动去重，避免一条消息触发多次播放逻辑。
    client.on('tts_stream_chunk', handler);
    client.on('tts_stream_chunk', handler);

    (client as any).handleMessage(JSON.stringify({
      type: 'tts_stream_chunk',
      data: { speech_id: 'speech-001', audio_base64: 'AA==' },
    }));

    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('should stop dispatching after the handler is removed once', () => {
    const client = new WebSocketClient();
    const handler = vi.fn();

    client.on('speech', handler);
    client.on('speech', handler);
    client.off('speech', handler);

    (client as any).handleMessage(JSON.stringify({
      type: 'speech',
      data: { speech_id: 'speech-001', text: 'test' },
    }));

    expect(handler).not.toHaveBeenCalled();
  });

  it('should ignore stale websocket connections that open late', async () => {
    class FakeWebSocket {
      static CONNECTING = 0;
      static OPEN = 1;
      static CLOSING = 2;
      static CLOSED = 3;
      static instances: FakeWebSocket[] = [];

      public readyState = FakeWebSocket.CONNECTING;
      public onopen: (() => void) | null = null;
      public onmessage: ((event: { data: string }) => void) | null = null;
      public onerror: ((error: unknown) => void) | null = null;
      public onclose: ((event: { code: number; reason: string }) => void) | null = null;

      constructor(public url: string) {
        FakeWebSocket.instances.push(this);
      }

      close(code = 1000, reason = ''): void {
        this.readyState = FakeWebSocket.CLOSED;
        this.onclose?.({ code, reason });
      }

      send(_data: string): void {
        return;
      }

      emitOpen(): void {
        this.readyState = FakeWebSocket.OPEN;
        this.onopen?.();
      }

      emitMessage(message: unknown): void {
        this.onmessage?.({ data: JSON.stringify(message) });
      }
    }

    const originalWebSocket = globalThis.WebSocket;
    Object.defineProperty(globalThis, 'WebSocket', {
      configurable: true,
      value: FakeWebSocket,
    });

    try {
      const client = new WebSocketClient();
      const handler = vi.fn();
      client.on('speech', handler);

      const firstConnectResult = client.connect('room-001', 'token').catch((error) => error);
      const firstSocket = FakeWebSocket.instances[0];

      // 模拟 StrictMode 首次挂载清理：旧连接被断开，但它的 onopen 仍可能晚到。
      client.disconnect();

      const secondConnectPromise = client.connect('room-001', 'token');
      const secondSocket = FakeWebSocket.instances[1];

      firstSocket.emitOpen();
      firstSocket.emitMessage({
        type: 'speech',
        data: { speech_id: 'stale-speech', text: 'old' },
      });

      secondSocket.emitOpen();
      await secondConnectPromise;
      secondSocket.emitMessage({
        type: 'speech',
        data: { speech_id: 'fresh-speech', text: 'new' },
      });

      const firstConnectError = await firstConnectResult;
      expect(firstConnectError).toBeInstanceOf(Error);
      expect(handler).toHaveBeenCalledTimes(1);
      expect(handler).toHaveBeenCalledWith({ speech_id: 'fresh-speech', text: 'new' });
    } finally {
      Object.defineProperty(globalThis, 'WebSocket', {
        configurable: true,
        value: originalWebSocket,
      });
    }
  });
});
