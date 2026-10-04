import type { ComponentType } from 'react'
import { Navigate, Route, Routes } from 'react-router'
import { homePathFor, useAuth } from './auth/authContext'
import { RequireRole } from './auth/RequireRole'
import { Header } from './components/Header'
import { AdminUsersPage } from './pages/AdminUsersPage'
import { AttemptDetailPage } from './pages/AttemptDetailPage'
import { GroupDetailPage } from './pages/GroupDetailPage'
import { GroupsPage } from './pages/GroupsPage'
import { LoginPage } from './pages/LoginPage'
import { MyResultsPage } from './pages/MyResultsPage'
import { QuestionFormPage } from './pages/QuestionFormPage'
import { QuestionsPage } from './pages/QuestionsPage'
import { QuizAssignPage } from './pages/QuizAssignPage'
import { QuizFormPage } from './pages/QuizFormPage'
import { QuizzesPage } from './pages/QuizzesPage'
import { RegisterPage } from './pages/RegisterPage'
import { RoomPage } from './pages/RoomPage'
import { ResultReviewPage } from './pages/ResultReviewPage'
import { ResultsPage } from './pages/ResultsPage'
import { StudentHomePage } from './pages/StudentHomePage'
import { TakeQuizPage } from './pages/TakeQuizPage'

const ADMIN_ROUTES: [string, ComponentType][] = [
  ['/admin/users', AdminUsersPage],
  ['/admin/questions', QuestionsPage],
  ['/admin/questions/new', QuestionFormPage],
  ['/admin/questions/:id', QuestionFormPage],
  ['/admin/quizzes', QuizzesPage],
  ['/admin/quizzes/new', QuizFormPage],
  ['/admin/quizzes/:id', QuizFormPage],
  ['/admin/quizzes/:id/assign', QuizAssignPage],
  ['/admin/groups', GroupsPage],
  ['/admin/groups/:id', GroupDetailPage],
  ['/admin/results', ResultsPage],
  ['/admin/results/:attemptId', AttemptDetailPage],
]

const STUDENT_ROUTES: [string, ComponentType][] = [
  ['/student', StudentHomePage],
  ['/student/quizzes/:quizId', TakeQuizPage],
  ['/student/results', MyResultsPage],
  ['/student/results/:attemptId', ResultReviewPage],
]

function App() {
  const { user } = useAuth()
  const home = user ? homePathFor(user.role) : '/login'

  return (
    <div className={`app-shell${user ? '' : ' app-shell--public'}`}>
      {user && <Header />}
      <div className="app-content">
      <Routes>
        <Route path="/login" element={user ? <Navigate to={home} replace /> : <LoginPage />} />
        <Route path="/register" element={user ? <Navigate to={home} replace /> : <RegisterPage />} />
        <Route path="/admin/rooms" element={<RequireRole role="ADMIN"><RoomPage mode="host" /></RequireRole>} />
        <Route path="/student/rooms" element={<RequireRole role="STUDENT"><RoomPage mode="student" /></RequireRole>} />
        {STUDENT_ROUTES.map(([path, Page]) => (
          <Route
            key={path}
            path={path}
            element={
              <RequireRole role="STUDENT">
                <Page />
              </RequireRole>
            }
          />
        ))}
        {ADMIN_ROUTES.map(([path, Page]) => (
          <Route
            key={path}
            path={path}
            element={
              <RequireRole role="ADMIN">
                <Page />
              </RequireRole>
            }
          />
        ))}
        <Route path="*" element={<Navigate to={home} replace />} />
      </Routes>
      </div>
    </div>
  )
}

export default App
