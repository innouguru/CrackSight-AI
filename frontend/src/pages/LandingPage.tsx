import {
  ArrowRight,
  Check,
  ClipboardCheck,
  FileImage,
  ScanLine,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { Brand } from '../components/Brand'
import { SafetyNotice } from '../components/Ui'
import { demoImages } from '../data/mockData'

const steps = [
  { title: 'Capture a clear view', text: 'Upload a building-component photo or capture one on your phone.' },
  { title: 'Review the AI output', text: 'Compare the original photograph with the predicted mask and overlay.' },
  { title: 'Record your inspection', text: 'Add observations and verify the result as part of your inspection.' },
]

const capabilities = [
  { icon: ScanLine, title: 'Crack segmentation', text: 'See model-highlighted regions overlaid on your inspection photograph.' },
  { icon: FileImage, title: 'Image-space measurements', text: 'Review available pixel measurements alongside the source image.' },
  { icon: ClipboardCheck, title: 'Human verification', text: 'Keep inspector observations distinct from AI-generated predictions.' },
]

export function LandingPage() {
  return (
    <div className="landing">
      <header className="landing-nav">
        <Link to="/" aria-label="CrackSight AI home"><Brand /></Link>
        <div className="landing-nav__actions">
          <Link className="landing-nav__signin" to="/sign-in">Sign in</Link>
          <Link className="button button--primary" to="/sign-up">Create account</Link>
        </div>
      </header>

      <main>
        <section className="landing-hero">
          <div className="landing-hero__copy">
            <p className="landing-kicker"><span /> BUILDING INSPECTION, WITH CLARITY</p>
            <h1>See the detail.<br /><em>Keep the judgment.</em></h1>
            <p className="landing-hero__lead">
              CrackSight AI helps you review visible cracks in building photographs with clear,
              inspectable segmentation results — while keeping engineering judgment where it belongs.
            </p>
            <div className="landing-hero__buttons">
              <Link className="button button--primary button--large" to="/try">
                Try a sample inspection <ArrowRight size={16} />
              </Link>
              <Link className="button button--secondary button--large" to="/sign-up">Create an account</Link>
            </div>
            <p className="landing-hero__microcopy">No account needed to explore the guest demo · 3 analyses per guest session</p>
          </div>
          <div className="landing-visual">
            <div className="landing-visual__image">
              <img src={demoImages.overlay} alt="Sample crack segmentation overlay on a concrete wall" />
            </div>
            <div className="landing-visual__tag"><span /> Segmentation overlay</div>
            <div className="landing-visual__caption">
              <small>SAMPLE INSPECTION · WALL</small>
              <strong>AI prediction ready</strong>
              <span>Review the output before recording an observation.</span>
            </div>
          </div>
        </section>

        <section className="landing-trust" aria-label="Product capabilities">
          <div className="landing-trust__inner">
            <span className="landing-trust__label">Designed for practical inspection workflows</span>
            <div className="landing-trust__items">
              <span><Check size={15} /> Walls, beams & columns</span>
              <span><Check size={15} /> Original + mask + overlay</span>
              <span><Check size={15} /> Pixel-space measurements</span>
            </div>
          </div>
        </section>

        <section className="landing-section">
          <div className="landing-section__heading">
            <p className="eyebrow">A clear workflow</p>
            <h2>From photograph to reviewed finding</h2>
            <p>Each step makes it clear what the model predicted and what the inspector observed.</p>
          </div>
          <div className="steps-grid">
            {steps.map((step, index) => (
              <article className="step-card" key={step.title}>
                <span className="step-card__number">0{index + 1}</span>
                <h3>{step.title}</h3>
                <p>{step.text}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="capabilities-section">
          <div className="landing-section">
            <div className="landing-section__heading">
              <p className="eyebrow">Built for review, not replacement</p>
              <h2>Useful outputs. Human decisions.</h2>
              <p>Technical views and measurements support your workflow without presenting a structural safety conclusion.</p>
            </div>
            <div className="capabilities-grid">
              {capabilities.map(({ icon: Icon, title, text }) => (
                <article className="capability-card" key={title}>
                  <span className="capability-card__icon"><Icon size={18} /></span>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </article>
              ))}
            </div>
            <div className="landing-bottom-cta" style={{ marginTop: 26 }}>
              <div>
                <h2>Explore the inspection experience</h2>
                <p>Try the sample workflow before creating an account.</p>
              </div>
              <Link className="button button--primary" to="/try">Open guest demo <ArrowRight size={15} /></Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="landing-footer">
        <Link to="/"><Brand /></Link>
        <span>CrackSight AI is an inspection aid, not a safety certification.</span>
        <span>© 2026 CrackSight AI · Prototype</span>
      </footer>
      <div className="landing-section" style={{ paddingTop: 16, paddingBottom: 24 }}>
        <SafetyNotice />
      </div>
    </div>
  )
}
