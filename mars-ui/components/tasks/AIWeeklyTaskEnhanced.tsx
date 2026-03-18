'use client'

import { useState, useEffect, useRef, useMemo } from 'react'
import { ArrowLeft, Calendar, Tags, Globe, Sparkles, Download, Loader2, Code, MessageSquare, FileText, Settings, CheckCircle2, AlertCircle } from 'lucide-react'
import { config, getApiUrl } from '@/lib/config'
import { useWebSocketContext } from '@/contexts/WebSocketContext'
import TaskWorkspaceView from './TaskWorkspaceView'
import ConsoleOutput from '@/components/ConsoleOutput'

interface AIWeeklyTaskEnhancedProps {
  onBack: () => void
}

export default function AIWeeklyTaskEnhanced({ onBack }: AIWeeklyTaskEnhancedProps) {
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
    costTimeSeries,
    results,
    setResults,
    pendingApproval,
    sendMessage
  } = useWebSocketContext()

  const [taskId, setTaskId] = useState<string | null>(null)
  const [result, setResult] = useState<any>(null)
  const [isReportDownloadReady, setIsReportDownloadReady] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showView, setShowView] = useState<'config' | 'execution'>('config')
  const [activeRightTab, setActiveRightTab] = useState<'console' | 'plan' | 'results'>('console')

  // HITL state
  const [contextEnrichment, setContextEnrichment] = useState<{
    step: 'initial' | 'questions' | 'confirmation' | 'complete'
    questions: Array<{ id: string; question: string; answer: string }>
    enrichedPrompt: string
  }>({
    step: 'initial',
    questions: [],
    enrichedPrompt: ''
  })

  const [approvalResponse, setApprovalResponse] = useState<{
    feedback: string
    modifications: string
  }>({ feedback: '', modifications: '' })

  // Post-execution state
  const fetchStartedRef = useRef(false)
  const runStartTimestampRef = useRef<number | null>(null)
  const postDismissedRef = useRef(false)
  const [showPostExecution, setShowPostExecution] = useState(false)
  const [postExecutionFeedback, setPostExecutionFeedback] = useState('')
  const [isRestarting, setIsRestarting] = useState(false)

  // Form state
  const [dateFrom, setDateFrom] = useState(() => {
    const date = new Date()
    date.setDate(date.getDate() - 7)
    return date.toISOString().split('T')[0]
  })
  const [dateTo, setDateTo] = useState(() => new Date().toISOString().split('T')[0])
  const [topics, setTopics] = useState<string[]>(['llm', 'cv'])
  const [sources, setSources] = useState<string[]>(['github', 'press-releases', 'company-announcements', 'major-releases', 'curated-ai-websites'])
  const [style, setStyle] = useState<'concise' | 'detailed' | 'technical'>('concise')

  // Advanced options
  const [reportAudience, setReportAudience] = useState<string>('technical-and-non-technical')
  const [reportTone, setReportTone] = useState<string>('professional')
  const [specificFocus, setSpecificFocus] = useState<string>('')
  const [excludeTopics, setExcludeTopics] = useState<string>('')

  const availableTopics = [
    { id: 'llm', label: 'Large Language Models' },
    { id: 'cv', label: 'Computer Vision' },
    { id: 'rl', label: 'Reinforcement Learning' },
    { id: 'robotics', label: 'Robotics' },
    { id: 'ml-ops', label: 'MLOps' },
    { id: 'ethics', label: 'AI Ethics' }
  ]

  const availableSources = [
    { id: 'github', label: 'GitHub Releases' },
    { id: 'press-releases', label: 'Press Releases' },
    { id: 'company-announcements', label: 'Company Announcements' },
    { id: 'major-releases', label: 'Major Product/Model Releases' },
    { id: 'curated-ai-websites', label: 'Curated AI Websites/Blogs' }
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

  const gatedDagData = useMemo(() => {
    if (!dagData?.nodes?.length) return dagData
    if (isReportDownloadReady) return dagData

    const nodes = [...dagData.nodes]
    const lastIndex = nodes.length - 1
    const lastNode = nodes[lastIndex]

    if (lastNode?.status === 'completed') {
      nodes[lastIndex] = {
        ...lastNode,
        status: isRunning ? 'executing' : 'pending'
      }
    }

    return { ...dagData, nodes }
  }, [dagData, isReportDownloadReady, isRunning])

  // Context enrichment questions
  const generateEnrichmentQuestions = () => {
    const questions = [
      {
        id: 'report_characteristics',
        question: `What are the key characteristics you want in this ${style} AI Weekly report? (e.g., focus areas, depth level, audience preferences)`,
        answer: ''
      },
      {
        id: 'focus_area',
        question: `For the topics ${topics.join(', ')}, what specific aspects or breakthroughs should we prioritize in the report?`,
        answer: ''
      },
      {
        id: 'depth_and_detail',
        question: 'How much technical depth do you want? Should we include implementation details, code examples, or focus on high-level summaries?',
        answer: ''
      },
      {
        id: 'business_context',
        question: 'Should we emphasize business applications, commercial implications, and industry impact alongside technical content?',
        answer: ''
      }
    ]

    setContextEnrichment({
      step: 'questions',
      questions,
      enrichedPrompt: ''
    })
  }

  const submitEnrichmentAnswers = () => {
    // Build enriched prompt from answers
    const enrichment = contextEnrichment.questions
      .map(q => `${q.question}\nAnswer: ${q.answer}`)
      .join('\n\n')

    const enrichedPrompt = `
CONTEXT ENRICHMENT FROM USER:
${enrichment}

SPECIFIC FOCUS: ${specificFocus || 'General coverage'}
EXCLUDE TOPICS: ${excludeTopics || 'None'}
REPORT AUDIENCE: ${reportAudience}
REPORT TONE: ${reportTone}
`

    setContextEnrichment({
      ...contextEnrichment,
      step: 'confirmation',
      enrichedPrompt
    })
  }

  const proceedWithEnrichedContext = async () => {
    setContextEnrichment({
      ...contextEnrichment,
      step: 'complete'
    })

    await startWorkflowWithEnrichment()
  }

  const startWorkflowWithEnrichment = async () => {
    if (topics.length === 0 || sources.length === 0) {
      setError('Please select at least one topic and one source')
      return
    }

    if (!dateFrom || !dateTo || dateFrom > dateTo) {
      setError('Please select a valid date range (From must be on or before To)')
      return
    }

    setError(null)
    setResult(null)
    setResults(null)
    setIsReportDownloadReady(false)
    clearConsole()
    setShowView('execution')
    setActiveRightTab('console')

    try {
      const taskId = `ai-weekly_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
      setTaskId(taskId)

      const timeStamp = new Date().toTimeString().slice(0, 8).replace(/:/g, '_')
      const reportFilename = `ai_weekly_report_${dateFrom}_to_${dateTo}_${timeStamp}.md`

      addConsoleOutput(`✅ Task created: ${taskId}`)
      addConsoleOutput(`📅 Date Range: ${dateFrom} to ${dateTo}`)
      addConsoleOutput(`🏷️  Topics: ${topics.join(', ')}`)
      addConsoleOutput(`📰 Sources: ${sources.join(', ')}`)
      addConsoleOutput(`🎯 Enhanced with user context`)
      addConsoleOutput(``)

      runStartTimestampRef.current = Date.now() / 1000
      setIsRunning(true)
      addConsoleOutput(`🚀 Connecting to workflow engine with HITL enabled...`)

      // Create enhanced task description with context enrichment
      const basePrompt = `Generate a Professional AI Weekly Report for organization-wide distribution covering ${dateFrom} to ${dateTo}.

AUDIENCE: ${reportAudience}
TONE: ${reportTone}
QUALITY: Publication-ready content suitable for executive briefings

Topics to cover: ${topics.join(', ')}
Sources to use: ${sources.join(', ')}
Report style: ${style}

${contextEnrichment.enrichedPrompt}

Task Requirements:
1. CRITICAL: Use web search tools to find REAL, RECENT, HIGH-QUALITY content
2. CRITICAL DATE FILTER: ONLY include items with publication/announcement/release dates in this inclusive window: ${dateFrom} to ${dateTo}
3. Date filtering is INCLUSIVE (include both boundary dates ${dateFrom} and ${dateTo})
4. Reject any item outside the date range, even if highly relevant
5. Every item must show an explicit date in YYYY-MM-DD format
6. Add this exact line near the top of the report: "Coverage Window (Inclusive): ${dateFrom} to ${dateTo}"
7. NO ITEM CAP: include ALL verified in-range items discovered across selected sources; do not stop after 10 or any fixed number
8. If 'press-releases' is selected, prioritize official newsroom/press pages and include as many in-range items as available
9. If 'company-announcements' is selected, prioritize official company announcement/blog channels and include as many in-range items as available
10. If 'major-releases' is selected, prioritize official release notes/changelogs/product launch pages and include as many in-range items as available
11. Keep source diversity: do not let the report be dominated by a single source type
12. ALL links must be ACTUAL working URLs - NO placeholder links
13. Prefer primary sources first (official company pages, release notes, newsroom posts), then supporting analysis
14. Do NOT use archive-style sources (no arxiv.org papers, no archive.org links, no historical retrospective datasets)
15. Focus ONLY on latest releases and official company release channels in the selected date window
16. Date coverage rule: include items across multiple dates in the range, not a single day only
17. Boundary coverage rule: include at least one item from ${dateFrom} and one from ${dateTo} when available; if unavailable, state this explicitly and include nearest in-range dates
18. Search GitHub for trending repos and major releases in AI
19. Search official press releases and company announcements for AI launches and updates
20. Search for major model/tool/platform releases announced in the date range
21. MANDATORY FIXED TOOL EXECUTION SEQUENCE — execute ALL of these steps in EXACTLY this order, EVERY run, with NO exceptions:
  STEP A: Call announcements_noauth(query="", company="", from_date="${dateFrom}", to_date="${dateTo}", limit=300) — broad sweep of ALL RSS feeds. Record every returned item.
  STEP B: Call rss_company_announcements(company="", from_date="${dateFrom}", to_date="${dateTo}", limit=200) — ensures no feed is missed. Merge with Step A results.
  STEP C: For EACH of these companies individually, call rss_company_announcements(company=X, from_date="${dateFrom}", to_date="${dateTo}"): openai, google, microsoft, meta, facebook, anthropic, nvidia, amazon, aws, oracle, cisco, uber, ibm, intel, amd, qualcomm, samsung, salesforce, sap, siemens, sony, huggingface, deeplearning_ai, lastweekinai, theneuron, therundownai, exponentialview. Merge ALL results.
  STEP D: Call curated_ai_sources_catalog() — get the full source list.
  STEP E: Call curated_ai_sources_search(query="AI news ${dateFrom} to ${dateTo}", limit=60) — sweep curated news aggregators.
  STEP F: Call newsapi_search(query="artificial intelligence OR machine learning", from_date="${dateFrom}", to_date="${dateTo}", page_size=100) if NEWSAPI_KEY is available.
  STEP G: Call gnews_search(query="artificial intelligence OR machine learning", from_date="${dateFrom}", to_date="${dateTo}", max_results=100) if GNEWS_API_KEY is available.
  STEP H: Call prwire_search(query="AI", from_date="${dateFrom}", to_date="${dateTo}", limit=100).
  STEP I: Call multi_engine_web_search for any company from the core list that returned ZERO results in steps A-H.
  After ALL steps A-I complete, merge ALL collected items into one master list, de-duplicate by URL+title, and use this master list as the ONLY source for the report.
22. If any tool call fails or returns an error, log the error and CONTINUE with the next step — never abort the sequence
23. EVERY item returned by tools A-I that passes date filtering MUST appear in the final report — do not cherry-pick or drop items
24. Write in professional ${style} style with clear, concise explanations
25. Include context and business implications for each item
25.1 For EVERY item, open the primary reference URL and extract concrete facts (announcement details, specs, metrics, stakeholders, timelines) before writing the description
25.2 Do not write generic summaries; each item description must be grounded in source details from the reference link
26. The broad sweep in Step A+B is non-negotiable — even if focused queries in Step C return data, the broad sweep ensures nothing is missed
27. The per-company passes in Step C are non-negotiable — even if the broad sweep returned data for that company, the focused pass may catch additional items
28. Never output a blank template or "no data" report if in-range items were found by tools; include verified items and provide deeper context instead of shortfall notes
29. Minimum detail requirement: each major section and each non-empty topic subsection must contain at least 50 words of meaningful analysis
30. Never include lines such as "Shortfall note", "Fewer than X", or "Limited significant developments found" in the final report
31. If a section has limited new items, add comparative analysis, implications, and forward-looking commentary based on verified in-range items
32. STRICT NO-DUPLICATE RULE:
  - Each unique release/announcement must appear EXACTLY ONCE in the entire report
  - Different versions ARE distinct items (e.g. GPT-5.3 and GPT-5.4 are two separate releases — each one can appear once)
  - But the SAME version must NEVER repeat (e.g. GPT-5.3 must not appear 2, 3, or 4 times — only once)
  - De-duplicate by: exact release name + organization + URL; if the same release name or URL appears more than once, keep only the first/best entry and delete all others
  - Before writing the final report, run a MANDATORY FINAL DEDUP PASS: scan the entire report, count occurrences of each release name; if any name appears more than once, remove all but the first occurrence
  - If the same announcement appears under different headlines, keep only the primary one
  - This applies to ALL releases from ALL companies: each unique release name gets exactly one entry in the entire report
33. Accuracy and genuineness rules:
  - Prefer correctness over volume; never pad with weak or uncertain items
  - Do not fabricate claims, dates, organizations, metrics, or URLs
  - Use only verifiable, genuine items from authoritative sources; if verification is weak, skip the item
  - If a high-priority organization has no verified in-range updates, briefly state unavailable rather than inventing coverage
34. Style-specific word count rules:
  - concise: each item description must contain at least 100 words
  - detailed: each item description must contain at least 150 words — this is a HARD minimum; if a paragraph is shorter, expand it with deeper analysis, implications, competitive context, and technical detail until it reaches 150 words
35. Topic and title uniqueness rules:
  - Topic/section headings must be globally unique throughout the full report
  - Every item title/release name must be globally unique throughout the full report
  - Any section may contain N items, but each title must be unique
  - A single news item can appear in only one section (no cross-section repetition)
36. Organization and topic diversity rules (strong preference, not a hard block):
  - Do not concentrate mostly on OpenAI/Google/Microsoft
  - Include coverage from Meta/Facebook, Oracle, Cisco, AWS/Amazon, Uber, IBM, Intel, AMD, Qualcomm when verified in-range updates are available
  - Include additional global organizations when available: Salesforce, SAP, Siemens, Tencent, Baidu, Alibaba, Samsung, Sony, Toyota, Bosch, Infosys, TCS, Wipro, Reliance Jio, and other global innovators
  - Broaden scope beyond pure AI/ML: also search for quantum computing, edge AI, neuromorphic computing, AI hardware, AI regulation/policy, and AI-driven scientific breakthroughs
  - Aim for broad organization and topic diversity, but do not force non-verified items
37. MANDATORY: Always run curated_ai_sources_catalog and curated_ai_sources_search to discover items from curated AI news sources — this is NOT optional and must happen in EVERY report generation regardless of which source checkboxes are selected
38. Agent must go deep and collect from multiple companies: OpenAI, Google, Microsoft, Meta/Facebook, Oracle, Cisco, IBM, Intel, AMD, Qualcomm, AWS/Amazon, Uber, Anthropic, Nvidia, Hugging Face, Samsung, Sony, Toyota, Bosch, Infosys, TCS, and major startups/investors. Also search for quantum computing (IBM Quantum, Google Quantum AI, IonQ, Rigetti, D-Wave), AI hardware, edge AI, and AI regulation/policy developments when in-range updates are available
39. MANDATORY curated sources — search ALL of these in EVERY run (not optional):
  - Axios AI: https://www.axios.com/technology/axios-ai (Breaking news and executive-level insights)
  - The Batch by Deeplearning.ai: https://www.deeplearning.ai/the-batch (Weekly deep-dive analysis from Andrew Ng)
  - Last Week in AI: https://lastweekin.ai (Weekly AI news roundup)
  - State of AI Report: https://www.stateof.ai (Annual comprehensive AI analysis)
  - Google AI Blog: http://blog.google/technology/ai (Major AI developments from Google)
  - Anthropic News: https://www.anthropic.com/news (Claude developments and AI safety)
  - Hugging Face Blog: https://huggingface.co/blog (Open-source AI and model releases)
  - What did OpenAI do this week?: https://www.whatdidopenaido.com (OpenAI-focused weekly updates)
  - Stanford AI Index: https://aiindex.stanford.edu/report (Annual AI progress and trends)
  - Gary Marcus on AI: https://garymarcus.substack.com (Critical AI analysis and research)
  - Goldman Sachs AI Insights: https://www.goldmansachs.com/insights/topics/ai-generated-insights (Business impact analysis)
  - Sequoia Capital: https://www.sequoiacap.com/article/generative-ai (Investment trends and startup insights)
  - Exponential View: https://www.exponentialview.co (AI impact, risks, and regulation)
  - The Rundown AI: https://www.therundown.ai (Daily AI newsletter, quick summaries)
  - The Neuron: https://www.theneurondaily.com (Daily AI insights for weekly compilation)
  For EACH source above, run a dedicated web search query: "site:<domain> AI news ${dateFrom}..${dateTo}" to pull fresh in-range items. Do NOT skip any source. Merge all results into Key Highlights.
40. MANDATORY COVERAGE AUDIT BEFORE FINAL SAVE:
  - Core organizations to explicitly audit in this run: OpenAI, Google, Microsoft, Meta, Anthropic, Nvidia, AWS/Amazon, IBM, Intel, AMD, Qualcomm, Oracle, Cisco, Uber, Salesforce, SAP, Samsung, Sony
  - For each organization above, run at least one targeted query for the selected date window and selected source types
  - If verified in-range updates are found, include them in Key Highlights with source-grounded details
  - If no verified in-range update is found for an organization after targeted queries, add one concise "No verified in-range update found" note in Trends & Strategic Implications (do not fabricate items)
  - Do not finalize report until this coverage audit pass is completed

Required Report Structure (FLAT — only two content sections, NO Technical Breakthroughs section):
- Executive Summary
- Key Highlights & Developments (ALL items including technical breakthroughs in one flat list, no sub-sections)
- Trends & Strategic Implications
- Quick Reference Table

MANDATORY OUTPUT FORMAT (MATCH THIS STYLE):
- Title line must be style-based:
  - concise: "# Concise AI Weekly Report"
  - detailed: "# Detailed AI Weekly Report"
  - technical: "# Technical AI Weekly Report"
- Next line must be: "Coverage period: ${dateFrom} to ${dateTo}"
- After Executive Summary, put ALL items (including technical breakthroughs) in a single "## Key Highlights & Developments" section — do NOT create a separate "Technical Breakthroughs" section or any other sub-sections
- Then Trends & Strategic Implications
- Then Quick Reference Table
- The report must have exactly 4 sections: Executive Summary, Key Highlights & Developments, Trends & Strategic Implications, Quick Reference Table
- For every item, use this exact field layout:
  - "Company Name: ..."
  - "Release Name: ... | Date: YYYY-MM-DD"
  - "Brief Description:"
  - First sentence in bold (one-line key takeaway)
  - Then a substantive paragraph with business + technical implications
  - "Reference Link: Primary: https://..."
- For concise style: each item paragraph must be at least 100 words
- For detailed style: each item paragraph must be at least 150 words — this is a HARD minimum; expand with deeper analysis, implications, and competitive context until 150 words is reached
- Do not output shortfall/template filler text (no "fewer than", no "shortfall note")
- Every item title/release name must be globally unique throughout the full report
- Do NOT create sub-headers like "Press Releases", "Major Releases", "Product Launches", "Industry News", "Technical Breakthroughs" anywhere in the report
- Include diverse organizations beyond OpenAI/Google/Microsoft when verified in-range
- Diversity is a strong preference, not a blocking requirement; never sacrifice correctness to satisfy diversity

FILE OUTPUT REQUIREMENTS (CRITICAL):
- You MUST save the final report as: "${reportFilename}"
- Use ONLY Python's open() function via code execution (do NOT use write_file tool, file_write tool, or any other file tool)
- Save the report ONLY to CMBAGENT_DEFAULT_WORK_DIR (do NOT save to project root, task root, or any other directory):
  import os
  default_dir = os.path.expanduser(os.getenv("CMBAGENT_DEFAULT_WORK_DIR", "~/Desktop/cmbdir"))
  os.makedirs(default_dir, exist_ok=True)
  output_path = os.path.join(default_dir, "${reportFilename}")
  with open(output_path, "w", encoding="utf-8") as f:
      f.write(report_content)
  print(f"Report saved to: {os.path.abspath(output_path)}")
- Markdown format with proper headers (##, ###) and lists
- Do NOT use any hardcoded absolute path
- Do NOT save any copy to os.path.dirname(os.getcwd()) or project root

${specificFocus ? `\nSPECIFIC FOCUS: ${specificFocus}` : ''}
${excludeTopics ? `\nEXCLUDE: ${excludeTopics}` : ''}
`

      // Create config with HITL enabled
      const taskConfig = {
        mode: 'planning-control',
        model: 'gpt-5',
        plannerModel: 'gpt-5',
        researcherModel: 'gpt-5',
        engineerModel: 'gpt-5',
        planReviewerModel: 'gpt-5',
        defaultModel: 'gpt-5',
        defaultFormatterModel: 'gpt-5',
        maxRounds: 120,
        maxAttempts: 8,
        maxPlanSteps: 2,
        nPlanReviews: 1,
        planInstructions: 'CRITICAL ARCHITECTURE CONSTRAINT: Each plan step runs in a SEPARATE agent session. Tool call results (RSS items, news articles, search hits) from one step are NOT available in the next step — only a brief text summary carries forward. Therefore you MUST create exactly 2 steps: Step 1 (engineer): Execute ALL mandatory tool calls (announcements_noauth, rss_company_announcements broad + per-company for openai google microsoft meta facebook anthropic nvidia amazon aws oracle cisco uber ibm intel amd qualcomm samsung salesforce sap siemens sony huggingface deeplearning_ai lastweekinai theneuron therundownai exponentialview, curated_ai_sources_catalog, curated_ai_sources_search, newsapi_search, gnews_search, prwire_search, multi_engine_web_search for zero-result companies), then from ALL collected results compile and WRITE the final markdown report file using Python open(). Step 2 (engineer): Verify the report file exists and contains all collected items. DO NOT split data collection across multiple steps or the data will be lost.',
        agent: 'planner',
        reportFilenamePattern: `ai_weekly_report_${dateFrom}_to_${dateTo}_*.md`,
        // Disable mandatory approval pauses so report generation proceeds end-to-end.
        approvalMode: 'never',
        requireApprovalBeforeSteps: false,
        enableManualControl: false
      }

      await connect(taskId, basePrompt, taskConfig)

    } catch (err: any) {
      setError(err.message)
      addConsoleOutput(`❌ Error: ${err.message}`)
      setIsRunning(false)
    }
  }

  const handleGenerate = async () => {
    // Start context enrichment flow
    generateEnrichmentQuestions()
  }

  const handleStop = () => {
    disconnect()
    setIsRunning(false)
    addConsoleOutput('🛑 Task execution stopped by user')
  }

  const handleApprovalResponse = (approved: boolean) => {
    if (!pendingApproval) return

    const message = {
      type: 'approval_response',
      approval_id: pendingApproval.approval_id,
      approved,
      feedback: approvalResponse.feedback,
      modifications: approvalResponse.modifications
    }

    sendMessage(message)
    setApprovalResponse({ feedback: '', modifications: '' })
    addConsoleOutput(approved ? '✅ Plan approved, continuing execution...' : '❌ Plan rejected')
  }

  const downloadReport = async () => {
    if (!result) return

    let content = result.fullReport

    // If we don't have content yet, try fetching it from the backend
    if (!content && result.path) {
      try {
        const contentRes = await fetch(getApiUrl(`/api/files/content?path=${encodeURIComponent(result.path)}`))
        const contentData = await contentRes.json()
        if (contentData.content) {
          content = contentData.content
          setResult({ ...result, fullReport: content })
          setIsReportDownloadReady(true)
        }
      } catch {
        // Also try searching in work directory
        try {
          const fallbackPrefix = `ai_weekly_report_${dateFrom}_to_${dateTo}_`
          const reportFilename = result.filename || `${fallbackPrefix}*.md`
          const workDir = result.workDir || results?.work_dir
          if (workDir) {
            const findRes = await fetch(getApiUrl(`/api/files/find?directory=${encodeURIComponent(workDir)}&filename=${encodeURIComponent(reportFilename)}`))
            const findData = await findRes.json()
            if (findData.count > 0) {
              const contentRes = await fetch(getApiUrl(`/api/files/content?path=${encodeURIComponent(findData.matches[0].path)}`))
              const contentData = await contentRes.json()
              if (contentData.content) {
                content = contentData.content
                setResult({ ...result, fullReport: content, path: findData.matches[0].path })
                setIsReportDownloadReady(true)
              }
            }
          }
        } catch { /* ignore */ }
      }
    }

    if (content) {
      const blob = new Blob([content], { type: 'text/markdown' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = result.filename || `ai-weekly-report-${dateFrom}-to-${dateTo}.md`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } else {
      addConsoleOutput(`⚠️ Report file not available for download yet. Location: ${result.path}`)
    }
  }

  const handleRestartWithModifications = async () => {
    if (!postExecutionFeedback.trim()) {
      setError('Please provide feedback on what to modify')
      return
    }

    setIsRestarting(true)
    setShowPostExecution(false)
    setError(null)
    clearConsole()

    try {
      // Add modification context to existing enriched prompt
      const modifiedPrompt = `${contextEnrichment.enrichedPrompt}

--- REVISION REQUEST ---
The report has been generated, but needs the following modifications:
${postExecutionFeedback}

Please regenerate the report incorporating these changes while maintaining all other requirements.`

      setContextEnrichment(prev => ({
        ...prev,
        enrichedPrompt: modifiedPrompt
      }))

      addConsoleOutput('🔄 Restarting workflow with modifications...')
      addConsoleOutput(`📝 Modification request: ${postExecutionFeedback}`)

      await startWorkflowWithEnrichment()
    } catch (err: any) {
      setError(err.message)
      addConsoleOutput(`❌ Error restarting: ${err.message}`)
    } finally {
      setIsRestarting(false)
      setPostExecutionFeedback('')
    }
  }

  // Download report as PDF using html2pdf.js
  const downloadReportAsPdf = async () => {
    if (!result) return

    let content = result.fullReport

    // If we don't have content yet, try fetching it
    if (!content && result.path) {
      try {
        const contentRes = await fetch(getApiUrl(`/api/files/content?path=${encodeURIComponent(result.path)}`))
        const contentData = await contentRes.json()
        if (contentData.content) {
          content = contentData.content
          setResult({ ...result, fullReport: content })
        }
      } catch { /* ignore */ }
    }

    if (!content) {
      addConsoleOutput(`⚠️ Report content not available for PDF conversion yet.`)
      return
    }

    try {
      const html2pdf = (await import('html2pdf.js')).default

      // Convert markdown to styled HTML
      const htmlContent = content
        .replace(/^### (.*$)/gm, '<h3 style="color:#1a1a2e;margin-top:18px;margin-bottom:8px;">$1</h3>')
        .replace(/^## (.*$)/gm, '<h2 style="color:#16213e;margin-top:24px;margin-bottom:10px;">$1</h2>')
        .replace(/^# (.*$)/gm, '<h1 style="color:#0f3460;margin-top:30px;margin-bottom:12px;">$1</h1>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/^- (.*$)/gm, '<li style="margin-left:20px;">$1</li>')
        .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" style="color:#2563eb;">$1</a>')
        .replace(/\n{2,}/g, '<br/><br/>')
        .replace(/\n/g, '<br/>')

      const wrapper = document.createElement('div')
      wrapper.innerHTML = `<div style="font-family:Arial,sans-serif;font-size:11px;line-height:1.6;color:#222;padding:20px;">${htmlContent}</div>`

      const opt = {
        margin: [10, 10, 10, 10] as [number, number, number, number],
        filename: result.filename?.replace('.md', '.pdf') || `ai-weekly-report-${dateFrom}-to-${dateTo}.pdf`,
        image: { type: 'jpeg' as const, quality: 0.98 },
        html2canvas: { scale: 2 },
        jsPDF: { unit: 'mm' as const, format: 'a4' as const, orientation: 'portrait' as const }
      }

      await html2pdf().set(opt).from(wrapper).save()
      addConsoleOutput('📥 PDF downloaded successfully!')
    } catch (err: any) {
      addConsoleOutput(`⚠️ PDF download failed: ${err.message}`)
    }
  }

  // Fetch report after workflow completion — retries up to 8 times (every 5 s)
  // so the file-writing step has time to finish.
  useEffect(() => {
    if (results?.work_dir && !result && !isRunning && !fetchStartedRef.current) {
      fetchStartedRef.current = true

      const MAX_RETRIES = 8
      const RETRY_DELAY_MS = 5000

      const searchForReport = async (workDir: string, reportPrefix: string) => {
        let findData = { count: 0, matches: [] as any[] }
        const minModified = (runStartTimestampRef.current ?? 0) - 5
        const keepFreshMatches = (matches: any[]) =>
          (matches || []).filter((m: any) => {
            const name = m?.name || (typeof m?.path === 'string' ? m.path.split('/').pop() : '')
            const modified = Number(m?.modified || 0)
            return Boolean(name && name.startsWith(reportPrefix) && modified >= minModified)
          })

        // 1) Direct listing
        try {
          const listRes = await fetch(getApiUrl(`/api/files/list?path=${encodeURIComponent(workDir)}`))
          if (listRes.ok) {
            const listData = await listRes.json()
            const markdownFiles = (listData.items || [])
              .filter((f: any) => f.type === 'file' && f.name.endsWith('.md') && f.name.startsWith(reportPrefix))
              .filter((f: any) => Number(f.modified || 0) >= minModified)
              .sort((a: any, b: any) => (b.modified || 0) - (a.modified || 0))
            if (markdownFiles.length > 0) {
              findData = { count: markdownFiles.length, matches: markdownFiles }
            }
          }
        } catch (_) { /* continue to fallback */ }

        // 2) Recursive search with exact prefix
        if (findData.count === 0) {
          try {
            const wildcardName = `${reportPrefix}*.md`
            const taskRes = await fetch(getApiUrl(`/api/files/find?directory=${encodeURIComponent(workDir)}&filename=${encodeURIComponent(wildcardName)}`))
            if (taskRes.ok) {
              const rawData = await taskRes.json()
              const freshMatches = keepFreshMatches(rawData.matches || [])
              findData = { ...rawData, matches: freshMatches, count: freshMatches.length }
            }
          } catch (_) { /* continue */ }
        }

        // 3) Broader fallback
        if (findData.count === 0) {
          try {
            const taskRes = await fetch(getApiUrl(`/api/files/find?directory=${encodeURIComponent(workDir)}&filename=${encodeURIComponent('ai_weekly_report_*.md')}`))
            if (taskRes.ok) {
              const rawData = await taskRes.json()
              const freshMatches = keepFreshMatches(rawData.matches || [])
              findData = { ...rawData, matches: freshMatches, count: freshMatches.length }
            }
          } catch (_) { /* continue */ }
        }

        return findData
      }

      const fetchReport = async () => {
        const reportPrefix = `ai_weekly_report_${dateFrom}_to_${dateTo}_`
        const isUsableReportContent = (content: string) => {
          const trimmed = (content || '').trim()
          if (trimmed.length < 200) return false
          return trimmed.includes('#') || trimmed.includes('##')
        }
        // Search both the task work_dir AND the CMBAGENT_DEFAULT_WORK_DIR (where the prompt tells the agent to save)
        const searchDirs = [results.work_dir]
        if (config.workDir && config.workDir !== results.work_dir) {
          searchDirs.push(config.workDir)
        }

        for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
          addConsoleOutput(`🔍 Searching for report file (attempt ${attempt}/${MAX_RETRIES})...`)

          for (const dir of searchDirs) {
            const findData = await searchForReport(dir, reportPrefix)

            if (findData.count > 0) {
              for (const match of findData.matches) {
                const foundPath = match.path
                addConsoleOutput(`📄 Found report at: ${foundPath}`)

                try {
                  const contentRes = await fetch(getApiUrl(`/api/files/content?path=${encodeURIComponent(foundPath)}`))
                  const contentData = await contentRes.json()
                  const content = typeof contentData.content === 'string' ? contentData.content : ''

                  if (isUsableReportContent(content)) {
                    setResult({
                      fullReport: content,
                      filename: match.name || foundPath.split('/').pop(),
                      path: foundPath,
                      workDir: results.work_dir
                    })
                    setIsReportDownloadReady(true)
                    addConsoleOutput(`✅ Report loaded successfully (${(contentData.size / 1024).toFixed(1)} KB)`)
                    setActiveRightTab('results')
                    return
                  }
                } catch (_) { /* try next match */ }
              }
              addConsoleOutput(`⚠️ Report file exists but content is empty or incomplete, retrying...`)
            }
          }

          if (attempt < MAX_RETRIES) {
            addConsoleOutput(`⏳ Report not ready yet, waiting ${RETRY_DELAY_MS / 1000}s before retry...`)
            await new Promise(resolve => setTimeout(resolve, RETRY_DELAY_MS))
          }
        }

        // All retries exhausted — do NOT set a fake success result
        addConsoleOutput(`❌ Report file was not found after ${MAX_RETRIES} attempts.`)
        addConsoleOutput(`   The file may not have been saved. Check the CMBAGENT_DEFAULT_WORK_DIR directory manually.`)
        setActiveRightTab('results')
        // Leave result as null so the UI shows the "processing" state, not a fake success
      }

      fetchReport().catch(err => {
        addConsoleOutput(`⚠️ Could not load report: ${err.message}`)
        fetchStartedRef.current = false
      })
    }
  }, [results, result, isRunning, dateFrom, dateTo])

  // Reset fetch guard when a new run starts
  useEffect(() => {
    if (isRunning) {
      fetchStartedRef.current = false
      postDismissedRef.current = false
    }
  }, [isRunning])

  // Monitor workflow completion — delay post-execution dialog until report fetch resolves
  useEffect(() => {
    if (connected && currentRunId && consoleOutput.length > 0 && isRunning) {
      const lastLog = consoleOutput[consoleOutput.length - 1]
      if (lastLog.includes('✅ Task execution completed') ||
        lastLog.includes('✅ Workflow completed') ||
        lastLog.includes('🎉 Workflow complete') ||
        lastLog.includes('✅ Task completed')) {
        setTimeout(() => {
          setIsRunning(false)
        }, 2000)
      }
    }
  }, [consoleOutput, connected, currentRunId, isRunning])

  // Show post-execution dialog only after we actually have a result or retries are exhausted
  useEffect(() => {
    if (!isRunning && results?.work_dir && !showPostExecution && !postDismissedRef.current) {
      // If result is loaded (report found), show dialog
      if (result) {
        setShowPostExecution(true)
        return
      }
      // If fetch has completed (fetchStartedRef is true and result is still null after guard),
      // wait a bit then show dialog without the success message
      if (fetchStartedRef.current) {
        const timer = setTimeout(() => {
          if (!result && !postDismissedRef.current) setShowPostExecution(true)
        }, 45000) // 8 retries × 5s = 40s max; give 5s margin
        return () => clearTimeout(timer)
      }
    }
  }, [isRunning, results, result, showPostExecution])

  return (
    <div className="min-h-screen p-6 pb-24">
      <div className="max-w-[1800px] mx-auto">
        {/* Context Enrichment Dialog */}
        {contextEnrichment.step === 'questions' && (
          <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-6">
            <div className="bg-gradient-to-br from-gray-900 to-black border-2 border-purple-500/30 rounded-xl max-w-3xl w-full max-h-[90vh] overflow-y-auto shadow-2xl">
              <div className="p-8">
                <div className="flex items-center gap-3 mb-6">
                  <MessageSquare className="w-8 h-8 text-purple-400" />
                  <div>
                    <h2 className="text-2xl font-bold text-white">Context Enrichment</h2>
                    <p className="text-gray-400 text-sm">Help us tailor the report to your needs</p>
                  </div>
                </div>

                <div className="space-y-6">
                  {contextEnrichment.questions.map((q, index) => (
                    <div key={q.id} className="bg-black/40 rounded-lg p-6 border border-white/10">
                      <label className="block text-white font-medium mb-3">
                        <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-purple-500/20 text-purple-400 text-sm font-bold mr-2">
                          {index + 1}
                        </span>
                        {q.question}
                      </label>
                      <textarea
                        value={q.answer}
                        onChange={(e) => {
                          const updated = [...contextEnrichment.questions]
                          updated[index].answer = e.target.value
                          setContextEnrichment({ ...contextEnrichment, questions: updated })
                        }}
                        className="w-full px-4 py-3 bg-black/50 border border-white/20 rounded-lg text-white placeholder-gray-500 focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 transition-all min-h-[100px]"
                        placeholder="Your answer..."
                      />
                    </div>
                  ))}

                  {/* Additional Advanced Options */}
                  <div className="bg-black/40 rounded-lg p-6 border border-white/10">
                    <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
                      <Settings className="w-5 h-5 text-blue-400" />
                      Additional Preferences
                    </h3>

                    <div className="space-y-4">
                      <div>
                        <label className="block text-gray-300 text-sm mb-2">Specific Focus Areas (optional)</label>
                        <input
                          type="text"
                          value={specificFocus}
                          onChange={(e) => setSpecificFocus(e.target.value)}
                          className="w-full px-4 py-2 bg-black/50 border border-white/20 rounded-lg text-white placeholder-gray-500 focus:border-blue-500 transition-all text-sm"
                          placeholder="e.g., healthcare AI, autonomous vehicles"
                        />
                      </div>

                      <div>
                        <label className="block text-gray-300 text-sm mb-2">Topics to Exclude (optional)</label>
                        <input
                          type="text"
                          value={excludeTopics}
                          onChange={(e) => setExcludeTopics(e.target.value)}
                          className="w-full px-4 py-2 bg-black/50 border border-white/20 rounded-lg text-white placeholder-gray-500 focus:border-red-500 transition-all text-sm"
                          placeholder="e.g., crypto AI, gaming"
                        />
                      </div>
                    </div>
                  </div>
                </div>

                <div className="flex gap-3 mt-8">
                  <button
                    onClick={() => setContextEnrichment({ step: 'initial', questions: [], enrichedPrompt: '' })}
                    className="flex-1 px-6 py-3 bg-gray-700/50 hover:bg-gray-700 text-white rounded-lg transition-all border border-gray-600"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={submitEnrichmentAnswers}
                    className="flex-1 px-6 py-3 bg-gradient-to-r from-purple-500 to-blue-500 hover:from-purple-600 hover:to-blue-600 text-white font-semibold rounded-lg transition-all flex items-center justify-center gap-2"
                  >
                    <CheckCircle2 className="w-5 h-5" />
                    Continue
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Confirmation Dialog */}
        {contextEnrichment.step === 'confirmation' && (
          <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-6">
            <div className="bg-gradient-to-br from-gray-900 to-black border-2 border-green-500/30 rounded-xl max-w-3xl w-full max-h-[90vh] overflow-y-auto shadow-2xl">
              <div className="p-8">
                <div className="flex items-center gap-3 mb-6">
                  <CheckCircle2 className="w-8 h-8 text-green-400" />
                  <div>
                    <h2 className="text-2xl font-bold text-white">Review Your Preferences</h2>
                    <p className="text-gray-400 text-sm">Confirm before generating the report</p>
                  </div>
                </div>

                <div className="bg-black/40 rounded-lg p-6 border border-white/10 mb-6">
                  <pre className="text-gray-300 text-sm whitespace-pre-wrap">
                    {contextEnrichment.enrichedPrompt}
                  </pre>
                </div>

                <div className="flex gap-3">
                  <button
                    onClick={() => setContextEnrichment({ ...contextEnrichment, step: 'questions' })}
                    className="flex-1 px-6 py-3 bg-gray-700/50 hover:bg-gray-700 text-white rounded-lg transition-all border border-gray-600"
                  >
                    Edit
                  </button>
                  <button
                    onClick={proceedWithEnrichedContext}
                    className="flex-1 px-6 py-3 bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600 text-white font-semibold rounded-lg transition-all flex items-center justify-center gap-2"
                  >
                    <Sparkles className="w-5 h-5" />
                    Generate Report
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Approval Dialog */}
        {pendingApproval && (
          <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-6">
            <div className="bg-gradient-to-br from-gray-900 to-black border-2 border-yellow-500/30 rounded-xl max-w-3xl w-full max-h-[90vh] overflow-y-auto shadow-2xl">
              <div className="p-8">
                <div className="flex items-center gap-3 mb-6">
                  <AlertCircle className="w-8 h-8 text-yellow-400" />
                  <div>
                    <h2 className="text-2xl font-bold text-white">Approval Required</h2>
                    <p className="text-gray-400 text-sm">{pendingApproval.description}</p>
                  </div>
                </div>

                <div className="bg-black/40 rounded-lg p-6 border border-white/10 mb-6">
                  <h3 className="text-white font-semibold mb-3">Plan Context:</h3>
                  <pre className="text-gray-300 text-sm whitespace-pre-wrap max-h-64 overflow-y-auto">
                    {JSON.stringify(pendingApproval.context, null, 2)}
                  </pre>
                </div>

                <div className="space-y-4 mb-6">
                  <div>
                    <label className="block text-gray-300 text-sm mb-2">Feedback (optional)</label>
                    <textarea
                      value={approvalResponse.feedback}
                      onChange={(e) => setApprovalResponse({ ...approvalResponse, feedback: e.target.value })}
                      className="w-full px-4 py-3 bg-black/50 border border-white/20 rounded-lg text-white placeholder-gray-500 focus:border-yellow-500 transition-all min-h-[100px]"
                      placeholder="Any feedback or concerns..."
                    />
                  </div>

                  <div>
                    <label className="block text-gray-300 text-sm mb-2">Modifications (if rejecting)</label>
                    <textarea
                      value={approvalResponse.modifications}
                      onChange={(e) => setApprovalResponse({ ...approvalResponse, modifications: e.target.value })}
                      className="w-full px-4 py-3 bg-black/50 border border-white/20 rounded-lg text-white placeholder-gray-500 focus:border-red-500 transition-all min-h-[100px]"
                      placeholder="Suggest changes to the plan..."
                    />
                  </div>
                </div>

                <div className="flex gap-3">
                  <button
                    onClick={() => handleApprovalResponse(false)}
                    className="flex-1 px-6 py-3 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg transition-all border border-red-500/50 font-semibold"
                  >
                    Reject
                  </button>
                  <button
                    onClick={() => handleApprovalResponse(true)}
                    className="flex-1 px-6 py-3 bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600 text-white font-semibold rounded-lg transition-all"
                  >
                    Approve & Continue
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Post-Execution Modification Dialog */}
        {showPostExecution && !isRunning && (
          <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-6">
            <div className="bg-gradient-to-br from-gray-900 to-black border-2 border-blue-500/30 rounded-xl max-w-3xl w-full max-h-[90vh] overflow-y-auto shadow-2xl">
              <div className="p-8">
                <div className="flex items-center gap-3 mb-6">
                  <MessageSquare className="w-8 h-8 text-blue-400" />
                  <div>
                    <h2 className="text-2xl font-bold text-white">{result?.fullReport ? 'Report Generated Successfully!' : 'Workflow Completed'}</h2>
                    <p className="text-gray-400 text-sm">{result?.fullReport ? 'Would you like to modify or regenerate the report?' : 'The report file could not be loaded automatically.'}</p>
                  </div>
                </div>

                <div className={`${result?.fullReport ? 'bg-green-500/10 border-green-500/30' : 'bg-yellow-500/10 border-yellow-500/30'} border rounded-lg p-4 mb-6`}>
                  <div className="flex items-start gap-3">
                    <CheckCircle2 className={`w-5 h-5 ${result?.fullReport ? 'text-green-400' : 'text-yellow-400'} flex-shrink-0 mt-0.5`} />
                    <div>
                      <p className={`${result?.fullReport ? 'text-green-400' : 'text-yellow-400'} font-medium mb-1`}>{result?.fullReport ? 'Workflow Completed' : 'Report Not Found'}</p>
                      <p className="text-gray-300 text-sm">
                        {result?.fullReport
                          ? 'The AI Weekly Report has been generated and is ready for review. You can view it in the Results tab.'
                          : 'The workflow finished but the report file was not found in CMBAGENT_DEFAULT_WORK_DIR. Check the directory manually or try regenerating.'}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="bg-black/40 rounded-lg p-6 border border-white/10 mb-6">
                  <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
                    <Sparkles className="w-5 h-5 text-blue-400" />
                    Request Modifications (Optional)
                  </h3>
                  <p className="text-gray-400 text-sm mb-4">
                    If you'd like to adjust the report content, describe the changes you want.
                    The workflow will restart with your modifications while keeping the base structure intact.
                  </p>
                  <textarea
                    value={postExecutionFeedback}
                    onChange={(e) => setPostExecutionFeedback(e.target.value)}
                    className="w-full px-4 py-3 bg-black/50 border border-white/20 rounded-lg text-white placeholder-gray-500 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all min-h-[120px]"
                    placeholder="Example: Add more technical details about the implementations, include more research papers on reinforcement learning, focus more on enterprise applications..."
                  />
                </div>

                {error && (
                  <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 mb-6 text-red-400 text-sm">
                    {error}
                  </div>
                )}

                <div className="flex gap-3">
                  <button
                    onClick={() => {
                      setShowPostExecution(false)
                      postDismissedRef.current = true
                      setPostExecutionFeedback('')
                      setError(null)
                    }}
                    className="flex-1 px-6 py-3 bg-gray-700/50 hover:bg-gray-700 text-white rounded-lg transition-all border border-gray-600 font-medium"
                  >
                    Done
                  </button>
                  <button
                    onClick={handleRestartWithModifications}
                    disabled={!postExecutionFeedback.trim() || isRestarting}
                    className="flex-1 px-6 py-3 bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 disabled:from-gray-500 disabled:to-gray-600 text-white font-semibold rounded-lg transition-all disabled:cursor-not-allowed flex items-center justify-center gap-2"
                  >
                    {isRestarting ? (
                      <>
                        <Loader2 className="w-5 h-5 animate-spin" />
                        <span>Restarting...</span>
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-5 h-5" />
                        <span>Regenerate with Modifications</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Main Content */}
        {showView === 'config' ? (
          <>
            {/* Header */}
            <div className="flex items-center space-x-4 mb-8">
              <button
                onClick={onBack}
                className="p-3 rounded-lg bg-black/30 backdrop-blur-sm border border-white/10 text-gray-400 hover:text-white transition-colors"
              >
                <ArrowLeft className="w-6 h-6" />
              </button>
              <div>
                <h1 className="text-3xl font-bold text-white">AI Weekly Report</h1>
                <p className="text-gray-400">Configure your AI research digest</p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-8">
              {/* Left Panel - Configuration */}
              <div className="space-y-6">

                {error && (
                  <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4 text-red-400">
                    {error}
                  </div>
                )}

                {/* Date Range */}
                <div className="bg-black/30 backdrop-blur-sm border border-white/10 rounded-lg p-6 space-y-4">
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
                        className="w-full px-4 py-2 bg-black/50 border border-white/10 rounded-lg text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-gray-400 mb-2">To</label>
                      <input
                        type="date"
                        value={dateTo}
                        onChange={(e) => setDateTo(e.target.value)}
                        className="w-full px-4 py-2 bg-black/50 border border-white/10 rounded-lg text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
                      />
                    </div>
                  </div>
                </div>

                {/* Topics */}
                <div className="bg-black/30 backdrop-blur-sm border border-white/10 rounded-lg p-6 space-y-4">
                  <div className="flex items-center space-x-2 mb-4">
                    <Tags className="w-5 h-5 text-green-400" />
                    <h2 className="text-lg font-semibold text-white">Topics</h2>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    {availableTopics.map(topic => (
                      <button
                        key={topic.id}
                        onClick={() => toggleTopic(topic.id)}
                        className={`px-4 py-3 rounded-lg text-sm font-medium transition-all ${topics.includes(topic.id)
                          ? 'bg-green-500 text-black'
                          : 'bg-black/50 text-gray-400 hover:text-white border border-white/10'
                          }`}
                      >
                        {topic.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Sources */}
                <div className="bg-black/30 backdrop-blur-sm border border-white/10 rounded-lg p-6 space-y-4">
                  <div className="flex items-center space-x-2 mb-4">
                    <Globe className="w-5 h-5 text-purple-400" />
                    <h2 className="text-lg font-semibold text-white">Sources</h2>
                  </div>
                  <div className="grid grid-cols-1 gap-3">
                    {availableSources.map(source => (
                      <button
                        key={source.id}
                        onClick={() => toggleSource(source.id)}
                        className={`px-4 py-3 rounded-lg text-sm font-medium transition-all ${sources.includes(source.id)
                          ? 'bg-purple-500 text-white'
                          : 'bg-black/50 text-gray-400 hover:text-white border border-white/10'
                          }`}
                      >
                        {source.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Style */}
                <div className="bg-black/30 backdrop-blur-sm border border-white/10 rounded-lg p-6 space-y-4">
                  <h2 className="text-lg font-semibold text-white">Report Style</h2>
                  <div className="grid grid-cols-3 gap-3">
                    {(['concise', 'detailed', 'technical'] as const).map(s => (
                      <button
                        key={s}
                        onClick={() => setStyle(s)}
                        className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium capitalize transition-all ${style === s
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
                      <span>Generate Weekly Report</span>
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
                      <h3 className="text-white font-medium mb-1">Stage 1: Context Enrichment</h3>
                      <p className="text-sm text-gray-400">Capture audience, focus, and depth preferences before execution begins</p>
                    </div>
                  </div>

                  <div className="flex items-start space-x-3">
                    <div className="w-8 h-8 rounded-full bg-green-500/20 flex items-center justify-center flex-shrink-0 mt-1">
                      <span className="text-green-400 text-sm font-semibold">2</span>
                    </div>
                    <div>
                      <h3 className="text-white font-medium mb-1">Stage 2: Plan Coverage Review</h3>
                      <p className="text-sm text-gray-400">Review the research plan and coverage strategy before collection starts</p>
                    </div>
                  </div>

                  <div className="flex items-start space-x-3">
                    <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center flex-shrink-0 mt-1">
                      <span className="text-purple-400 text-sm font-semibold">3</span>
                    </div>
                    <div>
                      <h3 className="text-white font-medium mb-1">Stage 3: Source Collection and Validation</h3>
                      <p className="text-sm text-gray-400">Track live collection, verification, deduplication, and coverage audit checks</p>
                    </div>
                  </div>

                  <div className="flex items-start space-x-3">
                    <div className="w-8 h-8 rounded-full bg-yellow-500/20 flex items-center justify-center flex-shrink-0 mt-1">
                      <span className="text-yellow-400 text-sm font-semibold">4</span>
                    </div>
                    <div>
                      <h3 className="text-white font-medium mb-1">Stage 4: Final Report Assembly</h3>
                      <p className="text-sm text-gray-400">Generate and review the final source-grounded AI weekly digest</p>
                    </div>
                  </div>

                  <div className="border-t border-white/10 pt-4 mt-4">
                    <p className="text-xs text-gray-500">
                      This workflow includes Human-in-the-Loop (HITL) integration for full control over the report generation process.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </>
        ) : (
          /* Execution View with 3 Tabs */
          <div className="h-[calc(100vh-200px)] flex flex-col gap-6">
            {/* Header */}
            <div className="bg-black/30 backdrop-blur-sm border border-white/10 rounded-lg p-4 flex-shrink-0">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4">
                  <button
                    onClick={() => {
                      setShowView('config')
                      setContextEnrichment({ step: 'initial', questions: [], enrichedPrompt: '' })
                    }}
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

            {/* Main Content Area */}
            <div className="flex-1 grid grid-cols-[1fr,500px] gap-6 min-h-0">
              {/* Left Side - Workspace */}
              <div className="min-h-0">
                <TaskWorkspaceView
                  dagData={gatedDagData}
                  currentRunId={currentRunId || undefined}
                  consoleOutput={consoleOutput}
                  costSummary={costSummary}
                  costTimeSeries={costTimeSeries}
                  isCollapsible={false}
                  defaultCollapsed={false}
                  showProgress={true}
                />
              </div>

              {/* Right Side - 3 Tabs */}
              <div className="flex flex-col min-h-0 bg-black/30 backdrop-blur-sm border border-white/10 rounded-lg overflow-hidden">
                {/* Tab Navigation */}
                <div className="flex border-b border-white/10 flex-shrink-0">
                  <button
                    onClick={() => setActiveRightTab('console')}
                    className={`flex-1 px-4 py-3 text-sm font-medium transition-all ${activeRightTab === 'console'
                      ? 'bg-blue-500/20 text-blue-400 border-b-2 border-blue-500'
                      : 'text-gray-400 hover:text-white hover:bg-white/5'
                      }`}
                  >
                    <div className="flex items-center justify-center gap-2">
                      <Code className="w-4 h-4" />
                      <span>Console</span>
                    </div>
                  </button>
                  <button
                    onClick={() => setActiveRightTab('plan')}
                    className={`flex-1 px-4 py-3 text-sm font-medium transition-all ${activeRightTab === 'plan'
                      ? 'bg-purple-500/20 text-purple-400 border-b-2 border-purple-500'
                      : 'text-gray-400 hover:text-white hover:bg-white/5'
                      }`}
                  >
                    <div className="flex items-center justify-center gap-2">
                      <FileText className="w-4 h-4" />
                      <span>Plan</span>
                    </div>
                  </button>
                  <button
                    onClick={() => setActiveRightTab('results')}
                    className={`flex-1 px-4 py-3 text-sm font-medium transition-all ${activeRightTab === 'results'
                      ? 'bg-green-500/20 text-green-400 border-b-2 border-green-500'
                      : 'text-gray-400 hover:text-white hover:bg-white/5'
                      }`}
                  >
                    <div className="flex items-center justify-center gap-2">
                      <Sparkles className="w-4 h-4" />
                      <span>Results</span>
                    </div>
                  </button>
                </div>

                {/* Tab Content */}
                <div className="flex-1 overflow-hidden">
                  {activeRightTab === 'console' && (
                    <div className="h-full overflow-auto p-4">
                      <ConsoleOutput output={consoleOutput} isRunning={isRunning} />
                    </div>
                  )}

                  {activeRightTab === 'plan' && (
                    <div className="h-full overflow-auto p-4">
                      <div className="space-y-4">
                        <h3 className="text-white font-semibold">Execution Plan</h3>
                        {gatedDagData?.nodes ? (
                          <div className="space-y-2">
                            {gatedDagData.nodes.map((node: any, index: number) => (
                              <div
                                key={node.id}
                                className={`p-3 rounded-lg border ${node.status === 'completed'
                                  ? 'bg-green-500/10 border-green-500/30'
                                  : node.status === 'executing'
                                    ? 'bg-blue-500/10 border-blue-500/30 animate-pulse'
                                    : node.status === 'failed'
                                      ? 'bg-red-500/10 border-red-500/30'
                                      : 'bg-white/5 border-white/10'
                                  }`}
                              >
                                <div className="flex items-center gap-2">
                                  <span className="text-gray-400 text-xs">Step {index + 1}</span>
                                  <span className="text-white text-sm font-medium">{node.name}</span>
                                </div>
                                {node.goal && (
                                  <p className="text-gray-400 text-xs mt-1">{node.goal}</p>
                                )}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="text-center text-gray-500 py-12">
                            <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
                            <p>Plan will appear here after generation</p>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {activeRightTab === 'results' && (
                    <div className="h-full overflow-auto p-4">
                      {result ? (
                        <div className="space-y-4">
                          <div className="flex items-center justify-between">
                            <h3 className="text-white font-semibold">Generated Report</h3>
                            <div className="flex items-center gap-2">
                              <button
                                onClick={downloadReport}
                                className="flex items-center gap-1 px-3 py-1 bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 rounded text-xs transition-colors"
                              >
                                <Download className="w-3 h-3" />
                                Download MD
                              </button>
                              <button
                                onClick={downloadReportAsPdf}
                                className="flex items-center gap-1 px-3 py-1 bg-purple-500/20 hover:bg-purple-500/30 text-purple-400 rounded text-xs transition-colors"
                              >
                                <Download className="w-3 h-3" />
                                Download PDF
                              </button>
                            </div>
                          </div>

                          {result.fullReport ? (
                            <div className="bg-black/50 rounded-lg p-3 border border-white/10 max-h-[600px] overflow-y-auto">
                              <pre className="text-xs text-gray-300 whitespace-pre-wrap font-mono leading-relaxed">
                                {result.fullReport}
                              </pre>
                            </div>
                          ) : (
                            <div className="space-y-4">
                              <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4">
                                <div className="flex items-start gap-3">
                                  <FileText className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
                                  <div>
                                    <p className="text-yellow-400 font-medium mb-1">Report file found but content could not be loaded</p>
                                    <p className="text-gray-300 text-sm">
                                      Check your CMBAGENT_DEFAULT_WORK_DIR directory manually, or try regenerating.
                                    </p>
                                  </div>
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="h-full flex items-center justify-center text-gray-500">
                          <div className="text-center">
                            <Sparkles className="w-12 h-12 mx-auto mb-3 opacity-50 animate-pulse" />
                            <p className="text-sm">Report will appear here once generated</p>
                            <p className="text-xs text-gray-600 mt-1">Processing...</p>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
