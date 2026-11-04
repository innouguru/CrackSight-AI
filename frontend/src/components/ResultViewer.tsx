import { Download, Maximize2 } from 'lucide-react'
import { useState } from 'react'

type ResultTab = 'Original' | 'Mask' | 'Overlay'

export function ResultViewer({
  originalImage = '',
  maskImage = '',
  overlayImage = '',
  uploadedImage = false,
  dimensions,
}: {
  originalImage?: string
  maskImage?: string
  overlayImage?: string
  uploadedImage?: boolean
  dimensions?: readonly [number, number]
}) {
  const [activeTab, setActiveTab] = useState<ResultTab>('Overlay')
  const imageForTab = {
    Original: originalImage,
    Mask: maskImage,
    Overlay: overlayImage,
  }[activeTab]
  const displayedDimensions = activeTab === 'Original' && dimensions ? dimensions : [416, 416]

  return (
    <section className="result-viewer" aria-label="Analysis image viewer">
      <div className="result-viewer__toolbar">
        <div className="result-viewer__tabs" role="tablist" aria-label="Image view">
          {(['Original', 'Mask', 'Overlay'] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              role="tab"
              aria-selected={activeTab === tab}
              className={activeTab === tab ? 'is-active' : ''}
              onClick={() => setActiveTab(tab)}
            >
              {tab}
            </button>
          ))}
        </div>
        {imageForTab && (
          <a className="button button--ghost" href={imageForTab} download>
            <Download size={14} /> Download {activeTab.toLowerCase()}
          </a>
        )}
      </div>
      <div className="result-viewer__canvas">
        {imageForTab ? (
          <img
            src={imageForTab}
            alt={`${activeTab} ${uploadedImage ? 'uploaded photograph result' : 'crack inspection image'}`}
          />
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 300, color: '#718087', fontSize: 12 }}>
            No image available
          </div>
        )}
      </div>
      <div className="result-viewer__footer">
        <span>
          {uploadedImage
            ? 'Your uploaded photograph · real model output'
            : 'Sample photo · concrete wall'}
        </span>
        <span><Maximize2 size={12} aria-hidden="true" /> {displayedDimensions[0]} × {displayedDimensions[1]} px</span>
      </div>
    </section>
  )
}
