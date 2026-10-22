import { useEffect, useState } from 'react'
import { depict } from '../structure'

/** A structure drawing; shown as an <img> so the generated SVG never enters the page's DOM. */
export function Structure({
  smiles,
  alt,
  width = 260,
  height = 200,
}: {
  smiles: string
  alt: string
  width?: number
  height?: number
}) {
  const [src, setSrc] = useState<string | null | undefined>(undefined)

  useEffect(() => {
    let cancelled = false
    depict(smiles, width, height)
      .then((url) => !cancelled && setSrc(url))
      .catch(() => !cancelled && setSrc(null))
    return () => {
      cancelled = true
    }
  }, [smiles, width, height])

  if (src === undefined) return <span className="muted small">Drawing…</span>
  if (src === null) return <span className="muted small">No drawing</span>
  return <img src={src} alt={alt} />
}
