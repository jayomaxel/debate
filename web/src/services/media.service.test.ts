import { beforeEach, describe, expect, it, vi } from 'vitest';

const { post } = vi.hoisted(() => ({ post: vi.fn() }));

vi.mock('@/lib/api', () => ({ api: { post } }));
vi.mock('@/lib/runtime-url', () => ({ getApiOriginBaseUrl: () => 'https://api.example.test' }));

import {
  clearMediaTicketCache,
  getPlayableMediaUrl,
  isPrivateMediaReference,
} from './media.service';

describe('media service', () => {
  beforeEach(() => {
    clearMediaTicketCache();
    post.mockReset();
  });

  it('exchanges a private object reference for a short-lived media URL', async () => {
    const original = '/uploads/audio/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.wav';
    post.mockResolvedValue({
      media_url: '/api/voice/media/audio/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.wav?ticket=signed',
      expires_in: 120,
    });

    const playable = await getPlayableMediaUrl(original);

    expect(post).toHaveBeenCalledWith('/api/voice/media/ticket', { audio_url: original });
    expect(playable).toBe(
      'https://api.example.test/api/voice/media/audio/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.wav?ticket=signed',
    );
  });

  it('does not exchange public or already-ticketed URLs', async () => {
    const ticketed = '/api/voice/media/audio/a.wav?ticket=signed';

    expect(isPrivateMediaReference(ticketed)).toBe(false);
    await expect(getPlayableMediaUrl(ticketed)).resolves.toBe(ticketed);
    expect(post).not.toHaveBeenCalled();
  });
});
