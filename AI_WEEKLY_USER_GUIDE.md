# AI Weekly Report - User Guide

## Overview

The AI Weekly Report feature provides an end-to-end Human-in-the-Loop (HITL) workflow for generating comprehensive, publication-ready AI research digests. The system allows you to customize report generation through interactive questions, review and approve execution plans, and request modifications after completion.

## Workflow Steps

### 1. Configuration Phase

Navigate to the AI Weekly Report task and configure:

- **Date Range**: Select the start and end dates for the report coverage
- **Topics**: Choose from:
  - Large Language Models (LLM)
  - Computer Vision (CV)
  - Reinforcement Learning (RL)
  - Robotics
  - MLOps
  - AI Ethics
- **Sources**: Select data sources:
  - ArXiv Papers
  - GitHub Releases
  - Tech Blogs
- **Report Style**: Choose one:
  - Concise
  - Detailed
  - Technical

Click "Generate Weekly Report" to proceed.

### 2. Context Enrichment (HITL Stage 1)

You'll be asked 4 questions to customize the report:

1. **Report Characteristics**: Define key characteristics (focus areas, depth, audience)
2. **Focus Areas**: Specify which aspects or breakthroughs to prioritize
3. **Technical Depth**: Decide on implementation details vs. high-level summaries
4. **Business Context**: Choose whether to emphasize commercial applications

**Additional Preferences (Optional):**
- Specific focus areas (e.g., "healthcare AI", "autonomous vehicles")
- Topics to exclude (e.g., "crypto AI", "gaming")

After answering, you can:
- **Cancel**: Return to configuration
- **Continue**: Proceed to confirmation

### 3. Confirmation

Review your preferences summary, then:
- **Edit**: Go back to modify your answers
- **Generate Report**: Start the workflow execution

### 4. Execution View

The interface splits into two panels:

#### Left Panel (60%): Workflow Workspace
Contains tabs for:
- **DAG View**: Visual representation of workflow steps with status indicators
- **Console**: Live execution logs
- **Files**: Generated files and outputs
- **Metrics**: Cost and performance tracking

#### Right Panel (40%): Three Monitoring Tabs

**Console Tab:**
- Real-time execution logs
- Progress updates
- File creation notifications

**Plan Tab:**
- Execution plan breakdown
- Step-by-step task list
- Status for each step (pending/running/completed/failed)

**Results Tab:**
- Generated report preview
- Download button
- File location information

### 5. Plan Review (HITL Stage 2)

After the planning phase, you'll see an approval dialog:

**Plan Context:**
- Generated execution plan
- Number of steps
- Task breakdown

**Actions:**
- **Feedback**: Provide optional comments
- **Modifications**: Suggest changes if rejecting
- **Reject**: Stop execution and provide modifications
- **Approve & Continue**: Proceed with the plan

### 6. Execution Monitoring

Watch real-time progress:
- DAG nodes change color (gray → blue → green/red)
- Console shows live output
- Plan tab updates step status
- Results tab shows "Processing..."

### 7. Post-Execution Review (HITL Stage 3)

When execution completes, a dialog appears:

**Report Status:**
- ✅ Workflow completed
- 📄 Report location
- 💾 File information

**Options:**

**Done:** Accept the report as-is
- Close dialog
- View report in Results tab
- Download from Files tab

**Regenerate with Modifications:**
1. Enter modification requests in the text area
   - Example: "Add more technical details about the implementations"
   - Example: "Include more research papers on reinforcement learning"
   - Example: "Focus more on enterprise applications"
2. Click "Regenerate with Modifications"
3. Workflow restarts with your feedback incorporated
4. Base prompt structure remains intact

## UI Features

### Connection Status Indicator
- **Green dot (pulsing)**: Connected to workflow engine
- Shows in execution view header

### Stop Button
- Available during execution
- Immediately stops the workflow
- Preserves partial progress

### Three-Tab Interface (Right Panel)

**Console Tab (Blue):**
- Code icon
- Real-time logs
- Scrollable output

**Plan Tab (Purple):**
- File icon
- Execution plan
- Step statuses

**Results Tab (Green):**
- Sparkles icon
- Generated report
- Download/view options

## Report Structure

The generated report includes:

