import { afterEach, expect, it, vi } from 'vitest'
import { arenaApi } from './arena-api'

afterEach(() => vi.unstubAllGlobals())

it('usa versione, token in header e la stessa chiave per il retry manuale', async () => {
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ready_to_run' }) })
  vi.stubGlobal('fetch', fetch)
  const key = 'durable-manual-retry'
  await arenaApi.write('sessions/id/run', { expected_version: 4, request_id: 'e1' }, 'credential-test', key)
  await arenaApi.write('sessions/id/run', { expected_version: 4, request_id: 'e1' }, 'credential-test', key)
  expect(fetch.mock.calls[0]).toEqual(fetch.mock.calls[1])
  const options = fetch.mock.calls[0][1]
  expect(options.headers).toMatchObject({ 'X-Zone-Arena-Version': '1', 'X-Zone-Token': 'credential-test', 'Idempotency-Key': key })
  expect(options.body).not.toContain('credential-test')
  expect(options.credentials).toBe('omit')
})

it('un errore di rete non ripete la richiesta', async () => {
  const fetch = vi.fn().mockRejectedValue(new Error('offline'))
  vi.stubGlobal('fetch', fetch)
  await expect(arenaApi.write('sessions/id/run', {}, 'test')).rejects.toThrow('not responding')
  expect(fetch).toHaveBeenCalledTimes(1)
})
