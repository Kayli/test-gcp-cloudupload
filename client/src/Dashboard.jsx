import { useState, useEffect, useCallback } from 'react'

/**
 * Dashboard
 *
 * Displays the list of files uploaded by the signed-in user.
 * Only rendered when the user is authenticated (enforced by App.jsx).
 *
 * Props
 * -----
 * getJSON   {Function}  authenticated GET helper – receives a URL and returns
 *                       the parsed JSON body
 * postJSON  {Function}  authenticated POST helper (reused for download URLs)
 * refreshKey {number}   incrementing counter; when it changes the list re-fetches
 */
export default function Dashboard({ getJSON, postJSON, refreshKey }) {
  const [files, setFiles] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [downloadingId, setDownloadingId] = useState(null)

  const fetchFiles = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getJSON('/files')
      setFiles(data.files ?? [])
    } catch (e) {
      setError('Failed to load files: ' + e.message)
    } finally {
      setLoading(false)
    }
  }, [getJSON])

  // Re-fetch whenever the component mounts or refreshKey changes (after an upload).
  useEffect(() => {
    fetchFiles()
  }, [fetchFiles, refreshKey])

  async function handleDownload(fileId, filename) {
    setDownloadingId(fileId)
    try {
      const data = await getJSON(`/files/${fileId}/download`)
      if (!data.downloadUrl) throw new Error('No download URL returned')
      const a = document.createElement('a')
      a.href = data.downloadUrl
      a.download = filename
      a.rel = 'noopener noreferrer'
      a.target = '_blank'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
    } catch (e) {
      alert('Download failed: ' + e.message)
    } finally {
      setDownloadingId(null)
    }
  }

  function formatSize(bytes) {
    if (bytes == null) return '—'
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }

  function formatDate(iso) {
    if (!iso) return '—'
    try {
      return new Date(iso).toLocaleString()
    } catch {
      return iso
    }
  }

  return (
    <section id="dashboard" style={{ marginTop: '2rem' }}>
      <div className="dashboard-header">
        <h2>Recent Files</h2>
        <button
          className="refresh-btn"
          onClick={fetchFiles}
          disabled={loading}
          title="Refresh file list"
        >
          {loading ? 'Loading…' : '↻ Refresh'}
        </button>
      </div>

      {error && <p className="dashboard-error">{error}</p>}

      {!loading && !error && files.length === 0 && (
        <p className="dashboard-empty">No files uploaded yet.</p>
      )}

      {files.length > 0 && (
        <div className="table-wrapper">
          <table className="files-table">
            <thead>
              <tr>
                <th>Filename</th>
                <th>Type</th>
                <th>Size</th>
                <th>Status</th>
                <th>Uploaded</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {files.map((f) => (
                <tr key={f.id}>
                  <td className="col-filename" title={f.filename}>{f.filename}</td>
                  <td className="col-type">{f.contentType ?? '—'}</td>
                  <td className="col-size">{formatSize(f.size)}</td>
                  <td>
                    <span className={`status-badge status-${f.status}`}>{f.status}</span>
                  </td>
                  <td className="col-date">{formatDate(f.createdAt)}</td>
                  <td>
                    {f.status === 'complete' ? (
                      <button
                        className="download-btn"
                        disabled={downloadingId === f.id}
                        onClick={() => handleDownload(f.id, f.filename)}
                      >
                        {downloadingId === f.id ? '…' : '⬇ Download'}
                      </button>
                    ) : (
                      <span className="no-action">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {files.length === 20 && (
            <p className="dashboard-limit-note">Showing the 20 most recent uploads.</p>
          )}
        </div>
      )}
    </section>
  )
}
