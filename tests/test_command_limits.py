import importlib
import inspect
import pkgutil
import re
import unittest

import discord
from discord import app_commands
from discord.ext import commands


DISCORD_NAME_RE = re.compile(r"^[-_\w]{1,32}$")
MAX_NAME_LEN = 32
MAX_DESCRIPTION_LEN = 100
MAX_CHOICE_NAME_LEN = 100
MAX_CHOICE_VALUE_LEN = 100
MAX_OPTIONS = 25
MAX_CHOICES = 25


def _discover_cog_classes() -> list[type[commands.Cog]]:
    """Imports every module under `cogs/` and returns all concrete Cog subclasses."""
    cog_classes: list[type[commands.Cog]] = []
    seen: set[type[commands.Cog]] = set()

    for _, mod_name, _ in pkgutil.walk_packages(["cogs"], prefix="cogs."):
        mod = importlib.import_module(mod_name)
        for _, obj in inspect.getmembers(mod, inspect.isclass):
            if (
                issubclass(obj, commands.Cog)
                and obj is not commands.Cog
                and obj.__module__ == mod_name
                and obj not in seen
            ):
                seen.add(obj)
                cog_classes.append(obj)

    return cog_classes


def _collect_app_commands(cog_cls: type[commands.Cog]) -> list[object]:
    """Extracts all slash/hybrid/context-menu app command objects defined on a Cog class."""
    found: list[object] = []

    if issubclass(cog_cls, commands.GroupCog) and getattr(cog_cls, "__cog_app_commands_group__", None):
        found.append(cog_cls.__cog_app_commands_group__)

    for cmd in cog_cls.__cog_commands__:
        if isinstance(cmd, (commands.HybridCommand, commands.HybridGroup)) and cmd.app_command is not None:
            found.append(cmd.app_command)

    for cmd in cog_cls.__cog_app_commands__:
        found.append(cmd)

    return found


def _validate_name(label: str, name: str, violations: list[str]) -> None:
    if not (1 <= len(name) <= MAX_NAME_LEN):
        violations.append(f"{label}: name length {len(name)} not in 1..{MAX_NAME_LEN} ({name!r})")
    if name != name.lower():
        violations.append(f"{label}: name must be lowercase ({name!r})")
    if not DISCORD_NAME_RE.match(name):
        violations.append(f"{label}: name contains invalid characters ({name!r})")


def _validate_description(label: str, desc: str | None, violations: list[str]) -> None:
    if not desc or not (1 <= len(desc) <= MAX_DESCRIPTION_LEN):
        length = len(desc) if desc is not None else 0
        violations.append(
            f"{label}: description length {length} not in 1..{MAX_DESCRIPTION_LEN} ({desc!r})"
        )


def _validate_app_command(
    cog_name: str,
    cmd: object,
    violations: list[str],
    prefix: str = "",
) -> int:
    """Validates an app command or group recursively; returns count of validated commands."""
    full_path = f"{prefix}/{cmd.name}" if prefix else f"{cog_name}:/{cmd.name}"

    if isinstance(cmd, app_commands.ContextMenu):
        if not (1 <= len(cmd.name) <= MAX_NAME_LEN):
            violations.append(
                f"{full_path}: context menu name length {len(cmd.name)} not in 1..{MAX_NAME_LEN}"
            )
        return 1

    if isinstance(cmd, app_commands.Group):
        _validate_name(full_path, cmd.name, violations)
        _validate_description(full_path, cmd.description, violations)
        count = 1
        for sub in cmd.commands:
            count += _validate_app_command(cog_name, sub, violations, prefix=full_path)
        return count

    if isinstance(cmd, app_commands.Command):
        _validate_name(full_path, cmd.name, violations)
        _validate_description(full_path, cmd.description, violations)

        if len(cmd.parameters) > MAX_OPTIONS:
            violations.append(f"{full_path}: {len(cmd.parameters)} options exceeds max {MAX_OPTIONS}")

        for param in cmd.parameters:
            param_label = f"{full_path} param '{param.display_name}'"
            _validate_name(param_label, param.display_name, violations)
            _validate_description(param_label, param.description, violations)

            if param.choices:
                if len(param.choices) > MAX_CHOICES:
                    violations.append(
                        f"{param_label}: {len(param.choices)} choices exceeds max {MAX_CHOICES}"
                    )
                for choice in param.choices:
                    if not (1 <= len(choice.name) <= MAX_CHOICE_NAME_LEN):
                        violations.append(
                            f"{param_label} choice {choice.name!r}: name length {len(choice.name)} "
                            f"not in 1..{MAX_CHOICE_NAME_LEN}"
                        )
                    if isinstance(choice.value, str) and len(choice.value) > MAX_CHOICE_VALUE_LEN:
                        violations.append(
                            f"{param_label} choice {choice.name!r}: value length {len(choice.value)} "
                            f"exceeds {MAX_CHOICE_VALUE_LEN}"
                        )
        return 1

    return 0


