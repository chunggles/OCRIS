import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Btn } from '../../components/ui/index'
import { ocrAPI } from '../../utils/api'
import { Sheet, sheetOf } from './sheet'

// A saved record laid out on the SF10-ES sheet, read-only
const RecordSheet = ({ record }) => <Sheet readOnly sheet={sheetOf(record)}/>

const PDF_FRAME_LIFETIME_MS = 5 * 60 * 1000

// A PDF scan is printed by the browser's own PDF viewer, loaded in a frame that takes no space.
// The frame has to stay while the print window is open, and the page isn't told when that
// closes, so it is cleared after a few minutes.
function printPdf(file) {
  const url = URL.createObjectURL(file)
  const frame = Object.assign(document.createElement('iframe'), { src: url, title: 'Scanned form' })
  frame.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0'
  frame.onload = () => {
    try {
      frame.contentWindow.focus()
      frame.contentWindow.print()
    } catch {
      window.open(url, '_blank')  // a browser that won't print the frame shows the PDF in a new tab instead
    }
  }
  document.body.appendChild(frame)
  setTimeout(() => { frame.remove(); URL.revokeObjectURL(url) }, PDF_FRAME_LIFETIME_MS)
}

// Prints `record` in one click. A scanned record prints the scan that was uploaded for it; a
// typed-in form, which has no scan, prints as the Form 137 sheet. What is printed is put on the
// page only while printing, where the print styles show it in place of the app (see
// "printing-form" in components.css).
export default function PrintFormBtn({ record, label = 'Print', size = 'sm', variant = 'secondary' }) {
  const [loading, setLoading] = useState(false)
  const [job,     setJob]     = useState(null)   // what is being printed: { scanUrl } or { sheet: true }
  const [ready,   setReady]   = useState(false)  // true once it is on the page; a scan has to load first

  useEffect(() => {
    if (!job || !ready) return
    const finish = () => { setJob(null); setReady(false) }
    document.body.classList.add('printing-form')
    window.addEventListener('afterprint', finish)
    window.print()
    return () => {
      window.removeEventListener('afterprint', finish)
      document.body.classList.remove('printing-form')
      if (job.scanUrl) URL.revokeObjectURL(job.scanUrl)
    }
  }, [job, ready])

  const printScan = async () => {
    setLoading(true)
    try {
      const file = await ocrAPI.scanBlob(record.scan_id)
      if (file.type === 'application/pdf') { printPdf(file); return }
      if (!file.type.startsWith('image/')) {
        alert('This uploaded file cannot be printed from here. Download it and print it from your computer.')
        return
      }
      setJob({ scanUrl: URL.createObjectURL(file) })
    } catch (e) {
      alert(e?.offline ? "Can't reach the server. Try again in a moment." : e?.data?.detail || 'Could not load the scanned form.')
    } finally {
      setLoading(false)
    }
  }

  const handleClick = () => {
    if (record.scan_id) printScan()
    else { setJob({ sheet: true }); setReady(true) }
  }
  const cancel = () => { setJob(null); setReady(false) }

  if (!record?.record_id) return null
  return (
    <>
      <Btn size={size} variant={variant} onClick={handleClick} disabled={loading || Boolean(job)}>
        {loading ? 'Preparing…' : label}
      </Btn>
      {job && createPortal(
        <div className="print-only">
          {job.scanUrl
            ? <img className="print-scan" src={job.scanUrl} alt="" onLoad={() => setReady(true)}
                onError={() => { alert('The scanned form could not be shown for printing.'); cancel() }}/>
            : <RecordSheet record={record}/>}
        </div>,
        document.body,
      )}
    </>
  )
}
