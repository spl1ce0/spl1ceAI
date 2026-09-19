from enum import Enum
from typing import Optional, List, Union
import discord
from discord import ui
from discord.ext.commands import Context
from cogs.utils.constants import Emojis, URLs, WelcomeMessages


class NotificationType(Enum):
    SUCCESS = ("✅", discord.Color.green())
    INFO = ("ℹ️", discord.Color.blurple())
    WARNING = ("⚠️", discord.Color.gold())
    PROGRESS = ("🔄", discord.Color.light_grey())


class DismissButton(ui.Button):
    """A standard dismiss button that removes the notification message."""

    def __init__(self, label: str = "Dismiss"):
        super().__init__(label=label, style=discord.ButtonStyle.gray)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            await interaction.delete_original_response()
        except Exception:
            try:
                if interaction.message:
                    await interaction.message.delete()
            except Exception:
                pass


class NotificationCardView(ui.LayoutView):
    """Discord Components V2 layout view for modern, card-based confirmations, notices, and info."""

    def __init__(
        self,
        card_type: NotificationType,
        title: str,
        description: str,
        details: Optional[str] = None,
        footer: Optional[str] = None,
        thumbnail_url: Optional[str] = None,
        buttons: Optional[List[ui.Button]] = None,
        timeout: Optional[float] = 180.0
    ):
        super().__init__(timeout=timeout)
        self.card_type = card_type
        container = ui.Container()
        container.accent_color = card_type.value[1]

        # 1. Header and Content
        icon = card_type.value[0]
        header = f"### {icon} {title}"
        body = description
        if details:
            body += f"\n\n{details}"
        if footer:
            body += f"\n-# {footer}"

        full_text = f"{header}\n{body}"

        if thumbnail_url:
            text_disp = ui.TextDisplay(full_text)
            thumb = ui.Thumbnail(media=thumbnail_url)
            container.add_item(ui.Section(text_disp, accessory=thumb))
        else:
            container.add_item(ui.TextDisplay(full_text))

        # 2. Interactive Action Row Buttons (if any)
        if buttons:
            container.add_item(ui.Separator())
            row = ui.ActionRow()
            for btn in buttons[:5]:
                row.add_item(btn)
            container.add_item(row)

        self.add_item(container)


def build_confirmation_card(
    title: str,
    description: str,
    details: Optional[str] = None,
    footer: Optional[str] = None,
    thumbnail_url: Optional[str] = None,
    buttons: Optional[List[ui.Button]] = None,
    add_dismiss: bool = False,
    timeout: Optional[float] = 180.0
) -> NotificationCardView:
    btn_list = list(buttons) if buttons else []
    if add_dismiss:
        btn_list.append(DismissButton())
    return NotificationCardView(
        card_type=NotificationType.SUCCESS,
        title=title,
        description=description,
        details=details,
        footer=footer,
        thumbnail_url=thumbnail_url,
        buttons=btn_list if btn_list else None,
        timeout=timeout
    )


def build_info_card(
    title: str,
    description: str,
    details: Optional[str] = None,
    footer: Optional[str] = None,
    thumbnail_url: Optional[str] = None,
    buttons: Optional[List[ui.Button]] = None,
    add_dismiss: bool = False,
    timeout: Optional[float] = 180.0
) -> NotificationCardView:
    btn_list = list(buttons) if buttons else []
    if add_dismiss:
        btn_list.append(DismissButton())
    return NotificationCardView(
        card_type=NotificationType.INFO,
        title=title,
        description=description,
        details=details,
        footer=footer,
        thumbnail_url=thumbnail_url,
        buttons=btn_list if btn_list else None,
        timeout=timeout
    )


def build_warning_card(
    title: str,
    description: str,
    details: Optional[str] = None,
    footer: Optional[str] = None,
    thumbnail_url: Optional[str] = None,
    buttons: Optional[List[ui.Button]] = None,
    add_dismiss: bool = False,
    timeout: Optional[float] = 180.0
) -> NotificationCardView:
    btn_list = list(buttons) if buttons else []
    if add_dismiss:
        btn_list.append(DismissButton())
    return NotificationCardView(
        card_type=NotificationType.WARNING,
        title=title,
        description=description,
        details=details,
        footer=footer,
        thumbnail_url=thumbnail_url,
        buttons=btn_list if btn_list else None,
        timeout=timeout
    )


