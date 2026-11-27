# 📡 Autonomous Market & Tech Intelligence Radar

An autonomous, multi-agent intelligence pipeline combining the **Model Context Protocol (MCP)** with a **zero-hallucination verification loop** to scout, filter, fact-check, and synthesize actionable briefings on emerging technologies.

---

## 🚀 Effortless 1-Click & Simple Commands

### Option A: 1-Click Launch (No Terminal Commands Required)
Simply double-click **`start.bat`** in Windows File Explorer!
* Automatically starts the Radar server
* Automatically launches the visual interactive Thoughtworks-style Radar in your default browser at `http://127.0.0.1:8844`
* You can type any new topic directly into the browser search bar and click **Run Swarm ⚡**!

---

### Option B: Simple CLI Commands (From Any Terminal)
Because `radar` is installed as a native Windows command, you can run simple, intuitive commands without remembering flags or complex Python paths:

```powershell
# 1. Launch the Web UI in your browser (Default)
radar
# (or in PowerShell/CMD: .\radar.bat or .\start.bat)

# 2. Run an autonomous swarm intelligence scan on any domain
radar "Autonomous Coding Agents"
radar "Rust WebAssembly"

# 3. Daily 8:00 AM IST Morning Briefing & Email
radar test-email         # Test your Gmail SMTP connection with a sample digest
radar morning            # Run the combined morning scan & send briefing to Gmail
radar schedule --install # Register 8:00 AM IST Windows Task Scheduler job
# (Or use .github/workflows/morning_briefing.yml for sleep/shutdown-proof cloud runs at 08:00 IST)

# 4. Open the interactive terminal menu
radar menu

# 5. View tracked technologies and momentum in SQLite database
radar history

# 6. List all connected internal and external MCP servers/tools
radar servers

# 7. Read the latest briefing report in your console
radar latest
```

---

## 🌟 Architecture & Features

* **Strict MCP Decoupling**: All external integrations (GitHub Search API, Hacker News Algolia API, Web Content Scraper, and SQLite persistence) run inside an isolated **FastMCP Server** (`radar-mcp`).
* **Multi-Agent Swarm (Hierarchical Coordinator-Worker)**:
  1. **Coordinator Agent**: Formulates search plans and query matrices from human topics.
  2. **Scout Swarm**: Parallel collectors running concurrent MCP calls across GitHub and Hacker News.
  3. **Signal Analyst Agent**: Deduplicates against historical SQLite records and computes velocity & novelty scores.
  4. **Fact-Checker / Critic Agent (Guardrail)**: Adversarial live auditor that probes live endpoints (verifying repository existence, commit dates, and star counts) to eliminate hallucinations.
  5. **Executive Editor Agent**: Compiles verified items into a structured Markdown briefing and commits intelligence items into SQLite.
* **Persistent Intelligence Base**: Tracks entities over time so yesterday's news isn't repeated.
* **Dual Execution Mode**:
  * Run as a **CLI pipeline** to produce research briefings on demand or on a schedule.
  * Run as a **Standard MCP Server** (`--serve-mcp`) accessible by Claude Desktop, Antigravity, or other MCP hosts.

---

## 🚀 Quickstart & Usage

### 1. Requirements & Setup
Python 3.11+ is required.

```bash
# Clone or navigate to the workspace
cd C:\Users\Admin\.gemini\antigravity\scratch\tech-intelligence-radar

# Install dependencies (already pre-configured)
pip install -e .
```

*(Optional)* Set `GITHUB_TOKEN` in your environment to increase GitHub API rate limits from 10 req/min to 30 req/min:
```bash
set GITHUB_TOKEN=your_personal_access_token
```

---

### 2. Run an Intelligence Cycle

Run an autonomous scan on any technical topic across **GitHub, Hacker News, arXiv, and Reddit**:

```bash
# Autonomous scan
python -m radar.cli "Model Context Protocol agents"

# Interactive Human-in-the-Loop selection (pause & choose candidates to audit)
python -m radar.cli "Autonomous Testing" -i

# Verbose logs with full verification traces
python -m radar.cli "Vector Databases and Rust" -v
```

---

### 3. Review Historical Intelligence & Visual Dashboard

Launch the interactive visual **Thoughtworks-Style Tech Radar** in your browser:
```bash
# In PowerShell / CMD:
.\radar.bat --ui
```
* Renders an interactive circular SVG radar with concentric rings (**Adopt**, **Trial**, **Assess**, **Hold**).
* Click any blip or list item to inspect live verified stats, author notes, and momentum badges.
* Automatically serves live REST data from SQLite on `http://localhost:8844/api/radar-data`.

You can also open the standalone HTML artifact directly in your browser without running a server:
```text
briefings/radar_latest.html
```

View tracked technologies and momentum snapshots in the terminal:
```bash
python -m radar.cli --history
```

Inspect all internal MCP tools and external third-party MCP servers:
```bash
python -m radar.cli --servers
```

Read the latest generated briefing directly in the terminal:
```bash
python -m radar.cli --latest
```

All briefings are also saved as standard Markdown files in:
```text
briefings/briefing_YYYY-MM-DD_<run_id>.md
```

---

### 4. Run as an MCP Server (Host Integration)

You can plug this radar directly into Claude Desktop or any MCP-compliant client by adding it to your `mcpServers` configuration:

```json
{
  "mcpServers": {
    "tech-radar": {
      "command": "python",
      "args": [
        "-m",
        "radar.cli",
        "--serve-mcp"
      ],
      "env": {
        "PYTHONPATH": "C:\\Users\\Admin\\.gemini\\antigravity\\scratch\\tech-intelligence-radar\\src"
      }
    }
  }
}
```

#### Available MCP Tools
* `github_search_trending`: Find repositories matching topics within time windows.
* `github_verify_repo`: Live inspection of stars, forks, and last commit dates.
* `hn_search_discussions`: Query Hacker News developer discussions and stories.
* `web_extract_markdown`: Fetch clean, prompt-injection-safe markdown from web pages.
* `db_persist_intel`: Store structured intelligence records.
* `db_query_history`: Search historical entries for deduplication.
* `db_save_briefing`: Store full briefing records.

#### Available MCP Resources
* `radar://briefings/latest`: Read the latest markdown briefing.
* `radar://entities/tracked`: Query all tracked technologies in JSON.
