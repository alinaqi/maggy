"""Social API Integration — X/Twitter + Reddit for build-in-public monitoring.

X/Twitter: Search, user lookup, retweet, timeline fetch via API v2.
Reddit: Subreddit monitoring, post search, hot/new posts via asyncpraw.
Unified interface for both platforms.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import AsyncGenerator

import httpx

logger = logging.getLogger(__name__)

# ── API Endpoints ────────────────────────────────────────────────────────
X_API = "https://api.x.com/2"
X_AUTH_URL = "https://api.x.com/oauth2/token"

# Local credential fallback: read Reddit creds from a sibling ideaminer
# checkout when they aren't in the environment. Lets local Maggy reuse
# ideaminer's Reddit app without re-entering keys.
_IDEAMINER_ENV_FILES = [
    Path.home() / "Documents" / "AI-Playground" / "ideaminer" / ".env",
    Path.home() / "Documents" / "AI-Playground" / "ideaminer" / "backend" / ".env",
    Path.home() / "Documents" / "AI-Playground" / "ideaminer" / ".env.local",
]
_ideaminer_env_cache: dict | None = None


def _ideaminer_env() -> dict:
    """Parse Reddit-relevant vars from ideaminer .env files (cached)."""
    global _ideaminer_env_cache
    if _ideaminer_env_cache is None:
        import re
        _ideaminer_env_cache = {}
        for f in _IDEAMINER_ENV_FILES:
            try:
                for line in f.read_text().splitlines():
                    m = re.match(r'\s*([A-Z0-9_]+)\s*=\s*["\']?([^"\'\n]+)', line)
                    if m and m.group(1).startswith("REDDIT_"):
                        _ideaminer_env_cache.setdefault(m.group(1), m.group(2))
            except OSError:
                continue
    return _ideaminer_env_cache


def reddit_cred(key: str) -> str:
    """Resolve a Reddit credential from the environment, then ideaminer."""
    return os.environ.get(key) or _ideaminer_env().get(key, "")


@dataclass
class SocialPost:
    id: str
    platform: str  # x, reddit
    text: str
    author: str = ""
    author_id: str = ""
    created_at: str = ""
    url: str = ""
    metrics: dict = field(default_factory=dict)
    subreddit: str = ""


class SocialMonitor:
    """Unified social media monitoring across X/Twitter and Reddit."""

    def __init__(self, project: str = "maggy"):
        self._project = project
        self._x_token = self._get_x_token()
        self._reddit_client = None
        self._cache = self._load_cache()

    def _get_x_token(self) -> str:
        return os.environ.get("X_BEARER_TOKEN", "")

    def _load_cache(self) -> dict:
        path = Path.home() / ".maggy" / "build-in-public" / "social-cache.json"
        try:
            return json.loads(path.read_text())
        except Exception:
            return {"x": {}, "reddit": {}}

    def _save_cache(self):
        path = Path.home() / ".maggy" / "build-in-public" / "social-cache.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._cache, indent=2))

    # ═══ X/TWITTER ═══════════════════════════════════════════════════════

    async def x_get_user(self, username: str) -> dict | None:
        """Look up a user by @handle. Returns {id, name, username, ...}."""
        if not self._x_token:
            return None
        clean = username.lstrip("@")
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{X_API}/users/by/username/{clean}",
                    headers={"Authorization": f"Bearer {self._x_token}"},
                    params={"user.fields": "description,public_metrics,verified"},
                )
                if resp.status_code == 200:
                    return resp.json().get("data", {})
        except Exception as e:
            logger.debug("X user lookup failed: %s", e)
        return None

    async def x_search(self, query: str, max_results: int = 10) -> list[SocialPost]:
        """Search recent tweets by topic. Returns list of SocialPost."""
        if not self._x_token:
            return []
        try:
            q = f"{query} lang:en -is:retweet"
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{X_API}/tweets/search/recent",
                    headers={"Authorization": f"Bearer {self._x_token}"},
                    params={
                        "query": q[:512], "max_results": max_results,
                        "tweet.fields": "created_at,author_id,public_metrics",
                        "expansions": "author_id",
                        "user.fields": "username",
                    },
                )
                if resp.status_code != 200:
                    return []

                data = resp.json()
                users = {u["id"]: u.get("username", "") for u in data.get("includes", {}).get("users", [])}
                posts = []
                for t in data.get("data", []):
                    posts.append(SocialPost(
                        id=t["id"], platform="x",
                        text=t.get("text", ""),
                        author=users.get(t.get("author_id", ""), ""),
                        author_id=t.get("author_id", ""),
                        created_at=t.get("created_at", ""),
                        url=f"https://x.com/i/status/{t['id']}",
                        metrics=t.get("public_metrics", {}),
                    ))
                return posts
        except Exception as e:
            logger.debug("X search failed: %s", e)
        return []

    async def x_get_user_tweets(self, user_id: str, max_results: int = 10) -> list[SocialPost]:
        """Fetch recent tweets from a specific user."""
        if not self._x_token:
            return []
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{X_API}/users/{user_id}/tweets",
                    headers={"Authorization": f"Bearer {self._x_token}"},
                    params={
                        "max_results": max_results,
                        "tweet.fields": "created_at,public_metrics",
                        "exclude": "retweets,replies",
                    },
                )
                if resp.status_code != 200:
                    return []
                return [
                    SocialPost(
                        id=t["id"], platform="x",
                        text=t.get("text", ""),
                        author_id=user_id,
                        created_at=t.get("created_at", ""),
                        url=f"https://x.com/i/status/{t['id']}",
                        metrics=t.get("public_metrics", {}),
                    )
                    for t in resp.json().get("data", [])
                ]
        except Exception as e:
            logger.debug("X user tweets failed: %s", e)
        return []

    async def x_retweet(self, tweet_id: str) -> bool:
        """Retweet a post by the authenticated user. Requires OAuth 1.0a user token."""
        token = os.environ.get("X_ACCESS_TOKEN", "")
        token_secret = os.environ.get("X_ACCESS_TOKEN_SECRET", "")
        if not token or not token_secret:
            logger.debug("X retweet skipped: no user access token")
            return False
        # OAuth 1.0a signing needed — placeholder for authenticated user
        logger.info("Would retweet %s (OAuth 1.0a required)", tweet_id)
        return False

    async def x_search_and_analyze(self, topics: list[str],
                                   max_per_topic: int = 5) -> list[SocialPost]:
        """Search multiple topics and return unified results."""
        all_posts = []
        for topic in topics:
            posts = await self.x_search(topic, max_per_topic)
            all_posts.extend(posts)
            # Rate limit: X API allows 1 req/sec for search
            await asyncio.sleep(1.1)
        return all_posts

    # ═══ REDDIT ═══════════════════════════════════════════════════════════

    def _get_reddit_client(self):
        """Lazy init asyncpraw client with credentials from env/ideaminer."""
        if self._reddit_client:
            return self._reddit_client
        try:
            import asyncpraw
            kwargs = {
                "client_id": reddit_cred("REDDIT_CLIENT_ID"),
                "client_secret": reddit_cred("REDDIT_CLIENT_SECRET"),
                "user_agent": reddit_cred("REDDIT_USER_AGENT") or "Maggy/1.0",
            }
            # Script-app write auth (e.g. ideaminer) when username/password exist.
            user, pw = reddit_cred("REDDIT_USERNAME"), reddit_cred("REDDIT_PASSWORD")
            if user and pw:
                kwargs["username"], kwargs["password"] = user, pw
            self._reddit_client = asyncpraw.Reddit(**kwargs)
        except ImportError:
            logger.debug("asyncpraw not installed")
        except Exception as e:
            logger.debug("Reddit client init failed: %s", e)
        return self._reddit_client

    async def reddit_search(self, query: str, subreddit: str = "all",
                            limit: int = 10) -> list[SocialPost]:
        """Search Reddit for posts matching query."""
        client = self._get_reddit_client()
        if not client:
            return []

        posts = []
        try:
            sub = await client.subreddit(subreddit)
            async for submission in sub.search(query, limit=limit, sort="relevance"):
                posts.append(SocialPost(
                    id=submission.id, platform="reddit",
                    text=f"{submission.title}\n{submission.selftext[:500] if submission.selftext else ''}",
                    author=str(submission.author) if submission.author else "",
                    subreddit=subreddit,
                    created_at=datetime.fromtimestamp(submission.created_utc, tz=timezone.utc).isoformat(),
                    url=f"https://reddit.com{submission.permalink}",
                    metrics={"score": submission.score, "comments": submission.num_comments},
                ))
        except Exception as e:
            logger.debug("Reddit search failed: %s", e)

        return posts

    async def reddit_hot(self, subreddit: str, limit: int = 10) -> list[SocialPost]:
        """Get hot posts from a subreddit."""
        client = self._get_reddit_client()
        if not client:
            return []

        posts = []
        try:
            sub = await client.subreddit(subreddit)
            async for submission in sub.hot(limit=limit):
                posts.append(SocialPost(
                    id=submission.id, platform="reddit",
                    text=f"{submission.title}\n{submission.selftext[:300] if submission.selftext else ''}",
                    author=str(submission.author) if submission.author else "",
                    subreddit=subreddit,
                    created_at=datetime.fromtimestamp(submission.created_utc, tz=timezone.utc).isoformat(),
                    url=f"https://reddit.com{submission.permalink}",
                    metrics={"score": submission.score, "comments": submission.num_comments},
                ))
        except Exception as e:
            logger.debug("Reddit hot failed: %s", e)

        return posts

    async def reddit_post_comments(self, submission_id: str,
                                   limit: int = 50) -> list[dict]:
        """Fetch top-level comments on one of our posts (read client)."""
        client = self._get_reddit_client()
        if not client:
            return []
        out: list[dict] = []
        try:
            sub = await client.submission(id=submission_id.replace("t3_", ""))
            await sub.comments.replace_more(limit=0)
            for c in sub.comments.list()[:limit]:
                out.append({
                    "id": c.id,
                    "fullname": f"t1_{c.id}",
                    "author": str(c.author) if c.author else "",
                    "body": getattr(c, "body", "") or "",
                })
        except Exception as e:
            logger.debug("Reddit comments fetch failed: %s", e)
        return out

    async def reddit_monitor_subreddits(self, subreddits: list[str],
                                        limit: int = 5) -> list[SocialPost]:
        """Monitor multiple subreddits for new content."""
        all_posts = []
        for sr in subreddits:
            posts = await self.reddit_hot(sr, limit)
            all_posts.extend(posts)
        return all_posts

    async def reddit_comment(self, post_id: str, text: str) -> bool:
        """Post a comment on a Reddit post. post_id = fullname (t3_abc123)."""
        if not self._reddit_grant():
            logger.debug("Reddit comment skipped: no user write credentials")
            return False
        try:
            access_token = await self._get_reddit_access_token()
            if not access_token:
                return False
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://oauth.reddit.com/api/comment",
                    headers={"Authorization": f"Bearer {access_token}"},
                    data={"thing_id": post_id, "text": text},
                )
                return resp.status_code == 200
        except Exception as e:
            logger.debug("Reddit comment failed: %s", e)
        return False

    async def reddit_reply_to_comment(self, comment_id: str, text: str) -> bool:
        """Reply to a comment. comment_id = fullname (t1_abc123)."""
        return await self.reddit_comment(comment_id, text)

    async def _get_reddit_access_token(self) -> str:
        """Get a user OAuth2 token via refresh_token or password grant.

        Credentials resolve from the environment, then ideaminer. Supports a
        web-app refresh token (REDDIT_REFRESH_TOKEN) or a script app
        (REDDIT_USERNAME + REDDIT_PASSWORD).
        """
        grant = self._reddit_grant()
        if not grant:
            return ""
        try:
            import base64
            async with httpx.AsyncClient(timeout=15) as client:
                auth = base64.b64encode(
                    f"{reddit_cred('REDDIT_CLIENT_ID')}:{reddit_cred('REDDIT_CLIENT_SECRET')}".encode()
                ).decode()
                resp = await client.post(
                    "https://www.reddit.com/api/v1/access_token",
                    headers={
                        "Authorization": f"Basic {auth}",
                        "Content-Type": "application/x-www-form-urlencoded",
                        "User-Agent": reddit_cred("REDDIT_USER_AGENT") or "Maggy/1.0",
                    },
                    data=grant,
                )
                if resp.status_code == 200:
                    return resp.json().get("access_token", "")
                logger.debug("Reddit token grant failed: %s", resp.text[:200])
        except Exception as e:
            logger.debug("Reddit auth failed: %s", e)
        return ""

    @staticmethod
    def _reddit_grant() -> dict:
        """Build the OAuth grant body from available write credentials."""
        refresh = reddit_cred("REDDIT_REFRESH_TOKEN")
        if refresh:
            return {"grant_type": "refresh_token", "refresh_token": refresh}
        user, pw = reddit_cred("REDDIT_USERNAME"), reddit_cred("REDDIT_PASSWORD")
        if user and pw:
            return {"grant_type": "password", "username": user, "password": pw}
        return {}

    async def reddit_post(self, subreddit: str, title: str,
                          text: str = "", url: str = "") -> str:
        """Submit a post. Returns the post fullname (t3_…) on success, else "".

        Requires user write credentials (refresh token or username/password).
        """
        if not self._reddit_grant():
            logger.debug("Reddit post skipped: no user write credentials")
            return ""
        try:
            access_token = await self._get_reddit_access_token()
            if not access_token:
                return ""

            data = {"sr": subreddit.lstrip("r/").strip("/"), "title": title[:300],
                    "kind": "self", "text": text, "api_type": "json"}
            if url:
                data["kind"] = "link"
                data["url"] = url

            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://oauth.reddit.com/api/submit",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "User-Agent": reddit_cred("REDDIT_USER_AGENT") or "Maggy/1.0",
                    },
                    data=data,
                )
                if resp.status_code != 200:
                    return ""
                jd = resp.json().get("json", {})
                if jd.get("errors"):
                    logger.debug("Reddit post errors: %s", jd["errors"])
                    return ""
                return jd.get("data", {}).get("name", "") or "t3_unknown"
        except Exception as e:
            logger.debug("Reddit post failed: %s", e)
        return ""


# ═══ Competitor & Influencer Discovery ═══════════════════════════════════

COMPETITOR_MAP = {
    "memory_management": [
        {"name": "Mem0", "handle": "@mem0ai", "domain": "memory layer for AI agents"},
        {"name": "Pinecone", "handle": "@pinecone", "domain": "vector database, assistant memory"},
        {"name": "Letta/MemGPT", "handle": "@letta_ai", "domain": "OS agent memory, MemGPT"},
        {"name": "Zep", "handle": "@getzep", "domain": "memory for AI assistants"},
        {"name": "Cognee", "handle": "@cognee_ai", "domain": "knowledge graphs for LLMs"},
        {"name": "LangChain Memory", "handle": "@LangChainAI", "domain": "langchain memory modules"},
        {"name": "Chroma", "handle": "@trychroma", "domain": "embeddings database for AI memory"},
        {"name": "Weaviate", "handle": "@weaviate_io", "domain": "vector DB, AI-native memory"},
    ],
    "dynamic_routing": [
        {"name": "OpenRouter", "handle": "@OpenRouterAI", "domain": "unified API, model routing"},
        {"name": "Martian", "handle": "@martianai", "domain": "LLM-as-classifier model router"},
        {"name": "Portkey", "handle": "@portkeyai", "domain": "LLM gateway, routing, fallbacks"},
        {"name": "Semantic Router", "handle": "@AurelioAI", "domain": "embedding-based routing"},
        {"name": "Not Diamond", "handle": "@notdiamondai", "domain": "AI model router"},
        {"name": "Unify", "handle": "@unifyai", "domain": "provider-level routing, latency opt"},
        {"name": "LangChain Routing", "handle": "@LangChainAI", "domain": "RouterChain, LangGraph"},
    ],
    "autonomous_sdlc": [
        {"name": "Devin/Cognition", "handle": "@cognition_labs", "domain": "autonomous AI engineer"},
        {"name": "SWE-Agent", "handle": "@princeton_nlp", "domain": "autonomous SWE agent"},
        {"name": "Factory AI", "handle": "@factory_ai", "domain": "autonomous SDLC platform"},
        {"name": "Cosine Genie", "handle": "@cosine_ai", "domain": "AI code genie, autonomous dev"},
        {"name": "Pythagora", "handle": "@pythagora_ai", "domain": "autonomous full-stack dev"},
        {"name": "OpenHands", "handle": "@allhands_ai", "domain": "AI agent for code, formerly OpenDevin"},
        {"name": "Cursor Agent", "handle": "@cursor_ai", "domain": "AI-native IDE with agent mode"},
        {"name": "GitHub Copilot Workspace", "handle": "@GitHub", "domain": "copilot-native dev environment"},
        {"name": "Aider", "handle": "@aider_ai", "domain": "AI pair programming in terminal"},
        {"name": "Claude Code", "handle": "@AnthropicAI", "domain": "Anthropic CLI coding agent"},
        {"name": "GPT-Engineer", "handle": "@lovable_dev", "domain": "AI generates codebase from prompt"},
        {"name": "Replit Agent", "handle": "@Replit", "domain": "AI agent in cloud IDE"},
    ],
    "build_in_public_influencers": [
        {"name": "Peter Steinberger", "handle": "@steipete", "domain": "iOS, PSPDFKit, build-in-public"},
        {"name": "Pieter Levels", "handle": "@levelsio", "domain": "12 startups in 12 months, nomadlist"},
        {"name": "Marc Lou", "handle": "@marc_louvion", "domain": "build-in-public, ship fast"},
        {"name": "Sahil Lavingia", "handle": "@shl", "domain": "gumroad, build-in-public"},
        {"name": "Danny Postma", "handle": "@dannypostmaa", "domain": "AI SaaS, indie hacking"},
        {"name": "Alex West", "handle": "@alexanderisora", "domain": "design, build-in-public, AI"},
    ],
}


def get_competitor_handles(category: str | None = None) -> list[str]:
    """Get all competitor X handles, optionally filtered by category."""
    if category and category in COMPETITOR_MAP:
        return [c["handle"] for c in COMPETITOR_MAP[category]]
    handles = []
    for cat in COMPETITOR_MAP.values():
        handles.extend(c["handle"] for c in cat)
    return list(set(handles))


def get_competitor_reddit_subreddits() -> list[str]:
    """Subreddits where competitors and the community discuss relevant topics."""
    return [
        "MachineLearning", "artificial", "LocalLLaMA", "LLMDevs",
        "ClaudeAI", "ChatGPTPro", "GPT3", "OpenAI",
        "Programming", "ExperiencedDevs", "coding",
        "SideProject", "SaaS", "buildinpublic", "indiedev",
    ]
