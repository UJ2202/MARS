'use client'

import { useState, useCallback, useEffect, useRef } from 'react'
import TaskInput from '@/components/TaskInput'
import ConsoleOutput from '@/components/ConsoleOutput'
import ResultDisplay from '@/components/ResultDisplay'
import Header from '@/components/Header'
import { useWebSocketContext } from '@/contexts/WebSocketContext'
import { WorkflowDashboard } from '@/components/workflow'
import { DAGWorkspace } from '@/components/dag'
import { Branch } from '@/types/branching'
import { WorkflowRow } from '@/types/tables'
import { getApiUrl } from '@/lib/config'

export default function Home() {
  const [directoryToOpen, setDirectoryToOpen] = useState<string | null>(null)
  const [upperHeight, setUpperHeight] = useState(60) // Percentage for upper section
  const [isResizing, setIsResizing] = useState(false)
  const [rightPanelTab, setRightPanelTab] = useState<'results' | 'workflow'>('results')
  const [elapsedTime, setElapsedTime] = useState('0:00')
  const [startTime, setStartTime] = useState<number | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  // Branch and history state
  const [branches, setBranches] = useState<Branch[]>([])
  const [currentBranchId, setCurrentBranchId] = useState<string | undefined>()
  const [workflowHistory, setWorkflowHistory] = useState<WorkflowRow[]>([])

  // Use WebSocket context instead of local state
  const {
    connected,
    isConnecting,
    connect,
    disconnect,
    sendMessage,
    currentRunId,
    consoleOutput,
    addConsoleOutput,
    clearConsole,
    results,
    setResults,
    isRunning,
    setIsRunning,
    workflowStatus,
    setWorkflowStatus,
    dagData,
    costSummary,
    costTimeSeries,
    filesUpdatedCounter,
  } = useWebSocketContext()

  // Track elapsed time when running
  useEffect(() => {
    if (isRunning && !startTime) {
      setStartTime(Date.now())
    } else if (!isRunning && startTime) {
      setStartTime(null)
    }
  }, [isRunning, startTime])

  useEffect(() => {
    if (!startTime) {
      setElapsedTime('0:00')
      return
    }

    const interval = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startTime) / 1000)
      const mins = Math.floor(elapsed / 60)
      const secs = elapsed % 60
      setElapsedTime(`${mins}:${secs.toString().padStart(2, '0')}`)
    }, 1000)

    return () => clearInterval(interval)
  }, [startTime])

  const handleTaskSubmit = async (task: string, config: any) => {
    if (isRunning) return

    setIsRunning(true)
    clearConsole()
    setResults(null)
    setStartTime(Date.now())

    // Generate a unique task ID
    const taskId = `task_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

    try {
      await connect(taskId, task, config)
    } catch (error) {
      console.error('Failed to start task:', error)
      addConsoleOutput(`❌ Error: Failed to connect to backend`)
      setIsRunning(false)
    }
  }

  const handleStopTask = () => {
    disconnect()
    setIsRunning(false)
    addConsoleOutput('🛑 Task execution stopped by user')
  }

  const handlePause = () => {
    if (connected && currentRunId) {
      sendMessage({ type: 'pause', run_id: currentRunId })
      setWorkflowStatus('paused')
      addConsoleOutput('⏸️ Pause request sent to workflow')
    } else {
      addConsoleOutput('⚠️ Cannot pause: not connected to backend')
    }
  }

  const handleResume = () => {
    if (connected && currentRunId) {
      sendMessage({ type: 'resume', run_id: currentRunId })
      setWorkflowStatus('executing')
      addConsoleOutput('▶️ Resume request sent to workflow')
    } else {
      addConsoleOutput('⚠️ Cannot resume: not connected to backend')
    }
  }

  const handleCancel = () => {
    handleStopTask()
  }

  const handlePlayFromNode = async (nodeId: string) => {
    if (!currentRunId) {
      addConsoleOutput('⚠️ Cannot play from node: No active workflow run')
      return
    }

    addConsoleOutput(`▶️ Initiating play from node: ${nodeId}...`)

    try {
      const response = await fetch(getApiUrl(`/api/runs/${currentRunId}/play-from-node`), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          node_id: nodeId,
          context_override: null
        }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to initiate play from node')
      }

      const result = await response.json()
      addConsoleOutput(`✅ Workflow prepared to resume from node ${nodeId}`)
      addConsoleOutput(`📋 Status: ${result.result?.status || 'ready'}`)

      // Update DAG node status to show it's starting from this node
      if (dagData) {
        // Reset downstream nodes to pending visually
        const nodeIndex = dagData.nodes.findIndex(n => n.id === nodeId)
        if (nodeIndex >= 0) {
          dagData.nodes.forEach((node, idx) => {
            if (idx >= nodeIndex && node.status !== 'completed') {
              node.status = 'pending'
            }
          })
        }
      }

      // Switch to workflow tab to show progress
      setRightPanelTab('workflow')

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error'
      addConsoleOutput(`❌ Failed to play from node: ${errorMessage}`)
    }
  }

  // Branch handlers
  const handleCreateBranch = (nodeId: string, name: string, hypothesis?: string) => {
    const newBranch: Branch = {
      branch_id: `branch_${Date.now()}`,
      run_id: currentRunId || '',
      parent_branch_id: currentBranchId,
      branch_point_step_id: nodeId,
      hypothesis,
      name,
      created_at: new Date().toISOString(),
      status: 'draft',
      is_main: false,
    }
    setBranches(prev => [...prev, newBranch])
    addConsoleOutput(`🌿 Created branch "${name}" from node ${nodeId}`)
  }

  const handleSelectBranch = (branchId: string) => {
    setCurrentBranchId(branchId)
    addConsoleOutput(`🔀 Switched to branch: ${branchId}`)
  }

  const handleViewBranch = (branchId: string) => {
    addConsoleOutput(`👁️ Viewing branch: ${branchId}`)
  }

  const handleCompareBranches = (branchIdA: string, branchIdB: string) => {
    addConsoleOutput(`🔍 Comparing branches: ${branchIdA} vs ${branchIdB}`)
  }

  // Workflow history handlers
  const handleViewWorkflow = (workflow: WorkflowRow) => {
    addConsoleOutput(`👁️ Viewing workflow: ${workflow.id}`)
  }

  const handleResumeWorkflow = (workflow: WorkflowRow) => {
    addConsoleOutput(`▶️ Resuming workflow: ${workflow.id}`)
  }

  const handleBranchWorkflow = (workflow: WorkflowRow) => {
    addConsoleOutput(`🌿 Creating branch from workflow: ${workflow.id}`)
  }

  // Add completed workflow to history
  useEffect(() => {
    if (!isRunning && results && currentRunId) {
      const newWorkflow: WorkflowRow = {
        id: currentRunId,
        session_id: 'session_1',
        task_description: results.task || 'Task completed',
        status: workflowStatus === 'failed' ? 'failed' : 'completed',
        agent: results.agent || 'engineer',
        model: results.model || 'gpt-4o',
        started_at: startTime ? new Date(startTime).toISOString() : undefined,
        completed_at: new Date().toISOString(),
        total_cost: results.total_cost || 0,
        step_count: dagData?.nodes.length || 1,
      }
      setWorkflowHistory(prev => {
        // Don't add if already exists
        if (prev.some(w => w.id === currentRunId)) return prev
        return [newWorkflow, ...prev]
      })

      // Create main branch for workflow if not exists
      if (branches.length === 0) {
        const mainBranch: Branch = {
          branch_id: `main_${currentRunId}`,
          run_id: currentRunId,
          name: 'main',
          created_at: new Date().toISOString(),
          status: newWorkflow.status,
          is_main: true,
        }
        setBranches([mainBranch])
        setCurrentBranchId(mainBranch.branch_id)
      }
    }
  }, [isRunning, results, currentRunId, workflowStatus, startTime, dagData, branches.length])

  const handleOpenDirectory = useCallback((path: string) => {
    setDirectoryToOpen(path)
    // Create a mock results object to show the file browser
    const mockResults = {
      execution_time: 0,
      base_work_dir: path,
      work_dir: path
    }
    setResults(mockResults)
  }, [setResults])

  // Handle resizing
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    setIsResizing(true)
    e.preventDefault()
  }, [])

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isResizing || !containerRef.current) return

    const containerRect = containerRef.current.getBoundingClientRect()
    const containerHeight = containerRect.height
    const mouseY = e.clientY - containerRect.top

    // Calculate percentage (min 20%, max 80%)
    const newUpperHeight = Math.min(80, Math.max(20, (mouseY / containerHeight) * 100))
    setUpperHeight(newUpperHeight)
  }, [isResizing])

  const handleMouseUp = useCallback(() => {
    setIsResizing(false)
  }, [])

  useEffect(() => {
    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove)
      document.addEventListener('mouseup', handleMouseUp)
      document.body.style.cursor = 'ns-resize'
      document.body.style.userSelect = 'none'
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
  }, [isResizing, handleMouseMove, handleMouseUp])





  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <Header />

      <main ref={containerRef} className="flex-1 flex flex-col min-h-0">
        {/* Upper Section - Task Input and Results */}
        <div 
          className="container mx-auto px-4 py-2 min-h-0 overflow-hidden"
          style={{ height: `${upperHeight}%` }}
        >
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 h-full">
            {/* Left Panel - Task Input */}
            <div className="h-full overflow-y-auto">
              <TaskInput
                onSubmit={handleTaskSubmit}
                onStop={handleStopTask}
                isRunning={isRunning}
                isConnecting={isConnecting}
                onOpenDirectory={handleOpenDirectory}
              />
            </div>

            {/* Right Panel - Results / Workflow Dashboard */}
            <div className="h-full flex flex-col overflow-hidden">
              {/* Tab Bar */}
              <div className="flex border-b border-gray-700 mb-2 flex-shrink-0">
                <button
                  onClick={() => setRightPanelTab('results')}
                  className={`px-4 py-2 text-sm font-medium transition-colors ${
                    rightPanelTab === 'results'
                      ? 'text-blue-400 border-b-2 border-blue-400'
                      : 'text-gray-400 hover:text-gray-200'
                  }`}
                >
                  Results
                </button>
                <button
                  onClick={() => setRightPanelTab('workflow')}
                  className={`px-4 py-2 text-sm font-medium transition-colors flex items-center gap-2 ${
                    rightPanelTab === 'workflow'
                      ? 'text-blue-400 border-b-2 border-blue-400'
                      : 'text-gray-400 hover:text-gray-200'
                  }`}
                >
                  Workflow
                  {dagData && dagData.nodes.length > 0 && (
                    <span className="px-1.5 py-0.5 text-xs bg-blue-500/20 text-blue-400 rounded-full">
                      {dagData.nodes.length}
                    </span>
                  )}
                </button>
              </div>

              {/* Tab Content */}
              <div className="flex-1 min-h-0 overflow-hidden">
                {rightPanelTab === 'results' && (
                  <div className="h-full overflow-y-auto">
                    <ResultDisplay results={results} />
                  </div>
                )}
                {rightPanelTab === 'workflow' && (
                  <div className="h-full overflow-hidden">
                    <WorkflowDashboard
                      status={workflowStatus || (isRunning ? 'executing' : 'draft')}
                      dagData={dagData}
                      elapsedTime={elapsedTime}
                      branches={branches}
                      currentBranchId={currentBranchId}
                      workflowHistory={workflowHistory}
                      costSummary={costSummary}
                      costTimeSeries={costTimeSeries}
                      filesUpdatedCounter={filesUpdatedCounter}
                      onPause={handlePause}
                      onResume={handleResume}
                      onCancel={handleCancel}
                      onPlayFromNode={handlePlayFromNode}
                      onCreateBranch={handleCreateBranch}
                      onSelectBranch={handleSelectBranch}
                      onViewBranch={handleViewBranch}
                      onCompareBranches={handleCompareBranches}
                      onViewWorkflow={handleViewWorkflow}
                      onResumeWorkflow={handleResumeWorkflow}
                      onBranchWorkflow={handleBranchWorkflow}
                    />
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Resizer Handle */}
        <div
          className={`h-1.5 bg-gray-600/30 hover:bg-blue-500/50 cursor-ns-resize transition-all duration-200 relative group flex-shrink-0 ${isResizing ? 'bg-blue-500/70' : ''}`}
          onMouseDown={handleMouseDown}
          title="Drag to resize console height"
        >
          <div className="absolute inset-x-0 -top-2 -bottom-2 flex items-center justify-center">
            <div className={`w-16 h-0.5 bg-gray-500/50 rounded-full group-hover:bg-blue-400/70 group-hover:w-20 transition-all duration-200 ${isResizing ? 'bg-blue-400 w-20' : ''}`}></div>
          </div>
          {/* Add dots for better visual indication */}
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="flex space-x-0.5">
              <div className={`w-1 h-1 bg-gray-400/40 rounded-full transition-opacity duration-200 ${isResizing ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}></div>
              <div className={`w-1 h-1 bg-gray-400/40 rounded-full transition-opacity duration-200 ${isResizing ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}></div>
              <div className={`w-1 h-1 bg-gray-400/40 rounded-full transition-opacity duration-200 ${isResizing ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}></div>
            </div>
          </div>
        </div>

        {/* Lower Section - Console Output */}
        <div 
          className="px-4 pb-2 min-h-0 overflow-hidden"
          style={{ height: `${100 - upperHeight}%` }}
        >
          <ConsoleOutput
            output={consoleOutput}
            isRunning={isRunning}
            onClear={clearConsole}
          />
        </div>
      </main>
    </div>
  )
}
