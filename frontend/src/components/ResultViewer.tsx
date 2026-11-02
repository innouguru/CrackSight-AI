import { Download, Maximize2 } from 'lucide-react'
import { useState } from 'react'
import { demoImages } from '../data/mockData'

type ResultTab = 'Original' | 'Mask' | 'Overlay'

export function ResultViewer({
  originalImage = demoImages.original,
  uploadedImage = false,
  dimensions,
}: {
  originalImage?: string
  uploadedImage?: boolean
  dimensions?: readonly [number, number]
}) {
  const [activeTab, setActiveTab] = useState<ResultTab>('Overlay')
  const imageForTab = {
    Original: originalImage,
    Mask: demoImages.mask,
    Overlay: demoImages.overlay,
  }[activeTab]
  const downloadForTab = {
    Original: originalImage,
    Mask: demoImages.mask,
    Overlay: demoImages.overlay,
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
        <a className="button button--ghost" href={downloadForTab} download>
          <Download size={14} /> Download {activeTab.toLowerCase()}
        </a>
      </div>
      <div className="result-viewer__canvas">
        <img
          src={imageForTab}
          alt={`${activeTab} ${uploadedImage && activeTab !== 'Original' ? 'illustrative sample result' : 'crack inspection image'}`}
        />
      </div>
      <div className="result-viewer__footer">
        <span>
          {uploadedImage && activeTab !== 'Original'
            ? 'Illustrative sample output · not computed from this upload'
            : uploadedImage
              ? 'Your browser-only upload preview'
              : 'Sample photo · concrete wall'}
        </span>
        <span><Maximize2 size={12} aria-hidden="true" /> {displayedDimensions[0]} × {displayedDimensions[1]} px</span>
      </div>
    </section>
  )
}
