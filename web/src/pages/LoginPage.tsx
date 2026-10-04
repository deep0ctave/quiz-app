import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router'
import { ApiError } from '../api/client'
import { homePathFor, useAuth } from '../auth/authContext'
import { digitsOnly } from '../components/digitsOnly'
import { Field } from '../components/Field'
import { AuthLayout } from '../components/AuthLayout'

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [mobile, setMobile] = useState('')
  const [pin, setPin] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    setFieldErrors({})
    try {
      const user = await login(digitsOnly(mobile), pin)
      const from = (location.state as { from?: string } | null)?.from
      navigate(from ?? homePathFor(user.role), { replace: true })
    } catch (err) {
      if (err instanceof ApiError) {
        setFieldErrors(err.fieldErrors)
        setError(Object.keys(err.fieldErrors).length ? null : err.message)
      } else {
        setError('Something went wrong. Please try again.')
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout
      eyebrow="WELCOME BACK"
      title="Log in"
      description="Pick up where your curiosity left off."
      footer={<>New to Schoolmela? <Link to="/register">Create an account</Link></>}
    >
      <form onSubmit={handleSubmit} noValidate>
        <Field
          label="Mobile number"
          type="tel"
          inputMode="numeric"
          autoComplete="tel"
          maxLength={14}
          value={mobile}
          onChange={(e) => setMobile(e.target.value)}
          error={fieldErrors.mobile}
          required
        />
        <Field
          label="PIN"
          type="password"
          inputMode="numeric"
          autoComplete="current-password"
          maxLength={6}
          value={pin}
          onChange={(e) => setPin(digitsOnly(e.target.value))}
          error={fieldErrors.pin}
          required
        />
        {error && (
          <p role="alert" className="alert">
            {error}
          </p>
        )}
        <button type="submit" className="button" disabled={busy}>
          {busy ? 'Please wait…' : 'Log in'}
        </button>
      </form>
    </AuthLayout>
  )
}
