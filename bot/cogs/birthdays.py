import asyncio
import datetime
import logging
import random
import re
from typing import *

from dateutil.relativedelta import relativedelta
import discord
from discord.ext import commands, tasks
import peewee
import peewee_async

from lib.database import manager, BaseModel
from lib import util

_logger = logging.getLogger(__name__)


class BirthdayParseError(ValueError):
    pass


class Birthday(BaseModel):
    user_id = peewee.BigIntegerField()
    guild_id = peewee.BigIntegerField()
    year = peewee.SmallIntegerField(null=True)
    month = peewee.SmallIntegerField()
    day = peewee.SmallIntegerField()
    last_notified = peewee.DateTimeField(null=True)
    enabled = peewee.BooleanField(default=True)

    class Meta:
        primary_key = peewee.CompositeKey("user_id", "guild_id")

    def __str__(self) -> str:
        if self.year:
            return datetime.date(self.year, self.month, self.day).strftime("%d.%m.%Y")

        return f"{self.day:02}.{self.month:02}."

    def __repr__(self):
        return super().__str__()

    PATTERNS_DATE: List[Tuple[re.Pattern, str]] = [
        (re.compile(_regex, re.IGNORECASE), _format)
        for _regex, _format in [
            (r"(?P<date>\d\d\d\d-[01]?\d-[0123]?\d)", "%Y-%m-%d"),
            (r"(?P<date>\d\d-[01]?\d-[0123]?\d)", "%y-%m-%d"),
            (r"(?P<date>[01]?\d-[0123]?\d)", "%m-%d"),
            (r"(?P<date>[0123]?\d\.[01]?\d\.\d\d\d\d)", "%d.%m.%Y"),
            (r"(?P<date>[0123]?\d\.[01]?\d\.\d\d)", "%d.%m.%y"),
            (r"(?P<date>[0123]?\d\.[01]?\d)", "%d.%m"),
            (r"(?P<date>[0123]?\d\.[01]?\d\.)", "%d.%m."),
            (r"(?P<date>[01]?\d/[0123]?\d/\d\d\d\d)", "%m/%d/%Y"),
            (r"(?P<date>[01]?\d/[0123]?\d/\d\d)", "%m/%d/%y"),
            (r"(?P<date>[01]?\d/[0123]?\d)", "%m/%d"),
        ]
    ]

    @classmethod
    def parse_date(cls, text: str) -> Tuple[Optional[int], int, int]:
        text = text.strip()

        match, fmt = None, None
        for pattern, fmt_ in cls.PATTERNS_DATE:
            match = pattern.match(text)
            if match:
                match = match["date"]
                fmt = fmt_
                break
        else:
            raise BirthdayParseError(
                "The birthday you've entered cannot be parsed. :pensive:"
            )

        if "%y" not in fmt and "%Y" not in fmt:
            year_fmt = " %Y"
            match += datetime.datetime.now().strftime(year_fmt)
            fmt += year_fmt
            date = datetime.datetime.strptime(match, fmt).date()

            return None, date.month, date.day

        date = datetime.datetime.strptime(match, fmt).date()

        if date > datetime.date.today():
            raise BirthdayParseError("You cannot be born in the future.")

        return date.year, date.month, date.day


