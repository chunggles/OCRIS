import { useObjectUrl } from '../../utils/useObjectUrl'

export const isPdf = (file) => file?.type === 'application/pdf'

// Shows an uploaded scan: an image as a picture, a PDF in the browser's own PDF viewer.
// `className` styles the picture; a PDF needs a fixed height, so it uses its own class.
export default function ScanPreview({ file, className = '', style, alt = 'Scanned form' }) {
  const url = useObjectUrl(file)
  if (!url) return null
  if (isPdf(file)) {
    return (
      <object data={`${url}#toolbar=0&navpanes=0`} type="application/pdf" className="scan-pdf" aria-label={alt}>
        <div className="hint">This browser can't show a PDF here. The file will still be read.</div>
      </object>
    )
  }
  return <img src={url} alt={alt} className={className} style={style}/>
}
