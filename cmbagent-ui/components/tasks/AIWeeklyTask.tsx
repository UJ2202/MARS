'use client'

import { useState, useEffect } from 'react'
import { ArrowLeft, Calendar, Tags, Globe, Sparkles, Download, Loader2, Network } from 'lucide-react'
import { getApiUrl } from '@/lib/config'
import { useWebSocketContext } from '@/contexts/WebSocketContext'
import { DAGWorkspace } from '@/components/dag'
import ConsoleOutput from '@/components/ConsoleOutput'

interface AIWeeklyTaskProps {
  onBack: () => void
}

export default function AIWeeklyTask({ onBack }: AIWeeklyTaskProps) {
  const {
    connected,
    connect,
    disconnect,
    currentRunId,
    consoleOutput,
    addConsoleOutput,
    clearConsole,
    dagData,
    isRunning,
    setIsRunning,
    costSummary,
    costTimeSeries
  } = useWebSocketContext()

  const [taskId, setTaskId] = useState<string | null>(null)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [showView, setShowView] = useState<'config' | 'execution'>('config')

  // Form state
  const [dateFrom, setDateFrom] = useState(() => {
    const date = new Date()
    date.setDate(date.getDate() - 7)
    return date.toISOString().split('T')[0]
  })
  const [dateTo, setDateTo] = useState(() => new Date().toISOString().split('T')[0])
  const [topics, setTopics] = useState<string[]>(['llm', 'cv'])
  const [sources, setSources] = useState<string[]>(['arxiv', 'github', 'blogs'])
  const [style, setStyle] = useState<'concise' | 'detailed' | 'technical'>('concise')

  const availableTopics = [
    { id: 'llm', label: 'Large Language Models' },
    { id: 'cv', label: 'Computer Vision' },
    { id: 'rl', label: 'Reinforcement Learning' },
    { id: 'robotics', label: 'Robotics' },
    { id: 'ml-ops', label: 'MLOps' },
    { id: 'ethics', label: 'AI Ethics' }
  ]

  const availableSources = [
    { id: 'arxiv', label: 'ArXiv Papers' },
    { id: 'github', label: 'GitHub Releases' },
    { id: 'blogs', label: 'Tech Blogs' }
  ]

  const toggleTopic = (topicId: string) => {
    setTopics(prev =>
      prev.includes(topicId)
        ? prev.filter(t => t !== topicId)
        : [...prev, topicId]
    )
  }

  const toggleSource = (sourceId: string) => {
    setSources(prev =>
      prev.includes(sourceId)
        ? prev.filter(s => s !== sourceId)
        : [...prev, sourceId]
    )
  }

  const handleGenerate = async () => {
    if (topics.length === 0 || sources.length === 0) {
      setError('Please select at least one topic and one source')
      return
    }

    setError(null)
    setResult(null)
    clearConsole()
    setShowView('execution')

    try {
      // Step 1: Create task via REST API
      addConsoleOutput(`📝 Creating task...`)
      const response = await fetch(getApiUrl('/api/tasks/ai-weekly/execute'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tool: 'ai-weekly',
          parameters: {
            dateFrom,
            dateTo,
            topics,
            sources,
            style,
            includeImpact: true
          }
        })
      })

      if (!response.ok) {
        throw new Error('Failed to create task')
      }

      const data = await response.json()
      const newTaskId = data.task_id
      setTaskId(newTaskId)

      addConsoleOutput(`✅ Task created: ${newTaskId}`)
      addConsoleOutput(`📅 Date Range: ${dateFrom} to ${dateTo}`)
      addConsoleOutput(`🏷️  Topics: ${topics.join(', ')}`)
      addConsoleOutput(`📰 Sources: ${sources.join(', ')}`)
      addConsoleOutput(``)

      // Step 2: Fetch task configuration
      addConsoleOutput(`⚙️  Fetching task configuration...`)
      const configResponse = await fetch(getApiUrl(`/api/tasks/tasks/${newTaskId}/config`))
      if (!configResponse.ok) {
        throw new Error('Failed to fetch task configuration')
      }
      const configData = await configResponse.json()
      
      setIsRunning(true)
      addConsoleOutput(`🚀 Connecting to workflow engine...`)
      
      // Step 3: Connect via WebSocket and start execution
      await connect(newTaskId, configData.description, configData.config)
      
    } catch (err: any) {
      setError(err.message)
      addConsoleOutput(`❌ Error: ${err.message}`)
      setIsRunning(false)
    }
  }

  const handleStop = () => {
    disconnect()
    setIsRunning(false)
    addConsoleOutput('🛑 Task execution stopped by user')
  }

  // Monitor workflow completion
  useEffect(() => {
    if (connected && currentRunId && consoleOutput.length > 0) {
      const lastLog = consoleOutput[consoleOutput.length - 1]
      if (lastLog.includes('✅') || lastLog.includes('Workflow completed')) {
        // Check if we got results
        setTimeout(() => {
          pollForResults(taskId!)
        }, 2000)
      }
    }
  }, [consoleOutput, connected, currentRunId, taskId])

  const pollForResults = async (id: string) => {
    try {
      const response = await fetch(getApiUrl(`/api/tasks/status/${id}`))
      const data = await response.json()

      if (data.status === 'completed' && data.result) {
        setResult(data.result)
        setIsRunning(false)
        addConsoleOutput('✅ Report generated successfully!')
      } else if (data.status === 'failed') {
        setError(data.error || 'Generation failed')
        setIsRunning(false)
      }
    } catch (err: any) {
      console.error('Error polling results:', err)
    }
  }

  const downloadReport = () => {
    if (!result?.fullReport) return

    const blob = new Blob([result.fullReport], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `ai-weekly-${dateFrom}-to-${dateTo}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900">
      {/* Header */}
      <header className="bg-black/20 backdrop-blur-sm border-b border-white/10">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center space-x-4">
            <button
              onClick={onBack}
              className="p-2 text-gray-400 hover:text-white transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-2xl font-bold text-white">AI Weekly Report</h1>
              <p className="text-sm text-gray-300">Generate comprehensive AI technology reports</p>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="container mx-auto px-4 py-8">
        {showView === 'config' ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Left Panel - Configuration */}
            <div className="space-y-6">
            {/* Date Range */}
            <div className="bg-black/30 backdrop-blur-sm border border-white/10 rounded-lg p-6">
              <div className="flex items-center space-x-2 mb-4">
                <Calendar className="w-5 h-5 text-blue-400" />
                <h2 className="text-lg font-semibold text-white">Date Range</h2>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-2">From</label>
                  <input
                    type="date"
                    value={dateFrom}
                    onChange={(e) => setDateFrom(e.target.value)}
                    className="w-full px-4 py-2 bg-black/50 border border-white/10 rounded-lg text-white focus:border-blue-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-2">To</label>
                  <input
                    type="date"
                    value={dateTo}
                    onChange={(e) => setDateTo(e.target.value)}
                    className="w-full px-4 py-2 bg-black/50 border border-white/10 rounded-lg text-white focus:border-blue-500 focus:outline-none"
                  />
                </div>
              </div>
            </div>

            {/* Topics */}
            <div className="bg-black/30 backdrop-blur-sm border border-white/10 rounded-lg p-6">
              <div className="flex items-center space-x-2 mb-4">
                <Tags className="w-5 h-5 text-purple-400" />
                <h2 className="text-lg font-semibold text-white">Topics</h2>
              </div>
              <div className="grid grid-cols-2 gap-3">
                {availableTopics.map(topic => (
                  <button
                    key={topic.id}
                    onClick={() => toggleTopic(topic.id)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                      topics.includes(topic.id)
                        ? 'bg-purple-500 text-white'
                        : 'bg-black/50 text-gray-400 hover:text-white border border-white/10'
                    }`}
                  >
                    {topic.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Sources */}
            <div className="bg-black/30 backdrop-blur-sm border border-white/10 rounded-lg p-6">
              <div className="flex items-center space-x-2 mb-4">
                <Globe className="w-5 h-5 text-green-400" />
                <h2 className="text-lg font-semibold text-white">Sources</h2>
              </div>
              <div className="space-y-3">
                {availableSources.map(source => (
                  <label
                    key={source.id}
                    className="flex items-center space-x-3 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={sources.includes(source.id)}
                      onChange={() => toggleSource(source.id)}
                      className="w-4 h-4 rounded border-gray-600 text-green-500 focus:ring-green-500"
                    />
                    <span className="text-white">{source.label}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Style */}
            <div className="bg-black/30 backdrop-blur-sm border border-white/10 rounded-lg p-6">
              <div className="flex items-center space-x-2 mb-4">
                <Sparkles className="w-5 h-5 text-yellow-400" />
                <h2 className="text-lg font-semibold text-white">Report Style</h2>
              </div>
              <div className="flex space-x-3">
                {(['concise', 'detailed', 'technical'] as const).map(s => (
                  <button
                    key={s}
                    onClick={() => setStyle(s)}
                    className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium capitalize transition-all ${
                      style === s
                        ? 'bg-yellow-500 text-black'
                        : 'bg-black/50 text-gray-400 hover:text-white border border-white/10'
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            {/* Generate Button */}
            <button
              onClick={handleGenerate}
              disabled={isRunning}
              className="w-full px-6 py-4 bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 disabled:from-gray-500 disabled:to-gray-600 text-white font-semibold rounded-lg transition-all disabled:cursor-not-allowed flex items-center justify-center space-x-2"
            >
              {isRunning ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>Generating Report...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-5 h-5" />
                  <span>Generate Report</span>
                </>
              )}
            </button>
          </div>

          {/* Right Panel - Preview */}
          <div className="bg-black/30 backdrop-blur-sm border border-white/10 rounded-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-white">What You'll Get</h2>
            </div>

            <div className="space-y-4 text-gray-300">
              <div className="flex items-start space-x-3">
                <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center flex-shrink-0 mt-1">
                  <span className="text-blue-400 text-sm font-semibold">1</span>
                </div>
                <div>
                  <h3 className="text-white font-medium mb-1">ArXiv Papers</h3>
                  <p className="text-sm text-gray-400">Latest research papers from selected topics</p>
                </div>
              </div>

              <div className="flex items-start space-x-3">
                <div className="w-8 h-8 rounded-full bg-green-500/20 flex items-center justify-center flex-shrink-0 mt-1">
                  <span className="text-green-400 text-sm font-semibold">2</span>
                </div>
                <div>
                  <h3 className="text-white font-medium mb-1">GitHub Releases</h3>
                  <p className="text-sm text-gray-400">Major framework and library updates</p>
                </div>
              </div>

              <div className="flex items-start space-x-3">
                <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center flex-shrink-0 mt-1">
                  <span className="text-purple-400 text-sm font-semibold">3</span>
                </div>
                <div>
                  <h3 className="text-white font-medium mb-1">Tech Blog Posts</h3>
                  <p className="text-sm text-gray-400">Announcements from AI companies</p>
                </div>
              </div>

              <div className="flex items-start space-x-3">
                <div className="w-8 h-8 rounded-full bg-yellow-500/20 flex items-center justify-center flex-shrink-0 mt-1">
                  <span className="text-yellow-400 text-sm font-semibold">4</span>
                </div>
                <div>
                  <h3 className="text-white font-medium mb-1">Impact Analysis</h3>
                  <p className="text-sm text-gray-400">Categorized by significance and topic</p>
                </div>
              </div>

              <div className="border-t border-white/10 pt-4 mt-4">
                <p className="text-xs text-gray-500">
                  The report will be generated using the planning & control workflow with real-time progress updates and DAG visualization.
                </p>
              </div>
            </div>
          </div>
        </div>
        ) : (
          /* Execution View */
          <div className="space-y-6">
            {/* Header with Stop Button */}
            <div className="bg-black/30 backdrop-blur-sm border border-white/10 rounded-lg p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4">
                  <button
                    onClick={() => setShowView('config')}
                    className="p-2 text-gray-400 hover:text-white transition-colors"
                  >
                    <ArrowLeft className="w-5 h-5" />
                  </button>
                  <div>
                    <h2 className="text-lg font-semibold text-white">Generating Report</h2>
                    <p className="text-sm text-gray-400">
                      {dateFrom} to {dateTo} • {topics.join(', ')}
                    </p>
                  </div>
                </div>
                <div className="flex items-center space-x-3">
                  {connected && (
                    <div className="flex items-center space-x-2 px-3 py-1.5 bg-green-500/20 rounded-lg">
                      <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
                      <span className="text-sm text-green-400">Connected</span>
                    </div>
                  )}
                  {isRunning && (
                    <button
                      onClick={handleStop}
                      className="px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg transition-colors text-sm"
                    >
                      Stop
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* DAG Workspace and Console in Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* DAG Visualization */}
              <div className="bg-black/30 backdrop-blur-sm border border-white/10 rounded-lg overflow-hidden">
                <div className="border-b border-white/10 p-4">
                  <div className="flex items-center space-x-2">
                    <Network className="w-5 h-5 text-purple-400" />
                    <h3 className="text-white font-semibold">Workflow DAG</h3>
                  </div>
                </div>
                <div className="h-[600px]">
                  {dagData ? (
                    <DAGWorkspace
                      dagData={dagData}
                      runId={currentRunId || undefined}
                      costSummary={costSummary}
                      costTimeSeries={costTimeSeries}
                    />
                  ) : (
                    <div className="flex items-center justify-center h-full text-gray-500">
                      <div className="text-center">
                        <Network className="w-12 h-12 mx-auto mb-3 opacity-50" />
                        <p>Workflow DAG will appear here</p>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Console Output */}
              <div className="bg-black/30 backdrop-blur-sm border border-white/10 rounded-lg overflow-hidden">
                <div className="border-b border-white/10 p-4">
                  <h3 className="text-white font-semibold">Console Output</h3>
                </div>
                <div className="h-[600px]">
                  <ConsoleOutput output={consoleOutput} />
                </div>
              </div>
            </div>

            {/* Results Section */}
            {result && (
              <div className="space-y-6">
                {/* Summary */}
                <div>
                  <div className="text-sm text-gray-400 mb-2">
                    {result.dateRange} • {result.itemCount} items
                  </div>
                  {result.headlines && result.headlines.length > 0 && (
                    <div className="space-y-2">
                      <h3 className="text-md font-semibold text-white">Top Headlines:</h3>
                      {result.headlines.map((headline: string, i: number) => (
                        <div key={i} className="text-gray-300 text-sm">
                          {i + 1}. {headline}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Sections */}
                {result.sections && result.sections.length > 0 && (
                  <div className="space-y-4">
                    {result.sections.map((section: any, i: number) => (
                      <div key={i} className="bg-white/5 rounded-lg p-4">
                        <h3 className="text-white font-semibold mb-2">{section.title}</h3>
                        <ul className="space-y-1">
                          {section.items.slice(0, 3).map((item: string, j: number) => (
                            <li key={j} className="text-gray-400 text-sm">• {item}</li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                )}

                {/* Full Report Preview */}
                {result.fullReport && (
                  <div className="border-t border-white/10 pt-4">
                    <h3 className="text-white font-semibold mb-2">Full Report Preview:</h3>
                    <pre className="text-xs text-gray-400 whitespace-pre-wrap font-mono bg-black/50 p-4 rounded-lg max-h-96 overflow-y-auto">
                      {result.fullReport.substring(0, 2000)}
                      {result.fullReport.length > 2000 && '\n\n... (truncated)'}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
