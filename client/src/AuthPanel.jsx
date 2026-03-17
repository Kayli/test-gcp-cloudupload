/**
 * AuthPanel
 *
 * Renders the signed-in status label, the dev fake-login button, and the
 * Google Sign-In button container.  All three DOM IDs (#signed-out,
 * #fake-login, #google-signin) are preserved so Playwright tests can find
 * them regardless of auth state.
 *
 * Props
 * -----
 * signedIn      {boolean}  whether the user is currently authenticated
 * statusText    {string}   human-readable label shown in #signed-out
 * allowDevAuth  {boolean}  whether the server permits the fake-login shortcut
 * onFakeLogin   {Function} called when the fake-login button is clicked
 */
export default function AuthPanel({ signedIn, statusText, allowDevAuth, onFakeLogin }) {
  return (
    <div id="auth">
      <p id="signed-out">{statusText}</p>

      {/* Dev fake-login button: visible only when not signed-in and server allows dev auth */}
      <button
        id="fake-login"
        style={{ display: !signedIn && allowDevAuth ? 'inline-block' : 'none' }}
        onClick={onFakeLogin}
      >
        Dev: Sign in as tester@example.com
      </button>

      {/* Google Sign-In button container: hidden once signed in */}
      <div
        id="google-signin"
        style={{ marginTop: '1rem', display: signedIn ? 'none' : '' }}
      />
    </div>
  )
}
