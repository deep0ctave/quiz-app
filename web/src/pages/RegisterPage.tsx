import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { ApiError } from '../api/client'
import { homePathFor, useAuth } from '../auth/authContext'
import { digitsOnly } from '../components/digitsOnly'
import { Field } from '../components/Field'
import { AuthLayout } from '../components/AuthLayout'

export function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ name: '', mobile: '', pin: '', confirmPin: '', email: '', school: '' })
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)

  function update(field: keyof typeof form, value: string) {
    setForm((f) => ({ ...f, [field]: value }))
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (form.pin !== form.confirmPin) {
      setFieldErrors({ confirmPin: 'The two PINs are not the same' })
      return
    }
    setFieldErrors({})
    setBusy(true)
    try {
      const user = await register({
        name: form.name,
        mobile: digitsOnly(form.mobile),
        pin: form.pin,
        email: form.email || undefined,
        school: form.school || undefined,
      })
      navigate(homePathFor(user.role), { replace: true })
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
      eyebrow="YOUR NEXT CHAPTER"
      title="Create an account"
      description="Start a learning space that is all yours."
      footer={<>Already have an account? <Link to="/login">Log in</Link></>}
    >
      <form onSubmit={handleSubmit} noValidate>
        <Field
          label="Your name"
          autoComplete="name"
          maxLength={100}
          value={form.name}
          onChange={(e) => update('name', e.target.value)}
          error={fieldErrors.name}
          required
        />
        <Field
          label="Mobile number"
          type="tel"
          inputMode="numeric"
          autoComplete="tel"
          maxLength={14}
          value={form.mobile}
          onChange={(e) => update('mobile', e.target.value)}
          error={fieldErrors.mobile}
          required
        />
        <Field
          label="Choose a PIN"
          hint="4 to 6 numbers. Remember it!"
          type="password"
          inputMode="numeric"
          autoComplete="new-password"
          maxLength={6}
          value={form.pin}
          onChange={(e) => update('pin', digitsOnly(e.target.value))}
          error={fieldErrors.pin}
          required
        />
        <Field
          label="Type your PIN again"
          type="password"
          inputMode="numeric"
          autoComplete="new-password"
          maxLength={6}
          value={form.confirmPin}
          onChange={(e) => update('confirmPin', digitsOnly(e.target.value))}
          error={fieldErrors.confirmPin}
          required
        />
        <Field
          label="School name (optional)"
          maxLength={150}
          value={form.school}
          onChange={(e) => update('school', e.target.value)}
          error={fieldErrors.school}
        />
        <Field
          label="Email (optional)"
          type="email"
          autoComplete="email"
          maxLength={254}
          value={form.email}
          onChange={(e) => update('email', e.target.value)}
          error={fieldErrors.email}
        />
        {error && (
          <p role="alert" className="alert">
            {error}
          </p>
        )}
        <button type="submit" className="button" disabled={busy}>
          {busy ? 'Please wait…' : 'Create account'}
        </button>
      </form>
    </AuthLayout>
  )
}
