// frontend/src/app/review/page.tsx
'use client'

import { useState, useEffect, useRef, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'

type ViewState =
  | { phase: 'loading' }
  | { phase: 'google_review'; google_review_url: string }
  | { phase: 'feedback_form' }
  | { phase: 'feedback_submitted' }
  | { phase: 'error' }

const API_BASE = '/api/backend'

const cardStyle: React.CSSProperties = {
  background: '#EDEEF0',
  borderRadius: 10,
  border: '0.5px solid #C8CDD6',
  padding: 32,
  maxWidth: 480,
  width: '100%',
}

const btnStyle: React.CSSProperties = {
  width: '100%',
  background: '#1F3148',
  color: '#FFFFFF',
  border: 'none',
  borderRadius: 8,
  height: 44,
  fontSize: 15,
  fontWeight: 500,
  fontFamily: 'Inter, sans-serif',
  cursor: 'pointer',
  marginTop: 20,
}

const headingStyle: React.CSSProperties = {
  fontSize: 16,
  color: '#1F3148',
  fontWeight: 500,
  margin: '0 0 12px',
  fontFamily: 'Inter, sans-serif',
}

const bodyStyle: React.CSSProperties = {
  fontSize: 14,
  color: '#374151',
  lineHeight: 1.6,
  margin: '0 0 0',
  fontFamily: 'Inter, sans-serif',
}

const mutedStyle: React.CSSProperties = {
  fontSize: 11,
  color: '#9CA3AF',
  marginTop: 12,
  fontFamily: 'Inter, sans-serif',
}

function ReviewPageInner() {
  const searchParams = useSearchParams()
  const score = searchParams.get('score')
  const firm = searchParams.get('firm')
  const engagement = searchParams.get('engagement')

  const [view, setView] = useState<ViewState>({ phase: 'loading' })
  const [feedbackText, setFeedbackText] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const called = useRef(false)

  useEffect(() => {
    if (called.current) return
    called.current = true

    if (!score || !firm || !engagement) {
      setView({ phase: 'error' })
      return
    }

    fetch(`${API_BASE}/review-requests/record-score`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        score: Number(score),
        firm_id: firm,
        engagement_id: engagement,
      }),
    })
      .then((res) => {
        if (!res.ok) throw new Error('bad response')
        return res.json()
      })
      .then((data) => {
        if (data.action === 'google_review') {
          setView({ phase: 'google_review', google_review_url: data.google_review_url })
        } else {
          setView({ phase: 'feedback_form' })
        }
      })
      .catch(() => setView({ phase: 'error' }))
  }, [score, firm, engagement])

  async function handleSubmitFeedback() {
    if (!score || !firm || !engagement) return
    setSubmitting(true)
    try {
      const res = await fetch(`${API_BASE}/review-requests/submit-feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          score: Number(score),
          firm_id: firm,
          engagement_id: engagement,
          feedback_text: feedbackText,
        }),
      })
      if (!res.ok) throw new Error('bad response')
      setView({ phase: 'feedback_submitted' })
    } catch {
      // keep form visible, let user retry
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        background: '#E4E6EA',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '32px 16px',
        fontFamily: 'Inter, sans-serif',
      }}
    >
      {view.phase === 'loading' && (
        <div style={{ textAlign: 'center' }}>
          <div
            style={{
              width: 28,
              height: 28,
              border: '3px solid #C8CDD6',
              borderTopColor: '#1F3148',
              borderRadius: '50%',
              animation: 'spin 0.8s linear infinite',
              margin: '0 auto 12px',
            }}
          />
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          <p style={{ fontSize: 13, color: '#9CA3AF' }}>One moment...</p>
        </div>
      )}

      {view.phase === 'google_review' && (
        <div style={cardStyle}>
          <p style={headingStyle}>Thank you!</p>
          <p style={bodyStyle}>
            We really appreciate you taking the time. Would you mind sharing your experience on
            Google? It helps other businesses find us and only takes a moment.
          </p>
          <button
            style={btnStyle}
            onClick={() => window.open(view.google_review_url, '_blank')}
          >
            Leave a Google Review →
          </button>
          <p style={mutedStyle}>Thank you again for choosing us.</p>
        </div>
      )}

      {view.phase === 'feedback_form' && (
        <div style={cardStyle}>
          <p style={headingStyle}>Thank you for the honest feedback.</p>
          <p style={bodyStyle}>
            We&apos;re still building and your input shapes what we improve next. What&apos;s one
            thing that could have been better?
          </p>
          <textarea
            value={feedbackText}
            onChange={(e) => setFeedbackText(e.target.value)}
            placeholder="Tell us what would make the experience better for you..."
            style={{
              width: '100%',
              minHeight: 100,
              background: '#F7F7F8',
              border: '0.5px solid #C8CDD6',
              borderRadius: 6,
              fontSize: 14,
              fontFamily: 'Inter, sans-serif',
              padding: '10px 12px',
              resize: 'vertical',
              color: '#1F3148',
              boxSizing: 'border-box',
              marginTop: 16,
              outline: 'none',
            }}
          />
          <button
            style={{ ...btnStyle, opacity: submitting ? 0.6 : 1 }}
            onClick={handleSubmitFeedback}
            disabled={submitting}
          >
            {submitting ? 'Submitting...' : 'Submit Feedback'}
          </button>
        </div>
      )}

      {view.phase === 'feedback_submitted' && (
        <div style={{ ...cardStyle, textAlign: 'center' }}>
          <p style={{ fontSize: 14, color: '#374151', margin: '0 0 6px' }}>
            Got it — thank you.
          </p>
          <p style={{ fontSize: 12, color: '#6B7280', margin: 0 }}>
            Your feedback goes directly to the team.
          </p>
        </div>
      )}

      {view.phase === 'error' && (
        <div style={cardStyle}>
          <p style={{ fontSize: 14, color: '#374151', margin: 0 }}>
            Something went wrong. Please try again.
          </p>
        </div>
      )}
    </div>
  )
}

export default function ReviewPage() {
  return (
    <Suspense fallback={
      <div style={{
        minHeight: '100vh',
        background: '#E4E6EA',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        <p style={{ fontSize: '13px', color: '#6B7280' }}>Loading...</p>
      </div>
    }>
      <ReviewPageInner />
    </Suspense>
  )
}
