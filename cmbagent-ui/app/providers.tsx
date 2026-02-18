'use client'

import { ReactNode } from 'react'
import { WebSocketProvider } from '@/contexts/WebSocketContext'
import { ThemeProvider } from '@/contexts/ThemeContext'
import { ParallelSessionsProvider } from '@/contexts/ParallelSessionsContext'
import { ToastProvider } from '@/components/core/ToastContainer'

interface ProvidersProps {
  children: ReactNode
}

export function Providers({ children }: ProvidersProps) {
  return (
    <ThemeProvider>
      <WebSocketProvider>
        <ParallelSessionsProvider>
          <ToastProvider>
            {children}
          </ToastProvider>
        </ParallelSessionsProvider>
      </WebSocketProvider>
    </ThemeProvider>
  )
}
