'use client'

import { useState } from 'react'
import { Newspaper, GitBranch, Code2, ArrowLeft } from 'lucide-react'
import Link from 'next/link'
import AIWeeklyTask from '@/components/tasks/AIWeeklyTask'
import ReleaseNotesTask from '@/components/tasks/ReleaseNotesTask'
import CodeReviewTask from '@/components/tasks/CodeReviewTask'

type ToolType = 'ai-weekly' | 'release-notes' | 'code-review' | null

export default function ToolsPage() {
  const [activeTool, setActiveTool] = useState<ToolType>(null)

  const tools = [
    {
      id: 'ai-weekly' as const,
      name: 'AI Weekly Report',
      description: 'Generate comprehensive weekly AI technology reports',
      icon: Newspaper,
      color: 'from-blue-500 to-purple-500'
    },
    {
      id: 'release-notes' as const,
      name: 'Release Notes',
      description: 'Automatically generate release notes from Git history',
      icon: GitBranch,
      color: 'from-green-500 to-teal-500'
    },
    {
      id: 'code-review' as const,
      name: 'Code Review',
      description: 'AI-powered code review assistant',
      icon: Code2,
      color: 'from-orange-500 to-red-500'
    }
  ]

  if (activeTool === 'ai-weekly') {
    return <AIWeeklyTask onBack={() => setActiveTool(null)} />
  }

  if (activeTool === 'release-notes') {
    return <ReleaseNotesTask onBack={() => setActiveTool(null)} />
  }

  if (activeTool === 'code-review') {
    return <CodeReviewTask onBack={() => setActiveTool(null)} />
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900">
      {/* Header */}
      <header className="bg-black/20 backdrop-blur-sm border-b border-white/10">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Jersey 10, cursive' }}>
                IT TASKS
              </h1>
              <p className="text-sm text-gray-300">AI-Powered Development Automation</p>
            </div>
            <Link
              href="/"
              className="flex items-center space-x-2 px-4 py-2 bg-white/10 hover:bg-white/20 rounded-lg transition-colors text-white"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Back to Research</span>
            </Link>
          </div>
        </div>
      </header>

      {/* Tool Cards */}
      <div className="container mx-auto px-4 py-12">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-4xl font-bold text-white mb-4">Choose Your Task</h2>
            <p className="text-gray-300 text-lg">
              Select an automation task to streamline your development workflow
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {tools.map((tool) => {
              const Icon = tool.icon
              return (
                <button
                  key={tool.id}
                  onClick={() => setActiveTool(tool.id)}
                  className="group relative overflow-hidden rounded-xl bg-black/30 backdrop-blur-sm border border-white/10 p-8 hover:border-white/30 transition-all duration-300 hover:scale-105"
                >
                  {/* Gradient Background */}
                  <div className={`absolute inset-0 bg-gradient-to-br ${tool.color} opacity-0 group-hover:opacity-10 transition-opacity duration-300`} />

                  {/* Content */}
                  <div className="relative z-10">
                    <div className={`w-16 h-16 rounded-full bg-gradient-to-br ${tool.color} flex items-center justify-center mb-4 mx-auto group-hover:scale-110 transition-transform`}>
                      <Icon className="w-8 h-8 text-white" />
                    </div>

                    <h3 className="text-xl font-semibold text-white mb-2">{tool.name}</h3>
                    <p className="text-gray-400 text-sm">{tool.description}</p>

                    <div className="mt-6 flex items-center justify-center text-sm text-blue-400 group-hover:text-blue-300">
                      <span>Launch Task</span>
                      <svg className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </div>
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
