# 🤖 Autonomous AI Agency System — Full Architecture

## Vision
A 24/7 autonomous agency that runs like a real business:
- Finds clients automatically
- Sends outreach & follows up
- Generates audit reports
- Builds & deploys automations
- Monitors everything
- Reports to Abdo for approvals

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ABDO (Human-in-the-Loop)                     │
│              Approves / Rejects / Strategic Decisions            │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Telegram
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    3MY (Chief of Staff)                          │
│         Receives Abdo's commands, coordinates everything         │
│              Uses OpenRouter free models + OpenClaw              │
└──────────────────────────┬──────────────────────────────────────┘
                           │ sessions_spawn / cron
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ORCHESTRATOR AGENT                             │
│   Manages workflow state, routes tasks, tracks everything        │
│         State: agents/orchestrator/state.json                    │
│         DB: outputs/agency-leads.db (SQLite)                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   ACQUISITION │  │   DELIVERY   │  │  OPERATIONS  │          │
│  │    TEAM       │  │    TEAM      │  │    TEAM      │          │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤          │
│  │ • Prospector │  │ • Auditor    │  │ • Monitor    │          │
│  │ • Outreach   │  │ • Builder    │  │ • Tracker    │          │
│  │ • FollowUp   │  │ • Integrator │  │ • Reporter   │          │
│  │ • Closer     │  │ • Tester     │  │ • Approver   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     n8n (Workflow Engine)                        │
│   All automations run here. Triggers, actions, integrations.     │
│   API: http://127.0.0.1:5678                                    │
├─────────────────────────────────────────────────────────────────┤
│  Workflows:                                                     │
│  • new-lead-intake → scrape → audit → email → notify           │
│  • outreach-sequence → LinkedIn → email → follow-up            │
│  • client-onboarding → build → test → deploy → monitor         │
│  • daily-report → collect metrics → send to Abdo               │
│  • health-check → verify all services → alert if down          │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DATA LAYER                                    │
│  • SQLite: agency-leads.db (leads, deals, pipeline)            │
│  • MongoDB: analytics, logs, metrics                           │
│  • File system: outputs/, reports/, templates/                  │
└─────────────────────────────────────────────────────────────────┘
```

## Agent Roster (8 Specialized Agents)

### Acquisition Team
1. **Prospector** — Finds new leads from LinkedIn, Product Hunt, Crunchbase
   - Runs: Daily via cron
   - Output: New leads added to agency-leads.db
   - Tools: web_search, web_fetch, LinkedIn scraping

2. **Outreach Agent** — Sends personalized LinkedIn messages & cold emails
   - Runs: Daily via cron (checks for leads in "ready_to_contact" status)
   - Output: Messages sent, status updated in DB
   - Tools: Gmail API (gog CLI), LinkedIn API or manual queue

3. **Follow-Up Agent** — Tracks responses, sends follow-ups on schedule
   - Runs: Every 3 days via cron
   - Output: Follow-ups sent, lead status updated
   - Tools: Gmail API, agency-leads.db

4. **Closer** — Handles interested leads, sends proposals, negotiates
   - Runs: Triggered when lead status = "interested"
   - Output: Proposal sent, deal status updated
   - Tools: proposal template, Gmail API

### Delivery Team
5. **Auditor** — Generates AI audit reports for prospects
   - Runs: Triggered by form submission or manual request
   - Output: Professional audit report (HTML + MD)
   - Tools: web_fetch, OpenRouter AI, template engine

6. **Builder** — Creates n8n workflows for client automations
   - Runs: Triggered when deal status = "signed"
   - Output: n8n workflow JSON, deployed to n8n
   - Tools: n8n API, OpenRouter AI

7. **Integrator** — Connects APIs, webhooks, third-party tools
   - Runs: Works with Builder during delivery
   - Output: Connected integrations, tested workflows
   - Tools: n8n API, curl, API testing

8. **Tester** — QA for all automations before client delivery
   - Runs: After Builder + Integrator finish
   - Output: Test report, bug list, approval/reject
   - Tools: n8n API, automated test scripts

### Operations Team
9. **Monitor** — 24/7 watchdog for all services and client automations
   - Runs: Every 30 min via cron
   - Output: Health report, alerts if issues
   - Tools: systemctl, n8n API, curl

10. **Tracker** — Tracks all metrics, pipeline value, revenue
    - Runs: Daily via cron
    - Output: Daily metrics saved to MongoDB
    - Tools: agency-leads.db, MongoDB

11. **Reporter** — Generates daily/weekly reports for Abdo
    - Runs: Daily at 7 AM Egypt time via cron
    - Output: Telegram message with key metrics
    - Tools: agency-leads.db, MongoDB, Telegram

12. **Approver** — Manages Abdo's approval queue
    - Runs: When agent needs human decision
    - Output: Sends approval request to Abdo, waits for response
    - Tools: Telegram, state.json

## n8n Workflows (Built on n8n)

### Workflow 1: New Lead Intake
```
Form Submission → Scrape Website → Generate Audit → Send Email → Notify 3my
```
- Trigger: Webhook (from form.html)
- Steps:
  1. Receive form data (name, email, company, website)
  2. Scrape website for business info
  3. Call OpenRouter API to generate audit analysis
  4. Generate HTML audit report
  5. Send email to prospect with audit attached
  6. Add lead to agency-leads.db
  7. Notify 3my via Telegram

### Workflow 2: Outreach Sequence
```
Lead (status=new) → Research → Personalize → Send LinkedIn → Wait 3d → Send Email → Wait 7d → Follow-up
```
- Trigger: Cron (daily at 9 AM Egypt time)
- Steps:
  1. Query agency-leads.db for leads ready for outreach
  2. Research each lead (web search, company info)
  3. Generate personalized message (OpenRouter)
  4. Send via LinkedIn or queue for manual review
  5. Update lead status + timestamp
  6. Schedule follow-up

### Workflow 3: Client Onboarding
```
Deal Signed → Kickoff Call → Build Automation → Test → Deploy → Monitor
```
- Trigger: Manual (when Abdo confirms deal)
- Steps:
  1. Create client folder in /outputs/clients/{company}/
  2. Generate project plan
  3. Build n8n workflows (Builder agent)
  4. Connect APIs (Integrator agent)
  5. Run tests (Tester agent)
  6. Deploy to production
  7. Start monitoring

### Workflow 4: Daily Report
```
Collect Metrics → Generate Report → Send to Abdo
```
- Trigger: Cron (daily at 5 AM Egypt time = 7 AM Cairo)
- Steps:
  1. Count new leads, responses, deals
  2. Calculate pipeline value
  3. Check service health
  4. Generate summary
  5. Send via Telegram

### Workflow 5: Health Check
```
Check Services → Check n8n Workflows → Check Disk/RAM → Alert if Issues
```
- Trigger: Cron (every 30 min)
- Steps:
  1. Check all services (openclaw, n8n, caddy, cloudflared, mongodb)
  2. Check n8n workflow execution status
  3. Check system resources
  4. Alert Abdo if critical issues

## Database Schema (SQLite — agency-leads.db)

```sql
CREATE TABLE leads (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    company TEXT NOT NULL,
    website TEXT,
    niche TEXT,           -- ecommerce, agency, saas
    status TEXT DEFAULT 'new',
    -- Statuses: new → researched → contacted → responded → interested → proposal_sent → signed → active_client
    source TEXT,          -- form, linkedin, cold_email, referral
    score INTEGER DEFAULT 0,  -- 0-100 lead score
    estimated_value INTEGER,  -- estimated monthly value
    first_contact_date TEXT,
    last_contact_date TEXT,
    next_action TEXT,
    next_action_date TEXT,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE outreach_log (
    id INTEGER PRIMARY KEY,
    lead_id INTEGER,
    channel TEXT,         -- linkedin, email, phone
    direction TEXT,       -- outbound, inbound
    message_type TEXT,    -- connection, value, email, follow_up
    content TEXT,
    sent_at TEXT,
    response_received BOOLEAN DEFAULT 0,
    response_content TEXT,
    response_at TEXT,
    FOREIGN KEY (lead_id) REFERENCES leads(id)
);

CREATE TABLE deals (
    id INTEGER PRIMARY KEY,
    lead_id INTEGER,
    package TEXT,         -- starter, growth, scale
    monthly_value INTEGER,
    setup_fee INTEGER,
    status TEXT DEFAULT 'negotiating',
    -- Statuses: negotiating → signed → active → churned
    signed_date TEXT,
    start_date TEXT,
    notes TEXT,
    FOREIGN KEY (lead_id) REFERENCES leads(id)
);

CREATE TABLE tasks (
    id INTEGER PRIMARY KEY,
    agent TEXT,           -- which agent spawned this
    type TEXT,            -- outreach, audit, build, test, deploy
    status TEXT DEFAULT 'pending',
    -- Statuses: pending → in_progress → completed → failed
    lead_id INTEGER,
    deal_id INTEGER,
    input TEXT,           -- JSON
    output TEXT,          -- JSON
    error TEXT,
    created_at TEXT,
    started_at TEXT,
    completed_at TEXT,
    FOREIGN KEY (lead_id) REFERENCES leads(id),
    FOREIGN KEY (deal_id) REFERENCES deals(id)
);
```

## Approval System (Human-in-the-Loop)

Abdo approves/rejects via Telegram:

| Action | Who Triggers | Abdo's Options |
|--------|-------------|----------------|
| Send outreach to new lead | Outreach Agent | Approve / Reject / Edit |
| Send proposal to interested lead | Closer Agent | Approve / Reject / Modify pricing |
| Start building for new client | Builder Agent | Approve scope / Reject |
| Deploy automation to production | Tester Agent | Approve / Request changes |
| Monthly report | Reporter | Auto-sent, no approval needed |
| Health alert | Monitor | Auto-sent if critical |

### Approval Flow:
```
Agent completes task → Creates approval request → Sends to Abdo via Telegram
→ Abdo replies "approve" / "reject [reason]" / "edit [changes]"
→ Agent proceeds based on response
→ If no response in 24h → Escalate / Auto-approve (configurable)
```

## Implementation Phases

### Phase 1: Foundation (Days 1-3) — NOW
- [x] GitHub repo with all docs
- [x] 3 practice automations
- [x] Target prospect list (50 leads)
- [x] Outreach templates
- [ ] Set up agency-leads.db with schema
- [ ] Create n8n workflows (5 core workflows)
- [ ] Set up cron jobs for all agents

### Phase 2: Agent Deployment (Days 4-7)
- [ ] Deploy all 8 agents as cron-triggered sub-agents
- [ ] Set up approval system
- [ ] Test full outreach sequence end-to-end
- [ ] Test lead intake → audit → email pipeline

### Phase 3: Go Live (Days 8-14)
- [ ] Start daily outreach (5-10 leads/day)
- [ ] Monitor and optimize
- [ ] First client calls
- [ ] First proposals sent

### Phase 4: Scale (Days 15-30)
- [ ] Increase outreach volume
- [ ] Build first client automation
- [ ] First revenue
- [ ] Optimize based on data
