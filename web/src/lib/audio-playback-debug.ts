const AUDIO_DEBUG_STORAGE_KEY = 'aidb:audio-debug';

const DEBUG_MESSAGE_TYPES = new Set([
  'speech',
  'tts_stream_start',
  'tts_stream_chunk',
  'tts_stream_end',
]);

interface AudioPlaybackDebugPayload {
  [key: string]: unknown;
}

/**
 * 判断当前是否开启了音频播放排查日志。
 * 支持 localStorage、window 全局开关和 Vite 环境变量三种方式，便于本地和线上同时排查。
 */
export const isAudioPlaybackDebugEnabled = (): boolean => {
  const globalScope = globalThis as typeof globalThis & {
    __AIDEBATE_AUDIO_DEBUG__?: boolean;
    localStorage?: Storage;
  };

  // 全局变量显式关闭时优先关闭，便于在默认开启的情况下临时止损。
  if (globalScope.__AIDEBATE_AUDIO_DEBUG__ === false) {
    return false;
  }
  if (globalScope.__AIDEBATE_AUDIO_DEBUG__ === true) {
    return true;
  }

  try {
    const localValue = globalScope.localStorage?.getItem(AUDIO_DEBUG_STORAGE_KEY);
    if (localValue === '0' || localValue === 'false') {
      return false;
    }
    if (localValue === '1' || localValue === 'true') {
      return true;
    }
  } catch {
    // 某些浏览器隐私模式下 localStorage 读取可能失败，这里静默降级即可。
  }

  const envValue = String((import.meta as any).env?.VITE_AUDIO_DEBUG || '').toLowerCase();
  if (envValue === 'false') {
    return false;
  }
  if (envValue === 'true') {
    return true;
  }

  // 默认开启，保证排查问题时不需要额外配置。
  return true;
};

/**
 * 控制台输出统一的音频排查日志。
 * 所有链路都走同一个入口，方便按 [AudioDebug] 关键字过滤。
 */
export const audioPlaybackDebug = (
  scope: string,
  message: string,
  payload?: AudioPlaybackDebugPayload
): void => {
  if (!isAudioPlaybackDebugEnabled()) {
    return;
  }

  const timestamp = new Date().toISOString();
  if (payload) {
    console.log(`[AudioDebug][${timestamp}][${scope}] ${message}`, payload);
    return;
  }
  console.log(`[AudioDebug][${timestamp}][${scope}] ${message}`);
};

/**
 * 只对和语音排查相关的 websocket 事件开启详细日志，避免普通业务消息刷屏。
 */
export const shouldDebugAudioMessageType = (messageType: string): boolean => {
  return DEBUG_MESSAGE_TYPES.has(messageType);
};

/**
 * 摘要化 audio 元素状态，便于快速判断是否出现了重复播放或多音轨叠加。
 */
export const getAudioElementDebugSnapshot = (
  audioElement: HTMLAudioElement | null | undefined
): AudioPlaybackDebugPayload | undefined => {
  if (!audioElement) {
    return undefined;
  }

  return {
    src: audioElement.currentSrc || audioElement.getAttribute('src') || '',
    paused: audioElement.paused,
    ended: audioElement.ended,
    currentTime: Number.isFinite(audioElement.currentTime) ? Number(audioElement.currentTime.toFixed(3)) : null,
    readyState: audioElement.readyState,
  };
};

/**
 * 向外暴露存储 key，便于开发者在浏览器控制台快速开启或关闭日志。
 */
export const AUDIO_PLAYBACK_DEBUG_STORAGE_KEY = AUDIO_DEBUG_STORAGE_KEY;
