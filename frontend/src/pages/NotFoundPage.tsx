import { Link } from 'react-router-dom'
import { Brand } from '../components/Brand'

export function NotFoundPage() {
  return (
    <main className="not-found">
      <Link to="/"><Brand /></Link>
      <p className="eyebrow">Page not found</p>
      <h1>That view isn’t here.</h1>
      <p>The address may be outdated, or the screen may not be part of this prototype.</p>
      <Link className="button button--primary" to="/">Return to CrackSight AI</Link>
    </main>
  )
}