1. **Executive Summary**: High-level overview
2. **Key Highlights**: Top 5 impactful stories
3. **Research & Innovation**: 5 significant papers from ArXiv
4. **Product Launches & Tools**: 5 major releases
5. **Technical Breakthroughs**: 5 items per selected topic
6. **Industry & Business News**: 5 major developments
7. **Trends & Strategic Implications**: Key insights
8. **Quick Reference Table**: All items in tabular format

Each item includes:
- Comprehensive summary (3-4 sentences)
- Working source links (no placeholders)
- Publication dates
- Business and technical context
- Impact analysis

## File Management

### Viewing Generated Files

1. Go to left panel workspace
2. Click "Files" tab
3. View all generated files with:
   - File names
   - Sizes
   - Creation times
   - Download buttons

### Downloading the Report

**Option 1: From Results Tab**
1. Click Results tab (right panel)
2. Click "Download" button
3. Report saves as `ai-weekly-report-YYYY-MM-DD-to-YYYY-MM-DD.md`

**Option 2: From Files Tab**
1. Click Files tab (left panel)
2. Find report file
3. Click download icon

## Advanced Features

### Approval Configuration

The workflow uses HITL with:
- **Approval Mode**: `after_planning`
- **Timeout**: None (waits indefinitely)
- **Feedback Required**: On rejection only
- **Manual Control**: Enabled

### Model Configuration

Default models used:
- **Planner**: gpt-4o
- **Researcher**: gpt-4.1-2025-04-14
- **Engineer**: gpt-4o
- **Plan Reviewer**: o3-mini-2025-01-31
- **Formatter**: o3-mini-2025-01-31

### Work Directory

Reports are saved to:
```
~/cmbagent_workdir/ai-weekly_[timestamp]_[id]/
```

## Troubleshooting

### Dialog Not Appearing
- Check WebSocket connection (green indicator)
- Verify console for errors
- Refresh page and try again

### Plan Not Showing
- Wait for planning phase to complete
- Check Console tab for progress
- Verify DAG data is being received

### Report Not Generated
- Check Console for error messages
- Verify API keys are configured
- Check work directory permissions
- Review file tracking in Files tab

### Connection Lost
- WebSocket will attempt to reconnect
- Approval state is persisted in database
- Can resume after reconnection

## Best Practices

1. **Be Specific in Context Enrichment**
   - Provide clear focus areas
   - Specify exact requirements
   - Mention any constraints

2. **Review Plans Carefully**
   - Check step breakdown
   - Verify task alignment
   - Provide feedback if needed

3. **Monitor Execution**
   - Watch Console for progress
   - Check DAG for step status
   - Note any warnings

4. **Iterative Refinement**
   - Use post-execution modifications
   - Be specific about changes
   - Can regenerate multiple times

## Keyboard Shortcuts

- `Esc`: Close open dialog (context enrichment, confirmation, approval)
- `Tab`: Navigate between input fields
- `Enter`: Submit form (in text inputs)

## Support

For issues or questions:
1. Check console output for errors
2. Review WebSocket events in browser DevTools
3. Check backend logs
4. Refer to [AI_WEEKLY_HITL_IMPLEMENTATION.md](./AI_WEEKLY_HITL_IMPLEMENTATION.md)
5. Create an issue with reproduction steps

## Example Workflow

1. Select dates: 2026-01-20 to 2026-01-27
2. Choose topics: LLM, CV
3. Select sources: ArXiv, GitHub, Tech Blogs
4. Style: Detailed
5. Click "Generate Weekly Report"
6. Answer enrichment questions:
   - Characteristics: "Focus on practical implementations"
   - Focus: "State-of-the-art models and real-world deployments"
   - Depth: "Include code examples and architecture details"
   - Business: "Yes, emphasize enterprise applications"
7. Review and confirm
8. Approve generated plan
9. Monitor execution in real-time
10. When complete, review report
11. If needed, request modifications: "Add more examples from healthcare AI"
12. Download final report

## Next Steps

After generating your report:
- Share with your team
- Archive in knowledge base
- Schedule regular generation
- Customize for different audiences
- Integrate with CI/CD pipelines

---

For technical implementation details, see [AI_WEEKLY_HITL_IMPLEMENTATION.md](./AI_WEEKLY_HITL_IMPLEMENTATION.md)
