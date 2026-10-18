import { afterEach, describe, expect, it, vi } from 'vitest'
import { accountTransport, api, ApiError } from './api'

afterEach(() => { accountTransport(false); vi.unstubAllGlobals() })

describe('confine HTTP del frontend', () => {
  it('usa cookie same-origin e CSRF per account, senza token legacy sulle sessioni', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }))
    vi.stubGlobal('fetch', fetcher)
    accountTransport(true, 'csrf-synthetic')
    await api.run('c'.repeat(32), 4, 'e1', 'ignored-legacy-secret')
    expect(fetcher.mock.calls[0][1].credentials).toBe('same-origin')
    expect(fetcher.mock.calls[0][1].headers['X-Zone-CSRF']).toBe('csrf-synthetic')
    expect(fetcher.mock.calls[0][1].headers['X-Zone-Token']).toBeUndefined()
    expect(fetcher.mock.calls[0][1].body).not.toContain('secret')
  })
  it('manda il token solo nell’header e non nelle letture pubbliche', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ session_id: 'a'.repeat(32), agent_token: 'agent-secret' }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ events: [], next_after: 0 }), { status: 200 }))
    vi.stubGlobal('fetch', fetcher)
    await api.create('w1234567890abcdef', 'operator-secret')
    await api.events('a'.repeat(32))
    expect(fetcher.mock.calls[0][0]).toBe('/v1/sessions')
    expect(fetcher.mock.calls[0][1].headers['X-Zone-Token']).toBe('operator-secret')
    expect(fetcher.mock.calls[0][1].body).not.toContain('operator-secret')
    expect(fetcher.mock.calls[0][1].credentials).toBe('omit')
    expect(fetcher.mock.calls[1][1].headers['X-Zone-Token']).toBeUndefined()
    expect(fetcher.mock.calls[1][0]).not.toContain('secret')
  })

  it('legge tutte le pagine del replay senza modificare lo stato', async () => {
    const first = Array.from({ length: 100 }, (_, i) => ({ seq: i + 1, actor: 'agent', message: { type: 'hypothesis' } }))
    const fetcher = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ events: first, next_after: 100 }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ events: [{ seq: 101, actor: 'apparatus', message: { type: 'observation' } }], next_after: 101 }), { status: 200 }))
    vi.stubGlobal('fetch', fetcher)
    expect((await api.events('b'.repeat(32))).map(e => e.seq)).toHaveLength(101)
    expect(fetcher.mock.calls[1][0]).toContain('after=100')
  })

  it('non ritenta una esecuzione quando la rete fallisce', async () => {
    const fetcher = vi.fn().mockRejectedValue(new TypeError('network'))
    vi.stubGlobal('fetch', fetcher)
    await expect(api.run('c'.repeat(32), 4, 'e1', 'operator-secret')).rejects.toBeInstanceOf(ApiError)
    expect(fetcher).toHaveBeenCalledTimes(1)
  })
})
