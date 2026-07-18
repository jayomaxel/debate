import { api } from '@/lib/api';
import { getApiOriginBaseUrl } from '@/lib/runtime-url';

type MediaTicket = {
  media_url: string;
  expires_in: number;
};

const ticketCache = new Map<string, Promise<string>>();

export const isPrivateMediaReference = (value?: string | null): boolean => {
  if (!value) return false;
  try {
    const parsed = new URL(value, 'http://local.invalid');
    return /^\/uploads\/(audio|asr)\/[A-Za-z0-9-]+\.[A-Za-z0-9]+$/.test(parsed.pathname);
  } catch {
    return false;
  }
};

const absoluteMediaUrl = (value: string): string => {
  if (/^https?:\/\//i.test(value)) return value;
  const origin = getApiOriginBaseUrl();
  if (!origin) return value;
  return value.startsWith('/') ? `${origin}${value}` : `${origin}/${value}`;
};

export const getPlayableMediaUrl = async (audioUrl: string): Promise<string> => {
  if (!isPrivateMediaReference(audioUrl)) return audioUrl;
  const existing = ticketCache.get(audioUrl);
  if (existing) return existing;
  const request = api
    .post<MediaTicket>('/api/voice/media/ticket', { audio_url: audioUrl })
    .then((result) => {
      const refreshAfterMs = Math.max(1, result.expires_in - 10) * 1000;
      window.setTimeout(() => ticketCache.delete(audioUrl), refreshAfterMs);
      return absoluteMediaUrl(result.media_url);
    })
    .catch((error) => {
      ticketCache.delete(audioUrl);
      throw error;
    });
  ticketCache.set(audioUrl, request);
  return request;
};

export const clearMediaTicketCache = (): void => ticketCache.clear();
