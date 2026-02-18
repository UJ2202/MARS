'use client'

import { useState, useCallback, useEffect, useRef } from 'react'
import { ArrowLeft } from 'lucide-react'
import TaskInput from '@/components/TaskInput'
import ConsoleOutput from '@/components/ConsoleOutput'
import { ApprovalChatPanel } from '@/components/ApprovalChatPanel'
import { CopilotView } from '@/components/CopilotView'
import { useWebSocketContext } from '@/contexts/WebSocketContext'
import { useParallelSessions } from '@/contexts/ParallelSessionsContext'
import { WorkflowDashboard } from '@/components/workflow'
import { DAGWorkspace } from '@/components/dag'
import { Branch } from '@/types/branching'
import { WorkflowRow } from '@/types/tables'
import { getApiUrl } from '@/lib/config'
import { ModeGallery } from '@/components/modes'
import { getModeDisplayName } from '@/lib/modes'
import BottomPanel from '@/components/layout/BottomPanel'

export default function Home() {
  const containerRef = useRef<HTMLDivElement>(null)

  // Tab/session management
  const {
    tabs,
    activeTabId,
    liveTabId,
    setActiveTab,
    addTab,
    closeTab,
    updateTab,
    setLiveTab,
  } = useParallelSessions()

  const activeTab = tabs.find(t => t.id === activeTabId)

  // Local UI state derived from active tab
  const [selectedMode, setSelectedMode] = useState<string | null>(activeTab?.mode || null)
  const [isCopilotMode, setIsCopilotMode] = useState(activeTab?.isCopilotMode || false)
  const [elapsedTime, setElapsedTime] = useState('0:00')
  const [startTime, setStartTime] = useState<number | null>(null)

  // Copilot state
  const [copilotMessages, setCopilotMessages] = useState<Array<{
    id: string
    role: 'user' | 'assistant' | 'system'
    content: string
    timestamp: Date
    status?: 'pending' | 'complete' | 'error'
  }>>([])
  const [copilotConfig, setCopilotConfig] = useState({
    enablePlanning: true,
    approvalMode: 'none',
    autoApproveSimple: true,
    maxPlanSteps: 5,
    model: 'gpt-4.1-2025-04-14',
    researcherModel: 'gpt-4.1-2025-04-14',
    plannerModel: 'gpt-4.1-2025-04-14',
    toolApproval: 'prompt',
    intelligentRouting: 'balanced',
    conversational: false,
  })

  // Branch and history state
  const [branches, setBranches] = useState<Branch[]>([])
  const [currentBranchId, setCurrentBranchId] = useState<string | undefined>()
  const [workflowHistory, setWorkflowHistory] = useState<WorkflowRow[]>([])

  // WebSocket context (live data for the connected session)
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
    setConsoleOutputDirect,
    setDagDataDirect,
    setCostSummaryDirect,
    setCostTimeSeriesDirect,
  } = useWebSocketContext()

  // Determine if active tab is the live (WS-connected) tab
  const isActiveTabLive = activeTabId === liveTabId

  // Display data: live from WS or from tab snapshot
  const displayConsole = isActiveTabLive ? consoleOutput : (activeTab?.consoleOutput || [])
  const displayResults = isActiveTabLive ? results : (activeTab?.results || null)
  const displayDag = isActiveTabLive ? dagData : (activeTab?.dagData || null)
  const displayWorkflowStatus = isActiveTabLive ? workflowStatus : (activeTab?.workflowStatus || null)
  const displayIsRunning = isActiveTabLive ? isRunning : (activeTab?.isRunning || false)
  const displayCostSummary = isActiveTabLive ? costSummary : (activeTab?.costSummary || { total_cost: 0, total_tokens: 0, input_tokens: 0, output_tokens: 0, model_breakdown: [], agent_breakdown: [], step_breakdown: [] })
  const displayCostTimeSeries = isActiveTabLive ? costTimeSeries : (activeTab?.costTimeSeries || [])

  // Save backend sessionId to the live tab when it arrives via WS
  useEffect(() => {
    if (copilotSessionId && liveTabId) {
      updateTab(liveTabId, { sessionId: copilotSessionId })
    }
  }, [copilotSessionId, liveTabId, updateTab])

  // Sync local state when active tab changes
  const prevTabRef = useRef(activeTabId)
  useEffect(() => {
    if (prevTabRef.current !== activeTabId) {
      const tab = tabs.find(t => t.id === activeTabId)
      setSelectedMode(tab?.mode || null)
      setIsCopilotMode(tab?.isCopilotMode || false)
      setCopilotMessages(tab?.copilotMessages || [])
      prevTabRef.current = activeTabId
    }
  }, [activeTabId, tabs])

  // Reload console logs from backend when switching to a non-live tab
  useEffect(() => {
    const tab = tabs.find(t => t.id === activeTabId)
    if (!tab || !tab.sessionId || isActiveTabLive) return
    // Only reload if the tab was running or just completed (has a session)
    if (tab.status === 'new') return

    const loadSessionLogs = async () => {
      try {
        const response = await fetch(getApiUrl(`/api/sessions/${tab.sessionId}/history?limit=500`))
        if (!response.ok) return
        const data = await response.json()
        const messages = data.messages || []
        if (messages.length === 0) return

        const logLines: string[] = []
        messages.forEach((msg: any) => {
          const agent = msg.agent ? `[${msg.agent}]` : ''
          const content = msg.content || ''
          const ts = msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString() : ''
          const prefix = ts ? `${ts} ` : ''
          if (msg.role === 'user') {
            logLines.push(`${prefix}[USER] ${content}`)
          } else if (agent) {
            logLines.push(`${prefix}${agent} ${content}`)
          } else if (content) {
            logLines.push(`${prefix}${content}`)
          }
        })

        if (logLines.length > 0) {
          updateTab(activeTabId, { consoleOutput: logLines })
        }
      } catch (error) {
        console.warn('Failed to reload session logs:', error)
      }
    }

    loadSessionLogs()
  }, [activeTabId, isActiveTabLive])

  // Track elapsed time when running
  useEffect(() => {
    if (displayIsRunning && !startTime) {
      setStartTime(Date.now())
    } else if (!displayIsRunning && startTime) {
      setStartTime(null)
    }
  }, [displayIsRunning, startTime])

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
    if (!isCopilotMode || agentMessages.length === 0 || !isActiveTabLive) return
    const lastAgentMsg = agentMessages[agentMessages.length - 1]
    if (!lastAgentMsg) return
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
      messageText.length > 100
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
  }, [agentMessages, isCopilotMode, isActiveTabLive])

  // Save live tab state when task completes
  useEffect(() => {
    if (!isRunning && liveTabId && prevRunningRef.current) {
      updateTab(liveTabId, {
        isRunning: false,
        status: workflowStatus === 'failed' ? 'failed' : 'completed',
        consoleOutput: [...consoleOutput],
        results: results,
        dagData: dagData,
        workflowStatus: workflowStatus,
        costSummary: costSummary,
        costTimeSeries: [...costTimeSeries],
        copilotMessages: [...copilotMessages],
      })
    }
    prevRunningRef.current = isRunning
  }, [isRunning])
  const prevRunningRef = useRef(isRunning)

  const handleTaskSubmit = async (task: string, config: any) => {
    const copilotMode = config.mode === 'copilot'

    // If entering copilot mode UI only (no task)
    if (config._enterCopilotMode && !task.trim()) {
      setIsCopilotMode(true)
      updateTab(activeTabId, { isCopilotMode: true })
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
      return
    }

    // Don't allow empty tasks
    if (!task.trim()) return

    // If this tab already has a running task, don't double-submit
    if (isActiveTabLive && isRunning) return

    // If another tab is live and running, save its state first
    if (liveTabId && liveTabId !== activeTabId && isRunning) {
      updateTab(liveTabId, {
        consoleOutput: [...consoleOutput],
        results: results,
        dagData: dagData,
        workflowStatus: workflowStatus,
        costSummary: costSummary,
        costTimeSeries: [...costTimeSeries],
        isRunning: true,
        currentRunId: currentRunId,
        copilotMessages: [...copilotMessages],
      })
    }

    setIsCopilotMode(copilotMode)
    updateTab(activeTabId, { isCopilotMode: copilotMode })

    if (copilotMode) {
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
      const userMessage = {
        id: `msg_${Date.now()}`,
        role: 'user' as const,
        content: task,
        timestamp: new Date(),
        status: 'complete' as const,
      }
      setCopilotMessages(prev => [...prev, userMessage])
      clearAgentMessages()
    }

    setIsRunning(true)
    clearConsole()
    setResults(null)
    setStartTime(Date.now())

    const taskId = `task_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

    // Mark this tab as live and active
    setLiveTab(activeTabId)
    updateTab(activeTabId, {
      isRunning: true,
      status: 'active',
      currentRunId: taskId,
      consoleOutput: [],
      results: null,
      dagData: null,
      workflowStatus: null,
      startedAt: new Date().toISOString(),
    })

    try {
      await connect(taskId, task, config)
    } catch (error) {
      console.error('Failed to start task:', error)
      addConsoleOutput(`Error: Failed to connect to backend`)
      setIsRunning(false)
      updateTab(activeTabId, { isRunning: false, status: 'failed' })
    }
  }

  const handleStopTask = () => {
    disconnect()
    setIsRunning(false)
    addConsoleOutput('Task execution stopped by user')
    updateTab(activeTabId, { isRunning: false, status: 'completed' })
  }

  const handlePause = () => {
    if (connected && currentRunId) {
      sendMessage({ type: 'pause', run_id: currentRunId })
      setWorkflowStatus('paused')
      addConsoleOutput('Pause request sent to workflow')
      updateTab(activeTabId, { status: 'paused' })
    }
  }

  const handleResume = () => {
    if (connected && currentRunId) {
      sendMessage({ type: 'resume', run_id: currentRunId })
      setWorkflowStatus('executing')
      addConsoleOutput('Resume request sent to workflow')
      updateTab(activeTabId, { status: 'active' })
    }
  }

  const handleCancel = () => {
    handleStopTask()
  }

  const handleApprovalResolve = (resolution: string, feedback?: string, modifications?: string) => {
    if (!pendingApproval) return
    sendMessage({
      type: 'resolve_approval',
      approval_id: pendingApproval.approval_id,
      resolution: resolution,
      feedback: feedback || '',
      modifications: modifications || '',
    })
    addConsoleOutput(`Approval response sent: ${resolution}${feedback ? ` - "${feedback}"` : ''}`)
    clearApproval()
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

  const handleCopilotSendMessage = async (message: string) => {
    if ((isActiveTabLive && isRunning) || !message.trim()) return

    const userMessage = {
      id: `msg_${Date.now()}`,
      role: 'user' as const,
      content: message,
      timestamp: new Date(),
      status: 'complete' as const,
    }
    setCopilotMessages(prev => [...prev, userMessage])
    clearAgentMessages()

    const config = {
      mode: 'copilot',
      ...copilotConfig,
      continuousMode: false,
      conversational: false,
      approvalMode: 'none',
      maxRounds: 10,
      copilotSessionId: copilotSessionId,
    }

    setIsRunning(true)
    clearConsole()
    setResults(null)
    setStartTime(Date.now())

    const taskId = `task_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

    // Mark this tab as live
    setLiveTab(activeTabId)
    updateTab(activeTabId, {
      isRunning: true,
      status: 'active',
      currentRunId: taskId,
    })

    try {
      await connect(taskId, message, config)
    } catch (error) {
      console.error('Failed to start task:', error)
      addConsoleOutput(`Error: Failed to connect to backend`)
      setIsRunning(false)
      updateTab(activeTabId, { isRunning: false, status: 'failed' })
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

  const handleClearCopilotSession = () => {
    setCopilotSessionId(null)
    setCopilotMessages([])
    clearAgentMessages()
    clearConsole()
    setResults(null)
  }

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
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Unknown error'
      addConsoleOutput(`Failed to load session logs: ${msg}`)
    }
  }

  const handleResumeSessionFromList = async (sessionId: string, mode?: string) => {
    if (isActiveTabLive && isRunning) return

    try {
      const response = await fetch(getApiUrl(`/api/sessions/${sessionId}`))
      if (!response.ok) throw new Error('Failed to load session')
      const sessionData = await response.json()
      const sessionMode = mode || sessionData.mode || 'one-shot'

      addConsoleOutput(`Resuming session ${sessionId} (mode: ${sessionMode})`)
      await fetch(getApiUrl(`/api/sessions/${sessionId}/resume`), { method: 'POST' })

      if (sessionMode === 'copilot') {
        setIsCopilotMode(true)
        setCopilotSessionId(sessionId)
        updateTab(activeTabId, { isCopilotMode: true, mode: 'copilot' })
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
        return
      }

      const resumableModes = ['planning-control', 'hitl-interactive', 'idea-generation']
      if (resumableModes.includes(sessionMode)) {
        const resumeConfig = {
          ...(sessionData.config || {}),
          mode: sessionMode,
          session_id: sessionId,
          copilotSessionId: sessionId,
        }
        const lastUserMsg = sessionData.conversation_history
          ?.filter((m: any) => m.role === 'user')
          ?.pop()
        const taskDescription = lastUserMsg?.content || sessionData.config?.task || 'Continue previous session'

        setIsRunning(true)
        clearConsole()
        setResults(null)
        setStartTime(Date.now())

        setLiveTab(activeTabId)
        updateTab(activeTabId, { isRunning: true, status: 'active', mode: sessionMode })

        const taskId = `task_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
        await connect(taskId, taskDescription, resumeConfig)
        return
      }

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
      addConsoleOutput('Cannot play from node: No active workflow run')
      return
    }
    addConsoleOutput(`Initiating play from node: ${nodeId}...`)
    try {
      const response = await fetch(getApiUrl(`/api/runs/${currentRunId}/play-from-node`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ node_id: nodeId, context_override: null }),
      })
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to initiate play from node')
      }
      const result = await response.json()
      addConsoleOutput(`Workflow prepared to resume from node ${nodeId}`)
      addConsoleOutput(`Status: ${result.result?.status || 'ready'}`)
      if (dagData) {
        const nodeIndex = dagData.nodes.findIndex(n => n.id === nodeId)
        if (nodeIndex >= 0) {
          dagData.nodes.forEach((node, idx) => {
            if (idx >= nodeIndex && node.status !== 'completed') {
              node.status = 'pending'
            }
          })
        }
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error'
      addConsoleOutput(`Failed to play from node: ${errorMessage}`)
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
      addConsoleOutput(`Cannot create branch: No active workflow run`)
      return
    }
    try {
      addConsoleOutput(`Creating branch "${name}" from node ${nodeId}...`)
      const response = await fetch(`http://localhost:8000/api/runs/${currentRunId}/branch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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
      addConsoleOutput(`Branch "${name}" created successfully (ID: ${result.branch_run_id})`)
      if (result.status === 'ready_to_execute' && executeImmediately) {
        addConsoleOutput(`Branch execution prepared. Connect via WebSocket to start.`)
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error'
      addConsoleOutput(`Failed to create branch: ${errorMessage}`)
    }
  }

  const handleSelectBranch = (branchId: string) => {
    setCurrentBranchId(branchId)
    addConsoleOutput(`Switched to branch: ${branchId}`)
  }

  const handleViewBranch = (branchId: string) => {
    addConsoleOutput(`Viewing branch: ${branchId}`)
  }

  const handleCompareBranches = (branchIdA: string, branchIdB: string) => {
    addConsoleOutput(`Comparing branches: ${branchIdA} vs ${branchIdB}`)
  }

  const handleViewWorkflow = (workflow: WorkflowRow) => {
    addConsoleOutput(`Viewing workflow: ${workflow.id}`)
  }

  const handleResumeWorkflow = (workflow: WorkflowRow) => {
    addConsoleOutput(`Resuming workflow: ${workflow.id}`)
  }

  const handleBranchWorkflow = (workflow: WorkflowRow) => {
    addConsoleOutput(`Creating branch from workflow: ${workflow.id}`)
  }

  // Add completed workflow to history
  useEffect(() => {
    if (!displayIsRunning && displayResults && currentRunId) {
      const newWorkflow: WorkflowRow = {
        id: currentRunId,
        session_id: 'session_1',
        task_description: displayResults.task || 'Task completed',
        status: displayWorkflowStatus === 'failed' ? 'failed' : 'completed',
        agent: displayResults.agent || 'engineer',
        model: displayResults.model || 'gpt-4o',
        started_at: startTime ? new Date(startTime).toISOString() : undefined,
        completed_at: new Date().toISOString(),
        total_cost: displayResults.total_cost || 0,
        step_count: displayDag?.nodes.length || 1,
      }
      setWorkflowHistory(prev => {
        if (prev.some(w => w.id === currentRunId)) return prev
        return [newWorkflow, ...prev]
      })
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
  }, [displayIsRunning, displayResults, currentRunId, displayWorkflowStatus, startTime, displayDag, branches.length])

  const handleOpenDirectory = useCallback((path: string) => {
    const mockResults = {
      execution_time: 0,
      base_work_dir: path,
      work_dir: path
    }
    setResults(mockResults)
  }, [setResults])

  // Handle mode launch from gallery
  const handleLaunchMode = (modeId: string) => {
    setSelectedMode(modeId)
    updateTab(activeTabId, {
      mode: modeId,
      name: getModeDisplayName(modeId),
    })
    if (modeId === 'copilot') {
      setIsCopilotMode(true)
      updateTab(activeTabId, { isCopilotMode: true })
      setCopilotConfig(prev => ({
        ...prev,
        enablePlanning: true,
        approvalMode: 'after_step',
        autoApproveSimple: true,
      }))
    }
  }

  // Handle going back to mode gallery
  const handleBackToGallery = () => {
    setSelectedMode(null)
    setIsCopilotMode(false)
    updateTab(activeTabId, { mode: null, isCopilotMode: false })
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Main Content */}
      <div ref={containerRef} className="flex-1 flex flex-col min-h-0 overflow-hidden">
        {isCopilotMode ? (
          /* Copilot Mode */
          <div className="flex-1 min-h-0 overflow-hidden">
            <div className="container mx-auto px-4 py-2 min-h-0 overflow-hidden h-full">
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 h-full">
                <div className="lg:col-span-2 h-full overflow-hidden rounded-lg border border-gray-700">
                  <CopilotView
                    consoleOutput={displayConsole}
                    isRunning={displayIsRunning}
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
                <div className="h-full flex flex-col overflow-hidden">
                  <div className="flex border-b border-gray-700 mb-2 flex-shrink-0">
                    <button
                      className="px-4 py-2 text-sm font-medium text-purple-400 border-b-2 border-purple-400 flex items-center gap-2"
                    >
                      Workflow
                      {displayDag && displayDag.nodes.length > 0 && (
                        <span className="px-1.5 py-0.5 text-xs bg-purple-500/20 text-purple-400 rounded-full">
                          {displayDag.nodes.length}
                        </span>
                      )}
                    </button>
                    <button
                      onClick={handleBackToGallery}
                      className="ml-auto px-3 py-1 text-xs text-gray-400 hover:text-white transition-colors"
                    >
                      Exit Copilot
                    </button>
                  </div>
                  <div className="flex-1 min-h-0 overflow-auto">
                    <WorkflowDashboard
                      status={displayWorkflowStatus || (displayIsRunning ? 'executing' : 'draft')}
                      dagData={displayDag}
                      elapsedTime={elapsedTime}
                      branches={branches}
                      currentBranchId={currentBranchId}
                      workflowHistory={workflowHistory}
                      costSummary={displayCostSummary}
                      costTimeSeries={displayCostTimeSeries}
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
                </div>
              </div>
            </div>
          </div>
        ) : selectedMode === null ? (
          /* Mode Gallery */
          <div className="flex-1 min-h-0 overflow-auto">
            <ModeGallery onLaunchMode={handleLaunchMode} />
          </div>
        ) : (
          /* Run View - Selected Mode with TaskInput (full width) */
          <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
            {/* Mode header with back button */}
            <div
              className="px-4 py-2 border-b flex items-center gap-3 flex-shrink-0"
              style={{ borderColor: 'var(--mars-color-border)' }}
            >
              <button
                onClick={handleBackToGallery}
                className="p-1 rounded-mars-sm transition-colors hover:bg-[var(--mars-color-bg-hover)]"
                style={{ color: 'var(--mars-color-text-secondary)' }}
                title="Back to Modes"
              >
                <ArrowLeft className="w-4 h-4" />
              </button>
              <span
                className="text-sm font-medium"
                style={{ color: 'var(--mars-color-text)' }}
              >
                {getModeDisplayName(selectedMode)}
              </span>
              {displayIsRunning && (
                <span className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--mars-color-success)' }}>
                  <span className="w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: 'var(--mars-color-success)' }} />
                  Running {elapsedTime}
                </span>
              )}
            </div>

            {/* TaskInput - centered single column */}
            <div className="flex-1 min-h-0 overflow-auto px-4 py-4">
              <div className="max-w-3xl mx-auto">
                <TaskInput
                  onSubmit={handleTaskSubmit}
                  onStop={handleStopTask}
                  isRunning={displayIsRunning}
                  isConnecting={isConnecting}
                  onOpenDirectory={handleOpenDirectory}
                  defaultMode={selectedMode}
                />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Bottom Panel - Console + Workflow (always visible, collapsible) */}
      <BottomPanel
        consoleOutput={displayConsole}
        isRunning={displayIsRunning}
        onClearConsole={clearConsole}
        pendingApproval={isActiveTabLive ? pendingApproval : null}
        onApprovalResolve={handleApprovalResolve}
        workflowStatus={displayWorkflowStatus}
        dagData={displayDag}
        elapsedTime={elapsedTime}
        costSummary={displayCostSummary}
        costTimeSeries={displayCostTimeSeries}
        filesUpdatedCounter={filesUpdatedCounter}
        branches={branches}
        currentBranchId={currentBranchId}
        workflowHistory={workflowHistory}
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
  )
}
