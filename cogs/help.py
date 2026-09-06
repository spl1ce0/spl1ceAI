import math
import discord
import discord.ui as ui
from discord.ext import commands
import typing
import logging

from cogs.utils.constants import Emojis, URLs

logger = logging.getLogger(__name__)

SUPPORT_SERVER_URL = URLs.SUPPORT
COMMANDS_PER_PAGE = 5

CATEGORY_CONFIG = {
    "ai": {
        "name": "AI",
        "emoji": "🤖",
        "cogs": ["AI"],
        "description": "Multi-model AI conversations, summaries, and quotas."
    },
    "games": {
        "name": "Games",
        "emoji": "🎮",
        "cogs": ["Games"],
        "description": "Multiplayer Blackjack, Connect 4, wallet, and daily rewards."
    },
    "tools": {
        "name": "Tools",
        "emoji": "🛠️",
        "cogs": ["Settings", "Billing", "Tools", "Logs", "Analytics"],
        "description": "Server configuration, persona settings, and utilities."
    },
    "other": {
        "name": "Other",
        "emoji": "📦",
        "cogs": ["Fun"],
        "description": "Recreational commands, coin flips, dice, and mini-games."
    },
    "dev": {
        "name": "Dev",
        "emoji": "👑",
        "cogs": ["Dev"],
        "description": "Owner-only administration, hot-reloading, and diagnostics."
    }
}


def get_command_permissions(cmd: commands.Command) -> str:
    """Extracts required user permissions for a command."""
    if getattr(cmd, "_is_owner", False):
        return "Owner Only"

    for check in getattr(cmd, "checks", []):
        qualname = getattr(check, "__qualname__", "")
        if "is_owner" in qualname:
            return "Owner Only"
        if "guild_only" in qualname:
            continue

    app_cmd = getattr(cmd, "app_command", None)
    if app_cmd and getattr(app_cmd, "default_member_permissions", None):
        perms = app_cmd.default_member_permissions
        if perms.administrator:
            return "Administrator"
        if perms.manage_guild:
            return "Manage Server"
        if perms.manage_channels:
            return "Manage Channels"
        if perms.ban_members:
            return "Ban Members"

    return "Public (Available to everyone)"


def get_command_signature(cmd: commands.Command) -> typing.Tuple[str, list]:
    """Generates standard usage string and detailed parameter list."""
    params_breakdown = []
    sig_parts = [f"/{cmd.qualified_name or cmd.name}"]

    clean_params = getattr(cmd, "clean_params", {})
    for param_name, param in clean_params.items():
        if param_name in ["self", "ctx", "interaction"]:
            continue

        is_optional = (param.default is not param.empty)
        if is_optional:
            sig_parts.append(f"[{param_name}]")
            req_str = "*(Optional)*"
        else:
            sig_parts.append(f"<{param_name}>")
            req_str = "*(Required)*"

        param_desc = f"• `{param_name}` {req_str}"
        params_breakdown.append(param_desc)

    usage_str = " ".join(sig_parts)
    return usage_str, params_breakdown