def build_progress_card(
    title: str,
    description: str,
    details: Optional[str] = None,
    footer: Optional[str] = None,
    thumbnail_url: Optional[str] = None,
    buttons: Optional[List[ui.Button]] = None,
    timeout: Optional[float] = 180.0
) -> NotificationCardView:
    return NotificationCardView(
        card_type=NotificationType.PROGRESS,
        title=title,
        description=description,
        details=details,
        footer=footer,
        thumbnail_url=thumbnail_url,
        buttons=buttons,
        timeout=timeout
    )


async def send_confirmation(
    target: Union[Context, discord.Interaction, discord.abc.Messageable],
    title: str,
    description: str,
    *,
    details: Optional[str] = None,
    footer: Optional[str] = None,
    thumbnail_url: Optional[str] = None,
    buttons: Optional[List[ui.Button]] = None,
    add_dismiss: bool = False,
    ephemeral: bool = False,
    timeout: Optional[float] = 180.0
):
    view = build_confirmation_card(
        title=title,
        description=description,
        details=details,
        footer=footer,
        thumbnail_url=thumbnail_url,
        buttons=buttons,
        add_dismiss=add_dismiss,
        timeout=timeout
    )
    return await _dispatch_card(target, view, ephemeral=ephemeral)


async def send_info(
    target: Union[Context, discord.Interaction, discord.abc.Messageable],
    title: str,
    description: str,
    *,
    details: Optional[str] = None,
    footer: Optional[str] = None,
    thumbnail_url: Optional[str] = None,
    buttons: Optional[List[ui.Button]] = None,
    add_dismiss: bool = False,
    ephemeral: bool = False,
    timeout: Optional[float] = 180.0
):
    view = build_info_card(
        title=title,
        description=description,
        details=details,
        footer=footer,
        thumbnail_url=thumbnail_url,
        buttons=buttons,
        add_dismiss=add_dismiss,
        timeout=timeout
    )
    return await _dispatch_card(target, view, ephemeral=ephemeral)


async def send_warning(
    target: Union[Context, discord.Interaction, discord.abc.Messageable],
    title: str,
    description: str,
    *,
    details: Optional[str] = None,
    footer: Optional[str] = None,
    thumbnail_url: Optional[str] = None,
    buttons: Optional[List[ui.Button]] = None,
    add_dismiss: bool = False,
    ephemeral: bool = False,
    timeout: Optional[float] = 180.0
):
    view = build_warning_card(
        title=title,
        description=description,
        details=details,
        footer=footer,
        thumbnail_url=thumbnail_url,
        buttons=buttons,
        add_dismiss=add_dismiss,
        timeout=timeout
    )
    return await _dispatch_card(target, view, ephemeral=ephemeral)


async def _dispatch_card(
    target: Union[Context, discord.Interaction, discord.abc.Messageable],
    view: ui.LayoutView,
    ephemeral: bool = False
):
    if isinstance(target, discord.Interaction):
        if target.response.is_done():
            return await target.followup.send(view=view, ephemeral=ephemeral)
        else:
            await target.response.send_message(view=view, ephemeral=ephemeral)
            try:
                return await target.original_response()
            except Exception:
                return None
    elif isinstance(target, Context):
        return await target.reply(view=view, mention_author=False)
    elif hasattr(target, 'send'):
        return await target.send(view=view)
    else:
        raise ValueError(f"Unsupported target for card dispatch: {type(target)}")


# =========================================================================
# --- GUILD WELCOME, INVITE & SUPPORT CARDS (DISCORD COMPONENTS V2) ---
# =========================================================================

def get_bot_invite_url(bot: discord.Client) -> str:
    """Helper to generate bot OAuth2 invite URL with fallback to URLs.INVITE."""
    if bot.user:
        return discord.utils.oauth_url(
            bot.user.id,
            permissions=discord.Permissions(8),
            scopes=("bot", "applications.commands")
        )
    return URLs.INVITE


