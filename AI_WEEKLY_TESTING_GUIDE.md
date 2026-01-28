# AI Weekly HITL - Quick Start & Testing Guide

## Testing the End-to-End AI Weekly Workflow

This guide provides step-by-step instructions for testing the complete Human-in-the-Loop AI Weekly Report workflow.

## Prerequisites

1. **Backend Running**
   ```bash
   cd backend
   python -m uvicorn main:app --reload --port 8000
   ```

2. **Frontend Running**
   ```bash
   cd cmbagent-ui
   npm run dev
   ```

3. **Environment Variables**
   Make sure these are set in your `.env` file:
   ```
   OPENAI_API_KEY=your_key_here
   ANTHROPIC_API_KEY=your_key_here (optional)
   ```

4. **Database**
   The system will automatically create SQLite database if not exists.

## Test Scenario: Complete AI Weekly Workflow

### Step 1: Navigate to AI Weekly
1. Open http://localhost:3000
2. Click on "Tasks" in navigation
3. Select "AI Weekly Report"

### Step 2: Configure Report
Configure the following:
- **Date From**: 2026-01-20
- **Date To**: 2026-01-27
- **Topics**: Select "LLM" and "Computer Vision"
- **Sources**: Select all (ArXiv, GitHub, Tech Blogs)
- **Report Style**: "Detailed"

Click "Generate Weekly Report"

**Expected Result**: Context enrichment dialog appears

### Step 3: Context Enrichment (HITL Stage 1)
Answer the 4 questions:

**Question 1: Report Characteristics**
```
Focus on practical implementations and real-world applications
suitable for technical leaders
```

**Question 2: Focus Areas**
```
State-of-the-art language models, vision transformers,
and multimodal AI systems
```

**Question 3: Technical Depth**
```
Include high-level architecture descriptions but avoid
low-level implementation details
```

**Question 4: Business Context**
```
Yes, emphasize enterprise readiness, scalability,
and ROI considerations
```

**Optional Fields**:
- Specific Focus: "Healthcare AI, Financial Services"
- Exclude Topics: "Gaming AI"

Click "Continue"

**Expected Result**: Confirmation dialog appears with summary

### Step 4: Confirmation
Review the enriched prompt summary.

Click "Generate Report"

**Expected Result**:
- View switches to execution mode
- Left panel shows DAG workspace
- Right panel shows 3 tabs (Console, Plan, Results)
- Console tab active by default
- WebSocket connects (green indicator)

### Step 5: Monitor Planning Phase
Watch the Console tab:
```
✅ Task created: ai-weekly_...
📅 Date Range: 2026-01-20 to 2026-01-27
🏷️  Topics: llm, cv
📰 Sources: arxiv, github, blogs
🎯 Enhanced with user context
🚀 Connecting to workflow engine with HITL enabled...
```

Watch the DAG tab:
- Planning node turns blue (running)
- Then turns yellow (waiting for approval)

**Expected Result**: Plan approval dialog appears after ~30-60 seconds

### Step 6: Plan Review (HITL Stage 2)
The approval dialog shows:
- Title: "Approval Required"
- Plan context with generated steps
- Two text areas for feedback

**Test Case A: Approve Plan**
1. Leave feedback blank or add: "Looks good, proceed"
2. Click "Approve & Continue"

**Expected Result**:
- Dialog closes
- Console shows: "✅ Plan approved, continuing execution..."
- DAG nodes start executing (blue → green)
- Plan tab shows steps being executed

**Test Case B: Reject Plan** (Alternative test)
1. Add modifications: "Add more focus on open-source tools"
2. Click "Reject"

**Expected Result**:
- Workflow stops
- Console shows: "❌ Plan rejected"
- Can return to config and restart

### Step 7: Monitor Execution
Watch real-time progress:

**Console Tab**: 
- Shows agent messages
- Tool calls (web search, arxiv queries)
- File operations
- Progress updates

**Plan Tab**:
- Each step shows status
- Completed steps turn green
- Currently executing step is blue

**DAG Workspace (Left Panel)**:
- Switch to "DAG View" tab
- Visual flow shows step progression
- Click nodes to see details
- Switch to "Files" tab to see generated files
- Switch to "Metrics" to see cost tracking

**Expected Duration**: 5-15 minutes depending on complexity

### Step 8: Completion
Watch for completion indicators:
```
✅ Task execution completed in X seconds
```

**Expected Results**:
- All DAG nodes turn green
- Post-execution dialog appears automatically
- Results tab populated with report info

### Step 9: Post-Execution Review (HITL Stage 3)
The post-execution dialog shows:
- ✅ "Report Generated Successfully!"
- Report location information
- Modification request text area
- Two buttons: "Done" and "Regenerate with Modifications"

**Test Case A: Accept Report**
1. Click "Done"

**Expected Result**:
- Dialog closes
- Can view report in Results tab
- Can download from Files tab

**Test Case B: Request Modifications**
1. Enter modification request:
   ```
   Add more examples of practical implementations.
   Include cost comparisons between different models.
   Add a section on deployment strategies.
   ```
2. Click "Regenerate with Modifications"

**Expected Result**:
- Dialog closes
- Console clears
- New workflow starts with modifications
- Goes through same HITL stages again

### Step 10: View and Download Report
**Option 1: Results Tab**
- Click Results tab (right panel)
- View report summary
- Click "Download" or "View Location"

**Option 2: Files Tab**
- Click Files tab (left panel workspace)
- Find `ai_weekly_report_2026-01-20_to_2026-01-27.md`
- Click download icon

## Verification Checklist

Use this checklist to verify all features work:

