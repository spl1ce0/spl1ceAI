import asyncio
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from cogs.dev import Dev
from cogs.errors import ErrorCardView, ErrorHandler
from cogs.help import get_command_permissions
from cogs.utils.cards import NotificationCardView
from cogs.utils.exceptions import GitHubAPIError, GitHubConfigError
from cogs.utils.github import (
    GITHUB_API_BASE,
    IDEA_LABEL,
    IDEA_REPO,
    build_idea_body,
    build_idea_title,
    create_idea_issue,
)


class FakeResponse:
    """Async context manager mocking an aiohttp.ClientResponse."""

    def __init__(self, status: int, json_data=None, text_data: str = "", headers=None):
        self.status = status
        self._json_data = json_data
        self._text_data = text_data
        self.headers = headers or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self, content_type=None):
        if isinstance(self._json_data, Exception):
            raise self._json_data
        return self._json_data

    async def text(self):
        return self._text_data


class FakeSession:
    """Mock aiohttp.ClientSession recording GET/POST calls and returning queued responses."""

    def __init__(self, get_responses=None, post_responses=None):
        self.get_responses = list(get_responses or [])
        self.post_responses = list(post_responses or [])
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        resp = self.get_responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        resp = self.post_responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp


def _extract_view_text(view: discord.ui.LayoutView) -> str:
    """Collects all TextDisplay content from a Components V2 LayoutView."""
    parts = []
    for item in view.children:
        if isinstance(item, discord.ui.Container):
            for child in item.children:
                if isinstance(child, discord.ui.TextDisplay):
                    parts.append(child.content)
    return "\n".join(parts)


class TestIdeaFormatting(unittest.TestCase):
    def test_short_title_preserved(self):
        self.assertEqual(build_idea_title("Add music queue command"), "Add music queue command")

    def test_multiline_title_collapsed_and_body_preserved(self):
        raw = "  Add slash command\nwith details on line two  "
        self.assertEqual(build_idea_title(raw), "Add slash command with details on line two")
        body = build_idea_body(raw)
        self.assertTrue(body.startswith("Add slash command\nwith details on line two"))
        self.assertIn("/idea", body)

    def test_long_title_trimmed_cleanly(self):
        raw = (
            "Add a rich daily digest summary command that aggregates server activity, "
            "highlights popular threads, and posts a neat recap every morning"
        )
        title = build_idea_title(raw)
        self.assertLessEqual(len(title), 80)
        self.assertTrue(title.endswith("…"))
        self.assertNotIn("  ", title)

    def test_unbroken_long_token_trimmed_to_80(self):
        raw = "x" * 120
        title = build_idea_title(raw)
        self.assertEqual(len(title), 80)
        self.assertTrue(title.endswith("…"))