class GuildWelcomeContainer(ui.Container):
    """Discord Components V2 Container for the Guild Welcome message."""
    def __init__(self, bot: discord.Client):
        super().__init__()

        # Title Section
        header_text = f"## {WelcomeMessages.TITLE}\n *I swear I'm not evil.*"
        
        self.add_item(ui.TextDisplay(header_text))

        self.add_item(ui.Separator())

        # Steps 1 & 2
        steps_body = (
            f"### {WelcomeMessages.STEP_1_TITLE}\n"
            f"{WelcomeMessages.STEP_1_DESC}\n"
            f"### {WelcomeMessages.STEP_2_TITLE}\n"
            f"{WelcomeMessages.STEP_2_DESC}\n"
            f"### {WelcomeMessages.STEP_3_TITLE}\n"
        )
        self.add_item(ui.TextDisplay(steps_body))

        # Step 3 (Web Dashboard Section with Website button accessory)
        dash_text = (
            f"{WelcomeMessages.STEP_3_DESC}"
        )
        dash_btn = ui.Button(label="Website", url=URLs.WEBSITE, style=discord.ButtonStyle.link)
        self.add_item(ui.Section(ui.TextDisplay(dash_text), accessory=dash_btn))

        self.add_item(ui.Separator())

        # Footer Section with Support button accessory
        support_btn = ui.Button(label="Support", url=URLs.SUPPORT, style=discord.ButtonStyle.link)
        self.add_item(ui.Section(ui.TextDisplay(WelcomeMessages.FOOTER_TEXT), accessory=support_btn))


class GuildWelcomeView(ui.LayoutView):
    """Discord Components V2 LayoutView for guild join welcome messages."""
    def __init__(self, bot: discord.Client):
        super().__init__(timeout=None)
        self.add_item(GuildWelcomeContainer(bot))


def build_guild_welcome_card(bot: discord.Client) -> GuildWelcomeView:
    return GuildWelcomeView(bot)


class InviteContainer(ui.Container):
    """Discord Components V2 Container for the /invite command."""
    def __init__(self, bot: discord.Client):
        super().__init__()

        header_text = "### Add spl1ceAI to your server."
        self.add_item(ui.TextDisplay(header_text))

        invite_url = get_bot_invite_url(bot)

        self.add_item(ui.Separator())

        action_row = ui.ActionRow()
        inv_btn = ui.Button(label="Add Me", url=invite_url, style=discord.ButtonStyle.link)
        action_row.add_item(inv_btn)
        support_btn = ui.Button(label="Support Server", url=URLs.SUPPORT, style=discord.ButtonStyle.link)
        action_row.add_item(support_btn)
        dash_btn = ui.Button(label="Website", url=URLs.WEBSITE, style=discord.ButtonStyle.link)
        action_row.add_item(dash_btn)
        self.add_item(action_row)


class InviteView(ui.LayoutView):
    """Discord Components V2 LayoutView for the /invite command."""
    def __init__(self, bot: discord.Client):
        super().__init__(timeout=None)
        self.add_item(InviteContainer(bot))


def build_invite_card(bot: discord.Client) -> InviteView:
    return InviteView(bot)


class SupportContainer(ui.Container):
    """Discord Components V2 Container for the /support command."""
    def __init__(self, bot: discord.Client):
        super().__init__()
        # Container color removed per user preference

        header_text = "### Join the support server to get help and updates."
        self.add_item(ui.TextDisplay(header_text))

        self.add_item(ui.Separator())

        invite_url = get_bot_invite_url(bot)
        action_row = ui.ActionRow()
        support_btn = ui.Button(label="Support Server", url=URLs.SUPPORT, style=discord.ButtonStyle.link)
        action_row.add_item(support_btn)
        dash_btn = ui.Button(label="Website", url=URLs.WEBSITE, style=discord.ButtonStyle.link)
        action_row.add_item(dash_btn)
        inv_btn = ui.Button(label="Add Me", url=invite_url, style=discord.ButtonStyle.link)
        action_row.add_item(inv_btn)
        self.add_item(action_row)


class SupportView(ui.LayoutView):
    """Discord Components V2 LayoutView for the /support command."""
    def __init__(self, bot: discord.Client):
        super().__init__(timeout=None)
        self.add_item(SupportContainer(bot))


def build_support_card(bot: discord.Client) -> SupportView:
    return SupportView(bot)