class HelpCategoryContainer(ui.Container):
    def __init__(self, bot, category_key: str, is_owner: bool, parent_view, page: int = 0):
        super().__init__()
        self.bot = bot
        self.category_key = category_key
        self.is_owner = is_owner
        self.parent_view = parent_view
        self.page = page
        self._make_container()

    def _make_container(self):
        # 1. Header with Support Server Link Button
        support_btn = ui.Button(label="Support Server", url=SUPPORT_SERVER_URL, style=discord.ButtonStyle.link)
        header_display = ui.TextDisplay("# Help Center")
        self.add_item(ui.Section(header_display, accessory=support_btn))

        # 2. Top Category Navigation Bar
        nav_row = ui.ActionRow()
        for key, info in CATEGORY_CONFIG.items():
            if key == "dev" and not self.is_owner:
                continue
            is_active = (key == self.category_key)
            style = discord.ButtonStyle.primary if is_active else discord.ButtonStyle.gray
            btn = ui.Button(label=info["name"], style=style)

            def make_nav_callback(k):
                async def _cb(interaction: discord.Interaction):
                    if interaction.user.id != self.parent_view.author.id:
                        await interaction.response.send_message("❌ This help menu is not yours.", ephemeral=True)
                        return
                    await self.parent_view.render_category(k, interaction, page=0)
                return _cb

            btn.callback = make_nav_callback(key)
            nav_row.add_item(btn)

        self.add_item(nav_row)
        self.add_item(ui.Separator())

        # 3. Command Listings with Inspect Arrow Buttons (Paginated)
        cat_commands = self.parent_view.get_category_commands(self.category_key)

        total_pages = max(1, math.ceil(len(cat_commands) / COMMANDS_PER_PAGE)) if cat_commands else 1
        current_page = max(0, min(self.page, total_pages - 1))
        self.page = current_page

        if not cat_commands:
            self.add_item(ui.TextDisplay("*No commands available in this category.*"))
        else:
            start_idx = current_page * COMMANDS_PER_PAGE
            page_commands = cat_commands[start_idx : start_idx + COMMANDS_PER_PAGE]

            for cmd in page_commands:
                usage_str, _ = get_command_signature(cmd)
                desc = cmd.description or cmd.help or cmd.short_doc or "No description."
                short_desc = desc.split("\n")[0]
                perms = get_command_permissions(cmd)
                
                perm_badge = ""
                if perms == "Owner Only":
                    perm_badge = " • `Owner`"
                elif perms != "Public (Available to everyone)":
                    perm_badge = f" • `{perms}`"

                cmd_display = ui.TextDisplay(
                    f"**`{usage_str}`**{perm_badge}\n"
                    f"-# {short_desc}"
                )
                inspect_btn = ui.Button(emoji=Emojis.ARROW, style=discord.ButtonStyle.gray)

                def make_inspect_callback(target_cmd):
                    async def _cb(interaction: discord.Interaction):
                        if interaction.user.id != self.parent_view.author.id:
                            await interaction.response.send_message("❌ This help menu is not yours.", ephemeral=True)
                            return
                        await self.parent_view.render_command(target_cmd, interaction)
                    return _cb

                inspect_btn.callback = make_inspect_callback(cmd)
                self.add_item(ui.Section(cmd_display, accessory=inspect_btn))

        # 4. Pagination Action Row (always shown)
        self.add_item(ui.Separator())
        page_row = ui.ActionRow()

        prev_btn = ui.Button(label="◀ Prev", style=discord.ButtonStyle.gray, disabled=(current_page == 0))
        page_indicator = ui.Button(label=f"Page {current_page + 1}/{total_pages}", style=discord.ButtonStyle.secondary, disabled=True)
        next_btn = ui.Button(label="Next ▶", style=discord.ButtonStyle.gray, disabled=(current_page >= total_pages - 1))

        async def _on_prev(interaction: discord.Interaction):
            if interaction.user.id != self.parent_view.author.id:
                await interaction.response.send_message("❌ This help menu is not yours.", ephemeral=True)
                return
            await self.parent_view.render_category(self.category_key, interaction, page=self.page - 1)

        async def _on_next(interaction: discord.Interaction):
            if interaction.user.id != self.parent_view.author.id:
                await interaction.response.send_message("❌ This help menu is not yours.", ephemeral=True)
                return
            await self.parent_view.render_category(self.category_key, interaction, page=self.page + 1)

        prev_btn.callback = _on_prev
        next_btn.callback = _on_next

        page_row.add_item(prev_btn)
        page_row.add_item(page_indicator)
        page_row.add_item(next_btn)
        self.add_item(page_row)



