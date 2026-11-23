import asyncio
from dataclasses import dataclass
import logging
import os
from typing import Optional

import aiohttp

from cogs.utils.exceptions import GitHubAPIError, GitHubConfigError, GitHubError

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
IDEA_REPO = "spl1ce0/spl1ceAI"
IDEA_LABEL = "idea"
IDEA_LABEL_COLOR = "a2eeef"
IDEA_LABEL_DESCRIPTION = "Project ideas captured from Discord"
TITLE_MAX_LENGTH = 80
REQUEST_TIMEOUT_SECONDS = 15


@dataclass(frozen=True)
class GitHubIssue:
    """Represents a newly created GitHub issue."""

    number: int
    title: str
    url: str
    labeled: bool = True


def build_idea_title(text: str, max_length: int = TITLE_MAX_LENGTH) -> str:
    """Normalizes idea text into a single-line issue title trimmed to ~80 chars."""
    single_line = " ".join(text.split())
    if len(single_line) <= max_length:
        return single_line

    truncated = single_line[: max_length - 1]
    if " " in truncated:
        word_boundary = truncated.rsplit(" ", 1)[0]
        if len(word_boundary) >= max_length // 2:
            truncated = word_boundary
    return f"{truncated.rstrip()}…"


def build_idea_body(text: str) -> str:
    """Builds the GitHub issue body containing the full idea text and Discord footer."""
    cleaned = text.strip()
    return f"{cleaned}\n\n---\n_Filed from Discord via `!idea`_"


def _build_headers(token: str) -> dict:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "spl1ceAI-bot",
    }


async def _extract_error_details(resp: aiohttp.ClientResponse) -> tuple[str, list]:
    """Safely extracts a human-readable message and error list from a GitHub error response."""
    try:
        data = await resp.json(content_type=None)
        if isinstance(data, dict):
            msg = data.get("message")
            errors = data.get("errors") if isinstance(data.get("errors"), list) else []
            if msg:
                return str(msg), errors
    except Exception:
        pass

    try:
        text = (await resp.text()).strip()
        if text:
            return text[:200], []
    except Exception:
        pass

    return f"HTTP {resp.status}", []


async def _ensure_idea_label(
    session: aiohttp.ClientSession,
    headers: dict,
    timeout: aiohttp.ClientTimeout,
) -> bool:
    """Ensures the 'idea' label exists on IDEA_REPO; returns False if unavailable."""
    label_url = f"{GITHUB_API_BASE}/repos/{IDEA_REPO}/labels/{IDEA_LABEL}"
    labels_url = f"{GITHUB_API_BASE}/repos/{IDEA_REPO}/labels"

    async with session.get(label_url, headers=headers, timeout=timeout) as resp:
        if resp.status == 200:
            return True
        if resp.status == 401:
            raise GitHubConfigError("GitHub token is invalid or expired (HTTP 401).")
        if resp.status != 404:
            msg, _ = await _extract_error_details(resp)
            logger.warning(
                "Could not verify '%s' label on %s (HTTP %s: %s); proceeding without label.",
                IDEA_LABEL,
                IDEA_REPO,
                resp.status,
                msg,
            )
            return False

    label_payload = {
        "name": IDEA_LABEL,
        "color": IDEA_LABEL_COLOR,
        "description": IDEA_LABEL_DESCRIPTION,
    }
    async with session.post(labels_url, json=label_payload, headers=headers, timeout=timeout) as resp:
        if resp.status == 201:
            return True
        if resp.status == 401:
            raise GitHubConfigError("GitHub token is invalid or expired (HTTP 401).")
        if resp.status == 422:
            msg, errors = await _extract_error_details(resp)
            if any(isinstance(err, dict) and err.get("code") == "already_exists" for err in errors):
                return True
            logger.warning(
                "Could not create '%s' label on %s (HTTP 422: %s); proceeding without label.",
                IDEA_LABEL,
                IDEA_REPO,
                msg,
            )
            return False

        msg, _ = await _extract_error_details(resp)
        logger.warning(
            "Could not create '%s' label on %s (HTTP %s: %s); proceeding without label.",
            IDEA_LABEL,
            IDEA_REPO,
            resp.status,
            msg,
        )
        return False


