import type { ReactNode } from 'react'
import { ArrowUpRight, Sparkles } from 'lucide-react'

export function AuthLayout({
  eyebrow,
  title,
  description,
  footer,
  children,
}: {
  eyebrow: string
  title: string
  description: string
  footer: ReactNode
  children: ReactNode
}) {
  return (
    <main className="auth-layout">
      <section className="auth-story" aria-label="Schoolmela Quiz">
        <div className="auth-story__brand">
          <span className="auth-story__mark"><Sparkles size={20} strokeWidth={2.2} /></span>
          <span>Schoolmela <strong>Quiz</strong></span>
        </div>
        <div className="auth-story__body">
          <p className="auth-story__eyebrow">A LITTLE THINKING GOES A LONG WAY</p>
          <h2>Curiosity looks good on you.</h2>
          <p className="auth-story__copy">A place to practice, discover, and celebrate what you know.</p>
          <div className="auth-story__score" aria-hidden="true">
            <div className="auth-story__score-top"><span>THE NEXT BIG IDEA</span><ArrowUpRight size={18} /></div>
            <div className="auth-story__question">Ready when<br />you are<span>?</span></div>
            <div className="auth-story__answers"><i /><i /><i /><i /></div>
            <div className="auth-story__score-bottom"><span>LEARN AT YOUR PACE</span><span>01 / 04</span></div>
          </div>
        </div>
        <div className="auth-story__footer"><span>Made for bright minds, everywhere.</span><span>© SCHOOLMELA</span></div>
      </section>
      <section className="auth-panel">
        <div className="auth-panel__mobile-brand"><Sparkles size={19} /> Schoolmela <strong>Quiz</strong></div>
        <div className="auth-panel__content">
          <p className="auth-panel__eyebrow">{eyebrow}</p>
          <h1>{title}</h1>
          <p className="auth-panel__description">{description}</p>
          {children}
          <div className="auth-panel__footer">{footer}</div>
        </div>
        <p className="auth-panel__note">Your learning space, ready whenever you are.</p>
      </section>
    </main>
  )
}