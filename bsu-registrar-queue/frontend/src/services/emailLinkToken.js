/**
 * Read the one-time token from an emailed link (`/reset-password#token=...`)
 * and strip it from the address bar, so it doesn't linger in browser history
 * or get copied along with the URL. The token rides in the fragment because
 * browsers never send a fragment to any server.
 */
export function takeTokenFromUrl(location = window.location, history = window.history) {
  const params = new URLSearchParams((location.hash || '').replace(/^#/, ''))
  const token = params.get('token') || ''
  if (location.hash) {
    history.replaceState(history.state, '', location.pathname + location.search)
  }
  return token
}
