---
name: tech-intelligence-radar
description: Verification-gated emerging tech discovery, multi-source signal scouting (GitHub, Hacker News, arXiv, Reddit), and live API auditing for market and technology intelligence.
version: 1.2.0
author: sreepranav99
tags:
  - market-intelligence
  - tech-radar
  - research
  - mcp
  - verification-gated
  - github-scout
  - fact-checking
---

# Tech Intelligence Radar Skill

An autonomous agent research skill that systematically scouts breakout technologies across developer ecosystems, filters noise, computes velocity/momentum metrics, and enforces a **verification-gated auditing barrier** by probing live APIs.

---

## When to Activate This Skill

Activate this skill whenever the user asks to:
* Research emerging, breakout, or trending open-source projects or developer tools.
* Formulate a Thoughtworks-style Technology Radar (Adopt, Trial, Assess, Hold) for any domain.
* Audit claimed GitHub repositories or tech releases against live endpoints (stars, forks, active commit cadence, licenses).
* Cross-reference community discussions across Hacker News, arXiv preprints, and developer subreddits (r/LocalLLaMA).
* Produce a publication-ready executive briefing and interactive visual radar.

---

## 1. Direct API Endpoints & Fallback Strategy

When executing queries, prefer direct public API reads. Be aware of standard rate limits:

| Source | Direct Endpoint | Unauthenticated Limit |
| :--- | :--- | :--- |
| **GitHub Search** | `https://api.github.com/search/repositories?q={query}&sort=stars&order=desc` | 10 req/min |
| **GitHub Repo** | `https://api.github.com/repos/{owner}/{repo}` (and `/releases`) | 60 req/hr |
| **Hacker News** | `https://hn.algolia.com/api/v1/search_by_date?query={query}&tags=story&numericFilters=created_at_i>{timestamp},points>={min_points}` | ~10,000 req/hr |
| **arXiv Preprints** | `https://export.arxiv.org/api/query?search_query=all:{query}&sortBy=submittedDate&sortOrder=descending` | 1 req/3s |
| **Reddit** | `https://www.reddit.com/r/LocalLLaMA/search.json?q={query}&restrict_sr=1&sort=relevance&t=month` | Requires custom User-Agent |

### Fallback & Status Labeling:
* **Verified:** Call a metric or link `Verified` **only after a successful direct API/HTTP read** (HTTP 200).
* **Unconfirmed:** If a direct read fails (e.g. rate-limited HTTP 403/429 or refused request), fall back to web search or search snippets, and **strictly mark the result as `Unconfirmed`**.

---

## 2. 5-Stage Verification-Gated Workflow

### Stage 1: Strategy & Query Decomposition
1. Deconstruct the user's domain (e.g. `"Model Context Protocol"`, `"Local LLM Inference"`, `"AI Agents"`) into targeted queries across code hosts, discussion forums, and research archives:
   * **GitHub:** Target active repositories created or pushed in the last 7–30 days.
   * **Hacker News:** Target recent releases, launches, and discussions (`points >= 10`).
   * **arXiv:** Target architectural preprints and foundational papers.
   * **Reddit:** Target practitioner benchmarks in `r/LocalLLaMA`.

### Stage 2: Multi-Source Harvesting
Gather candidate signals across all 4 platforms via available FastMCP tools or direct HTTP requests.

### Stage 3: Rigorous Mathematical Scoring

#### A. Velocity Score (1.0 to 10.0)
Measures traction momentum:
* **Metric:** Stars gained per day since the last saved scan. On a first run: `stars / max(7, age_in_days)`.
* **Velocity Bands:**
  * $\ge 100$ stars/day $\rightarrow$ **9.5**
  * $\ge 30$ stars/day $\rightarrow$ **8.5**
  * $\ge 10$ stars/day $\rightarrow$ **7.5**
  * $\ge 3$ stars/day $\rightarrow$ **6.5**
  * Below 3 stars/day $\rightarrow$ **4.0**
