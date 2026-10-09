import { describe, expect, it, vi } from 'vitest'
import { takeTokenFromUrl } from '../emailLinkToken.js'

function fakeLocation(hash, pathname = '/reset-password', search = '') {
  return { hash, pathname, search }
}

describe('takeTokenFromUrl', () => {
  it('reads the token from the fragment and strips it from the address bar', () => {
    const history = { state: { k: 1 }, replaceState: vi.fn() }
    expect(takeTokenFromUrl(fakeLocation('#token=abc_DEF-123'), history)).toBe('abc_DEF-123')
    expect(history.replaceState).toHaveBeenCalledWith({ k: 1 }, '', '/reset-password')
  })

  it('keeps any query string when stripping the fragment', () => {
    const history = { state: null, replaceState: vi.fn() }
    takeTokenFromUrl(fakeLocation('#token=x', '/verify-email', '?a=1'), history)
    expect(history.replaceState).toHaveBeenCalledWith(null, '', '/verify-email?a=1')
  })

  it('returns an empty string and leaves the URL alone when there is no fragment', () => {
    const history = { state: null, replaceState: vi.fn() }
    expect(takeTokenFromUrl(fakeLocation(''), history)).toBe('')
    expect(history.replaceState).not.toHaveBeenCalled()
  })
})