class Birthdays(commands.Cog):
    RETENTION_DAYS = 90

    # {day} must be ordinal number + space or just a space char
    BIRTHDAY_MESSAGES = [
        "Happy {day}birthday, {name}! :tada:",
        "It's {name}'s {day}birthday today! Congratulations! :tada:",
        "Oh look, it's {name}'s {day}birthday! Congratz! :tada:",
        "Happy {day}birthday to you, {name}! :tada:",
    ]

    BIRTHDAY_COMMENTS = [
        "How does it feel to have aged by another year?",
        "Starting to feel old?",
        "Imagine *aging.*",
        "Soon you may actually sit with the adults.",
        "Feeling old yet?",
        "You know what they say, good fruit takes time to ripen.",
        "May all your wishes come true, except the illegal ones.",
        "May all your wishes come true, especially the illegal ones.",
        "May all your wishes come true.",
        "Imagine being born.",
        "Wishing you an abundance of love.",
        "Hope you're gonna celebrate!",
        "Hope you're gonna party!",
        "Hope you're gonna consume various psychoactive substances!",
        "You did a great job in this year of your life. No really, I mean it.",
        "You got older! Hooray!",
        "You aged by another year. How does that make you feel?",
        "You're one year closer to your death.",
        "... more like, happy :bee:-rthday.\n\nHaha.",
        "You did the thing, you got older!",
        "Aging like fine wine, I'm sure.",
        "Aging like fine milk, I'm sure.",
        "Embrace your inner party animal and celebrate.",
        "Sounds like someone's gotta celebrate.",
        "I didn't know what to get you, so I got you this notification to your birthday.",
        "Statistics show that those who have the most birthdays live the longest.",
        "Age is merely the number of years the world has been enjoying you.",
        "Remember that growing old is mandatory, but growing up is optional!\n\nAnd you should really consider growing up.",
        "If anyone calls you old, hit them with your cane and throw your teeth at them.",
        "One year closer to getting that drip with those velcro shoes.",
        "Go solve your crossword puzzles like the old person you just became.",
        "Turn up the *meow*sic and let's get this *paw*ty started! :cat:",
        "What type of music is scary for birthday balloons? Pop music.",
        "What goes up and never goes down? Your age.",
        "What does every birthday end with? The letter Y.",
        "How do raccoons celebrate their birthday? They get trashed.",
        "Why do cats love birthdays? They love to *purr*ty. :cat:",
        "Don't die.",
        "Careful. Too many birthdays will eventually kill you.",
        'I wanted to send you something "sexy" but the mailman made me get out of the mailbox. So here\'s this wacky message instead!',
        "Since it's your birthday, I'll let you leave the lights on. :smirk:",
        "Let's get shitfaced.",
        "You're the best thing your mother ever birthed.",
    ]

    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.birthday_cron_retention.start()
        self.birthday_cron_notify.start()

    @commands.group(name="birthday", invoke_without_command=True)
    async def birthday(self, ctx: commands.Context, *, text: Optional[str] = None):
        user_id = ctx.author.id
        guild_id = ctx.guild.id

        if text:
            try:
                year, month, day = Birthday.parse_date(text)

                birthday = await manager.safe_get(
                    Birthday, user_id=user_id, guild_id=guild_id
                )

                if birthday:
                    await manager.update_fields(
                        birthday, year=year, month=month, day=day
                    )

                else:
                    birthday = await manager.create(
                        Birthday,
                        **{
                            "user_id": user_id,
                            "guild_id": guild_id,
                            "year": year,
                            "month": month,
                            "day": day,
                        },
                    )

                embed_data = {"description": f"Your birthday was set to `{birthday}`"}

            except BirthdayParseError as e:
                embed_data = {"title": "Error", "description": str(e)}

        else:
            birthday = await manager.safe_get(
                Birthday, user_id=user_id, guild_id=guild_id
            )

            if birthday:
                embed_data = {"description": f"Your birthday is on `{birthday}`"}

            else:
                embed_data = {"description": "You haven't set your birthday yet."}

        return await ctx.reply(embed=discord.Embed.from_dict(embed_data))

    @birthday.command(name="delete", aliases=("del", "remove", "forget"))
    async def birthday_delete(self, ctx: commands.Context):
        birthday = await manager.safe_get(
            Birthday, user_id=ctx.author.id, guild_id=ctx.guild.id
        )

        if birthday:
            await manager.delete(birthday)
            embed_data = {"description": "Your birthday was successfully deleted."}

        else:
            embed_data = {
                "title": "Error",
                "description": "You haven't set a birthday that you could delete.",
            }

        return await ctx.reply(embed=discord.Embed.from_dict(embed_data))

    @commands.command(name="unbirthday")
    async def unbirthday(self, ctx):
        return await self.birthday_delete(ctx)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Enables birthday notifications for a member if they join a guild
        with which they recently shared their birthday with.

        :param member: The guild member for which to try to enable birthday notifications.
        """
        birthday = manager.safe_get(
            Birthday, user_id=member.id, guild_id=member.guild.id
        )

        if birthday:
            await manager.update_fields(birthday, enabled=True)

    @commands.Cog.listener()
    async def on_member_leave(self, member: discord.Member):
        """Disables birthday notifications for a member if they leave a guild
        with which they shared their birthday with.

        :param member: The guild member for which to try to disable birthday notifications.
        """
        birthday = manager.safe_get(
            Birthday, user_id=member.id, guild_id=member.guild.id
        )

        if birthday:
            await manager.update_fields(birthday, enabled=False)

    @commands.Cog.listener()
    async def on_member_ban(self, member: discord.Member):
        birthday = manager.safe_get(
            Birthday, user_id=member.id, guild_id=member.guild.id
        )

        if birthday:
            await manager.delete(birthday)

    @tasks.loop(hours=24)
    async def birthday_cron_retention(self):
        now = datetime.datetime.now()
        date_expired = now - relativedelta(days=self.RETENTION_DAYS)

        query = Birthday.select().where(
            (Birthday.enabled == False) & (Birthday.date_updated < date_expired)
        )

        for birthday in await peewee_async.select(query):
            _logger.info(f"Deleting birthday of {birthday.user_id}")
            await manager.delete(birthday)

    @tasks.loop(hours=4)
    async def birthday_cron_notify(self):
        today = datetime.date.today()
        today_dt = datetime.datetime(today.year, today.month, today.day, 0, 0)

        # NOTE: Should probably just compare by year or so; comparing by datetime
        #       is just for debugging

        query = Birthday.select().where(
            Birthday.enabled
            & (Birthday.day == today.day)
            & (Birthday.month == today.month)
            & ((Birthday.last_notified < today_dt) | (Birthday.last_notified.is_null()))
        )

        result = await peewee_async.select(query)
        coroutines = [self.try_notify(birthday, today) for birthday in result]
        await asyncio.gather(*coroutines)

    @birthday_cron_notify.before_loop
    async def before_birthday_cron_notify(self):
        await self.bot.wait_until_ready()

    async def try_notify(
        self, birthday: Birthday, today: Optional[datetime.date] = None
    ):
        today = today if today is not None else datetime.date.today()

        guild: discord.Guild = self.bot.get_guild(birthday.guild_id)
        if not guild:
            _logger.error(
                f"Unable to get guild from {birthday.guild_id = }. "
                "Is the bot still in that server?"
            )
            return

        if not guild.system_channel:
            _logger.error(
                f"Cannot send birthday notifications for {guild = } "
                "because no system channel is set. Skipping."
            )
            return

        member: discord.Member = guild.get_member(birthday.user_id)
        if not member:
            _logger.error(
                f"Unable to get member from {birthday.user_id = }. "
                "Did they leave the server?"
            )
            return

        if birthday.year:
            birthday_date = datetime.date(birthday.year, birthday.month, birthday.day)
            years_old = relativedelta(today, birthday_date).years

            # Don't forget space at the end
            day = f"{util.ordinal(years_old)} "
        else:
            day = " "

        heading = random.choice(self.BIRTHDAY_MESSAGES).format(
            day=day, name=member.mention
        )
        content = random.choice(self.BIRTHDAY_COMMENTS)

        embed_data = {
            "description": f"**{heading}**\n\n{content}",
        }

        await guild.system_channel.send(embed=discord.Embed.from_dict(embed_data))
        await manager.update_fields(birthday, last_notified=datetime.datetime.now())


def setup(bot: commands.Bot):
    Birthday.create_table(safe=True)
    bot.add_cog(Birthdays(bot))


def teardown(bot: commands.Bot):
    bot.remove_cog(Birthdays.__name__)
