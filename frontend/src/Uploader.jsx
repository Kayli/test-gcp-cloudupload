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
 * postJSON          {Function}  authenticated POST helper from App
 * onUploadComplete  {Function}  called after a successful upload to trigger dashboard refresh
 */
export default function Uploader({ postJSON, onUploadComplete }) {
  const [uploadResult, setUploadResult] = useState('')
  const fileInputRef = useRef(null)

  async function handleFileChange(ev) {
    const file = ev.target.files?.[0]
    if (!file) return
    setUploadResult('Requesting upload URL…')
    try {
      const res = await postJSON('/uploads', {
        tenantId: 'team-a',
        filename: file.name,
        contentType: file.type || 'application/octet-stream',
      })
      if (!res.uploadUrl) {
        setUploadResult('Error: no uploadUrl in response\n' + JSON.stringify(res, null, 2))
        return
      }

      setUploadResult('Uploading directly to storage…')
      let uploadResp
      try {
        uploadResp = await fetch(res.uploadUrl, {
          method: 'PUT',
          body: file,
          headers: { 'Content-Type': file.type || 'application/octet-stream' },
        })
      } catch (e) {
        setUploadResult('Upload failed: ' + e.message)
        return
      }

      if (!uploadResp.ok) {
        setUploadResult(`Upload failed: ${uploadResp.status} ${uploadResp.statusText}`)
        return
      }

      setUploadResult('Registering upload…')
      try {
        const completeRes = await postJSON(`/uploads/${res.id}/complete`, { size: file.size })
        setUploadResult(
          `Upload complete ✓\n` +
          `File ID : ${completeRes.id}\n` +
          `Status  : ${completeRes.status}\n` +
          `Size    : ${file.size} bytes`,
        )
        onUploadComplete?.()
      } catch (e) {
        setUploadResult('Upload succeeded but registration failed: ' + e.message)
      }
    } catch (e) {
      setUploadResult('Error requesting upload URL: ' + e.message)
    }
  }

  return (
    <section
      id="uploader"
      style={{ marginTop: '1.5rem' }}
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
