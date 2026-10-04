import {
  BookOpenCheck,
  CircleHelp,
  ClipboardList,
  DoorOpen,
  GraduationCap,
  LayoutDashboard,
  LogOut,
  Radio,
  UsersRound,
} from 'lucide-react'
import { Link, NavLink, useNavigate } from 'react-router'
import { useAuth } from '../auth/authContext'

const ADMIN_LINKS = [
  { to: '/admin/users', label: 'Students', icon: UsersRound },
  { to: '/admin/groups', label: 'Classes & groups', icon: GraduationCap },
  { to: '/admin/questions', label: 'Question bank', icon: CircleHelp },
  { to: '/admin/quizzes', label: 'Quizzes', icon: BookOpenCheck },
  { to: '/admin/rooms', label: 'Live room', icon: Radio },
  { to: '/admin/results', label: 'Results', icon: ClipboardList },
]

const STUDENT_LINKS = [
  { to: '/student', label: 'My learning', icon: LayoutDashboard },
  { to: '/student/rooms', label: 'Join a live room', icon: Radio },
  { to: '/student/results', label: 'My scores', icon: ClipboardList },
]

export function Header() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <header className="header">
      <Link to={user ? (user.role === 'ADMIN' ? '/admin/quizzes' : '/student') : '/login'} className="header__brand">
        <span className="header__mark"><GraduationCap size={21} strokeWidth={2.4} /></span>
        <span className="header__brand-name">Schoolmela<span>QUIZ</span></span>
      </Link>
      {user && (
        <nav className="header__nav" aria-label="Main navigation">
          <span className="header__section-label">{user.role === 'ADMIN' ? 'TEACHER STUDIO' : 'YOUR SPACE'}</span>
          {(user.role === 'ADMIN' ? ADMIN_LINKS : STUDENT_LINKS).map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} end={to === '/student'} className="header__link"
              aria-label={to === '/student' ? 'My quizzes' : undefined} title={label}>
              <Icon size={18} strokeWidth={1.9} aria-hidden="true" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
      )}
      {user && (
        <div className="header__user">
          <span className="header__avatar" aria-hidden="true">{user.name.slice(0, 1).toUpperCase()}</span>
          <span className="header__identity"><strong>{user.name}</strong><small>{user.role === 'ADMIN' ? 'Teacher' : 'Student'}</small></span>
          <button type="button" className="header__logout" onClick={handleLogout} aria-label="Log out" title="Log out">
            <LogOut size={18} aria-hidden="true" />
            <span>Log out</span>
          </button>
          <span className="visually-hidden">{user.name}</span>
          <DoorOpen className="header__logout-mobile-icon" size={18} aria-hidden="true" />
        </div>
      )}
    </header>
  )
}
