import { Download, FileText, Info } from 'lucide-react'
import { useState } from 'react'
import { DemoNotice, PageHeading, SafetyNotice } from '../components/Ui'
import { demoImages, reportRecords } from '../data/mockData'

export function ReportsPage() {
  const [selectedId, setSelectedId] = useState(reportRecords[0]?.id ?? '')
  const [notice, setNotice] = useState('')
  const selected = reportRecords.find((report) => report.id === selectedId) ?? reportRecords[0]

  return (
    <>
      <PageHeading
        eyebrow="Inspection documentation"
        title="PDF reports"
        description="Preview the report structure and review sample report history."
        action={<button className="button button--primary" onClick={() => setNotice('PDF generation is a sample interaction only. Report generation is not connected to the backend.') }><FileText size={15} /> Generate report</button>}
      />
      <DemoNotice>Report records and the preview below are sample content. No PDF is generated or downloaded by this prototype.</DemoNotice>
      {notice && <p className="prototype-alert" role="status">{notice}</p>}
      <div className="report-preview" style={{ marginTop: 15 }}>
        <section className="card card--padded report-list">
          <div className="card-heading"><div><h2>Recent reports</h2><p>Sample report history</p></div></div>
          {reportRecords.map((report) => (
            <button className="report-list__item" key={report.id} onClick={() => setSelectedId(report.id)} aria-pressed={selectedId === report.id} style={{ textAlign: 'left', border: 0, borderBottom: '1px solid #edf0ef', background: selectedId === report.id ? '#f5faf8' : 'transparent', cursor: 'pointer' }}>
              <span className="report-list__icon"><FileText size={16} /></span>
              <span className="report-list__text"><strong>{report.inspection}</strong><small>{report.id} · {report.date}</small></span>
            </button>
          ))}
          <div style={{ marginTop: 14 }}>
            <button className="button button--secondary" style={{ width: '100%' }} onClick={() => setNotice('The sample report cannot be downloaded as a PDF until the report API is connected.')}><Download size={14} /> Download PDF <span className="form-field__hint">(not connected)</span></button>
          </div>
        </section>
        <section className="report-sheet" aria-label="PDF report preview">
          <div className="report-sheet__header">
            <span className="report-sheet__brand">CrackSight AI</span>
            <span className="report-sheet__id">REPORT PREVIEW<br />{selected?.id ?? 'RPT-0182'}</span>
          </div>
          <h2>{selected?.inspection ?? 'Building inspection'}</h2>
          <p className="report-sheet__sub">Generated 02 Nov 2026 · Sample inspection record</p>
          <div className="report-sheet__image-row">
            <img src={demoImages.original} alt="Sample original wall photograph" />
            <img src={demoImages.overlay} alt="Sample crack segmentation overlay" />
          </div>
          <p className="report-sheet__label">AI-assisted prediction · Wall</p>
          <p className="report-sheet__body">A predicted crack region is visible in the model overlay. The sample image-space measurement is 2,814 pixels. Model version: m3_baseline_b1. This model output is shown separately from the inspector’s field notes and must be reviewed by a qualified professional.</p>
          <p className="report-sheet__label" style={{ marginTop: 13 }}>Inspector observation</p>
          <p className="report-sheet__body">Fine surface crack visible across wall finish. Verify extent and context during site review. (Sample note)</p>
          <div className="report-sheet__disclaimer"><strong>Limitations:</strong> AI-assisted crack predictions are not a structural safety assessment and do not replace qualified structural engineering review. Measurements are image-space pixels only; no physical scale is implied.</div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 15, paddingTop: 8, borderTop: '1px solid #edf0ef', color: '#9aa5a7', fontSize: 8 }}><span>CrackSight AI · Private inspection record</span><span>Page 1 of {selected?.pages ?? 1}</span></div>
        </section>
      </div>
      <div style={{ marginTop: 15 }}><SafetyNotice /></div>
      {notice && <div className="prototype-banner" style={{ marginTop: 12 }}><Info size={14} />{notice}</div>}
    </>
  )
}
