'use client'

import { useState, useCallback, useEffect, useRef } from 'react'
import TaskInput from '@/components/TaskInput'
import ConsoleOutput from '@/components/ConsoleOutput'
import ResultDisplay from '@/components/ResultDisplay'
import Header from '@/components/Header'
import TopNavigation from '@/components/TopNavigation'
import { ApprovalChatPanel } from '@/components/ApprovalChatPanel'
import { CopilotView } from '@/components/CopilotView'
import { SessionList } from '@/components/SessionManager'
import { SessionDetailPanel } from '@/components/SessionManager/SessionDetailPanel'
import { useWebSocketContext } from '@/contexts/WebSocketContext'
import { WorkflowDashboard } from '@/components/workflow'
import { DAGWorkspace } from '@/components/dag'
import { Branch } from '@/types/branching'
import { WorkflowRow } from '@/types/tables'
import { getApiUrl } from '@/lib/config'

export default function Home() {
  const [directoryToOpen, setDirectoryToOpen] = useState<string | null>(null)
  const [rightPanelTab, setRightPanelTab] = useState<'console' | 'workflow' | 'results' | 'sessions'>('console')
  const [elapsedTime, setElapsedTime] = useState('0:00')
  const [startTime, setStartTime] = useState<number | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  // Copilot mode state
  const [isCopilotMode, setIsCopilotMode] = useState(false)
  const [copilotMessages, setCopilotMessages] = useState<Array<{
    id: string
    role: 'user' | 'assistant' | 'system'
    content: string
    timestamp: Date
    status?: 'pending' | 'complete' | 'error'
  }>>([])
  const [copilotConfig, setCopilotConfig] = useState({
    enablePlanning: true,
    approvalMode: 'none',  // Don't use approval mode for chat - each message is explicit human turn
    autoApproveSimple: true,
    maxPlanSteps: 5,
    model: 'gpt-4.1-2025-04-14',
    researcherModel: 'gpt-4.1-2025-04-14',
    plannerModel: 'gpt-4.1-2025-04-14',
    toolApproval: 'prompt',
    intelligentRouting: 'balanced',
    conversational: false,  // Don't use conversational mode - chat messages are the conversation
  })

  // Branch and history state
  const [branches, setBranches] = useState<Branch[]>([])
  const [currentBranchId, setCurrentBranchId] = useState<string | undefined>()
  const [workflowHistory, setWorkflowHistory] = useState<WorkflowRow[]>([])

  // Session detail state
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)

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
    agentMessages,
    clearAgentMessages,
    copilotSessionId,
    setCopilotSessionId,
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

  // Convert agent messages to copilot chat messages
  useEffect(() => {
    if (!isCopilotMode || agentMessages.length === 0) return

    // Only add new agent messages that aren't already in copilot messages
    const lastAgentMsg = agentMessages[agentMessages.length - 1]
    if (!lastAgentMsg) return

    // Keywords to capture for chat display - be more inclusive
    const importantKeywords = [
      'completed', 'result', 'Output', 'finished', 'done', 'success',
      'created', 'generated', 'wrote', 'saved', 'executed', 'running',
      'error', 'failed', 'warning', 'summary', 'analysis', 'found',
      'Step', 'Plan', 'Task', 'Response', 'Answer', 'Code', 'File',
      'processing', 'analyzing', 'computing', 'calculating'
    ]

    const messageText = lastAgentMsg.message || ''
    const hasImportantContent = lastAgentMsg.role === 'assistant' ||
                                importantKeywords.some(kw => messageText.toLowerCase().includes(kw.toLowerCase())) ||
                                messageText.length > 100  // Long messages are usually important

    if (hasImportantContent) {
      const assistantMessage = {
        id: `agent_${Date.now()}_${lastAgentMsg.agent}`,
        role: 'assistant' as const,
        content: `[${lastAgentMsg.agent}] ${messageText}`,
        timestamp: new Date(),
        status: 'complete' as const,
      }
      setCopilotMessages(prev => [...prev, assistantMessage])
    }
  }, [agentMessages, isCopilotMode])

  const handleTaskSubmit = async (task: string, config: any) => {
    // Detect copilot mode
    const copilotMode = config.mode === 'copilot'

    // If just entering copilot mode UI (no task to run)
    if (config._enterCopilotMode && !task.trim()) {
      setIsCopilotMode(true)
      setCopilotConfig({
        enablePlanning: config.enablePlanning ?? true,
        approvalMode: config.approvalMode ?? 'after_step',
        autoApproveSimple: config.autoApproveSimple ?? true,
        maxPlanSteps: config.maxPlanSteps ?? 5,
        model: config.model ?? 'gpt-4.1-2025-04-14',
        researcherModel: config.researcherModel ?? 'gpt-4.1-2025-04-14',
        plannerModel: config.plannerModel ?? 'gpt-4.1-2025-04-14',
        toolApproval: config.toolApproval ?? 'prompt',
        intelligentRouting: config.intelligentRouting ?? 'balanced',
        conversational: config.conversational ?? false,
      })
      return // Don't start a task, just show the UI
    }

    if (isRunning) return
    if (!task.trim()) return // No empty tasks

    setIsCopilotMode(copilotMode)

    if (copilotMode) {
      // Update copilot config
      setCopilotConfig({
        enablePlanning: config.enablePlanning ?? true,
        approvalMode: config.approvalMode ?? 'after_step',
        autoApproveSimple: config.autoApproveSimple ?? true,
        maxPlanSteps: config.maxPlanSteps ?? 5,
        model: config.model ?? 'gpt-4.1-2025-04-14',
        researcherModel: config.researcherModel ?? 'gpt-4.1-2025-04-14',
        plannerModel: config.plannerModel ?? 'gpt-4.1-2025-04-14',
        toolApproval: config.toolApproval ?? 'prompt',
        intelligentRouting: config.intelligentRouting ?? 'balanced',
        conversational: config.conversational ?? false,
      })

      // Add user message to copilot messages
      const userMessage = {
        id: `msg_${Date.now()}`,
        role: 'user' as const,
        content: task,
        timestamp: new Date(),
        status: 'complete' as const,
      }
      setCopilotMessages(prev => [...prev, userMessage])
      // Clear previous agent messages for fresh context
      clearAgentMessages()
    }

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
      addConsoleOutput(`Error: Failed to connect to backend`)
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

    // If in copilot mode and user submitted a new message, add it to chat
    if (isCopilotMode && resolution === 'submit' && feedback) {
      const userMessage = {
        id: `msg_${Date.now()}`,
        role: 'user' as const,
        content: feedback,
        timestamp: new Date(),
        status: 'complete' as const,
      }
      setCopilotMessages(prev => [...prev, userMessage])
    }
  }

  // Handler for sending messages from CopilotView
  // HUMAN INPUT FLOW:
  // - Each user message is a human turn in the conversation
  // - First message creates a new orchestrator session
  // - Subsequent messages continue the same session (preserves context)
  // - approvalMode='none' and conversational=false means no mid-execution pauses
  // - Tool approvals (dangerous operations) still work via toolApproval setting
  // - maxRounds per message keeps responses concise
  const handleCopilotSendMessage = async (message: string) => {
    if (isRunning || !message.trim()) return

    // Add user message to chat
    const userMessage = {
      id: `msg_${Date.now()}`,
      role: 'user' as const,
      content: message,
      timestamp: new Date(),
      status: 'complete' as const,
    }
    setCopilotMessages(prev => [...prev, userMessage])
    // Clear agent messages for fresh context
    clearAgentMessages()

    // Build config with current copilot settings
    const config = {
      mode: 'copilot',
      ...copilotConfig,
      continuousMode: false,  // Don't auto-continue - wait for next user message
      conversational: false,   // Chat interface handles conversation flow
      approvalMode: 'none',    // No mid-execution approvals in chat mode
      maxRounds: 10,           // Allow more rounds for complex tasks (was 5)
      // Indicate if this is a continuation of existing session
      copilotSessionId: copilotSessionId,
    }

    // Start the task
    setIsRunning(true)
    clearConsole()
    setResults(null)
    setStartTime(Date.now())

    // Always generate a unique task ID for each message
    // The copilotSessionId is passed in config for session continuity
    const taskId = `task_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

    try {
      await connect(taskId, message, config)
    } catch (error) {
      console.error('Failed to start task:', error)
      addConsoleOutput(`Error: Failed to connect to backend`)
      setIsRunning(false)

      // Add error message to chat
      const errorMessage = {
        id: `msg_${Date.now()}`,
        role: 'system' as const,
        content: 'Failed to connect to backend. Please try again.',
        timestamp: new Date(),
        status: 'error' as const,
      }
      setCopilotMessages(prev => [...prev, errorMessage])
    }
  }

  // Handler to clear copilot session and start fresh
  const handleClearCopilotSession = () => {
    setCopilotSessionId(null)
    setCopilotMessages([])
    clearAgentMessages()
    clearConsole()
    setResults(null)
  }

  // Handler to view session console logs
  const handleViewSessionLogs = async (sessionId: string, mode?: string) => {
    try {
      const response = await fetch(getApiUrl(`/api/sessions/${sessionId}/history?limit=500`))
      if (!response.ok) throw new Error('Failed to load session history')

      const data = await response.json()
      const messages = data.messages || []

      clearConsole()

      if (messages.length === 0) {
        addConsoleOutput(`[Session ${sessionId}] No logs recorded for this session.`)
      } else {
        addConsoleOutput(`--- Session Logs (${mode || 'unknown'}) - ${messages.length} entries ---`)
        messages.forEach((msg: any) => {
          const agent = msg.agent ? `[${msg.agent}]` : ''
          const role = msg.role || 'system'
          const content = msg.content || ''
          const ts = msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString() : ''
          const prefix = ts ? `${ts} ` : ''

          if (role === 'user') {
            addConsoleOutput(`${prefix}[USER] ${content}`)
          } else if (agent) {
            addConsoleOutput(`${prefix}${agent} ${content}`)
          } else {
            addConsoleOutput(`${prefix}${content}`)
          }
        })
        addConsoleOutput(`--- End of Session Logs ---`)
      }

      // Switch to console tab to show the logs
      setRightPanelTab('console')
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Unknown error'
      addConsoleOutput(`Failed to load session logs: ${msg}`)
    }
  }

  // Handler to resume a session from the Sessions tab (works for ALL modes)
  const handleResumeSessionFromList = async (sessionId: string, mode?: string) => {
    if (isRunning) return

    try {
      // Fetch session details to get task context
      const response = await fetch(getApiUrl(`/api/sessions/${sessionId}`))
      if (!response.ok) throw new Error('Failed to load session')

      const sessionData = await response.json()
      const sessionMode = mode || sessionData.mode || 'one-shot'

      addConsoleOutput(`Resuming session ${sessionId} (mode: ${sessionMode})`)

      // Mark session as active in DB
      await fetch(getApiUrl(`/api/sessions/${sessionId}/resume`), { method: 'POST' })

      // For copilot mode, switch to copilot view and let user send next message
      if (sessionMode === 'copilot') {
        setIsCopilotMode(true)
        setCopilotSessionId(sessionId)

        // Restore copilot config from session
        if (sessionData.config) {
          setCopilotConfig(prev => ({
            ...prev,
            enablePlanning: sessionData.config.enablePlanning ?? prev.enablePlanning,
            model: sessionData.config.model ?? prev.model,
            researcherModel: sessionData.config.researcherModel ?? prev.researcherModel,
            plannerModel: sessionData.config.plannerModel ?? prev.plannerModel,
            toolApproval: sessionData.config.toolApproval ?? prev.toolApproval,
            intelligentRouting: sessionData.config.intelligentRouting ?? prev.intelligentRouting,
          }))
        }

        // Load conversation history into chat
        if (sessionData.conversation_history?.length > 0) {
          const messages = sessionData.conversation_history.map((msg: any, idx: number) => ({
            id: `session_${idx}`,
            role: msg.role === 'user' ? 'user' as const : 'assistant' as const,
            content: msg.agent ? `[${msg.agent}] ${msg.content}` : msg.content,
            timestamp: new Date(msg.timestamp || Date.now()),
            status: 'complete' as const,
          }))
          setCopilotMessages(messages)
        }

        addConsoleOutput(`Copilot session restored. Type a message to continue.`)
        // Switch to workflow tab to show the copilot view
        setRightPanelTab('workflow')
        return
      }

      // For resumable modes (planning-control, hitl-interactive, idea-generation),
      // start a new WebSocket task that continues from the saved session state
      const resumableModes = ['planning-control', 'hitl-interactive', 'idea-generation']
      if (resumableModes.includes(sessionMode)) {
        // Build config from session data
        const resumeConfig = {
          ...(sessionData.config || {}),
          mode: sessionMode,
          session_id: sessionId,
          copilotSessionId: sessionId, // Backend checks both keys
        }

        // Get the last user task from conversation history
        const lastUserMsg = sessionData.conversation_history
          ?.filter((m: any) => m.role === 'user')
          ?.pop()
        const taskDescription = lastUserMsg?.content || sessionData.config?.task || 'Continue previous session'

        // Start execution via WebSocket
        setIsRunning(true)
        clearConsole()
        setResults(null)
        setStartTime(Date.now())

        const taskId = `task_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
        await connect(taskId, taskDescription, resumeConfig)
        return
      }

      // For non-resumable modes (one-shot, ocr, arxiv, enhance-input),
      // just show previous output
      if (sessionData.conversation_history?.length > 0) {
        sessionData.conversation_history.forEach((msg: any) => {
          if (msg.content) {
            addConsoleOutput(`[${msg.agent || msg.role || 'system'}] ${msg.content.substring(0, 200)}`)
          }
        })
      }

      addConsoleOutput(`Session ${sessionId} history loaded. This mode does not support mid-execution resume.`)
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Unknown error'
      addConsoleOutput(`Failed to resume session: ${msg}`)
    }
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
  const handleCreateBranch = async (
    nodeId: string,
    name: string,
    hypothesis?: string,
    newInstructions?: string,
    executeImmediately?: boolean
  ) => {
    if (!currentRunId) {
      addConsoleOutput(`❌ Cannot create branch: No active workflow run`)
      return
    }

    try {
      addConsoleOutput(`🌿 Creating branch "${name}" from node ${nodeId}...`)

      const response = await fetch(`http://localhost:8000/api/runs/${currentRunId}/branch`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          node_id: nodeId,
          branch_name: name,
          hypothesis: hypothesis || null,
          new_instructions: newInstructions || null,
          execute_immediately: executeImmediately || false
        }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to create branch')
      }

      const result = await response.json()

      // Create local branch record
      const newBranch: Branch = {
        branch_id: result.branch_run_id,
        run_id: currentRunId,
        parent_branch_id: currentBranchId,
        branch_point_step_id: nodeId,
        hypothesis,
        name,
        created_at: new Date().toISOString(),
        status: executeImmediately ? 'executing' : 'draft',
        is_main: false,
      }
      setBranches(prev => [...prev, newBranch])
      addConsoleOutput(`✅ Branch "${name}" created successfully (ID: ${result.branch_run_id})`)

      // If execute_immediately was set and we got execution context, the branch is ready
      if (result.status === 'ready_to_execute' && executeImmediately) {
        addConsoleOutput(`🚀 Branch execution prepared. Connect via WebSocket to start.`)
        // TODO: Trigger WebSocket connection for branch execution
      }

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error'
      addConsoleOutput(`❌ Failed to create branch: ${errorMessage}`)
    }
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
        {/* Main Content - Conditional layout based on mode */}
        {isCopilotMode ? (
          /* Copilot Mode - Full-width chat interface */
          <div className="container mx-auto px-4 py-2 min-h-0 overflow-hidden flex-1">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 h-full">
              {/* Left Panel - Copilot Chat View (takes 2/3 of space) */}
              <div className="lg:col-span-2 h-full overflow-hidden rounded-lg border border-gray-700">
                <CopilotView
                  consoleOutput={consoleOutput}
                  isRunning={isRunning}
                  onSendMessage={handleCopilotSendMessage}
                  onStop={handleStopTask}
                  onClearSession={handleClearCopilotSession}
                  pendingApproval={pendingApproval}
                  onApprovalResolve={handleApprovalResolve}
                  messages={copilotMessages}
                  config={copilotConfig}
                  onConfigChange={setCopilotConfig}
                />
              </div>

              {/* Right Panel - Workflow/Results (1/3 of space) */}
              <div className="h-full flex flex-col overflow-hidden">
                {/* Tab Bar */}
                <div className="flex border-b border-gray-700 mb-2 flex-shrink-0">
                  <button
                    onClick={() => setRightPanelTab('workflow')}
                    className={`px-4 py-2 text-sm font-medium transition-colors flex items-center gap-2 ${
                      rightPanelTab === 'workflow'
                        ? 'text-purple-400 border-b-2 border-purple-400'
                        : 'text-gray-400 hover:text-gray-200'
                    }`}
                  >
                    Workflow
                    {dagData && dagData.nodes.length > 0 && (
                      <span className="px-1.5 py-0.5 text-xs bg-purple-500/20 text-purple-400 rounded-full">
                        {dagData.nodes.length}
                      </span>
                    )}
                  </button>
                  <button
                    onClick={() => setRightPanelTab('results')}
                    className={`px-4 py-2 text-sm font-medium transition-colors ${
                      rightPanelTab === 'results'
                        ? 'text-purple-400 border-b-2 border-purple-400'
                        : 'text-gray-400 hover:text-gray-200'
                    }`}
                  >
                    Results
                  </button>
                  <button
                    onClick={() => {
                      setIsCopilotMode(false)
                      setCopilotMessages([])
                      clearAgentMessages()
                    }}
                    className="ml-auto px-3 py-1 text-xs text-gray-400 hover:text-white transition-colors"
                  >
                    Exit Copilot
                  </button>
                </div>

                {/* Tab Content */}
                <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
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
        ) : (
          /* Standard Mode - Task Input and Tabbed Panel */
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
                  <button
                    onClick={() => setRightPanelTab('sessions')}
                    className={`px-4 py-2 text-sm font-medium transition-colors ${
                      rightPanelTab === 'sessions'
                        ? 'text-blue-400 border-b-2 border-blue-400'
                        : 'text-gray-400 hover:text-gray-200'
                    }`}
                  >
                    Sessions
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
                  {rightPanelTab === 'sessions' && (
                    <div className="h-full flex">
                      <div className={`${selectedSessionId ? 'w-1/3 border-r border-gray-700' : 'w-full'} h-full overflow-y-auto p-3`}>
                        <SessionList
                          onResume={handleResumeSessionFromList}
                          onViewLogs={handleViewSessionLogs}
                          onSelect={(id) => setSelectedSessionId(id)}
                          selectedSessionId={selectedSessionId}
                          compact={!!selectedSessionId}
                        />
                      </div>
                      {selectedSessionId && (
                        <div className="w-2/3 h-full overflow-hidden">
                          <SessionDetailPanel
                            sessionId={selectedSessionId}
                            onClose={() => setSelectedSessionId(null)}
                            onResume={handleResumeSessionFromList}
                          />
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
