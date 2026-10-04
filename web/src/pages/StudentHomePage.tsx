import { useCallback } from 'react'
import { Radio } from 'lucide-react'
import { Link } from 'react-router'
import { listMyQuizzes } from '../api/attempts'
import { useAuth } from '../auth/authContext'
import { quizTimeText } from '../components/format'
import { useLoad } from '../components/useLoad'

const dateFormat = new Intl.DateTimeFormat('en-IN', { weekday: 'short', day: 'numeric', month: 'short' })

export function StudentHomePage() {
  const { user } = useAuth()
  const { data: quizzes, error } = useLoad(useCallback(() => listMyQuizzes(), []), 'Could not load your quizzes.')
  const newCount = quizzes?.filter((q) => q.status === 'NEW').length ?? 0

  return (
    <main>
      <section className="student-home__intro">
        <div>
          <p className="eyebrow">YOUR LEARNING SPACE</p>
          <h1>Hello, {user?.name}!</h1>
          <p>Pick a quiz, settle in, and see what you know.</p>
        </div>
        <Link to="/student/rooms" className="button button--secondary">
          <Radio size={17} aria-hidden="true" /> Join a live room
        </Link>
      </section>

      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}

      {quizzes && quizzes.length === 0 && (
        <p className="empty">You have no quizzes yet. Your teacher will add them soon.</p>
      )}

      {newCount > 0 && (
        <p role="status" className="notice">
          You have {newCount} new {newCount === 1 ? 'quiz' : 'quizzes'}!
        </p>
      )}

      {quizzes && quizzes.length > 0 && (
        <ul className="quiz-cards" aria-label="Your quizzes">
          {quizzes.map((quiz) => (
            <li key={quiz.quizId} className={`quiz-card${quiz.status === 'COMPLETED' ? ' quiz-card--done' : ''}`}>
              <div className="quiz-card__title">
                <h2>{quiz.title}</h2>
                {quiz.status === 'NEW' && <span className="badge badge--new">New</span>}
                {quiz.status === 'COMPLETED' && <span className="badge badge--ok">Done</span>}
              </div>
              <p className="quiz-card__facts">
                <span>
                  <span aria-hidden="true">📝</span> {quiz.questionCount}{' '}
                  {quiz.questionCount === 1 ? 'question' : 'questions'}
                </span>
                <span>
                  <span aria-hidden="true">⏱</span> {quizTimeText(quiz)}
                </span>
                {quiz.dueAt && quiz.status !== 'COMPLETED' && (
                  <span>
                    <span aria-hidden="true">📅</span> Finish by {dateFormat.format(new Date(quiz.dueAt))}
                  </span>
                )}
              </p>
              {quiz.status === 'COMPLETED' ? (
                <>
                  <p className="quiz-card__score">
                    Your score: {quiz.score} out of {quiz.questionCount}
                  </p>
                  <Link
                    to={`/student/results/${quiz.attemptId}`}
                    className="button button--secondary quiz-card__action"
                    aria-label={`See results for ${quiz.title}`}
                  >
                    See results
                  </Link>
                </>
              ) : (
                <Link
                  to={`/student/quizzes/${quiz.quizId}`}
                  className="button quiz-card__action"
                  aria-label={`${quiz.status === 'NEW' ? 'Start' : 'Continue'} ${quiz.title}`}
                >
                  {quiz.status === 'NEW' ? 'Start' : 'Continue'}
                </Link>
              )}
            </li>
          ))}
        </ul>
      )}
    </main>
  )
}