class TestGitHubIssueCreation(unittest.IsolatedAsyncioTestCase):
    async def test_missing_token_raises_config_error(self):
        session = FakeSession()
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(GitHubConfigError) as ctx:
                await create_idea_issue(session, "Add dark mode")
        self.assertIn("GITHUB_TOKEN", str(ctx.exception))
        self.assertEqual(session.calls, [])

    async def test_creates_issue_when_label_exists(self):
        issue_url = f"https://github.com/{IDEA_REPO}/issues/42"
        session = FakeSession(
            get_responses=[FakeResponse(200, {"name": IDEA_LABEL})],
            post_responses=[
                FakeResponse(
                    201,
                    {
                        "number": 42,
                        "title": "Add reminder command",
                        "html_url": issue_url,
                    },
                )
            ],
        )

        issue = await create_idea_issue(session, "Add reminder command", token="ghp_test_token")

        self.assertEqual(issue.number, 42)
        self.assertEqual(issue.url, issue_url)
        self.assertTrue(issue.labeled)

        self.assertEqual(len(session.calls), 2)
        method_get, url_get, kwargs_get = session.calls[0]
        self.assertEqual(method_get, "GET")
        self.assertEqual(url_get, f"{GITHUB_API_BASE}/repos/{IDEA_REPO}/labels/{IDEA_LABEL}")
        self.assertEqual(kwargs_get["headers"]["Authorization"], "Bearer ghp_test_token")

        method_post, url_post, kwargs_post = session.calls[1]
        self.assertEqual(method_post, "POST")
        self.assertEqual(url_post, f"{GITHUB_API_BASE}/repos/{IDEA_REPO}/issues")
        self.assertEqual(kwargs_post["json"]["labels"], [IDEA_LABEL])
        self.assertEqual(kwargs_post["json"]["title"], "Add reminder command")
        self.assertIn("Add reminder command", kwargs_post["json"]["body"])
        self.assertIn("/idea", kwargs_post["json"]["body"])

    async def test_creates_missing_label_then_files_issue(self):
        issue_url = f"https://github.com/{IDEA_REPO}/issues/43"
        session = FakeSession(
            get_responses=[FakeResponse(404, {"message": "Not Found"})],
            post_responses=[
                FakeResponse(201, {"name": IDEA_LABEL}),
                FakeResponse(201, {"number": 43, "title": "New idea", "html_url": issue_url}),
            ],
        )

        issue = await create_idea_issue(session, "New idea", token="ghp_test_token")

        self.assertEqual(issue.url, issue_url)
        self.assertTrue(issue.labeled)
        self.assertEqual(len(session.calls), 3)
        self.assertEqual(session.calls[1][1], f"{GITHUB_API_BASE}/repos/{IDEA_REPO}/labels")
        self.assertEqual(session.calls[1][2]["json"]["name"], IDEA_LABEL)
        self.assertEqual(session.calls[2][1], f"{GITHUB_API_BASE}/repos/{IDEA_REPO}/issues")
        self.assertEqual(session.calls[2][2]["json"]["labels"], [IDEA_LABEL])

    async def test_gracefully_handles_label_creation_failure(self):
        issue_url = f"https://github.com/{IDEA_REPO}/issues/44"
        session = FakeSession(
            get_responses=[FakeResponse(404, {"message": "Not Found"})],
            post_responses=[
                FakeResponse(403, {"message": "Resource not accessible by personal access token"}),
                FakeResponse(201, {"number": 44, "title": "Fallback idea", "html_url": issue_url}),
            ],
        )

        issue = await create_idea_issue(session, "Fallback idea", token="ghp_test_token")

        self.assertEqual(issue.url, issue_url)
        self.assertFalse(issue.labeled)
        self.assertNotIn("labels", session.calls[2][2]["json"])

    async def test_retries_without_label_on_422_label_validation_error(self):
        issue_url = f"https://github.com/{IDEA_REPO}/issues/45"
        session = FakeSession(
            get_responses=[FakeResponse(200, {"name": IDEA_LABEL})],
            post_responses=[
                FakeResponse(
                    422,
                    {"message": "Validation Failed", "errors": [{"field": "labels", "code": "invalid"}]},
                ),
                FakeResponse(201, {"number": 45, "title": "Retry idea", "html_url": issue_url}),
            ],
        )

        issue = await create_idea_issue(session, "Retry idea", token="ghp_test_token")

        self.assertEqual(issue.url, issue_url)
        self.assertFalse(issue.labeled)
        self.assertEqual(session.calls[1][2]["json"]["labels"], [IDEA_LABEL])
        self.assertNotIn("labels", session.calls[2][2]["json"])

    async def test_invalid_token_raises_config_error(self):
        session = FakeSession(get_responses=[FakeResponse(401, {"message": "Bad credentials"})])
        with self.assertRaises(GitHubConfigError) as ctx:
            await create_idea_issue(session, "Some idea", token="bad_token")
        self.assertIn("401", str(ctx.exception))

    async def test_forbidden_issue_creation_raises_config_error(self):
        session = FakeSession(
            get_responses=[FakeResponse(200, {"name": IDEA_LABEL})],
            post_responses=[FakeResponse(403, {"message": "Resource not accessible by personal access token"})],
        )
        with self.assertRaises(GitHubConfigError) as ctx:
            await create_idea_issue(session, "Some idea", token="limited_token")
        self.assertIn("403", str(ctx.exception))

    async def test_api_server_error_raises_api_error(self):
        session = FakeSession(
            get_responses=[FakeResponse(200, {"name": IDEA_LABEL})],
            post_responses=[FakeResponse(502, text_data="Bad Gateway")],
        )
        with self.assertRaises(GitHubAPIError) as ctx:
            await create_idea_issue(session, "Some idea", token="ghp_test_token")
        self.assertEqual(ctx.exception.status, 502)

    async def test_network_timeout_raises_api_error(self):
        session = FakeSession(get_responses=[asyncio.TimeoutError("timed out")])
        with self.assertRaises(GitHubAPIError):
            await create_idea_issue(session, "Some idea", token="ghp_test_token")

    async def test_aiohttp_client_error_raises_api_error(self):
        session = FakeSession(get_responses=[aiohttp.ClientError("connection reset")])
        with self.assertRaises(GitHubAPIError):
            await create_idea_issue(session, "Some idea", token="ghp_test_token")