### Configuration Phase
- [ ] Can select date range
- [ ] Can toggle topics (all 6)
- [ ] Can toggle sources (all 3)
- [ ] Can select report style
- [ ] Generate button enables/disables correctly
- [ ] Error messages show for invalid input

### Context Enrichment
- [ ] 4 questions appear correctly
- [ ] Can type in all text areas
- [ ] Optional fields work
- [ ] Cancel returns to config
- [ ] Continue shows confirmation
- [ ] Confirmation shows enriched prompt
- [ ] Edit button returns to questions
- [ ] Generate Report starts workflow

### Execution Monitoring
- [ ] WebSocket connects (green indicator)
- [ ] Console shows live output
- [ ] DAG nodes update in real-time
- [ ] Plan tab shows steps
- [ ] Results tab shows "Processing..."
- [ ] Can switch between tabs smoothly
- [ ] Stop button works during execution

### Plan Approval
- [ ] Dialog appears after planning
- [ ] Shows plan context
- [ ] Can enter feedback
- [ ] Can enter modifications
- [ ] Reject stops workflow
- [ ] Approve continues workflow
- [ ] Dialog closes after response

### Post-Execution
- [ ] Dialog appears after completion
- [ ] Shows success message
- [ ] Can enter modification request
- [ ] Done button closes dialog
- [ ] Regenerate button starts new workflow
- [ ] Regenerate includes modifications

### Results and Files
- [ ] Results tab shows report info
- [ ] Can view report location
- [ ] Files tab shows generated files
- [ ] Can download report
- [ ] Report filename correct
- [ ] Report content matches requirements

## Troubleshooting

### Dialog Not Appearing
**Symptom**: Approval or post-execution dialog doesn't show

**Checks**:
1. Check browser console for JavaScript errors
2. Verify WebSocket connection (should see green indicator)
3. Check backend console for approval events
4. Try refreshing page and restarting workflow

**Fix**: 
- Clear browser cache
- Restart both frontend and backend
- Check database permissions

### WebSocket Connection Failed
**Symptom**: Red "Disconnected" or no connection indicator

**Checks**:
1. Backend is running on correct port (8000)
2. No firewall blocking WebSocket connections
3. Check backend logs for connection errors

**Fix**:
```bash
# Restart backend
cd backend
python -m uvicorn main:app --reload --port 8000

# Check if port is available
lsof -i :8000
```

### Approval Times Out
**Symptom**: Workflow stops with timeout error

**Checks**:
1. Check `approval_config.timeout_seconds` setting
2. Database connection status

**Fix**:
- Current config has no timeout (waits indefinitely)
- If modified, increase timeout or set to `None`

### Report Not Generated
**Symptom**: Workflow completes but no report file

**Checks**:
1. Check Console tab for file save confirmation
2. Check work directory permissions
3. Verify API keys are valid
4. Check backend logs for errors

**Fix**:
```bash
# Check work directory
ls -la ~/cmbagent_workdir/

# Set permissions
chmod 755 ~/cmbagent_workdir/

# Verify API key
echo $OPENAI_API_KEY
```

### Plan Tab Empty
**Symptom**: Plan tab shows "Plan will appear here"

**Checks**:
1. Wait for planning phase to complete
2. Check if DAG data is being received
3. Browser console for data errors

**Fix**:
- Plan appears after planning node completes
- If still empty, check `dagData.nodes` in React DevTools

## Advanced Testing

### Test Error Recovery
1. Start workflow
2. During execution, kill backend
3. Restart backend
4. Check if workflow can resume

**Expected**: Approval state persisted, can resume after reconnection

### Test Multiple Users
1. Open two browser windows
2. Start workflows with different task IDs
3. Verify each gets own approval dialogs
4. Check no cross-contamination

**Expected**: Each workflow independent

### Test Modification Iterations
1. Complete workflow
2. Request modifications
3. Approve plan again
4. Request more modifications
5. Repeat 3-4 times

**Expected**: Can iterate indefinitely

### Performance Testing
1. Note execution time for baseline
2. Request modifications with "Add 10 more papers per topic"
3. Compare execution time

**Expected**: Proportional increase in time

## Success Criteria

The workflow is working correctly if:
1. ✅ All 3 HITL stages appear and function
2. ✅ Real-time monitoring works throughout
3. ✅ Report is generated with correct content
4. ✅ Modifications can be requested and applied
5. ✅ Files are accessible and downloadable
6. ✅ No JavaScript or Python errors
7. ✅ WebSocket connection stable
8. ✅ Database operations complete
9. ✅ All UI elements responsive
10. ✅ Can complete multiple workflows in sequence

## Report Validation

After generation, verify report contains:
- [ ] Executive Summary section
- [ ] Key Highlights (5 items)
- [ ] Research & Innovation (5 items)
- [ ] Product Launches (5 items)
- [ ] Technical Breakthroughs per topic
- [ ] Industry News (5 items)
- [ ] Trends & Implications
- [ ] Quick Reference Table
- [ ] All links are working URLs (not placeholders)
- [ ] Dates match requested range
- [ ] Topics match selected categories
- [ ] Style matches request (concise/detailed/technical)
- [ ] Context enrichment reflected in content

## Next Steps After Testing

Once workflow is verified:
1. Document any issues found
2. Test edge cases (empty inputs, very long date ranges)
3. Performance profiling
4. User acceptance testing
5. Production deployment planning

## Support

If issues persist:
1. Collect logs (browser console + backend)
2. Note exact reproduction steps
3. Check [AI_WEEKLY_USER_GUIDE.md](./AI_WEEKLY_USER_GUIDE.md)
4. Review [AI_WEEKLY_HITL_IMPLEMENTATION.md](./AI_WEEKLY_HITL_IMPLEMENTATION.md)
5. Create issue with all information

---

**Happy Testing!** 🚀
