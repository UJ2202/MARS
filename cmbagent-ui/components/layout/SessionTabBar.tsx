'use client'

import React from 'react'
import { Plus, X } from 'lucide-react'
import { useParallelSessions, SessionTab } from '@/contexts/ParallelSessionsContext'
import { getModeConfig, getModeDisplayName } from '@/lib/modes'
import { useRouter, usePathname } from 'next/navigation'

const statusColors: Record<string, string> = {
  active: 'var(--mars-color-success)',
  paused: 'var(--mars-color-warning)',
  completed: 'var(--mars-color-primary)',
  failed: 'var(--mars-color-danger)',
  new: 'var(--mars-color-text-tertiary)',
}

function getTabDisplayName(tab: SessionTab): string {
  if (tab.name && tab.name !== 'New Tab' && tab.name !== '') return tab.name
  if (tab.mode) return getModeDisplayName(tab.mode)
  return 'New Tab'
}

export default function SessionTabBar() {
  const { tabs, activeTabId, liveTabId, setActiveTab, addTab, closeTab } = useParallelSessions()
  const router = useRouter()
  const pathname = usePathname()

  const handleTabClick = (tabId: string) => {
    setActiveTab(tabId)
    if (pathname !== '/') {
      router.push('/')
    }
  }

  const handleNewTab = () => {
    addTab()
    if (pathname !== '/') {
      router.push('/')
    }
  }

  const handleCloseTab = (e: React.MouseEvent, tabId: string) => {
    e.stopPropagation()
    closeTab(tabId)
  }

  return (
    <div
      className="flex items-end gap-0.5 overflow-x-auto flex-shrink-0 px-1"
      style={{ scrollbarWidth: 'none' }}
    >
      {tabs.map(tab => {
        const isActive = tab.id === activeTabId
        const isLive = tab.id === liveTabId
        const dotColor = statusColors[tab.status] || statusColors.new

        return (
          <div
            key={tab.id}
            onClick={() => handleTabClick(tab.id)}
            className="group flex items-center gap-1.5 px-3 py-1.5 rounded-t-lg text-xs font-medium cursor-pointer transition-all duration-150 select-none relative"
            style={{
              minWidth: '100px',
              maxWidth: '200px',
              backgroundColor: isActive
                ? 'var(--mars-color-bg)'
                : 'transparent',
              color: isActive
                ? 'var(--mars-color-text)'
                : 'var(--mars-color-text-secondary)',
              borderTop: isActive ? '2px solid var(--mars-color-primary)' : '2px solid transparent',
              borderLeft: isActive ? '1px solid var(--mars-color-border)' : '1px solid transparent',
              borderRight: isActive ? '1px solid var(--mars-color-border)' : '1px solid transparent',
              marginBottom: isActive ? '-1px' : '0',
              zIndex: isActive ? 2 : 1,
            }}
            onMouseEnter={(e) => {
              if (!isActive) {
                (e.currentTarget as HTMLDivElement).style.backgroundColor = 'var(--mars-color-bg-hover)'
              }
            }}
            onMouseLeave={(e) => {
              if (!isActive) {
                (e.currentTarget as HTMLDivElement).style.backgroundColor = 'transparent'
              }
            }}
          >
            {/* Status indicator */}
            {tab.status !== 'new' && (
              <span
                className={`w-2 h-2 rounded-full flex-shrink-0 ${isLive && tab.isRunning ? 'animate-pulse' : ''}`}
                style={{ backgroundColor: dotColor }}
              />
            )}

            {/* Tab name */}
            <span className="truncate flex-1">{getTabDisplayName(tab)}</span>

            {/* Close button */}
            {tabs.length > 1 && (
              <button
                onClick={(e) => handleCloseTab(e, tab.id)}
                className="flex-shrink-0 p-0.5 rounded-sm opacity-0 group-hover:opacity-100 transition-opacity"
                style={{ color: 'var(--mars-color-text-tertiary)' }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'var(--mars-color-surface-overlay)'
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'transparent'
                }}
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
        )
      })}

      {/* New tab button */}
      <button
        onClick={handleNewTab}
        className="flex items-center justify-center w-7 h-7 rounded-md transition-colors flex-shrink-0 ml-0.5 mb-0.5"
        style={{ color: 'var(--mars-color-text-tertiary)' }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'var(--mars-color-bg-hover)'
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'transparent'
        }}
        title="New tab"
      >
        <Plus className="w-3.5 h-3.5" />
      </button>
    </div>
  )
}
