import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const audioDebugEnabled = () => {
  if (typeof localStorage === 'undefined') {
    return false;
  }

  return localStorage.getItem('debug_audio_playback') === 'true';
};

export function audioPlaybackDebug(
  scope: string,
  message: string,
  payload?: Record<string, unknown>
) {
  if (!audioDebugEnabled()) {
    return;
  }

  if (payload) {
    console.debug(`[AudioPlayback][${scope}] ${message}`, payload);
    return;
  }

  console.debug(`[AudioPlayback][${scope}] ${message}`);
}

export function debateDebug(
  scope: string,
  message: string,
  payload?: Record<string, unknown>
) {
  const isDev = Boolean(
    (import.meta as ImportMeta & { env?: { DEV?: boolean } }).env?.DEV
  );
  if (!isDev) {
    return;
  }

  if (payload) {
    console.debug(`[Debate][${scope}] ${message}`, payload);
    return;
  }

  console.debug(`[Debate][${scope}] ${message}`);
}

export function shouldDebugAudioMessageType(type: string) {
  return [
    'speech',
    'tts_stream_start',
    'tts_stream_chunk',
    'tts_stream_end',
    'speech_playback_started',
    'speech_playback_finished',
    'speech_playback_failed',
    'speech_playback_skipped',
  ].includes(type);
}

export function getAudioElementDebugSnapshot(audio?: HTMLAudioElement | null) {
  if (!audio) {
    return null;
  }

  return {
    src: audio.currentSrc || audio.src || '',
    currentTime: audio.currentTime,
    duration: Number.isFinite(audio.duration) ? audio.duration : null,
    paused: audio.paused,
    ended: audio.ended,
    readyState: audio.readyState,
    networkState: audio.networkState,
  };
}
