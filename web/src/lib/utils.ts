import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * 合并 Tailwind CSS 类名的工具函数
 * @param inputs - 类名数组或对象
 * @returns 合并后的类名字符串
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * 格式化日期
 * @param date - 日期对象或字符串
 * @param options - 格式化选项
 * @returns 格式化后的日期字符串
 */
export function formatDate(
  date: Date | string,
  options: Intl.DateTimeFormatOptions = {}
): string {
  const dateObj = typeof date === 'string' ? new Date(date) : date;
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    ...options,
  }).format(dateObj);
}

/**
 * 格式化数字
 * @param num - 数字
 * @param options - 格式化选项
 * @returns 格式化后的数字字符串
 */
export function formatNumber(
  num: number,
  options: Intl.NumberFormatOptions = {}
): string {
  return new Intl.NumberFormat('zh-CN', options).format(num);
}

/**
 * 生成随机 ID
 * @param length - ID 长度
 * @returns 随机 ID 字符串
 */
export function generateId(length: number = 8): string {
  const chars =
    'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  let result = '';
  for (let i = 0; i < length; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}

/**
 * 防抖函数
 * @param func - 要防抖的函数
 * @param wait - 等待时间（毫秒）
 * @returns 防抖后的函数
 */
export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: ReturnType<typeof setTimeout>;
  return (...args: Parameters<T>) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
}

/**
 * 节流函数
 * @param func - 要节流的函数
 * @param limit - 时间限制（毫秒）
 * @returns 节流后的函数
 */
export function throttle<T extends (...args: any[]) => any>(
  func: T,
  limit: number
): (...args: Parameters<T>) => void {
  let inThrottle: boolean;
  return (...args: Parameters<T>) => {
    if (!inThrottle) {
      func(...args);
      inThrottle = true;
      setTimeout(() => (inThrottle = false), limit);
    }
  };
}

/**
 * 检查是否为移动设备
 * @returns 是否为移动设备
 */
export function isMobile(): boolean {
  if (typeof window === 'undefined') return false;
  return window.innerWidth < 768;
}

/**
 * 检查是否为暗色模式
 * @returns 是否为暗色模式
 */
export function isDarkMode(): boolean {
  if (typeof window === 'undefined') return false;
  return document.documentElement.classList.contains('dark');
}

/**
 * 切换暗色模式
 */
export function toggleDarkMode(): void {
  if (typeof window === 'undefined') return;
  document.documentElement.classList.toggle('dark');
  localStorage.setItem(
    'darkMode',
    document.documentElement.classList.contains('dark').toString()
  );
}

/**
 * 初始化暗色模式
 */
export function initDarkMode(): void {
  if (typeof window === 'undefined') return;
  const saved = localStorage.getItem('darkMode');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

  if (saved === 'true' || (saved === null && prefersDark)) {
    document.documentElement.classList.add('dark');
  }
}

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
export function isAudioPlaybackDebugEnabled(): boolean {
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
}

/**
 * 控制台输出统一的音频排查日志。
 * 所有链路都走同一个入口，方便按 [AudioDebug] 关键字过滤。
 */
export function audioPlaybackDebug(
  scope: string,
  message: string,
  payload?: AudioPlaybackDebugPayload
): void {
  if (!isAudioPlaybackDebugEnabled()) {
    return;
  }

  const timestamp = new Date().toISOString();
  if (payload) {
    console.log(`[AudioDebug][${timestamp}][${scope}] ${message}`, payload);
    return;
  }
  console.log(`[AudioDebug][${timestamp}][${scope}] ${message}`);
}

/**
 * 只对和语音排查相关的 websocket 事件开启详细日志，避免普通业务消息刷屏。
 */
export function shouldDebugAudioMessageType(messageType: string): boolean {
  return DEBUG_MESSAGE_TYPES.has(messageType);
}

/**
 * 摘要化 audio 元素状态，便于快速判断是否出现了重复播放或多音轨叠加。
 */
export function getAudioElementDebugSnapshot(
  audioElement: HTMLAudioElement | null | undefined
): AudioPlaybackDebugPayload | undefined {
  if (!audioElement) {
    return undefined;
  }

  return {
    src: audioElement.currentSrc || audioElement.getAttribute('src') || '',
    paused: audioElement.paused,
    ended: audioElement.ended,
    currentTime: Number.isFinite(audioElement.currentTime)
      ? Number(audioElement.currentTime.toFixed(3))
      : null,
    readyState: audioElement.readyState,
  };
}

/**
 * 向外暴露存储 key，便于开发者在浏览器控制台快速开启或关闭日志。
 */
export const AUDIO_PLAYBACK_DEBUG_STORAGE_KEY = AUDIO_DEBUG_STORAGE_KEY;
