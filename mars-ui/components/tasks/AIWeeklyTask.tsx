'use client'

import { useState, useEffect, useMemo, useRef } from 'react'
import { ArrowLeft, Calendar, Tags, Globe, Sparkles, Download, Loader2, Code } from 'lucide-react'
import { config, getApiUrl } from '@/lib/config'
import { useWebSocketContext } from '@/contexts/WebSocketContext'
import TaskWorkspaceView from './TaskWorkspaceView'
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
    costTimeSeries,
    results,
    setResults
  } = useWebSocketContext()

  const [taskId, setTaskId] = useState<string | null>(null)
  const [result, setResult] = useState<any>(null)
  const [isReportDownloadReady, setIsReportDownloadReady] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showView, setShowView] = useState<'config' | 'execution'>('config')
  const fetchStartedRef = useRef(false)
  const runStartTimestampRef = useRef<number | null>(null)

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

  // Download report function
  const downloadReport = () => {
    if (!result?.fullReport) return

    const blob = new Blob([result.fullReport], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `ai-weekly-report-${dateFrom}-to-${dateTo}.md`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const handleGenerate = async () => {
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

    try {
      const taskId = `ai-weekly_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
      setTaskId(taskId)

      const timeStamp = new Date().toTimeString().slice(0, 8).replace(/:/g, '_')
      const reportFilename = `ai_weekly_report_${dateFrom}_to_${dateTo}_${timeStamp}.md`

      addConsoleOutput(`✅ Task created: ${taskId}`)
      addConsoleOutput(`📅 Date Range: ${dateFrom} to ${dateTo}`)
      addConsoleOutput(`🏷️  Topics: ${topics.join(', ')}`)
      addConsoleOutput(`📰 Sources: ${sources.join(', ')}`)
      addConsoleOutput(`📁 Expected output file: ${reportFilename}`)
      addConsoleOutput(``)

      runStartTimestampRef.current = Date.now() / 1000
      setIsRunning(true)
      addConsoleOutput(`🚀 Connecting to workflow engine...`)

      // Create task description with actual instructions
      const enhancedTask = `Generate a Professional AI Weekly Report for organization-wide distribution covering ${dateFrom} to ${dateTo}.

AUDIENCE: Technical and non-technical stakeholders across the organization
TONE: Professional, clear, and actionable
QUALITY: Publication-ready content suitable for executive briefings

Topics to cover: ${topics.join(', ')}
Sources to use: ${sources.join(', ')}
Report style: ${style}

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
12. ALL links must be ACTUAL working URLs - NO placeholder links like "example.com"
13. Do NOT use archive-style sources (no arxiv.org papers, no archive.org links, no historical retrospective datasets)
14. Focus ONLY on latest releases and official company release channels in the selected date window
15. Date coverage rule: include items across multiple dates in the range, not a single day only
16. Boundary coverage rule: include at least one item from ${dateFrom} and one from ${dateTo} when available; if unavailable, state this explicitly and include nearest in-range dates
17. Search GitHub for trending repos and major releases in AI
18. Search official press releases and company announcements for AI launches and updates
19. Search for major model/tool/platform releases announced in the date range
20. MANDATORY FIXED TOOL EXECUTION SEQUENCE — execute ALL of these steps in EXACTLY this order, EVERY run, with NO exceptions:
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
21. If any tool call fails or returns an error, log the error and CONTINUE with the next step — never abort the sequence
22. EVERY item returned by tools A-I that passes date filtering MUST appear in the final report — do not cherry-pick or drop items
23. Write in professional ${style} style with clear, concise explanations
24. Include context and business implications for each item
24.1 For EVERY item, open the primary reference URL and extract concrete facts (announcement details, specs, metrics, stakeholders, timelines) before writing the description
24.2 Do not write generic summaries; each item description must be grounded in source details from the reference link
25. The broad sweep in Step A+B is non-negotiable — even if focused queries in Step C return data, the broad sweep ensures nothing is missed
26. The per-company passes in Step C are non-negotiable — even if the broad sweep returned data for that company, the focused pass may catch additional items
27. Never output a blank template or "no data" report if in-range items were found by tools; include verified items and provide deeper context instead of shortfall notes
28. STRICT NO-DUPLICATE RULE:
  - Each unique release/announcement must appear EXACTLY ONCE in the entire report
  - Different versions ARE distinct items (e.g. GPT-5.3 and GPT-5.4 are two separate releases — each one can appear once)
  - But the SAME version must NEVER repeat (e.g. GPT-5.3 must not appear 2, 3, or 4 times — only once)
  - De-duplicate by: exact release name + organization + URL; if the same release name or URL appears more than once, keep only the first/best entry and delete all others
  - Before writing the final report, run a MANDATORY FINAL DEDUP PASS: scan the entire report, count occurrences of each release name; if any name appears more than once, remove all but the first occurrence
  - If the same announcement appears under different headlines, keep only the primary one
29. Omit empty topic sections entirely. Do not render a topic header (for example RL) if there are zero verified in-range items for that topic
30. Style rules by report style:
  - concise: each item description must contain at least 100 words
  - detailed: each item description must contain at least 150 words — this is a HARD minimum; if a paragraph is shorter, expand it with deeper analysis, implications, competitive context, and technical detail until it reaches 150 words
  - technical: keep high technical depth with concrete metrics and implementation notes; each item at least 150 words
31. Minimum detail requirement: each major section must contain at least 50 words of meaningful analysis
32. Never include lines such as "Shortfall note", "Fewer than X", or "Limited significant developments found" in the final report
33. If a section has limited new items, add comparative analysis, implications, and forward-looking commentary based on verified in-range items
34. EACH RELEASE APPEARS EXACTLY ONCE:
  - GPT-5.3 can appear once, GPT-5.4 can appear once — they are different releases
  - But GPT-5.3 must NOT appear 1+ times, and GPT-5.4 must NOT appear 1+ times
  - This applies to ALL releases from ALL companies: each unique release name gets exactly one entry in the entire report
  - If you need to reference a release already covered, do not create a new entry — just mention it briefly in the context of another item
35. Accuracy and genuineness rules:
  - Prefer correctness over volume; never pad with weak or uncertain items
  - Do not fabricate claims, dates, organizations, metrics, or URLs
  - Use only verifiable, genuine items from authoritative sources; if verification is weak, skip the item
  - If a high-priority organization has no verified in-range updates, briefly state unavailable rather than inventing coverage
36. Topic and title uniqueness rules:
  - Topic/section headings must be globally unique throughout the full report
  - Every item title/release name must be globally unique throughout the full report
  - Any section may contain N items, but each title must be unique
  - A single news item can appear in only one section (no cross-section repetition)
37. Organization and topic diversity rules (strong preference, not a hard block):
  - Do not concentrate mostly on OpenAI/Google/Microsoft
  - Include coverage from Meta/Facebook, Oracle, Cisco, AWS/Amazon, Uber, IBM, Intel, AMD, Qualcomm when verified in-range updates are available
  - Include additional global organizations when available: Salesforce, SAP, Siemens, Tencent, Baidu, Alibaba, Samsung, Sony, Toyota, Bosch, Infosys, TCS, Wipro, Reliance Jio, and other global innovators
  - Broaden scope beyond pure AI/ML: also search for quantum computing, edge AI, neuromorphic computing, AI hardware, AI regulation/policy, and AI-driven scientific breakthroughs
  - Aim for broad organization and topic diversity, but do not force non-verified items
38. MANDATORY: Always run curated_ai_sources_catalog and curated_ai_sources_search to discover items from curated AI news sources — this is NOT optional and must happen in EVERY report generation regardless of which source checkboxes are selected
39. Agent must go deep and collect from multiple companies: OpenAI, Google, Microsoft, Meta/Facebook, Oracle, Cisco, IBM, Intel, AMD, Qualcomm, AWS/Amazon, Uber, Anthropic, Nvidia, Hugging Face, Samsung, Sony, Toyota, Bosch, Infosys, TCS, and major startups/investors. Also search for quantum computing (IBM Quantum, Google Quantum AI, IonQ, Rigetti, D-Wave), AI hardware, edge AI, and AI regulation/policy developments when in-range updates are available
40. MANDATORY curated sources — search ALL of these in EVERY run (not optional):
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
41. Search fallback policy: when DuckDuckGo fails for a query, retry via Google, Bing, Yahoo, and Brave instead of stopping
42. MANDATORY COVERAGE AUDIT BEFORE FINAL SAVE:
  - Core organizations to explicitly audit in this run: OpenAI, Google, Microsoft, Meta, Anthropic, Nvidia, AWS/Amazon, IBM, Intel, AMD, Qualcomm, Oracle, Cisco, Uber, Salesforce, SAP, Samsung, Sony
  - For each organization above, run at least one targeted query for the selected date window and selected source types
  - If verified in-range updates are found, include them in Key Highlights with source-grounded details
  - If no verified in-range update is found for an organization after targeted queries, add one concise "No verified in-range update found" note in Trends & Strategic Implications (do not fabricate items)
  - Do not finalize report until this coverage audit pass is completed

Required Report Structure (FLAT — only two content sections, NO Technical Breakthroughs section):

## 📋 Executive Summary
Professional 3-4 sentence overview highlighting the week's most significant developments and their strategic implications.

## 🔥 Key Highlights & Developments
This is the MAIN and ONLY content body of the report. Include ALL verified in-range items here in a single flat list — press releases, company announcements, major releases, product launches, technical breakthroughs, industry news, funding rounds, partnerships, quantum computing updates, AI hardware, regulation/policy, and any other noteworthy developments. Do NOT split these into separate sub-sections or separate "Technical Breakthroughs" section.

For each item include:
- **Bold headline** — Company/Organization Name | Date: YYYY-MM-DD
  - Comprehensive paragraph (concise: ≥100 words; detailed: ≥150 words) explaining what happened, why it matters, competitive context, technical significance, and business implications
  - [Authoritative source link](url)

IMPORTANT: List items sequentially. Do NOT create any sub-headers within this section. Every item is equal — just list them one after another. Include technical breakthroughs inline here, not in a separate section.

## 💭 Trends & Strategic Implications
Key insights for organizational decision-making. For each:
- **Trend/Pattern**: Clear statement
  - Evidence and analysis
  - Strategic recommendations

## 📊 Quick Reference Table
Comprehensive table with ALL items from the report:

| Title | Organization | Date | Link |
|-------|-------------|------|------|
| Item name | Company | YYYY-MM-DD | [Link](url) |

---

*Report compiled: ${new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}*
*Coverage period: ${dateFrom} to ${dateTo}*
*Topics: ${topics.join(', ')}*

CRITICAL QUALITY CHECKLIST:
✅ Each item MUST have a 3-4 sentence comprehensive summary (not just headlines)
✅ Each item summary must be source-grounded: extract details from its own reference link before writing
✅ Include context, implications, and "why it matters" for every entry
✅ NO placeholder links (example.com, placeholder.com, dummy URLs)
✅ Verify all GitHub repos exist (github.com/org/repo format)
✅ Use actual news article URLs from authoritative sources only
✅ Include publication dates for all items (YYYY-MM-DD format)
✅ Professional language suitable for executive distribution
✅ Add specific details: metrics, names, institutions, funding amounts, performance numbers
✅ No shortfall boilerplate lines in final output; provide substantive analysis instead
✅ Facts must be correct and genuine; do not include unverifiable or fabricated items
✅ Coverage audit completed for all core organizations before final save
✅ Do NOT create separate sections for Press Releases, Major Releases, Product Launches, or Industry News — merge all into Key Highlights

WRITING STYLE:
- Each summary should be self-contained and informative
- Use concrete details and specific numbers/metrics where available
- Explain technical concepts clearly for non-technical readers
- Balance depth with readability - aim for executive summary quality
✅ Clear business context and implications for each item
✅ Minimum 50 words for every major section and every non-empty topic subsection

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

Keep output structure and tone aligned with the mandatory format above.`

      // Create config directly like research mode does
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
        reportFilenamePattern: `ai_weekly_report_${dateFrom}_to_${dateTo}_*.md`
      }

      await connect(taskId, enhancedTask, taskConfig)

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

  // Monitor for completion in console
  useEffect(() => {
    if (connected && currentRunId && consoleOutput.length > 0 && isRunning) {
      const lastLog = consoleOutput[consoleOutput.length - 1]
      if (lastLog.includes('✅ Task execution completed') ||
        lastLog.includes('✅ Workflow completed') ||
        lastLog.includes('🎉 Workflow complete')) {
        setTimeout(() => {
          setIsRunning(false)
        }, 2000)
      }
    }
  }, [consoleOutput, connected, currentRunId, isRunning])

  // Reset fetch guard when a new run starts
  useEffect(() => {
    if (isRunning) fetchStartedRef.current = false
  }, [isRunning])

  // Fetch report after workflow completion — retries up to 8 times (every 5 s)
  useEffect(() => {
    if (results?.work_dir && !result && !isRunning && !fetchStartedRef.current) {
      fetchStartedRef.current = true

      const MAX_RETRIES = 8
      const RETRY_DELAY_MS = 5000

      const searchInDir = async (dir: string, reportPrefix: string) => {
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
          const listRes = await fetch(getApiUrl(`/api/files/list?path=${encodeURIComponent(dir)}`))
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
        } catch (_) { /* continue */ }

        // 2) Recursive search with exact prefix
        if (findData.count === 0) {
          try {
            const wildcardName = `${reportPrefix}*.md`
            const taskRes = await fetch(getApiUrl(`/api/files/find?directory=${encodeURIComponent(dir)}&filename=${encodeURIComponent(wildcardName)}`))
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
            const taskRes = await fetch(getApiUrl(`/api/files/find?directory=${encodeURIComponent(dir)}&filename=${encodeURIComponent('ai_weekly_report_*.md')}`))
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
        const searchDirs = [results.work_dir]
        if (config.workDir && config.workDir !== results.work_dir) {
          searchDirs.push(config.workDir)
        }

        for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
          addConsoleOutput(`🔍 Searching for report file (attempt ${attempt}/${MAX_RETRIES})...`)

          for (const dir of searchDirs) {
            const findData = await searchInDir(dir, reportPrefix)

            if (findData.count > 0) {
              for (const match of findData.matches) {
                const foundPath = match.path
                addConsoleOutput(`📄 Found report at: ${foundPath}`)

                try {
                  const contentRes = await fetch(getApiUrl(`/api/files/content?path=${encodeURIComponent(foundPath)}`))
                  const contentData = await contentRes.json()
                  const content = typeof contentData.content === 'string' ? contentData.content : ''

                  if (isUsableReportContent(content)) {
                    parseAndSetReport(content)
                    addConsoleOutput(`✅ Report loaded: ${match.name || foundPath.split('/').pop()}`)
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

        // All retries exhausted
        addConsoleOutput(`❌ Report file was not found after ${MAX_RETRIES} attempts.`)
        addConsoleOutput(`   Check the CMBAGENT_DEFAULT_WORK_DIR directory manually.`)
      }

      fetchReport().catch(err => {
        addConsoleOutput(`⚠️ Could not load report: ${err.message}`)
        fetchStartedRef.current = false
      })
    }
  }, [results, result, isRunning, dateFrom, dateTo])

  // Parse markdown content and extract structured data
  const parseAndSetReport = (content: string) => {
    const lines = content.split('\n')
    const headlines: string[] = []
    const sections: any[] = []
    let currentSection: any = null

    lines.forEach(line => {
      // Extract headlines (lines starting with ## or ###)
      if (line.startsWith('## ')) {
        const headline = line.replace('## ', '').trim()
        if (headline && !headline.toLowerCase().includes('weekly report')) {
          headlines.push(headline)

          // Start a new section
          if (currentSection) sections.push(currentSection)
          currentSection = { title: headline, items: [] }
        }
      } else if (line.startsWith('### ')) {
        const headline = line.replace('### ', '').trim()
        if (headline) {
          headlines.push(headline)
        }
      } else if (line.trim().startsWith('- ') || line.trim().startsWith('* ')) {
        // Extract list items
        const item = line.trim().replace(/^[-*]\s+/, '')
        if (currentSection && item) {
          currentSection.items.push(item)
        }
      }
    })

    if (currentSection) sections.push(currentSection)

    setResult({
      fullReport: content,
      dateRange: `${dateFrom} to ${dateTo}`,
      itemCount: sections.reduce((acc, s) => acc + s.items.length, 0),
      headlines: headlines.slice(0, 5), // Top 5 headlines
      sections: sections.slice(0, 4)     // First 4 sections
    })
    setIsReportDownloadReady(true)
  }

  // Fallback: Parse report data from console output
  const parseReportFromConsole = () => {
    const reportLines = consoleOutput.filter(line =>
      !line.startsWith('✅') &&
      !line.startsWith('🚀') &&
      !line.startsWith('📊') &&
      !line.startsWith('📁') &&
      line.length > 10
    )

    setResult({
      fullReport: reportLines.join('\n'),
      dateRange: `${dateFrom} to ${dateTo}`,
      itemCount: reportLines.length,
      headlines: ['Report generated successfully'],
      sections: [{
        title: 'Generated Output',
        items: reportLines.slice(0, 10)
      }]
    })
    setIsReportDownloadReady(false)

    addConsoleOutput('✅ Report preview created from execution logs')
    disconnect()
  }

  const pollForResults = async (id: string) => {
    try {
      const response = await fetch(getApiUrl(`/api/tasks/status/${id}`))
      const data = await response.json()

      if (data.status === 'completed' && data.result) {
        setResult(data.result)
        // Keep final step gated until report is confirmed via file-based fetch flow.
        setIsReportDownloadReady(false)
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
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${topics.includes(topic.id)
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
                    <h3 className="text-white font-medium mb-1">Stage 1: Plan Coverage Scope</h3>
                    <p className="text-sm text-gray-400">Create a research plan that spans selected sources, dates, and organizations</p>
                  </div>
                </div>

                <div className="flex items-start space-x-3">
                  <div className="w-8 h-8 rounded-full bg-green-500/20 flex items-center justify-center flex-shrink-0 mt-1">
                    <span className="text-green-400 text-sm font-semibold">2</span>
                  </div>
                  <div>
                    <h3 className="text-white font-medium mb-1">Stage 2: Collect Source Evidence</h3>
                    <p className="text-sm text-gray-400">Gather verified updates from company pages, announcements, and ecosystem signals</p>
                  </div>
                </div>

                <div className="flex items-start space-x-3">
                  <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center flex-shrink-0 mt-1">
                    <span className="text-purple-400 text-sm font-semibold">3</span>
                  </div>
                  <div>
                    <h3 className="text-white font-medium mb-1">Stage 3: Validate and De-duplicate</h3>
                    <p className="text-sm text-gray-400">Check dates, links, uniqueness, and perform final coverage audit before writing</p>
                  </div>
                </div>

                <div className="flex items-start space-x-3">
                  <div className="w-8 h-8 rounded-full bg-yellow-500/20 flex items-center justify-center flex-shrink-0 mt-1">
                    <span className="text-yellow-400 text-sm font-semibold">4</span>
                  </div>
                  <div>
                    <h3 className="text-white font-medium mb-1">Stage 4: Generate Final Report</h3>
                    <p className="text-sm text-gray-400">Produce source-grounded analysis with executive-ready structure and detail</p>
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
          /* Execution View with Creative Layout */
          <div className="h-[calc(100vh-200px)] flex gap-6">
            {/* Left Side - Task Progress & Workspace (60%) */}
            <div className="flex-[6] flex flex-col space-y-4 overflow-hidden">
              {/* Header with Task Info and Stop Button */}
              <div className="bg-black/30 backdrop-blur-sm border border-white/10 rounded-lg p-4 flex-shrink-0">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-4">
                    <button
                      onClick={() => { setShowView('config') }}
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

              {/* Workspace View - Collapsible */}
              <div className="flex-1 min-h-0">
                <TaskWorkspaceView
                  dagData={gatedDagData}
                  currentRunId={currentRunId ?? undefined}
                  consoleOutput={consoleOutput}
                  costSummary={costSummary}
                  costTimeSeries={costTimeSeries}
                  isCollapsible={true}
                  defaultCollapsed={false}
                  showProgress={true}
                />
              </div>
            </div>

            {/* Right Side - Console & Output (40%) */}
            <div className="flex-[4] flex flex-col space-y-4 overflow-hidden">
              {/* Console Output - Always Visible, Compact */}
              <div className="h-[40%] bg-black/30 backdrop-blur-sm border border-white/10 rounded-lg overflow-hidden flex flex-col">
                <div className="border-b border-white/10 p-3 flex items-center justify-between flex-shrink-0">
                  <h3 className="text-white font-semibold text-sm flex items-center gap-2">
                    <Code className="w-4 h-4 text-blue-400" />
                    Live Console
                  </h3>
                  {consoleOutput.length > 0 && (
                    <span className="text-xs text-gray-400">{consoleOutput.length} logs</span>
                  )}
                </div>
                <div className="flex-1 overflow-auto">
                  <ConsoleOutput output={consoleOutput} isRunning={isRunning} />
                </div>
              </div>

              {/* Generated Report Output */}
              <div className="flex-1 bg-black/30 backdrop-blur-sm border border-white/10 rounded-lg overflow-hidden flex flex-col">
                <div className="border-b border-white/10 p-3 flex items-center justify-between flex-shrink-0">
                  <h3 className="text-white font-semibold text-sm flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-yellow-400" />
                    Generated Report
                  </h3>
                  {result && (
                    <button
                      onClick={downloadReport}
                      className="flex items-center gap-1 px-3 py-1 bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 rounded text-xs transition-colors"
                    >
                      <Download className="w-3 h-3" />
                      Download MD
                    </button>
                  )}
                </div>
                <div className="flex-1 overflow-auto p-4">
                  {result ? (
                    <div className="space-y-4">
                      {/* Summary Stats */}
                      {(result.dateRange || result.itemCount) && (
                        <div className="bg-white/5 rounded-lg p-3 border border-white/10">
                          <div className="flex items-center justify-between text-sm">
                            {result.dateRange && (
                              <span className="text-gray-400">📅 {result.dateRange}</span>
                            )}
                            {result.itemCount && (
                              <span className="text-gray-400">📊 {result.itemCount} items</span>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Headlines */}
                      {result.headlines && result.headlines.length > 0 && (
                        <div className="space-y-2">
                          <h4 className="text-sm font-semibold text-white flex items-center gap-2">
                            <span className="text-lg">📌</span>
                            Top Headlines
                          </h4>
                          <div className="space-y-1.5">
                            {result.headlines.map((headline: string, i: number) => (
                              <div key={i} className="text-gray-300 text-xs bg-white/5 rounded p-2 border-l-2 border-blue-400">
                                {headline}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Sections Preview */}
                      {result.sections && result.sections.length > 0 && (
                        <div className="space-y-3">
                          <h4 className="text-sm font-semibold text-white flex items-center gap-2">
                            <span className="text-lg">📑</span>
                            Report Sections
                          </h4>
                          {result.sections.map((section: any, i: number) => (
                            <div key={i} className="bg-white/5 rounded-lg p-3 border border-white/10">
                              <h5 className="text-white font-medium text-sm mb-2">{section.title}</h5>
                              <ul className="space-y-1">
                                {section.items.slice(0, 3).map((item: string, j: number) => (
                                  <li key={j} className="text-gray-400 text-xs flex items-start gap-2">
                                    <span className="text-blue-400 mt-0.5">•</span>
                                    <span>{item}</span>
                                  </li>
                                ))}
                                {section.items.length > 3 && (
                                  <li className="text-gray-500 text-xs italic">
                                    + {section.items.length - 3} more items
                                  </li>
                                )}
                              </ul>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Full Report Preview */}
                      {result.fullReport && (
                        <div className="space-y-2">
                          <h4 className="text-sm font-semibold text-white flex items-center gap-2">
                            <span className="text-lg">📄</span>
                            Full Report Preview
                          </h4>
                          <div className="bg-black/50 rounded-lg p-3 border border-white/10 max-h-64 overflow-y-auto">
                            <pre className="text-xs text-gray-300 whitespace-pre-wrap font-mono leading-relaxed">
                              {result.fullReport.substring(0, 2000)}
                              {result.fullReport.length > 2000 && '\n\n... (truncated, download for full report)'}
                            </pre>
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
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