def _is_label_validation_error(message: str, errors: list) -> bool:
    if "label" in message.lower():
        return True
    return any(
        isinstance(err, dict) and str(err.get("field", "")).lower() in ("label", "labels")
        for err in errors
    )


async def _raise_for_issue_error(resp: aiohttp.ClientResponse, message: str) -> None:
    if resp.status == 401:
        raise GitHubConfigError("GitHub token is invalid or expired (HTTP 401).")
    if resp.status == 403:
        if resp.headers.get("X-RateLimit-Remaining") == "0" or "rate limit" in message.lower():
            raise GitHubAPIError(f"GitHub API rate limit exceeded (HTTP 403): {message}", status=403)
        raise GitHubConfigError(
            f"GitHub token lacks permission to create issues on `{IDEA_REPO}` (HTTP 403): {message}"
        )
    if resp.status == 404:
        raise GitHubAPIError(
            f"Repository `{IDEA_REPO}` was not found or the token does not have access to it (HTTP 404).",
            status=404,
        )
    raise GitHubAPIError(f"GitHub API error (HTTP {resp.status}): {message}", status=resp.status)


async def create_idea_issue(
    session: aiohttp.ClientSession,
    text: str,
    *,
    token: Optional[str] = None,
) -> GitHubIssue:
    """Files a project idea as a GitHub issue on spl1ce0/spl1ceAI."""
    cleaned = text.strip()
    if not cleaned:
        raise GitHubError("Idea text cannot be empty.")

    resolved_token = (token if token is not None else os.getenv("GITHUB_TOKEN", "")).strip()
    if not resolved_token:
        raise GitHubConfigError(
            "`GITHUB_TOKEN` is not configured. Set a fine-grained PAT with **Issues (Read and write)** "
            f"permission on `{IDEA_REPO}`."
        )

    title = build_idea_title(cleaned)
    body = build_idea_body(cleaned)
    headers = _build_headers(resolved_token)
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
    issues_url = f"{GITHUB_API_BASE}/repos/{IDEA_REPO}/issues"

    try:
        has_label = await _ensure_idea_label(session, headers, timeout)

        payload: dict = {"title": title, "body": body}
        if has_label:
            payload["labels"] = [IDEA_LABEL]

        async with session.post(issues_url, json=payload, headers=headers, timeout=timeout) as resp:
            if resp.status in (200, 201):
                data = await resp.json(content_type=None)
                issue_url = data.get("html_url") if isinstance(data, dict) else None
                if not issue_url:
                    raise GitHubAPIError("GitHub returned a success response without an issue URL.", status=resp.status)
                return GitHubIssue(
                    number=int(data.get("number", 0)),
                    title=str(data.get("title", title)),
                    url=str(issue_url),
                    labeled=has_label,
                )

            message, errors = await _extract_error_details(resp)

            if resp.status == 422 and has_label and _is_label_validation_error(message, errors):
                logger.warning("Retrying issue creation on %s without '%s' label.", IDEA_REPO, IDEA_LABEL)
                has_label = False
            else:
                await _raise_for_issue_error(resp, message)

        # Fallback retry without labels
        retry_payload = {"title": title, "body": body}
        async with session.post(issues_url, json=retry_payload, headers=headers, timeout=timeout) as resp:
            if resp.status in (200, 201):
                data = await resp.json(content_type=None)
                issue_url = data.get("html_url") if isinstance(data, dict) else None
                if not issue_url:
                    raise GitHubAPIError("GitHub returned a success response without an issue URL.", status=resp.status)
                return GitHubIssue(
                    number=int(data.get("number", 0)),
                    title=str(data.get("title", title)),
                    url=str(issue_url),
                    labeled=False,
                )
            message, _ = await _extract_error_details(resp)
            await _raise_for_issue_error(resp, message)

    except GitHubError:
        raise
    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
        logger.error("Network error while calling GitHub API: %s", exc)
        raise GitHubAPIError(f"Could not reach GitHub API: {exc}") from exc