class TestIdeaCommand(unittest.IsolatedAsyncioTestCase):
    def _make_bot_and_ctx(self, *, is_owner: bool, web_client=None):
        bot = MagicMock()
        bot.is_owner = AsyncMock(return_value=is_owner)
        bot.web_client = web_client or FakeSession()

        ctx = MagicMock()
        ctx.author = MagicMock(id=123456789)
        ctx.defer = AsyncMock()
        ctx.reply = AsyncMock()
        return bot, ctx

    async def test_non_owner_gets_ephemeral_refusal(self):
        session = FakeSession()
        bot, ctx = self._make_bot_and_ctx(is_owner=False, web_client=session)
        cog = Dev(bot)

        await cog.idea.callback(cog, ctx, text="Should not be filed")

        bot.is_owner.assert_awaited_once_with(ctx.author)
        ctx.defer.assert_not_awaited()
        ctx.reply.assert_awaited_once()
        args, kwargs = ctx.reply.call_args
        self.assertTrue(kwargs.get("ephemeral"))
        self.assertIn("owner", args[0].lower())
        self.assertEqual(session.calls, [])

    async def test_owner_blank_text_gets_ephemeral_warning(self):
        session = FakeSession()
        bot, ctx = self._make_bot_and_ctx(is_owner=True, web_client=session)
        cog = Dev(bot)

        await cog.idea.callback(cog, ctx, text="   \n\t  ")

        ctx.defer.assert_not_awaited()
        ctx.reply.assert_awaited_once()
        self.assertTrue(ctx.reply.call_args.kwargs.get("ephemeral"))
        self.assertEqual(session.calls, [])

    async def test_owner_files_issue_and_gets_ephemeral_url_reply(self):
        issue_url = f"https://github.com/{IDEA_REPO}/issues/99"
        session = FakeSession(
            get_responses=[FakeResponse(200, {"name": IDEA_LABEL})],
            post_responses=[
                FakeResponse(
                    201,
                    {
                        "number": 99,
                        "title": "Add polls feature",
                        "html_url": issue_url,
                    },
                )
            ],
        )
        bot, ctx = self._make_bot_and_ctx(is_owner=True, web_client=session)
        cog = Dev(bot)

        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test_token"}):
            await cog.idea.callback(cog, ctx, text="Add polls feature")

        ctx.defer.assert_awaited_once_with(ephemeral=True)
        ctx.reply.assert_awaited_once()
        reply_kwargs = ctx.reply.call_args.kwargs
        self.assertTrue(reply_kwargs.get("ephemeral"))
        view = reply_kwargs.get("view")
        self.assertIsInstance(view, NotificationCardView)
        self.assertIn(issue_url, _extract_view_text(view))

    async def test_command_registered_as_owner_only_in_help(self):
        bot = MagicMock()
        cog = Dev(bot)
        self.assertEqual(get_command_permissions(cog.idea), "Owner Only")

    async def test_error_handler_unwraps_hybrid_github_error_ephemerally(self):
        bot = MagicMock()
        bot.tree = MagicMock()
        handler = ErrorHandler(bot)

        ctx = MagicMock()
        ctx.command = MagicMock(spec=["qualified_name", "signature"])
        ctx.command.qualified_name = "idea"
        ctx.command.signature = "<text>"
        ctx.cog = MagicMock()
        ctx.cog.qualified_name = "Dev"
        ctx.prefix = "/"
        ctx.reply = AsyncMock()

        gh_err = GitHubConfigError("GITHUB_TOKEN is not configured.")
        wrapped = commands.HybridCommandError(app_commands.CommandInvokeError(MagicMock(), gh_err))

        await handler.on_command_error(ctx, wrapped)

        ctx.reply.assert_awaited_once()
        reply_kwargs = ctx.reply.call_args.kwargs
        self.assertTrue(reply_kwargs.get("ephemeral"))
        view = reply_kwargs.get("view")
        self.assertIsInstance(view, ErrorCardView)
        self.assertIn("GITHUB_TOKEN is not configured.", _extract_view_text(view))

    async def test_error_handler_renders_wrapped_hybrid_app_command_cooldown(self):
        bot = MagicMock()
        bot.tree = MagicMock()
        handler = ErrorHandler(bot)

        ctx = MagicMock()
        ctx.command = MagicMock(spec=["qualified_name", "signature"])
        ctx.command.qualified_name = "ytmp3"
        ctx.command.signature = "<url>"
        ctx.cog = MagicMock()
        ctx.cog.qualified_name = "Dev"
        ctx.prefix = "/"
        ctx.reply = AsyncMock()

        cooldown_err = app_commands.CommandOnCooldown(app_commands.Cooldown(1, 10.0), retry_after=4.5)
        wrapped = commands.HybridCommandError(cooldown_err)

        await handler.on_command_error(ctx, wrapped)

        ctx.reply.assert_awaited_once()
        view = ctx.reply.call_args.kwargs.get("view")
        self.assertIsInstance(view, ErrorCardView)
        text = _extract_view_text(view)
        self.assertIn("Command on Cooldown", text)
        self.assertIn("4.5s", text)

    async def test_error_handler_renders_wrapped_hybrid_transformer_error(self):
        bot = MagicMock()
        bot.tree = MagicMock()
        handler = ErrorHandler(bot)

        ctx = MagicMock()
        ctx.command = MagicMock(spec=["qualified_name", "signature"])
        ctx.command.qualified_name = "givemoney"
        ctx.command.signature = "<user> <amount>"
        ctx.cog = MagicMock()
        ctx.cog.qualified_name = "Dev"
        ctx.prefix = "/"
        ctx.reply = AsyncMock()

        transformer_err = app_commands.TransformerError(
            "not-a-number",
            discord.AppCommandOptionType.integer,
            MagicMock(),
        )
        wrapped = commands.HybridCommandError(transformer_err)

        await handler.on_command_error(ctx, wrapped)

        ctx.reply.assert_awaited_once()
        view = ctx.reply.call_args.kwargs.get("view")
        self.assertIsInstance(view, ErrorCardView)
        self.assertIn("Invalid Argument Passed", _extract_view_text(view))

    async def test_app_command_error_handler_renders_github_api_error(self):
        bot = MagicMock()
        bot.tree = MagicMock()
        handler = ErrorHandler(bot)

        interaction = MagicMock()
        interaction.command = MagicMock()
        interaction.command.name = "idea"
        interaction.command.binding = MagicMock(qualified_name="Dev")
        interaction.response = MagicMock()
        interaction.response.is_done.return_value = True
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()

        err = app_commands.CommandInvokeError(MagicMock(), GitHubAPIError("GitHub API error (HTTP 500)", status=500))
        await handler.on_app_command_error(interaction, err)

        interaction.followup.send.assert_awaited_once()
        kwargs = interaction.followup.send.call_args.kwargs
        self.assertTrue(kwargs.get("ephemeral"))
        view = kwargs.get("view")
        self.assertIsInstance(view, ErrorCardView)
        self.assertIn("HTTP 500", _extract_view_text(view))


if __name__ == "__main__":
    unittest.main()