* **Discussion Velocity (HN/Reddit):**
  * Hacker News: $\min(9.2, (\text{points} \times 0.015) + (\text{comments} \times 0.025) + 4.5)$
  * Reddit: $\min(9.0, (\text{score} \times 0.02) + (\text{comments} \times 0.03) + 4.5)$
  * arXiv: **7.4** baseline preprint momentum.

#### B. Novelty Score (1.0 to 10.0)
Measures architectural freshness:
* **Base score:** Start at **5.0**.
* **Age Boost:**
  * Add **+2.0** if repo/announcement is under 30 days old ($<30\text{d}$).
  * Add **+1.0** if under 90 days old ($<90\text{d}$).
* **Architectural Marker Boost:** Add **+1.5** once if title/summary contains markers such as `mcp`, `autonomous`, `agentic`, `orchestration`, or `zero-shot`.
* **Well-Known Cap:** Maximum **3.0** if over 12 months old with more than 20,000 stars (prevents mature giants like LangChain or Ollama from dominating emerging novelty rankings).

### Stage 4: Live Verification & Star Check Gate
Never include unverified claims:
1. **Endpoint Reachability:** Verify URL returns HTTP 200. Exclude archived, abandoned, or 404 repositories.
2. **Tightened Star Tolerance:**
   * Record each count with its timestamp and source.
   * Apply a 10% tolerance *only* to counts taken within 48 hours of each other.
   * For older claims ($>48\text{h}$), fail verification only if the current live count is more than 10% *lower* than claimed.
3. **Maturity Check:** Inspect repository age, license, and `/releases` tag history.

### Stage 5: Thoughtworks Maturity Rings
Maturity decides the rings. Apply these rules strictly from top to bottom (first matching rule applies):

| Ring | Rule / Criteria |
| :--- | :--- |
| **HOLD** | Unexplained star spike/pattern, unresolved serious security issue, archived, or no activity for $>90$ days. |
| **ASSESS (Capped)** | Pre-release, developer preview, or unconfirmed metrics. |
| **ADOPT** | Velocity $\ge 7.0$, stable release (v1.0+ or tagged release history), at least 6 months old, and confirmed hands-on use. |
| **TRIAL** | Velocity $\ge 7.0$ OR Novelty $\ge 7.0$ (breakout active projects worth prototyping). |
| **ASSESS** | Velocity $\ge 5.5$ (emerging signals worth monitoring; anything lower is omitted). |

---

## 3. Output Formats

### A. Markdown Executive Briefing (`briefing.md`)
Includes:
1. **Executive Pulse:** 3 punchy bullet points on dominant architectural patterns and velocity outlook.
2. **Deep Dives (Top 8 Items):**
   * **What It Actually Is:** Plain-English explanation of mechanics.
   * **Why You Should Care:** Engineering architectural trade-off and production use case.
   * **Verified Traction:** Live verified star count, forks, maintainer commit cadence, and velocity badges.
   * **Audit Proof:** Verification status (`Verified Live` or `Unconfirmed Fallback`).
3. **Technology Radar Matrix Table:** Summary table comparing all evaluated candidates.

### B. Interactive Visual SVG Radar (`radar.html`)
When completing a scan, generate a standalone, self-contained HTML file featuring an interactive circular SVG radar with 4 concentric rings (**Adopt**, **Trial**, **Assess**, **Hold**), interactive hovering tooltips, and category legend.

---

## 4. MCP Server Integration (Optional)

This package includes a production-grade FastMCP server (`src/radar`) providing 10 internal tools (`github_verify_repo`, `hn_search_discussions`, `web_extract_markdown`, `arxiv_search_papers`, `db_persist_intel`, `db_get_velocity_delta`).

To connect your agent directly to the included FastMCP server:
```json
{
  "mcpServers": {
    "tech-radar": {
      "command": "python",
      "args": ["-m", "radar.cli", "--serve-mcp"],
      "env": {
        "PYTHONPATH": "./src"
      }
    }
  }
}
```
Run `pip install -e .` in the project root to install dependencies.
