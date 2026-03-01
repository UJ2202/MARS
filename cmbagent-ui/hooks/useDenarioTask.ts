'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import { getApiUrl, getWsUrl } from '@/lib/config'
import type {
  DenarioTaskState,
  DenarioStageContent,
  DenarioCreateResponse,
  DenarioRefineResponse,
  RefinementMessage,
  UploadedFile,
  DenarioWizardStep,
} from '@/types/denario'

interface UseDenarioTaskReturn {
  // State
  taskId: string | null
  taskState: DenarioTaskState | null
  currentStep: DenarioWizardStep
  isLoading: boolean
  error: string | null

  // Stage content
  editableContent: string
  refinementMessages: RefinementMessage[]
  consoleOutput: string[]
  isExecuting: boolean

  // Files
  uploadedFiles: UploadedFile[]

  // Actions
  createTask: (task: string, dataDescription?: string, config?: Record<string, unknown>) => Promise<void>
  executeStage: (stageNum: number) => Promise<void>
  fetchStageContent: (stageNum: number) => Promise<DenarioStageContent | null>
  saveStageContent: (stageNum: number, content: string, field: string) => Promise<void>
  refineContent: (stageNum: number, message: string, content: string) => Promise<string | null>
  uploadFile: (file: File) => Promise<void>
  setCurrentStep: (step: DenarioWizardStep) => void
  setEditableContent: (content: string) => void
  resumeTask: (taskId: string) => Promise<void>
  clearError: () => void
}