def _validate_serialized_payload(label: str, payload: dict, violations: list[str]) -> None:
    """Validates the Discord JSON payload produced by `to_dict(tree)`."""
    cmd_type = payload.get("type", 1)
    name = payload.get("name", "")
    if cmd_type == 1:
        _validate_name(f"{label} (payload)", name, violations)
        _validate_description(f"{label} (payload)", payload.get("description"), violations)
    else:
        if not (1 <= len(name) <= MAX_NAME_LEN):
            violations.append(f"{label} (payload): name length {len(name)} not in 1..{MAX_NAME_LEN}")

    options = payload.get("options", [])
    if len(options) > MAX_OPTIONS:
        violations.append(f"{label} (payload): {len(options)} options exceeds max {MAX_OPTIONS}")

    for opt in options:
        opt_label = f"{label} -> {opt.get('name', '<unnamed>')}"
        _validate_name(opt_label, opt.get("name", ""), violations)
        _validate_description(opt_label, opt.get("description"), violations)
        if opt.get("type") in (1, 2):  # subcommand / subcommand group
            _validate_serialized_payload(opt_label, opt, violations)
        for choice in opt.get("choices", []):
            ch_name = choice.get("name", "")
            ch_val = choice.get("value")
            if not (1 <= len(ch_name) <= MAX_CHOICE_NAME_LEN):
                violations.append(
                    f"{opt_label} choice {ch_name!r}: name length {len(ch_name)} "
                    f"not in 1..{MAX_CHOICE_NAME_LEN}"
                )
            if isinstance(ch_val, str) and len(ch_val) > MAX_CHOICE_VALUE_LEN:
                violations.append(
                    f"{opt_label} choice {ch_name!r}: value length {len(ch_val)} "
                    f"exceeds {MAX_CHOICE_VALUE_LEN}"
                )


class TestDiscordCommandLimits(unittest.TestCase):
    def test_all_hybrid_and_app_commands_meet_discord_limits(self):
        bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())
        cog_classes = _discover_cog_classes()
        self.assertGreater(len(cog_classes), 0, "Expected to discover cog classes under cogs/")

        violations: list[str] = []
        checked_commands = 0

        for cog_cls in cog_classes:
            for app_cmd in _collect_app_commands(cog_cls):
                checked_commands += _validate_app_command(cog_cls.__name__, app_cmd, violations)
                payload = app_cmd.to_dict(bot.tree)
                _validate_serialized_payload(f"{cog_cls.__name__}:/{app_cmd.name}", payload, violations)

        self.assertGreater(checked_commands, 0, "Expected to find hybrid/app commands across cogs")
        self.assertEqual(
            violations,
            [],
            "Discord slash/hybrid command limit violations found:\n" + "\n".join(violations),
        )


if __name__ == "__main__":
    unittest.main()
