'use client'

import React, { createContext, useContext, useState, useCallback, useEffect, useRef, ReactNode } from 'react'
import { getApiUrl } from '@/lib/config'

export interface SessionTab {
  id: string
  name: string
  mode: string | null
  status: 'new' | 'active' | 'paused' | 'completed' | 'failed'
  progress: number
  currentStep?: string
  startedAt?: string
  // Backend session ID (set when backend creates session)
  sessionId: string | null
  // State snapshot (saved when tab is not live)
  consoleOutput: string[]
  results: any | null
  dagData: any | null
  workflowStatus: string | null
  costSummary: any | null
  costTimeSeries: any[]
  isRunning: boolean
  currentRunId: string | null
  isCopilotMode: boolean
  copilotMessages: any[]
}

interface ParallelSessionsContextValue {
  tabs: SessionTab[]
  activeTabId: string
  liveTabId: string | null
  setActiveTab: (tabId: string) => void
  addTab: (mode?: string) => string
  closeTab: (tabId: string) => void
  updateTab: (tabId: string, updates: Partial<SessionTab>) => void
  setLiveTab: (tabId: string | null) => void
}

const ParallelSessionsContext = createContext<ParallelSessionsContextValue | undefined>(undefined)

function createNewTab(mode?: string): SessionTab {
  return {
    id: `tab_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`,
    name: mode ? '' : 'New Tab',
    mode: mode || null,
    status: 'new',
    progress: 0,
    sessionId: null,
    consoleOutput: [],
    results: null,
    dagData: null,
    workflowStatus: null,
    costSummary: null,
    costTimeSeries: [],
    isRunning: false,
    currentRunId: null,
    isCopilotMode: false,
    copilotMessages: [],
  }
}

export function ParallelSessionsProvider({ children }: { children: ReactNode }) {
  const initialTab = createNewTab()
  const [tabs, setTabs] = useState<SessionTab[]>([initialTab])
  const [activeTabId, setActiveTabIdState] = useState(initialTab.id)
  const [liveTabId, setLiveTabState] = useState<string | null>(null)

  const setActiveTab = useCallback((tabId: string) => {
    setActiveTabIdState(tabId)
  }, [])

  const addTab = useCallback((mode?: string): string => {
    const newTab = createNewTab(mode)
    setTabs(prev => [...prev, newTab])
    setActiveTabIdState(newTab.id)
    return newTab.id
  }, [])

  const closeTab = useCallback((tabId: string) => {
    setTabs(prev => {
      const filtered = prev.filter(t => t.id !== tabId)
      if (filtered.length === 0) {
        const newTab = createNewTab()
        return [newTab]
      }
      return filtered
    })
    setLiveTabState(prev => prev === tabId ? null : prev)
  }, [])

  // Fix active tab if it was closed
  useEffect(() => {
    const activeExists = tabs.some(t => t.id === activeTabId)
    if (!activeExists && tabs.length > 0) {
      setActiveTabIdState(tabs[tabs.length - 1].id)
    }
  }, [tabs, activeTabId])

  const updateTab = useCallback((tabId: string, updates: Partial<SessionTab>) => {
    setTabs(prev => prev.map(t => t.id === tabId ? { ...t, ...updates } : t))
  }, [])

  const setLiveTab = useCallback((tabId: string | null) => {
    setLiveTabState(tabId)
  }, [])

  // Background polling: track non-live tabs that are still running
  const tabsRef = useRef(tabs)
  tabsRef.current = tabs
  const liveTabRef = useRef(liveTabId)
  liveTabRef.current = liveTabId

  useEffect(() => {
    const pollBackgroundTabs = async () => {
      const currentTabs = tabsRef.current
      const currentLiveTabId = liveTabRef.current

      // Find tabs that claim to be running but are NOT the live tab
      const backgroundRunning = currentTabs.filter(
        t => t.isRunning && t.id !== currentLiveTabId && t.sessionId
      )

      if (backgroundRunning.length === 0) return

      try {
        // Fetch all sessions from backend
        const response = await fetch(getApiUrl('/api/sessions?limit=50'))
        if (!response.ok) return
        const data = await response.json()
        const sessions = data.sessions || []

        // Match sessions to background tabs and update status
        for (const tab of backgroundRunning) {
          const session = sessions.find(
            (s: any) => s.session_id === tab.sessionId
          )
          if (!session) continue

          const backendStatus = session.status
          const currentPhase = session.current_phase

          // Map backend status to tab status
          if (backendStatus === 'completed' || currentPhase === 'completed') {
            setTabs(prev => prev.map(t =>
              t.id === tab.id ? {
                ...t,
                isRunning: false,
                status: 'completed' as const,
                workflowStatus: 'completed',
                progress: 100,
                currentStep: 'Completed',
              } : t
            ))
          } else if (backendStatus === 'failed' || currentPhase === 'failed') {
            setTabs(prev => prev.map(t =>
              t.id === tab.id ? {
                ...t,
                isRunning: false,
                status: 'failed' as const,
                workflowStatus: 'failed',
                currentStep: 'Failed',
              } : t
            ))
          } else if (backendStatus === 'suspended' || backendStatus === 'paused') {
            setTabs(prev => prev.map(t =>
              t.id === tab.id ? {
                ...t,
                status: 'paused' as const,
                currentStep: currentPhase || tab.currentStep,
              } : t
            ))
          } else {
            // Still active - update current phase
            setTabs(prev => prev.map(t =>
              t.id === tab.id ? {
                ...t,
                currentStep: currentPhase || tab.currentStep,
              } : t
            ))
          }
        }
      } catch (error) {
        // Polling failure is non-critical, just log
        console.warn('[SessionPolling] Failed to poll background sessions:', error)
      }
    }

    // Poll every 5 seconds
    const interval = setInterval(pollBackgroundTabs, 5000)
    // Poll immediately on mount
    pollBackgroundTabs()
    return () => clearInterval(interval)
  }, []) // Stable effect - uses refs to avoid re-creating

  const value: ParallelSessionsContextValue = {
    tabs,
    activeTabId,
    liveTabId,
    setActiveTab,
    addTab,
    closeTab,
    updateTab,
    setLiveTab,
  }

  return (
    <ParallelSessionsContext.Provider value={value}>
      {children}
    </ParallelSessionsContext.Provider>
  )
}

export function useParallelSessions() {
  const context = useContext(ParallelSessionsContext)
  if (!context) {
    throw new Error('useParallelSessions must be used within a ParallelSessionsProvider')
  }
  return context
}
