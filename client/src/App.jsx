import { useState, useEffect } from 'react'
import AuthPanel from './AuthPanel.jsx'
import Uploader from './Uploader.jsx'

// Initialise window globals immediately so Playwright sees them as soon as the
// module is evaluated — before the first React render.
window.dummyUser = null
window.idToken = null
window._appConfig = { googleClientId: null, allowDevAuth: false }
window._configLoaded = false

export default function App() {
  const [dummyUser, _setDummyUser] = useState(null)
  const [idToken, _setIdToken] = useState(null)
  const [config, setConfig] = useState({ googleClientId: null, allowDevAuth: false })

  const signedIn = !!(idToken || dummyUser)

  // Keep window globals in sync with React state for test compatibility.
  function setDummyUser(val) {
    window.dummyUser = val
    _setDummyUser(val)
  }

  function setIdToken(val) {
    window.idToken = val
    _setIdToken(val)
  }

  // Fetch /config on mount and conditionally load Google Identity Services.
  useEffect(() => {
    fetch('/config')
      .then((r) => r.json())
      .then((cfg) => {
        const merged = { googleClientId: null, allowDevAuth: false, ...cfg }
        window._appConfig = merged
        setConfig(merged)
        if (merged.googleClientId) {
          const s = document.createElement('script')
          s.src = 'https://accounts.google.com/gsi/client'
          s.onload = () => initGSI(merged.googleClientId)
          document.head.appendChild(s)
        }
      })
      .catch((e) => console.warn('Could not fetch config', e))
      .finally(() => {
        window._configLoaded = true
      })
  }, [])

  function initGSI(clientId) {
    if (!window.google || !clientId) return
    window.google.accounts.id.initialize({
      client_id: clientId,
      callback: (response) => setIdToken(response.credential),
    })
    const el = document.getElementById('google-signin')
    if (el) {
      window.google.accounts.id.renderButton(el, { theme: 'outline', size: 'large' })
    }
    window.google.accounts.id.prompt()
  }

  function handleFakeLogin() {
    setDummyUser('tester@example.com')
  }

  async function postJSON(url, body) {
    const headers = { 'Content-Type': 'application/json' }
    if (idToken) headers['Authorization'] = 'Bearer ' + idToken
    else if (dummyUser) headers['x-dummy-user'] = dummyUser
    const r = await fetch(url, { method: 'POST', headers, body: JSON.stringify(body) })
    return r.json()
  }

  // Derive signed-in status label.
  let statusText = 'Not signed in.'
  if (idToken) {
    try {
      const payload = JSON.parse(
        atob(idToken.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')),
      )
      statusText = 'Signed in as ' + (payload.email || 'unknown')
    } catch {
      statusText = 'Signed in'
    }
  } else if (dummyUser) {
    statusText = 'Signed in as ' + dummyUser
  }

  return (
    <>
      <h1 className="app-title">DocStore Prototype</h1>

      {/* Auth panel — always in the DOM so #signed-out.innerText is always readable */}
      <AuthPanel
        signedIn={signedIn}
        statusText={statusText}
        allowDevAuth={config.allowDevAuth}
        onFakeLogin={handleFakeLogin}
      />

      {/* Uploader — hidden until signed in; display toggled via inline style so
          Playwright can read element.style.display directly */}
      <Uploader signedIn={signedIn} postJSON={postJSON} />
    </>
  )
}
