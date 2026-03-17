import { useRef, useState } from 'react'

/**
 * Uploader
 *
 * Renders the file upload section. Hidden until the user is signed in.
 * DOM IDs (#uploader, #upload-btn, #file-input, #upload-result) are preserved
 * so Playwright tests can interact with them directly.
 *
 * Props
 * -----
 * signedIn   {boolean}   whether the user is authenticated (controls visibility)
 * postJSON   {Function}  authenticated POST helper from App
 */
export default function Uploader({ signedIn, postJSON }) {
  const [uploadResult, setUploadResult] = useState('')
  const fileInputRef = useRef(null)

  async function handleFileChange(ev) {
    const file = ev.target.files?.[0]
    if (!file) return
    setUploadResult('Requesting upload URL...')
    try {
      const res = await postJSON('/uploads', { tenantId: 'team-a', filename: file.name })
      let text = 'Upload URL response:\n' + JSON.stringify(res, null, 2)
      setUploadResult(text)
      if (res.uploadUrl) {
        text += '\n\nUploading file...'
        setUploadResult(text)
        try {
          const uploadResp = await fetch(res.uploadUrl, {
            method: 'PUT',
            body: file,
            headers: { 'Content-Type': file.type || 'application/octet-stream' },
          })
          setUploadResult(
            text + '\nUpload finished: ' + uploadResp.status + ' ' + uploadResp.statusText,
          )
        } catch (e) {
          setUploadResult(text + '\nUpload failed: ' + e.message)
        }
      }
    } catch (e) {
      setUploadResult('Error requesting upload URL: ' + e.message)
    }
  }

  return (
    <section
      id="uploader"
      style={{ marginTop: '1.5rem', display: signedIn ? 'block' : 'none' }}
    >
      <button id="upload-btn" onClick={() => fileInputRef.current?.click()}>
        Upload file
      </button>
      <input
        id="file-input"
        ref={fileInputRef}
        type="file"
        style={{ display: 'none' }}
        onChange={handleFileChange}
      />
      <pre id="upload-result" style={{ marginTop: '0.75rem' }}>
        {uploadResult}
      </pre>
    </section>
  )
}
