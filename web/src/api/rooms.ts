import { apiFetch, getSession } from './client'

export interface QuizRoom {
  id: number
  code: string
  quizId: number
  quizTitle: string
  status: 'LOBBY' | 'IN_PROGRESS' | 'COMPLETED'
  members?: number
}

export function createRoom(quizId: number): Promise<QuizRoom> {
  return apiFetch('/admin/rooms', { method: 'POST', body: JSON.stringify({ quizId }) })
}

export function joinRoom(code: string): Promise<QuizRoom> {
  return apiFetch(`/me/rooms/${encodeURIComponent(code)}/join`, { method: 'POST' })
}

export function roomSocket(code: string): WebSocket {
  const session = getSession()
  if (!session) throw new Error('Please log in again.')
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return new WebSocket(`${protocol}//${location.host}/api/ws/rooms/${encodeURIComponent(code)}`,
    ['bearer', session.accessToken])
}