class HelpCommandInspectorContainer(ui.Container):
    def __init__(self, bot, cmd: commands.Command, category_key: str, parent_view):
        super().__init__()
        self.bot = bot
        self.cmd = cmd
        self.category_key = category_key
        self.parent_view = parent_view
        self._make_container()

    def _make_container(self):
        # 1. Header with < Back Button on Top Right
        back_btn = ui.Button(label="< Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self.parent_view._on_back_to_category

        header_display = ui.TextDisplay(f"# Command: /{self.cmd.qualified_name or self.cmd.name}")
        self.add_item(ui.Section(header_display, accessory=back_btn))
        self.add_item(ui.Separator())

        # 2. Detailed Metadata
        desc = self.cmd.description or self.cmd.help or "No description provided."
        usage_str, params = get_command_signature(self.cmd)
        aliases = getattr(self.cmd, "aliases", [])
        aliases_str = ", ".join([f"`/{a}`" for a in aliases]) if aliases else "None"
        perms_str = get_command_permissions(self.cmd)

        params_text = "\n".join(params) if params else "*No parameters required.*"

        content = (
            f"**Description**\n{desc}\n\n"
            f"**Usage**\n`{usage_str}`\n\n"
            f"**Parameters**\n{params_text}\n\n"
            f"**Aliases**\n{aliases_str}\n\n"
            f"**Permissions**\n{perms_str}"
        )
        self.add_item(ui.TextDisplay(content))


class HelpView(ui.LayoutView):
    def __init__(self, bot, author: discord.User, initial_category: str = "ai"):
        super().__init__(timeout=180)
        self.bot = bot
        self.author = author
        self.category_key = initial_category
        self.category_page = 0
        self.is_owner = False

    async def initialize(self, target_command_name: typing.Optional[str] = None):
        self.is_owner = await self.bot.is_owner(self.author)
        if target_command_name:
            cmd, cat_key = self.find_command(target_command_name)
            if cmd:
                self.category_key = cat_key
                self.category_page = 0
                await self.render_command(cmd)
                return
        await self.render_category(self.category_key, page=0)

    def find_command(self, query: str) -> typing.Tuple[typing.Optional[commands.Command], str]:
        """Finds a command by name or alias and its category key."""
        clean_q = query.strip().lstrip("/").lower()
        cmd = self.bot.get_command(clean_q)
        if not cmd:
            return None, "ai"

        cog_name = cmd.cog_name
        for cat_key, info in CATEGORY_CONFIG.items():
            if cog_name in info["cogs"]:
                return cmd, cat_key
        return cmd, "other"

    def get_category_commands(self, category_key: str) -> list:
        """Dynamically retrieves all valid registered commands for a category."""
        cat_info = CATEGORY_CONFIG.get(category_key)
        if not cat_info:
            return []

        cogs = cat_info["cogs"]
        cmd_list = []
        for cog_name in cogs:
            cog = self.bot.get_cog(cog_name)
            if not cog:
                continue
            for cmd in cog.get_commands():
                if cmd.hidden and not self.is_owner:
                    continue
                if category_key == "dev" and not self.is_owner:
                    continue
                cmd_list.append(cmd)

        return sorted(cmd_list, key=lambda c: c.name)

    async def render_category(self, category_key: str, interaction: typing.Optional[discord.Interaction] = None, page: int = 0):
        if category_key != self.category_key:
            self.category_page = 0
        else:
            self.category_page = page
        self.category_key = category_key
        self.clear_items()
        container = HelpCategoryContainer(self.bot, self.category_key, self.is_owner, self, page=self.category_page)
        self.add_item(container)

        if interaction:
            await interaction.response.edit_message(view=self)

    async def render_command(self, cmd: commands.Command, interaction: typing.Optional[discord.Interaction] = None):
        self.clear_items()
        container = HelpCommandInspectorContainer(self.bot, cmd, self.category_key, self)
        self.add_item(container)

        if interaction:
            await interaction.response.edit_message(view=self)

    async def _on_back_to_category(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ This help menu is not yours.", ephemeral=True)
            return
        await self.render_category(self.category_key, interaction, page=self.category_page)


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._original_help_command = bot.help_command
        bot.help_command = None

    def cog_unload(self):
        self.bot.help_command = self._original_help_command

    @commands.hybrid_command(name="help", aliases=["h", "cmds", "bothelp"])
    @discord.app_commands.describe(command="Specific command to inspect (e.g. ask, quota, blackjack)")
    async def help_command(self, ctx: commands.Context, command: typing.Optional[str] = None):
        """Displays the interactive command center, feature guides, and syntax help."""
        await ctx.defer()
        view = HelpView(self.bot, ctx.author)
        await view.initialize(target_command_name=command)
        await ctx.reply(view=view)


async def setup(bot):
    if bot.get_command("help"):
        bot.remove_command("help")
    bot.help_command = None
    await bot.add_cog(Help(bot))
