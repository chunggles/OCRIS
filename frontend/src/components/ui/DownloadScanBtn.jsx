import { useState } from 'react'
import { Btn } from './index'
import { ocrAPI } from '../../utils/api'

// Downloads the original uploaded Form 137 file for a scan
export default function DownloadScanBtn({ scanId, label = 'Download', size = 'sm', variant = 'secondary' }) {
  const [busy, setBusy] = useState(false)
  if (!scanId) return null

  const handleClick = async () => {
    setBusy(true)
    try {
      await ocrAPI.downloadFile(scanId)
    } catch (e) {
      alert(e?.offline ? "Can't reach the server. Try again in a moment." : e?.data?.detail || 'Download failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Btn size={size} variant={variant} onClick={handleClick} disabled={busy}>
      {busy ? 'Downloading…' : label}
    </Btn>
  )
}
