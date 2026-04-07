import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

describe('WebSocket Client Reconnection Logic', () => {
  let originalWebSocket: typeof globalThis.WebSocket;

  class FakeWebSocket {
    static CONNECTING = 0;
    static OPEN = 1;
    static CLOSING = 2;
    static CLOSED = 3;
    static instances: FakeWebSocket[] = [];

    readyState = FakeWebSocket.CONNECTING;
    onopen: (() => void) | null = null;
    onclose: ((event: { code: number; reason: string }) => void) | null = null;
    onerror: ((error: unknown) => void) | null = null;
    onmessage: ((event: { data: string }) => void) | null = null;
    send = vi.fn();

    constructor(public url: string) {
      FakeWebSocket.instances.push(this);
    }

    close(code = 1000, reason = ''): void {
      this.readyState = FakeWebSocket.CLOSED;
      this.onclose?.({ code, reason });
    }

    emitOpen(): void {
      this.readyState = FakeWebSocket.OPEN;
      this.onopen?.();
    }

    emitClose(code = 1006, reason = 'Connection lost'): void {
      this.readyState = FakeWebSocket.CLOSED;
      this.onclose?.({ code, reason });
    }
  }

  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    FakeWebSocket.instances = [];
    originalWebSocket = globalThis.WebSocket;
    Object.defineProperty(globalThis, 'WebSocket', {
      configurable: true,
      value: FakeWebSocket,
    });
  });

  afterEach(() => {
    Object.defineProperty(globalThis, 'WebSocket', {
      configurable: true,
      value: originalWebSocket,
    });
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('should not trigger reconnect if connection never established', async () => {
    const WebSocketClient = (await import('../websocket-client')).default;
    const client = new WebSocketClient({ maxReconnectAttempts: 3, reconnectInterval: 100 });

    const connectPromise = client.connect('test-room', 'test-token');
    const firstSocket = FakeWebSocket.instances[0];

    firstSocket.emitClose(1006, 'Connection failed');

    await expect(connectPromise).rejects.toThrow();
    await vi.advanceTimersByTimeAsync(150);

    expect(FakeWebSocket.instances).toHaveLength(1);
  });

  it('should trigger reconnect only after successful connection', async () => {
    const WebSocketClient = (await import('../websocket-client')).default;
    const client = new WebSocketClient({
      maxReconnectAttempts: 2,
      reconnectInterval: 100,
    });

    const connectPromise = client.connect('test-room', 'test-token');
    const firstSocket = FakeWebSocket.instances[0];

    firstSocket.emitOpen();
    await connectPromise;

    firstSocket.emitClose(1006, 'Connection lost');
    await vi.advanceTimersByTimeAsync(100);

    expect(FakeWebSocket.instances).toHaveLength(2);
  });

  it('should not schedule duplicate reconnect timers while one reconnect is pending', async () => {
    const WebSocketClient = (await import('../websocket-client')).default;
    const client = new WebSocketClient({
      maxReconnectAttempts: 5,
      reconnectInterval: 50,
    });

    const connectPromise = client.connect('test-room', 'test-token');
    const firstSocket = FakeWebSocket.instances[0];

    firstSocket.emitOpen();
    await connectPromise;

    firstSocket.emitClose(1006, 'Connection lost');
    firstSocket.emitClose(1006, 'Duplicate close event');

    await vi.advanceTimersByTimeAsync(50);

    expect(FakeWebSocket.instances).toHaveLength(2);
  });
});
