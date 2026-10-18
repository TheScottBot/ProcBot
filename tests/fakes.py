"""Stand-ins for Discord objects, so slash commands can be run without connecting to Discord."""

import asyncio
import types

import discord


def run(coro):
    return asyncio.run(coro)


class User:
    def __init__(self, uid: int, name: str):
        self.id, self.name, self.display_name = uid, name, name
        self.mention = f"<@{uid}>"

    def __str__(self):
        return self.name


class Guild:
    def __init__(self, gid: int = 111, name: str = "Test Server"):
        self.id, self.name = gid, name

    def __str__(self):
        return self.name


class Sent:
    def __init__(self, content=None, embed=None, ephemeral=False, allowed_mentions=None):
        self.content, self.embed, self.ephemeral, self.allowed_mentions = content, embed, ephemeral, allowed_mentions


class Response:
    def __init__(self, interaction):
        self.interaction = interaction
        self.done = False

    def is_done(self):
        return self.done

    async def send_message(self, content=None, *, embed=None, ephemeral=False, allowed_mentions=None, **kwargs):
        self.done = True
        self.interaction.sent.append(Sent(content, embed, ephemeral, allowed_mentions))


class Thread(discord.Thread):
    """A thread in a channel: real enough for isinstance(), with just its ids."""

    def __init__(self, tid: int, parent_id: int):
        self.id, self.parent_id = tid, parent_id


class Interaction:
    """A slash command being run: in a server (guild given) or a DM (guild=None), in a channel or a thread."""

    def __init__(self, user: User | None = None, guild: Guild | None = "default", channel_id: int = 500,
                 thread: Thread | None = None):
        self.user = user or User(1, "scott")
        self.guild = Guild() if guild == "default" else guild
        self.guild_id = self.guild.id if self.guild else None
        self.channel = thread or types.SimpleNamespace(id=channel_id)
        self.channel_id = thread.id if thread else channel_id
        self.client = types.SimpleNamespace(user=User(999, "ProcBot"))
        self.response = Response(self)
        self.sent: list[Sent] = []

    @property
    def last(self) -> Sent:
        return self.sent[-1]
