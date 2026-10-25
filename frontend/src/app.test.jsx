import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, session } from './api'
import { AuthContext } from './auth'
import { I18nContext, LANGS, dictionaries, isRtl, translate } from './i18n'
import { ErrorNote, Money } from './components/ui'
import AuthPage from './pages/AuthPage'
import WageCalculator from './pages/WageCalculator'
import { ChecksList } from './pages/NewClaim'

function jsonResponse(status, body) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }))
}

function wrap(ui, { lang = 'en', auth = {} } = {}) {
  const i18n = { lang, setLang: () => {}, t: (k, v) => translate(lang, k, v) }
  const a = { user: null, ready: true, startSession: vi.fn(), signOut: vi.fn(), setUser: vi.fn(), refreshUser: vi.fn(), ...auth }
  return { a, ...render(<I18nContext.Provider value={i18n}><AuthContext.Provider value={a}>{ui}</AuthContext.Provider></I18nContext.Provider>) }
}

beforeEach(() => { session.clear() })
afterEach(() => { vi.restoreAllMocks() })

describe('i18n', () => {
  it('translates with variables and falls back to English', () => {
    expect(translate('hi', 'hello', { name: 'Asha' })).toBe('नमस्ते, Asha')
    expect(translate('kn', 'wc_pending')).toBe(dictionaries.en.wc_pending)
    expect(translate('en', 'no_such_key')).toBe('no_such_key')
  })
  it('every language only uses keys that exist in English', () => {
    for (const lang of Object.keys(dictionaries)) for (const k of Object.keys(dictionaries[lang])) expect(dictionaries.en).toHaveProperty(k)
  })
  it('all 13 languages cover the main worker screens and every claim status', () => {
    const core = ['tellUs', 's1Title', 'speak', 'anyLanguageNote', 'addFiles', 'sendClaim', 'confirmReceived', 'iAmWorker', 'signIn']
    const statuses = Object.keys(dictionaries.en).filter((k) => k.startsWith('st_'))
    expect(LANGS).toHaveLength(13)
    for (const { code } of LANGS) {
      expect(dictionaries).toHaveProperty(code)
      for (const k of [...core, ...statuses]) expect(dictionaries[code][k], `${code}.${k}`).toBeTruthy()
    }
    expect(isRtl('ur')).toBe(true)
    expect(isRtl('hi')).toBe(false)
  })
})

describe('api client', () => {
  it('sends the bearer token and parses error bodies', async () => {
    session.set('tok123')
    const spy = vi.spyOn(globalThis, 'fetch').mockImplementation(() => jsonResponse(409, { error: { code: 'already_submitted', message: 'Already sent' } }))
    await expect(api('/api/x', { method: 'POST', body: { a: 1 } })).rejects.toMatchObject({ status: 409, code: 'already_submitted' })
    const [, opts] = spy.mock.calls[0]
    expect(opts.headers.Authorization).toBe('Bearer tok123')
    expect(opts.body).toBe('{"a":1}')
  })
  it('turns network failures into a friendly error', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => Promise.reject(new TypeError('Failed to fetch')))
    await expect(api('/api/x')).rejects.toMatchObject({ code: 'network_error' })
    wrap(<ErrorNote error={new ApiError(0, 'network_error', 'network')} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Could not reach HAQ')
  })
})

describe('components', () => {
  it('formats rupees in Indian style', () => {
    render(<Money value="120000.00" />)
    expect(screen.getByText('₹1,20,000')).toBeInTheDocument()
  })
  it('shows check classifications without fraud language', () => {
    wrap(<ChecksList checks={[{ classification: 'possible_inconsistency', message: 'Amounts differ', evidence: [{ label: 'E2' }] }]} />)
    expect(screen.getByText('Possible inconsistency')).toBeInTheDocument()
    expect(screen.getByText('(E2)')).toBeInTheDocument()
    expect(document.body.textContent.toLowerCase()).not.toContain('fraud')
  })
})

describe('sign in', () => {
  it('shows the server message when the account belongs to the other portal', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => jsonResponse(403, { error: { code: 'wrong_portal', message: 'This is a worker account. Please use the worker sign-in page.' } }))
    const { a } = wrap(<MemoryRouter initialEntries={['/employer/sign-in']}><Routes><Route path="/:portal/sign-in" element={<AuthPage mode="login" />} /></Routes></MemoryRouter>)
    await userEvent.type(screen.getByLabelText('Email'), 'asha@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'Passw0rd!')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('worker account')
    expect(a.startSession).not.toHaveBeenCalled()
    const body = JSON.parse(globalThis.fetch.mock.calls[0][1].body)
    expect(body.portal).toBe('employer')
    expect(body).not.toHaveProperty('role')
  })

  it('registers a worker without sending a role', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => jsonResponse(201, { token: 't', user: { role: 'worker', display_name: 'Asha', email_verified: false } }))
    const { a } = wrap(<MemoryRouter initialEntries={['/worker/register']}><Routes>
      <Route path="/:portal/register" element={<AuthPage mode="register" />} /><Route path="/worker" element={<p>home</p>} /></Routes></MemoryRouter>)
    await userEvent.type(screen.getByLabelText('Your name'), 'Asha')
    await userEvent.type(screen.getByLabelText('Email'), 'asha@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'Passw0rd!')
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }))
    await waitFor(() => expect(a.startSession).toHaveBeenCalledWith('t', expect.objectContaining({ role: 'worker' })))
    expect(globalThis.fetch.mock.calls[0][0]).toBe('/api/auth/register/worker')
    expect(JSON.parse(globalThis.fetch.mock.calls[0][1].body)).not.toHaveProperty('role')
  })
})

describe('wage calculator', () => {
  it('shows the server-calculated result and the estimate disclaimer', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => jsonResponse(200, {
      expected_wages: '14400.00', payments_received: '8000.00', potential_outstanding: '6400.00', excess_payment: '0.00',
      formula: '800.00 × 18 days = 14400.00', disclaimer: 'x',
    }))
    wrap(<WageCalculator />, { lang: 'en' })
    await userEvent.type(screen.getByLabelText('Agreed rate (₹)'), '800')
    await userEvent.type(screen.getByLabelText('Days worked'), '18')
    await userEvent.clear(screen.getByLabelText('Total already paid (₹)'))
    await userEvent.type(screen.getByLabelText('Total already paid (₹)'), '8000')
    await userEvent.click(screen.getByRole('button', { name: 'Calculate' }))
    expect(await screen.findByText('₹6,400')).toBeInTheDocument()
    expect(screen.getByText(/not a legal decision/)).toBeInTheDocument()
  })
})
