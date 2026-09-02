import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'

// .env.local sets VITE_MOCK_MODE=true for local dev; these tests exercise the
// real fetch path, and api.ts reads the flag at module load — so stub the env
// first and import afterwards.
vi.stubEnv('VITE_MOCK_MODE', 'false')
let api: typeof import('../lib/api')
beforeAll(async () => {
  api = await import('../lib/api')
})

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

const downloadArgs = {
  title: 'Dune',
  author: 'Frank Herbert',
  releaseTitle: 'Dune [EPUB]',
  indexer: 'MyAnonamouse',
  protocol: 'torrent',
  downloadUrl: 'http://localhost:29254/dl',
  mediaType: 'ebook' as const,
}

describe('api error handling', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('surfaces the MAM 429 payload via ApiError + mamBlockedDetail', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse(429, {
          detail: {
            message: 'MAM download limit reached — downloads are paused',
            next_free_at: 1_800_008_040,
            unsatisfied: 150,
            limit: 150,
          },
        })
      )
    )

    let caught: unknown
    try {
      await api.downloadRelease(downloadArgs)
    } catch (err) {
      caught = err
    }

    expect(caught).toBeInstanceOf(api.ApiError)
    const apiErr = caught as InstanceType<typeof api.ApiError>
    expect(apiErr.status).toBe(429)
    // Human-readable message, not "[object Object]".
    expect(apiErr.message).toBe('MAM download limit reached — downloads are paused')
    expect(api.mamBlockedDetail(caught)).toEqual({ nextFreeAt: 1_800_008_040 })
  })

  it('treats a null next_free_at as "waiting for downloads"', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse(429, { detail: { message: 'paused', next_free_at: null } }))
    )
    const err = await api.downloadRelease(downloadArgs).catch((e: unknown) => e)
    expect(api.mamBlockedDetail(err)).toEqual({ nextFreeAt: null })
  })

  it('keeps plain string details as the message, and is not a MAM block', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(503, { detail: 'Cannot verify MAM slot status' })))
    const err = await api.downloadRelease(downloadArgs).catch((e: unknown) => e)
    expect(err).toBeInstanceOf(api.ApiError)
    const apiErr = err as InstanceType<typeof api.ApiError>
    expect(apiErr.status).toBe(503)
    expect(apiErr.message).toBe('Cannot verify MAM slot status')
    expect(api.mamBlockedDetail(err)).toBeNull()
  })

  it('still throws SESSION_EXPIRED on 401', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(401, { detail: 'nope' })))
    await expect(api.downloadRelease(downloadArgs)).rejects.toThrow('SESSION_EXPIRED')
  })

  it('maps /portal/mam-status snake_case to MamStatus', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse(200, {
          unsatisfied: null,
          limit: 150,
          block_threshold: 145,
          slots_free: null,
          blocked: true,
          next_free_at: null,
          server_time: 1_800_000_000,
        })
      )
    )
    expect(await api.getMamStatus()).toEqual({
      unsatisfied: null,
      limit: 150,
      blockThreshold: 145,
      slotsFree: null,
      blocked: true,
      nextFreeAt: null,
      serverTime: 1_800_000_000,
    })
  })
})