export function useDenarioTask(): UseDenarioTaskReturn {
  const [taskId, setTaskId] = useState<string | null>(null)
  const [taskState, setTaskState] = useState<DenarioTaskState | null>(null)
  const [currentStep, setCurrentStep] = useState<DenarioWizardStep>(0)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [editableContent, setEditableContent] = useState('')
  const [refinementMessages, setRefinementMessages] = useState<RefinementMessage[]>([])
  const [consoleOutput, setConsoleOutput] = useState<string[]>([])
  const [isExecuting, setIsExecuting] = useState(false)
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([])

  const wsRef = useRef<WebSocket | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const consolePollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const consoleIndexRef = useRef(0)

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      wsRef.current?.close()
      if (pollRef.current) clearInterval(pollRef.current)
      if (consolePollRef.current) clearInterval(consolePollRef.current)
    }
  }, [])

  const clearError = useCallback(() => setError(null), [])

  // ---- API helpers ----

  const apiFetch = useCallback(async (path: string, options?: RequestInit) => {
    const resp = await fetch(getApiUrl(path), {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    })
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({ detail: resp.statusText }))
      throw new Error(body.detail || `HTTP ${resp.status}`)
    }
    return resp.json()
  }, [])

  // ---- Task lifecycle ----

  const loadTaskState = useCallback(async (id: string) => {
    const state: DenarioTaskState = await apiFetch(`/api/denario/${id}`)
    setTaskState(state)
    return state
  }, [apiFetch])

  const createTask = useCallback(async (
    task: string,
    dataDescription?: string,
    config?: Record<string, unknown>,
  ) => {
    setIsLoading(true)
    setError(null)
    try {
      const resp: DenarioCreateResponse = await apiFetch('/api/denario/create', {
        method: 'POST',
        body: JSON.stringify({ task, data_description: dataDescription, config }),
      })
      setTaskId(resp.task_id)

      // Upload any pending files
      for (const f of uploadedFiles) {
        if (f.status === 'pending') {
          // File is already staged in uploadedFiles, actual upload happens here
          // (file objects no longer accessible here - upload happens in uploadFile)
        }
      }

      // Load full task state
      await loadTaskState(resp.task_id)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to create task')
    } finally {
      setIsLoading(false)
    }
  }, [apiFetch, loadTaskState, uploadedFiles])

  // ---- Stage execution ----

  const startPolling = useCallback((id: string, stageNum: number) => {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const state = await loadTaskState(id)
        const stage = state.stages.find(s => s.stage_number === stageNum)
        if (stage && (stage.status === 'completed' || stage.status === 'failed')) {
          setIsExecuting(false)
          if (pollRef.current) clearInterval(pollRef.current)
          pollRef.current = null
          if (consolePollRef.current) clearInterval(consolePollRef.current)
          consolePollRef.current = null
          wsRef.current?.close()
        }
      } catch {
        // ignore polling errors
      }
    }, 5000)
  }, [loadTaskState])

  const startConsolePoll = useCallback((id: string, stageNum: number) => {
    if (consolePollRef.current) clearInterval(consolePollRef.current)
    consoleIndexRef.current = 0
    consolePollRef.current = setInterval(async () => {
      try {
        const resp = await fetch(
          getApiUrl(`/api/denario/${id}/stages/${stageNum}/console?since=${consoleIndexRef.current}`)
        )
        if (!resp.ok) return
        const data = await resp.json()
        if (data.lines && data.lines.length > 0) {
          setConsoleOutput(prev => [...prev, ...data.lines])
          consoleIndexRef.current = data.next_index
        }
      } catch {
        // ignore console poll errors
      }
    }, 2000)
  }, [])

  const connectWs = useCallback((id: string, stageNum: number) => {
    wsRef.current?.close()
    const url = getWsUrl(`/ws/denario/${id}/${stageNum}`)
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.event_type === 'stage_completed') {
          setIsExecuting(false)
          if (consolePollRef.current) clearInterval(consolePollRef.current)
          consolePollRef.current = null
          loadTaskState(id)
          ws.close()
        } else if (msg.event_type === 'stage_failed') {
          setIsExecuting(false)
          setError(msg.data?.error || 'Stage failed')
          if (consolePollRef.current) clearInterval(consolePollRef.current)
          consolePollRef.current = null
          loadTaskState(id)
          ws.close()
        }
        // Console output is handled by REST poll to avoid duplication
      } catch {
        // ignore parse errors
      }
    }

    ws.onerror = () => {}
    ws.onclose = () => {}
  }, [loadTaskState])

  const executeStage = useCallback(async (stageNum: number) => {
    if (!taskId) return
    setIsExecuting(true)
    setError(null)
    setConsoleOutput([])

    try {
      await apiFetch(`/api/denario/${taskId}/stages/${stageNum}/execute`, {
        method: 'POST',
        body: JSON.stringify({}),
      })

      // Connect WS + start polling (status + console)
      connectWs(taskId, stageNum)
      startPolling(taskId, stageNum)
      startConsolePoll(taskId, stageNum)
      setConsoleOutput([`Stage ${stageNum} execution started...`])
    } catch (e: unknown) {
      setIsExecuting(false)
      setError(e instanceof Error ? e.message : 'Failed to execute stage')
    }
  }, [taskId, apiFetch, connectWs, startPolling, startConsolePoll])

  // ---- Content ----

  const fetchStageContent = useCallback(async (stageNum: number): Promise<DenarioStageContent | null> => {
    if (!taskId) return null
    try {
      const content: DenarioStageContent = await apiFetch(`/api/denario/${taskId}/stages/${stageNum}/content`)
      if (content.content) {
        setEditableContent(content.content)
      }
      return content
    } catch {
      return null
    }
  }, [taskId, apiFetch])

  const saveStageContent = useCallback(async (stageNum: number, content: string, field: string) => {
    if (!taskId) return
    try {
      await apiFetch(`/api/denario/${taskId}/stages/${stageNum}/content`, {
        method: 'PUT',
        body: JSON.stringify({ content, field }),
      })
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to save')
    }
  }, [taskId, apiFetch])

  const refineContent = useCallback(async (
    stageNum: number,
    message: string,
    content: string,
  ): Promise<string | null> => {
    if (!taskId) return null

    // Add user message
    const userMsg: RefinementMessage = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: message,
      timestamp: Date.now(),
    }
    setRefinementMessages(prev => [...prev, userMsg])

    try {
      const resp: DenarioRefineResponse = await apiFetch(`/api/denario/${taskId}/stages/${stageNum}/refine`, {
        method: 'POST',
        body: JSON.stringify({ message, content }),
      })

      // Add assistant response
      const assistantMsg: RefinementMessage = {
        id: `a-${Date.now()}`,
        role: 'assistant',
        content: resp.refined_content,
        timestamp: Date.now(),
      }
      setRefinementMessages(prev => [...prev, assistantMsg])
      return resp.refined_content
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Refinement failed')
      return null
    }
  }, [taskId, apiFetch])

  // ---- File upload ----

  const uploadFile = useCallback(async (file: File) => {
    const entry: UploadedFile = {
      name: file.name,
      size: file.size,
      status: 'uploading',
    }
    setUploadedFiles(prev => [...prev, entry])

    // If no taskId yet, we can't upload - mark as pending
    if (!taskId) {
      setUploadedFiles(prev =>
        prev.map(f => f.name === file.name ? { ...f, status: 'pending' as const } : f)
      )
      return
    }

    const formData = new FormData()
    formData.append('file', file)
    formData.append('task_id', taskId)
    formData.append('subfolder', 'input_files')

    try {
      const resp = await fetch(getApiUrl('/api/files/upload'), {
        method: 'POST',
        body: formData,
      })
      if (!resp.ok) throw new Error('Upload failed')
      const data = await resp.json()
      setUploadedFiles(prev =>
        prev.map(f => f.name === file.name ? { ...f, status: 'done' as const, path: data.path } : f)
      )
    } catch (e: unknown) {
      setUploadedFiles(prev =>
        prev.map(f => f.name === file.name ? {
          ...f,
          status: 'error' as const,
          error: e instanceof Error ? e.message : 'Upload failed',
        } : f)
      )
    }
  }, [taskId])

  // ---- Resume ----

  const resumeTask = useCallback(async (id: string) => {
    setIsLoading(true)
    setError(null)
    try {
      setTaskId(id)
      const state = await loadTaskState(id)

      // Find the right step to resume at
      let resumeStep: DenarioWizardStep = 0
      for (const stage of state.stages) {
        if (stage.status === 'running') {
          // Stage is running - go to that step and reconnect
          resumeStep = stage.stage_number as DenarioWizardStep
          setIsExecuting(true)
          connectWs(id, stage.stage_number)
          startPolling(id, stage.stage_number)
          startConsolePoll(id, stage.stage_number)
          break
        }
        if (stage.status === 'completed') {
          // Completed - advance past it
          resumeStep = Math.min(stage.stage_number + 1, 4) as DenarioWizardStep
        } else {
          // Pending or failed - stop here
          resumeStep = stage.stage_number as DenarioWizardStep
          break
        }
      }

      setCurrentStep(resumeStep)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to resume task')
    } finally {
      setIsLoading(false)
    }
  }, [loadTaskState, connectWs, startPolling, startConsolePoll])

  return {
    taskId,
    taskState,
    currentStep,
    isLoading,
    error,
    editableContent,
    refinementMessages,
    consoleOutput,
    isExecuting,
    uploadedFiles,
    createTask,
    executeStage,
    fetchStageContent,
    saveStageContent,
    refineContent,
    uploadFile,
    setCurrentStep: setCurrentStep as (step: DenarioWizardStep) => void,
    setEditableContent,
    resumeTask,
    clearError,
  }
}
