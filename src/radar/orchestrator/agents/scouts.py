import asyncio
from typing import List
from radar.orchestrator.agents.base import BaseAgent
from radar.orchestrator.state import RadarState, RawSignal

class GitHubScoutAgent(BaseAgent):
    """Gathers trending and active repositories matching topic queries via MCP."""

    def __init__(self, mcp_client):
        super().__init__(
            name="GitHubScout",
            role="GitHub Open Source Intelligence Gathering",
            mcp_client=mcp_client
        )

    async def execute(self, state: RadarState) -> None:
        plan = state.__dict__.get("_search_plan", {})
        queries = plan.get("github_queries", [state.topic_query])
        
        state.log(f"[{self.name}] Initiating queries across GitHub: {queries}")
        collected: List[RawSignal] = []

        for q in queries:
            repos = await self.mcp.search_github(topic=q, days_back=30, min_stars=20, limit=8)
            for repo in repos:
                collected.append(
                    RawSignal(
                        source_type="github",
                        external_id=repo.get("name", "unknown"),
                        title=f"{repo.get('name')}: {repo.get('description', '')[:80]}",
                        url=repo.get("url", ""),
                        raw_snippet=repo.get("description", ""),
                        metrics={
                            "stars": repo.get("stars", 0),
                            "forks": repo.get("forks", 0),
                            "language": repo.get("language", "Unknown"),
                            "created_at": repo.get("created_at"),
                            "pushed_at": repo.get("pushed_at")
                        }
                    )
                )

        # Deduplicate by URL before adding to state
        existing_urls = {s.url for s in state.raw_signals}
        new_items = 0
        for s in collected:
            if s.url not in existing_urls:
                state.raw_signals.append(s)
                existing_urls.add(s.url)
                new_items += 1

        state.log(f"[{self.name}] Harvested {new_items} unique signals from GitHub.")


class HackerNewsScoutAgent(BaseAgent):
    """Gathers community discussions and releases from Hacker News via MCP."""

    def __init__(self, mcp_client):
        super().__init__(
            name="HackerNewsScout",
            role="Community Discussion & Traction Gathering",
            mcp_client=mcp_client
        )

    async def execute(self, state: RadarState) -> None:
        plan = state.__dict__.get("_search_plan", {})
        queries = plan.get("hn_queries", [state.topic_query])

        state.log(f"[{self.name}] Querying Hacker News discussions for: {queries}")
        collected: List[RawSignal] = []

        for q in queries:
            stories = await self.mcp.search_hackernews(query=q, days_back=14, min_points=10, limit=10)
            for story in stories:
                collected.append(
                    RawSignal(
                        source_type="hackernews",
                        external_id=str(story.get("id", "")),
                        title=story.get("title", "Untitled"),
                        url=story.get("url", ""),
                        raw_snippet=f"HN Story with {story.get('points', 0)} points and {story.get('comments', 0)} comments.",
                        metrics={
                            "points": story.get("points", 0),
                            "comments": story.get("comments", 0),
                            "discussion_url": story.get("discussion_url", ""),
                            "created_at": story.get("created_at", "")
                        }
                    )
                )

        existing_urls = {s.url for s in state.raw_signals}
        new_items = 0
        for s in collected:
            if s.url not in existing_urls:
                state.raw_signals.append(s)
                existing_urls.add(s.url)
                new_items += 1

        state.log(f"[{self.name}] Harvested {new_items} unique signals from Hacker News.")


class ArxivScoutAgent(BaseAgent):
    """Scouts arXiv for scientific research preprints and foundational breakthroughs via MCP."""

    def __init__(self, mcp_client):
        super().__init__(
            name="ArxivScout",
            role="Scientific Research & Preprint Discovery",
            mcp_client=mcp_client
        )

    async def execute(self, state: RadarState) -> None:
        plan = state.__dict__.get("_search_plan", {})
        queries = plan.get("arxiv_queries") or plan.get("primary_topics", [state.topic_query])
        
        state.log(f"[{self.name}] Scouting arXiv preprints for: {queries}")
        collected: List[RawSignal] = []

        for q in queries[:3]:
            papers = await self.mcp.search_arxiv(query=q, limit=6)
            for paper in papers:
                collected.append(
                    RawSignal(
                        source_type="arxiv",
                        external_id=paper.get("id", ""),
                        title=f"Paper: {paper.get('title', '')}",
                        url=paper.get("url", ""),
                        raw_snippet=paper.get("summary", ""),
                        metrics={
                            "authors": paper.get("authors", []),
                            "published": paper.get("published", "")
                        }
                    )
                )

        existing_urls = {s.url for s in state.raw_signals}
        new_items = 0
        for s in collected:
            if s.url not in existing_urls:
                state.raw_signals.append(s)
                existing_urls.add(s.url)
                new_items += 1

        state.log(f"[{self.name}] Harvested {new_items} research papers from arXiv.")


class RedditScoutAgent(BaseAgent):
    """Scouts developer subreddits for organic sentiment and benchmarks via MCP."""

    def __init__(self, mcp_client):
        super().__init__(
            name="RedditScout",
            role="Community Sentiment & Practitioner Discussion Gathering",
            mcp_client=mcp_client
        )

    async def execute(self, state: RadarState) -> None:
        plan = state.__dict__.get("_search_plan", {})
        queries = plan.get("reddit_queries") or plan.get("primary_topics", [state.topic_query])

        state.log(f"[{self.name}] Scouting Reddit (r/LocalLLaMA) discussions for: {queries}")
        collected: List[RawSignal] = []

        for q in queries[:3]:
            posts = await self.mcp.search_reddit(query=q, subreddit="LocalLLaMA", limit=6)
            for post in posts:
                collected.append(
                    RawSignal(
                        source_type="reddit",
                        external_id=str(post.get("id", "")),
                        title=f"Reddit: {post.get('title', '')}",
                        url=post.get("url", ""),
                        raw_snippet=post.get("snippet", ""),
                        metrics={
                            "score": post.get("score", 0),
                            "comments": post.get("comments", 0),
                            "subreddit": post.get("subreddit", "LocalLLaMA")
                        }
                    )
                )

        existing_urls = {s.url for s in state.raw_signals}
        new_items = 0
        for s in collected:
            if s.url not in existing_urls:
                state.raw_signals.append(s)
                existing_urls.add(s.url)
                new_items += 1

        state.log(f"[{self.name}] Harvested {new_items} community threads from Reddit.")


class ScoutPool(BaseAgent):
    """Coordinates and executes all scouts concurrently across all 4 platforms."""

    def __init__(self, mcp_client):
        super().__init__(
            name="ScoutPool",
            role="Parallel Multi-Source Scout Orchestrator",
            mcp_client=mcp_client
        )
        self.gh_scout = GitHubScoutAgent(mcp_client)
        self.hn_scout = HackerNewsScoutAgent(mcp_client)
        self.arxiv_scout = ArxivScoutAgent(mcp_client)
        self.reddit_scout = RedditScoutAgent(mcp_client)

    async def execute(self, state: RadarState) -> None:
        state.log(f"[{self.name}] Launching 4 parallel scout swarms (GitHub, HN, arXiv, Reddit)...")
        await asyncio.gather(
            self.gh_scout.execute(state),
            self.hn_scout.execute(state),
            self.arxiv_scout.execute(state),
            self.reddit_scout.execute(state)
        )
        state.log(f"[{self.name}] Scouting phase complete. Total raw signals: {len(state.raw_signals)}")
