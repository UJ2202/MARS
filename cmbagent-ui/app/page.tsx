'use client'

import { useState, useCallback, useEffect, useRef } from 'react'
import TaskInput from '@/components/TaskInput'
import ConsoleOutput from '@/components/ConsoleOutput'
import ResultDisplay from '@/components/ResultDisplay'
import Header from '@/components/Header'
import TopNavigation from '@/components/TopNavigation'
import { ApprovalChatPanel } from '@/components/ApprovalChatPanel'
import { useWebSocketContext } from '@/contexts/WebSocketContext'
import { WorkflowDashboard } from '@/components/workflow'
import { DAGWorkspace } from '@/components/dag'
import { Branch } from '@/types/branching'
import { WorkflowRow } from '@/types/tables'
import { getApiUrl } from '@/lib/config'

export default function Home() {
  const [directoryToOpen, setDirectoryToOpen] = useState<string | null>(null)
  const [rightPanelTab, setRightPanelTab] = useState<'console' | 'workflow' | 'results'>('console')
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
    pendingApproval,
    clearApproval,
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

  const handleApprovalResolve = (resolution: string, feedback?: string, modifications?: string) => {
    if (!pendingApproval) return

    // Send approval response via WebSocket
    sendMessage({
      type: 'resolve_approval',
      approval_id: pendingApproval.approval_id,
      resolution: resolution,
      feedback: feedback || '',
      modifications: modifications || '',
    })

    addConsoleOutput(`✅ Approval response sent: ${resolution}${feedback ? ` - "${feedback}"` : ''}`)
    clearApproval()
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





  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <TopNavigation />
      <Header />

      <main ref={containerRef} className="flex-1 flex min-h-0">
        {/* Main Content - Task Input and Tabbed Panel */}
        <div className="container mx-auto px-4 py-2 min-h-0 overflow-hidden flex-1">
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

            {/* Right Panel - Console / Workflow / Results */}
            <div className="h-full flex flex-col overflow-hidden">
              {/* Tab Bar */}
              <div className="flex border-b border-gray-700 mb-2 flex-shrink-0">
                <button
                  onClick={() => setRightPanelTab('console')}
                  className={`px-4 py-2 text-sm font-medium transition-colors flex items-center gap-2 ${
                    rightPanelTab === 'console'
                      ? 'text-blue-400 border-b-2 border-blue-400'
                      : 'text-gray-400 hover:text-gray-200'
                  }`}
                >
                  Console
                  {isRunning && (
                    <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                  )}
                  {pendingApproval && (
                    <span className="px-1.5 py-0.5 text-xs bg-yellow-500/20 text-yellow-400 rounded-full animate-pulse">
                      !
                    </span>
                  )}
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
              </div>

              {/* Tab Content */}
              <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
                {rightPanelTab === 'console' && (
                  <div className="h-full flex flex-col overflow-hidden">
                    <div className="flex-1 min-h-0 overflow-hidden">
                      <ConsoleOutput
                        output={consoleOutput}
                        isRunning={isRunning}
                        onClear={clearConsole}
                      />
                    </div>
                    {/* Approval Chat Panel - appears at bottom when approval is pending */}
                    {pendingApproval && (
                      <ApprovalChatPanel
                        approval={pendingApproval}
                        onResolve={handleApprovalResolve}
                      />
                    )}
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
                {rightPanelTab === 'results' && (
                  <div className="h-full overflow-y-auto">
                    <ResultDisplay results={results} />
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
