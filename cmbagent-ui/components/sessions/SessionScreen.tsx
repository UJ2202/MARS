'use client'

import React, { useState, useEffect, useCallback } from 'react'
import { RefreshCw, History, Search } from 'lucide-react'
import { getApiUrl } from '@/lib/config'
import SessionCard from './SessionCard'
import { SessionDetailPanel } from '@/components/SessionManager/SessionDetailPanel'
import { EmptyState, Badge, IconButton, Skeleton } from '@/components/core'

interface Session {
  session_id: string
  name: string
  mode: string
  status: string
  current_phase?: string | null
  current_step?: number | null
  created_at?: string | null
  updated_at?: string | null
  progress?: number
}

const STATUS_GROUPS = [
  { key: 'active', label: 'Active', statuses: ['active'] },
  { key: 'queued', label: 'Queued', statuses: ['queued'] },
  { key: 'paused', label: 'Paused', statuses: ['suspended', 'paused'] },
  { key: 'completed', label: 'Completed', statuses: ['completed'] },
  { key: 'failed', label: 'Failed', statuses: ['failed'] },
]

export default function SessionScreen() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')

  const fetchSessions = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await fetch(getApiUrl('/api/sessions?limit=100'))
      if (!response.ok) throw new Error('Failed to fetch sessions')
      const data = await response.json()
      setSessions(data.sessions || data || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchSessions()
    const interval = setInterval(fetchSessions, 30000)
    return () => clearInterval(interval)
  }, [fetchSessions])

  const handleResume = async (sessionId: string, mode?: string) => {
    window.location.href = `/?resumeSession=${sessionId}${mode ? `&mode=${mode}` : ''}`
  }

  const handleViewLogs = (sessionId: string) => {
    setSelectedSessionId(sessionId)
  }

  const handlePause = async (sessionId: string) => {
    try {
      const response = await fetch(getApiUrl(`/api/sessions/${sessionId}/suspend`), {
        method: 'POST',
      })
      if (response.ok) {
        fetchSessions()
      }
    } catch (err) {
      console.error('Failed to pause session:', err)
    }
  }

  // Filter sessions by search query
  const filteredSessions = sessions.filter((s) => {
    if (!searchQuery.trim()) return true
    const q = searchQuery.toLowerCase()
    return (
      s.name.toLowerCase().includes(q) ||
      s.mode.toLowerCase().includes(q) ||
      s.status.toLowerCase().includes(q)
    )
  })

  // Group sessions by status
  const groupedSessions = STATUS_GROUPS.map((group) => ({
    ...group,
    sessions: filteredSessions.filter((s) => group.statuses.includes(s.status)),
  })).filter((group) => group.sessions.length > 0)

  const totalCount = sessions.length
  const activeCount = sessions.filter((s) => s.status === 'active').length

  return (
    <div className="flex h-full">
      {/* Session List */}
      <div
        className={`${selectedSessionId ? 'w-1/2 border-r' : 'w-full'} flex flex-col h-full transition-all duration-mars-normal`}
        style={{ borderColor: 'var(--mars-color-border)' }}
      >
        {/* Header */}
        <div
          className="flex-shrink-0 px-6 py-4 border-b"
          style={{ borderColor: 'var(--mars-color-border)' }}
        >
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2
                className="text-2xl font-semibold"
                style={{ color: 'var(--mars-color-text)' }}
              >
                Sessions
              </h2>
              <p
                className="text-sm mt-1"
                style={{ color: 'var(--mars-color-text-secondary)' }}
              >
                {totalCount} total{activeCount > 0 ? ` · ${activeCount} active` : ''}
              </p>
            </div>
            <IconButton
              variant="ghost"
              size="md"
              label="Refresh sessions"
              icon={<RefreshCw className="w-4 h-4" />}
              onClick={fetchSessions}
            />
          </div>

          {/* Search */}
          <div
            className="flex items-center gap-2 h-9 px-3 rounded-mars-md border"
            style={{
              backgroundColor: 'var(--mars-color-surface)',
              borderColor: 'var(--mars-color-border)',
            }}
          >
            <Search
              className="w-4 h-4 flex-shrink-0"
              style={{ color: 'var(--mars-color-text-tertiary)' }}
            />
            <input
              type="text"
              placeholder="Search sessions..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="flex-1 bg-transparent text-sm outline-none"
              style={{ color: 'var(--mars-color-text)' }}
            />
          </div>
        </div>

        {/* Session List Content */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-4xl mx-auto">
            {loading ? (
              <div className="space-y-3">
                <Skeleton height={80} />
                <Skeleton height={80} />
                <Skeleton height={80} />
              </div>
            ) : error ? (
              <div
                className="p-4 rounded-mars-md border text-sm"
                style={{
                  borderColor: 'var(--mars-color-danger)',
                  color: 'var(--mars-color-danger)',
                  backgroundColor: 'var(--mars-color-danger-subtle)',
                }}
              >
                Error: {error}
                <button
                  onClick={fetchSessions}
                  className="ml-2 underline"
                >
                  Retry
                </button>
              </div>
            ) : groupedSessions.length === 0 ? (
              <EmptyState
                icon={<History className="w-6 h-6" />}
                title={searchQuery ? 'No sessions match your search' : 'No sessions yet'}
                description={
                  searchQuery
                    ? 'Try adjusting your search query'
                    : 'Launch a workflow from the Modes screen to create a session.'
                }
                action={
                  searchQuery
                    ? undefined
                    : { label: 'Go to Modes', onClick: () => { window.location.href = '/' } }
                }
              />
            ) : (
              <div className="space-y-8">
                {groupedSessions.map((group) => (
                  <div key={group.key}>
                    <div className="flex items-center gap-2 mb-3">
                      <h3
                        className="text-xs font-medium uppercase tracking-wider"
                        style={{ color: 'var(--mars-color-text-tertiary)' }}
                      >
                        {group.label}
                      </h3>
                      <Badge variant="default" size="sm">
                        {group.sessions.length}
                      </Badge>
                    </div>
                    <div className="space-y-2">
                      {group.sessions.map((session) => (
                        <SessionCard
                          key={session.session_id}
                          session={session}
                          selected={selectedSessionId === session.session_id}
                          onSelect={setSelectedSessionId}
                          onResume={handleResume}
                          onViewLogs={handleViewLogs}
                          onPause={handlePause}
                        />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Detail Panel */}
      {selectedSessionId && (
        <div className="w-1/2 h-full overflow-hidden">
          <SessionDetailPanel
            sessionId={selectedSessionId}
            onClose={() => setSelectedSessionId(null)}
            onResume={handleResume}
          />
        </div>
      )}
    </div>
  )
}
