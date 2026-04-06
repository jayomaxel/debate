/**
 * WebSocket客户端测试
 * 验证重连逻辑修复
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

describe('WebSocket Client Reconnection Logic', () => {
  let mockWebSocket: any;
  let originalWebSocket: any;

  beforeEach(() => {
    // 保存原始WebSocket
    originalWebSocket = global.WebSocket;

    // 创建模拟WebSocket
    mockWebSocket = vi.fn().mockImplementation(() => {
      const ws = {
        readyState: 0, // CONNECTING
        onopen: null as any,
        onclose: null as any,
        onerror: null as any,
        onmessage: null as any,
        send: vi.fn(),
        close: vi.fn(),
      };
      return ws;
    });

    global.WebSocket = mockWebSocket as any;
  });

  afterEach(() => {
    // 恢复原始WebSocket
    global.WebSocket = originalWebSocket;
    vi.clearAllMocks();
  });

  it('should not trigger reconnect if connection never established', async () => {
    const WebSocketClient = (await import('../websocket-client')).default;
    const client = new WebSocketClient({ maxReconnectAttempts: 3 });

    // 尝试连接
    const connectPromise = client.connect('test-room', 'test-token');

    // 获取WebSocket实例
    const wsInstance = mockWebSocket.mock.results[0].value;

    // 模拟连接失败（在onopen之前触发onclose）
    if (wsInstance.onclose) {
      wsInstance.onclose({ code: 1006, reason: 'Connection failed' });
    }

    // 连接应该被reject
    await expect(connectPromise).rejects.toThrow();

    // 不应该创建新的WebSocket实例（没有重连）
    expect(mockWebSocket).toHaveBeenCalledTimes(1);
  });

  it('should trigger reconnect only after successful connection', async () => {
    const WebSocketClient = (await import('../websocket-client')).default;
    const client = new WebSocketClient({ 
      maxReconnectAttempts: 2,
      reconnectInterval: 100 
    });

    // 尝试连接
    const connectPromise = client.connect('test-room', 'test-token');

    // 获取第一个WebSocket实例
    const wsInstance1 = mockWebSocket.mock.results[0].value;

    // 模拟连接成功
    wsInstance1.readyState = 1; // OPEN
    if (wsInstance1.onopen) {
      wsInstance1.onopen({});
    }

    // 等待连接成功
    await connectPromise;

    // 模拟连接断开
    wsInstance1.readyState = 3; // CLOSED
    if (wsInstance1.onclose) {
      wsInstance1.onclose({ code: 1006, reason: 'Connection lost' });
    }

    // 等待重连
    await new Promise(resolve => setTimeout(resolve, 150));

    // 应该创建了第二个WebSocket实例（重连）
    expect(mockWebSocket).toHaveBeenCalledTimes(2);
  });

  it('should stop reconnecting after max attempts', async () => {
    const WebSocketClient = (await import('../websocket-client')).default;
    const client = new WebSocketClient({ 
      maxReconnectAttempts: 2,
      reconnectInterval: 50 
    });

    // 第一次连接
    let connectPromise = client.connect('test-room', 'test-token');
    let wsInstance = mockWebSocket.mock.results[0].value;
    
    // 连接成功
    wsInstance.readyState = 1;
    if (wsInstance.onopen) wsInstance.onopen({});
    await connectPromise;

    // 第一次断开 -> 第一次重连
    wsInstance.readyState = 3;
    if (wsInstance.onclose) wsInstance.onclose({ code: 1006, reason: 'Lost' });
    await new Promise(resolve => setTimeout(resolve, 100));

    // 第二次连接成功
    wsInstance = mockWebSocket.mock.results[1].value;
    wsInstance.readyState = 1;
    if (wsInstance.onopen) wsInstance.onopen({});

    // 第二次断开 -> 第二次重连
    wsInstance.readyState = 3;
    if (wsInstance.onclose) wsInstance.onclose({ code: 1006, reason: 'Lost' });
    await new Promise(resolve => setTimeout(resolve, 100));

    // 第三次连接成功
    wsInstance = mockWebSocket.mock.results[2].value;
    wsInstance.readyState = 1;
    if (wsInstance.onopen) wsInstance.onopen({});

    // 第三次断开 -> 不应该再重连（达到最大次数）
    wsInstance.readyState = 3;
    if (wsInstance.onclose) wsInstance.onclose({ code: 1006, reason: 'Lost' });
    await new Promise(resolve => setTimeout(resolve, 100));

    // 总共应该只有3次连接尝试（初始 + 2次重连）
    expect(mockWebSocket).toHaveBeenCalledTimes(3);
  });
});
