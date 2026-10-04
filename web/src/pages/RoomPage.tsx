import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { joinRoom, createRoom, roomSocket, type QuizRoom } from '../api/rooms'
import { listQuizzes, type QuizSummary } from '../api/quizzes'

type RoomEvent = {
  type: string
  count?: number
  answered?: number
  total?: number
  position?: number
  questionCount?: number
  text?: string
  options?: string[]
  secondsLeft?: number
  correct?: boolean
  scores?: { userId: number; name: string; score: number }[]
  detail?: string
}

export function RoomPage({ mode }: { mode: 'host' | 'student' }) {
  const [quizzes, setQuizzes] = useState<QuizSummary[]>([])
  const [quizId, setQuizId] = useState('')
  const [code, setCode] = useState('')
  const [room, setRoom] = useState<QuizRoom | null>(null)
  const [connected, setConnected] = useState(false)
  const [online, setOnline] = useState(0)
  const [started, setStarted] = useState(false)
  const [liveQuestion, setLiveQuestion] = useState<RoomEvent | null>(null)
  const [selectedOption, setSelectedOption] = useState<number | null>(null)
  const [answerFeedback, setAnswerFeedback] = useState<boolean | null>(null)
  const [answerProgress, setAnswerProgress] = useState<{ answered: number; total: number } | null>(null)
  const [scoreboard, setScoreboard] = useState<RoomEvent['scores']>(undefined)
  const [secondsLeft, setSecondsLeft] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const socketRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (mode !== 'host') return
    listQuizzes({ page: 0, size: 100 }).then((result) => setQuizzes(result.content), () => {
      setError('Could not load quizzes.')
    })
  }, [mode])

  useEffect(() => {
    if (!room) return
    const socket = roomSocket(room.code)
    socketRef.current = socket
    socket.onopen = () => setConnected(true)
    socket.onclose = () => {
      socketRef.current = null
      setConnected(false)
    }
    socket.onerror = () => setError('Live connection lost. Refresh to reconnect.')
    socket.onmessage = (event) => {
      const message = JSON.parse(event.data) as RoomEvent
      if (message.type === 'presence') setOnline(message.count ?? 0)
      if (message.type === 'started') setStarted(true)
      if (message.type === 'question') {
        setStarted(true)
        setLiveQuestion(message)
        setSelectedOption(null)
        setAnswerFeedback(null)
        setAnswerProgress(null)
      }
      if (message.type === 'answer_result') setAnswerFeedback(message.correct ?? false)
      if (message.type === 'answer_count') {
        setAnswerProgress({ answered: message.answered ?? 0, total: message.total ?? 0 })
      }
      if (message.type === 'finished') setScoreboard(message.scores ?? [])
      if (message.type === 'error') setError(message.detail ?? 'The room could not be started.')
    }
    return () => socket.close()
  }, [room])

  useEffect(() => {
    if (!liveQuestion) return
    const endsAt = Date.now() + (liveQuestion.secondsLeft ?? 0) * 1000
    const update = () => setSecondsLeft(Math.max(0, Math.ceil((endsAt - Date.now()) / 1000)))
    update()
    const timer = window.setInterval(update, 250)
    return () => window.clearInterval(timer)
  }, [liveQuestion])

  async function openRoom(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const next = mode === 'host' ? await createRoom(Number(quizId)) : await joinRoom(code.trim().toUpperCase())
      setRoom(next)
      setCode(next.code)
    } catch {
      setError(mode === 'host' ? 'Could not create the room.' : 'Room not found. Check the code and try again.')
    } finally {
      setBusy(false)
    }
  }

  function startRoom() {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({ type: 'start' }))
    }
  }

  function submitLiveAnswer() {
    if (selectedOption === null || socketRef.current?.readyState !== WebSocket.OPEN) return
    socketRef.current.send(JSON.stringify({ type: 'answer', option: selectedOption }))
    setSelectedOption(null)
  }

  return (
    <main className="room-page">
      <Link className="room-back" to={mode === 'host' ? '/admin/quizzes' : '/student'}>← Back</Link>
      <p className="eyebrow">LIVE SESSION</p>
      <h1>{mode === 'host' ? 'Bring the class together.' : 'Join your class.'}</h1>
      <p className="room-intro">{mode === 'host' ? 'Choose a quiz and open a room for students.' : 'Enter the room code your teacher shared.'}</p>

      {error && <p className="alert" role="alert">{error}</p>}

      {!room ? (
        <form className="room-form" onSubmit={openRoom}>
          {mode === 'host' ? (
            <label className="field">
              <span>Quiz</span>
              <select required value={quizId} onChange={(event) => setQuizId(event.target.value)}>
                <option value="">Choose a quiz</option>
                {quizzes.map((quiz) => <option key={quiz.id} value={quiz.id}>{quiz.title}</option>)}
              </select>
            </label>
          ) : (
            <label className="field">
              <span>Room code</span>
              <input autoCapitalize="characters" autoComplete="off" maxLength={6} required value={code} onChange={(event) => setCode(event.target.value.toUpperCase())} />
            </label>
          )}
          <button className="button" type="submit" disabled={busy || (mode === 'host' && quizzes.length === 0)}>
            {busy ? 'Opening room…' : mode === 'host' ? 'Create live room' : 'Join room'}
          </button>
        </form>
      ) : (
        <section className="room-lobby" aria-live="polite">
          <div className="room-lobby__topline"><span className={`connection-dot${connected ? ' is-online' : ''}`} />{connected ? 'Live connection' : 'Connecting…'}</div>
          <p className="room-lobby__label">ROOM CODE</p>
          <p className="room-code">{room.code}</p>
          <h2>{room.quizTitle}</h2>
          {started ? (
            <p className="room-status">The teacher started the session. Keep this room open.</p>
          ) : (
            <p className="room-status">{online} {online === 1 ? 'person' : 'people'} connected. Waiting for the teacher.</p>
          )}
          {mode === 'host' && !started && (
            <button className="button room-start" type="button" onClick={startRoom} disabled={!connected || online < 2}>
              Start live session
            </button>
          )}
          {liveQuestion && !scoreboard && (
            <section className="live-question" aria-live="polite">
              <div className="live-question__meta">
                <span>Question {liveQuestion.position} of {liveQuestion.questionCount}</span>
                <span className={secondsLeft <= 10 ? 'is-low' : ''}>{secondsLeft}s</span>
              </div>
              <div className="live-question__track"><span style={{ width: `${Math.max(0, secondsLeft / Math.max(1, liveQuestion.secondsLeft ?? 1)) * 100}%` }} /></div>
              <h3>{liveQuestion.text}</h3>
              {mode === 'student' ? (
                <>
                  <div className="live-answers" role="group" aria-label="Choose your answer">
                    {liveQuestion.options?.map((option, index) => (
                      <button key={index} type="button" className={selectedOption === index ? 'is-selected' : ''}
                        onClick={() => setSelectedOption(index)} disabled={answerFeedback !== null || secondsLeft === 0}>
                        <span>{String.fromCharCode(65 + index)}</span>{option}
                      </button>
                    ))}
                  </div>
                  {answerFeedback !== null && <p className={`live-feedback ${answerFeedback ? 'is-correct' : 'is-incorrect'}`}>
                    {answerFeedback ? 'Correct answer.' : 'Not quite. Stay ready for the next one.'}
                  </p>}
                  <button className="button room-start" type="button" onClick={submitLiveAnswer}
                    disabled={selectedOption === null || answerFeedback !== null || secondsLeft === 0}>
                    Send answer
                  </button>
                </>
              ) : (
                <p className="room-status">Students are answering. {answerProgress && `${answerProgress.answered} of ${answerProgress.total} responses received.`}</p>
              )}
            </section>
          )}
          {scoreboard && (
            <section className="live-scoreboard" aria-live="polite">
              <h2>Session complete</h2>
              <ol>{scoreboard.map((entry, index) => <li key={entry.userId}>
                <span>{index + 1}. {entry.name}</span><strong>{entry.score}</strong>
              </li>)}</ol>
            </section>
          )}
        </section>
      )}
    </main>
  )
}