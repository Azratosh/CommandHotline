import asyncio
import traceback

import discord
from discord.ext import commands

import peewee
import peewee_async


from lib.config import Config

import logging

logging.basicConfig(
    level=Config.logging["level"],
    format="[%(asctime)s] %(levelname)s: %(message)s",
)


_logger = logging.getLogger(__name__)

_default_extensions = {"Birthdays": "cogs.birthdays"}


def init_event_handlers(bot: commands.Bot):
    @bot.event
    async def on_ready():
        for name, module in _default_extensions.items():
            if module not in bot.extensions:
                _logger.debug(f"Loading extension: {name} ({module})")
                bot.load_extension(module)
            else:
                _logger.debug(f"Extension already loaded: {name} ({module})")

        _logger.info(f"{bot.user.name} is up and running.")

    @bot.event
    async def on_connect():
        _logger.info(f"{bot.user.name} connected.")

    @bot.event
    async def on_disconnect():
        _logger.warning(f"{bot.user.name} disconnected.")

    @bot.event
    async def on_command_error(ctx: commands.Context, exception):
        author_full = f"{ctx.author.name}#{ctx.author.discriminator} ({ctx.author.id})"
        if isinstance(ctx.channel, discord.DMChannel):
            guild_full = "None"
            channel_full = "Direct Message"
        else:
            guild_full = f"{ctx.guild.name} ({ctx.guild.id})"
            channel_full = f"{ctx.channel.name} ({ctx.channel.id})"

        _logger.error("Encountered exception during execution of command.")
        for log_message, arg in [
            ("Message: %s", ctx.message),
            ("Author: %s", author_full),
            ("Guild: %s", guild_full),
            ("Channel: %s", channel_full),
        ]:
            _logger.error(log_message, arg)

        _logger.error(
            " ".join(
                traceback.format_exception(
                    type(exception), exception, exception.__traceback__
                )
            )
        )

        embed = discord.Embed.from_dict(
            {
                "title": "Error",
                "description": str(exception),
            }
        )


def main():
    if Config.mentionable:
        command_prefix = commands.when_mentioned_or(Config.prefix)
    else:
        command_prefix = Config.prefix

    bot = commands.Bot(
        command_prefix=command_prefix,
        intents=discord.Intents.all(),
    )

    init_event_handlers(bot)

    bot.run(Config.token)


if __name__ == "__main__":
    main()
