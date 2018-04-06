import discord
from discord.ext import commands
import aiohttp
import time
import async_timeout
import checks
from datetime import datetime
import asyncio
import random
import rethinkdb as db
import twitter
import requests
import json
from io import TextIOWrapper
import sys
import feedparser

sys.stdout.flush()

f = open("tokens.json", "r")
tokens = json.loads(f.read())
f.close()

# Adds error logging to Linux journalctl
sys.stdout = TextIOWrapper(sys.stdout.detach(),
                           encoding=sys.stdout.encoding,
                           errors="replace",
                           line_buffering=True)

twitterapi = twitter.Api(consumer_key=tokens["twitter"]["consumer_key"],
                         consumer_secret=tokens["twitter"]["consumer_secret"],
                         access_token_key=tokens["twitter"]["access_token_key"],
                         access_token_secret=tokens["twitter"]["access_token_secret"])

db.connect("localhost", 28015, 'spacebot').repl()


def getprefix(bot, message):
    try:
        return db.table("serverdata").get(message.server.id).get_field("prefix").run()
    except (db.ReqlNonExistenceError, AttributeError):
        return '?'


SHORTCUTS = {"VirginGalactic": "VG", "Roscosmos": "RFSA", "SpaceX": "SpX", "OrbitalATK": "ATK",
             "BlueOrigin": "BO", "RocketLab": "RL", "CloudAerospace": "CA", "VectorSpaceSystems": "Vector",
             "SierraNevadaCorp": "SNC", "CopenhagenSuborbitals": "Copsub", "StratolaunchSystems": "Stratolaunch"}

description = '''A bot made by @Cakeofdestiny#2318 for space-related info, launch timings, tweets, and reddit posts.'''

bot = commands.Bot(command_prefix=getprefix, description=description)


# bot.remove_command("help")


class main:
    def __init__(self, bot):

        self.server = discord.server
        self.newprefix = None
        self.bot = bot
        self.notifstimer = 0
        self.last_fetch = 0
        self.launch_data = []
        self.mnames = {"January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6, "July": 7, "August": 8,
                       "September": 9, "October": 10,
                       "November": 11, "December": 12}

        self.session = aiohttp.ClientSession(loop=self.bot.loop)

    async def on_ready(self):
        print('Logged in as', flush=True)
        print(self.bot.user.name, flush=True)
        print(self.bot.user.id, flush=True)
        print(discord.utils.oauth_url(self.bot.user.id), flush=True)
        print('------', flush=True)
        try:
            self.llanswers = await self.fetch("https://launchlibrary.net/1.2/launch/next/10")
        except asyncio.TimeoutError:
            print("llanswers timeout")

        self.bot.loop.create_task(self.updateservercount())
        self.bot.loop.create_task(self.update_launch_data())

    async def on_message(self, message):
        if message.channel.is_private:
            return
        if message.content.startswith(message.server.me.mention):
            await self.bot.send_message(message.channel,
                                        "The current prefix for this server is: " + str(
                                            getprefix(self.bot, message)))

        if message.content[-17:] == " Unknown command." and message.author.id == "256766117505269760":
            await self.bot.delete_message(message)
        for r in range(len(message.content)):
            try:
                if message.content[r:r + 10] == "¯\_(ツ)_/¯" and str(
                        message.server.id) == "153646955464097792" and not message.author.permissions_in(
                         message.channel).manage_channels:
                    msgtodelete = await self.bot.send_message(message.channel, "\U0001F6D1 **No shrugs!**")
                    await self.bot.delete_message(message)
                    await asyncio.sleep(5)
                    await self.bot.delete_message(msgtodelete)
            except:
                pass

    async def on_member_join(self, member):
        try:
            wmessage = db.table("serverdata").get(member.server.id).get_field("wmessage").run()
        except db.ReqlNonExistenceError:
            return

        try:
            await self.bot.send_message(self.bot.get_channel(wmessage[0]), wmessage[1].format(member.mention))
        except:
            pass

    async def on_member_remove(self, member):
        try:

            if int(member.server.id) == 316186751565824001:
                memberTime = member.joined_at
                diffTime = datetime.now() - memberTime

                if member.nick:
                    await self.bot.send_message(self.bot.get_channel("316188105528836099"),
                                                "📤** `{0.name}#{0.discriminator}` (ID: `{0.id}`), AKA `{0.nick}` has left this server.**\n He joined at `{1.day}.{1.month}.{1.year}, on {1.hour}:{1.minute}`. That was `{2.day}` days ago."
                                                .format(member, memberTime, diffTime))
                else:
                    await self.bot.send_message(self.bot.get_channel("316188105528836099"),
                                                "📤** `{0.name}#{0.discriminator}` (ID: `{0.id}`) has left this server.**\n He joined at `{1.day}.{1.month}.{1.year}, on {1.hour}:{1.minute}`. That was `{2.days}` days ago."
                                                .format(member, memberTime, diffTime))

        except discord.Forbidden:
            pass

    async def on_command_error(self, error, ctx):
        if ctx.invoked_subcommand:
            pages = bot.formatter.format_help_for(ctx, ctx.invoked_subcommand)
        else:
            pages = bot.formatter.format_help_for(ctx, ctx.command)

        for page in pages:
            if isinstance(error, commands.MissingRequiredArgument):
                em = discord.Embed(title="Missing args ❌",
                                   description=page.strip("```").replace('<', '[').replace('>', ']'),
                                   color=discord.Color.red())
            elif isinstance(error, commands.BadArgument):
                em = discord.Embed(title="Bad args ❌",
                                   description=page.strip("```").replace('<', '[').replace('>', ']'),
                                   color=discord.Color.red())
            else:
                em = discord.Embed(title="Command Error! ❌",
                                   description=page.strip("```").replace('<', '[').replace('>', ']') + "\n\n{}".format(error),
                                   color=discord.Color.red())
                print(error)

            await self.bot.send_message(ctx.message.channel, embed=em)

    """
    @commands.command(pass_context=True)
    async def help(self, ctx, specific: str = None):
        fullmessage = ""

        if specific:
            command = self.bot.commands.get(specific)
            if not command:
                await self.embederror(ctx, "The command {} does not exist.".format(specific))
                return
            page = bot.formatter.format_help_for(ctx, command)[0]
            fullmessage = page.strip("```").replace('<', '[').replace('>', ']')

        else:
            for key, value in sorted(self.bot.commands.items()):
                if key in ['getinvite', 'l', 'getall', 'rss', 'wm','eq','graphicsinterchangeformat', 'gifs', 'eq', 'elonquote','decr']:
                    continue
                fullmessage += ("**_{}_ - {} **\n".format(key, value.short_doc))

        em = discord.Embed(title="Displaying help for {}:".format(self.bot.user.name)
                           , description=fullmessage, color=discord.Color.blue())
        em.set_thumbnail(url=self.bot.user.avatar_url)
        await self.bot.say(embed=em)"""

    async def updateservercount(self):
        while not self.bot.is_closed:
            thepostdata = {
                "server_count": len(self.bot.servers)
            }
            header = {
                'Authorization': tokens["discord.pw_token"],
                'Content-Type': 'application/json'}

            async with self.session.post('https://bots.discord.pw/api/bots/291185373860855808/stats', headers=header,
                                         data=json.dumps(thepostdata)) as resp:
                pass

            await asyncio.sleep(3600)

    async def fetch(self, url):
        with async_timeout.timeout(60):
            tries = 0
            while tries < 5:
                try:
                    async with self.session.get(url) as response:
                        return response
                except aiohttp.ClientConnectionError:
                    print("Connection error with " + url)
                    tries += 1
                    continue
            raise aiohttp.ClientConnectionError



    @staticmethod
    def get_time_to(timestamp: int):
        if timestamp == 0:
            return "TBD"

        launchtime = datetime.fromtimestamp(timestamp)
        now = datetime.fromtimestamp(time.time())
        td = launchtime - now

        td = td.total_seconds()

        ttime = {"days": int(td / 86400), "hours": 0, "minutes": 0}
        td = td % 86400
        ttime["hours"] = int(td / 3600)
        td = td % 3600
        ttime["minutes"] = int(td / 60)

        return ttime

    @commands.command(aliases=['addme'])
    async def invite(self):
        """Invite me to your server!"""
        em = discord.Embed(description="**Spacebot** by Cakeofdestiny#2318 .\n"
                                       "[Invite Link](https://discordapp.com/oauth2/authorize?client_id=291185373860855808&scope=bot&permissions=27648)\n"
                                       "[Github](https://github.com/plutoberth/Spacebot)\n"
                                       "[Official Server (kinda)](https://discord.gg/dHdbpwV)",
                           color=discord.Color.blue())
        print(self.bot.user.avatar_url)
        em.set_author(name="Links:", icon_url=self.bot.user.avatar_url)
        await self.bot.say(embed=em)

    @commands.command()
    async def randomlanding(self):
        async with self.session.get(
                "http://api.giphy.com/v1/gifs/search?q=spacex+landing.json&api_key=" + tokens["giphy_api_key"]) as resp:
            try:
                tdict = await resp.json()
            except json.decoder.JSONDecodeError:
                print("JSONDecodeError! r: {}. Giphy is probably down.", flush=True)

            em = discord.Embed(color=discord.Colour.dark_blue())
            randomelement = random.choice(tdict["data"])["url"]

            dashocr = []
            for r in range(len(randomelement)):
                if randomelement[r] == "-":
                    dashocr.append(r)
            url = "https://media.giphy.com/media/{}/giphy.gif".format(randomelement[dashocr[-1] + 1:])
            print(url)
            em.set_image(url=url)
            await self.bot.say(embed=em)

    @commands.command()
    async def randomlaunch(self):
        async with self.session.get(
                "http://api.giphy.com/v1/gifs/search?q=rocket+launch.json&api_key=" + tokens["giphy_api_key"]) as resp:
            try:
                tdict = await resp.json()
            except json.decoder.JSONDecodeError:
                print("JSONDecodeError! r: {}. Giphy is probably down.", flush=True)

            em = discord.Embed(color=discord.Colour.dark_blue())
            randomelement = random.choice(tdict["data"])["url"]

            dashocr = []
            for r in range(len(randomelement)):
                if randomelement[r] == "-":
                    dashocr.append(r)
            url = "https://media.giphy.com/media/{}/giphy.gif".format(randomelement[dashocr[-1] + 1:])
            print(url)
            em.set_image(url=url)
            await self.bot.say(embed=em)

    @commands.cooldown(1, 30, commands.BucketType.user)
    @checks.mod_or_permissions(manage_channels=True)
    @commands.command(pass_context=True)
    async def echo(self, ctx, *, message: str = None):
        """Repeat a message."""
        if not message:
            return

        await self.bot.delete_message(ctx.message)
        em = discord.Embed(description=message, color=discord.Colour.dark_blue())
        await self.bot.say(embed=em)

    @checks.mod_or_permissions(manage_channels=True)
    @commands.command(pass_context=True)
    async def purge(self, ctx, *, amount: str = None):
        """Purge a certain amount of messages from the chat"""
        if not amount:
            await self.bot.say(
                "Usage : *{}purge [messages]* \n Messages has to be below 100 (except easter eggs).".format(
                    getprefix(self.bot, ctx.message)))
            return
        if amount.isdigit():
            if int(amount) > 100:
                await self.bot.say(
                    "Usage : `**{}purge [messages - maximum of 100]**`".format(
                        getprefix(self.bot, ctx.message)))
            else:
                amount = int(amount)
                await self.bot.purge_from(ctx.message.channel, limit=amount)

        else:
            await self.bot.delete_message(ctx.message)
            await self.bot.say("**I WILL DESTROY {}** :boom: :boom:".format(amount.upper()))

    @checks.mod_or_permissions(manage_server=True)
    @commands.command(pass_context=True, no_pm=True, aliases=['wm'])
    async def welcomemessage(self, ctx, *, message: str = None):
        prefix = getprefix(self.bot, ctx.message)
        # Try to get the welcome message
        try:
            wmessage = db.table("serverdata").get(ctx.message.server.id).get_field("wmessage").run()
        except db.ReqlNonExistenceError:
            # If it does not exist, and the user didn't enter one, respond with an explanation prompt.
            if message is None:
                await self.bot.say(
                    "ℹ **This server has no welcome message. \n\n To set one, use {}welcomemessage "
                    "[message]\n Curly Brackets `{}` in your message will be replaced with a mention of the user.**".format(
                        prefix, '{}'))
                return

        if message == "clear":
            db.table("serverdata").get(ctx.message.server.id).delete().run()
            await self.bot.say(":negative_squared_cross_mark: Welcome messages disabled successfully.")
            return

        # If it exists, and the user did not enter one, reply with the message.
        if message is None:
            r = requests.post("https://pastebin.com/api/api_post.php",
                              data={'api_dev_key': tokens["pastebin_api_dev_key"], 'api_option': 'paste',
                                    'api_paste_code': wmessage[1]})

            await self.bot.say(
                "ℹ **The welcome message for this server is hosted on Pastebin: {0} \n\nTo change it, "
                "use `{1}wm [message]`"
                "\nCurly Brackets `{2}` in your message will be replaced with a mention of the user."
                "\nTo disable welcome messages, type `{1}wm clear`** ".format(r.text, prefix, '{}'))
            return

        if "{}" not in message:
            await self.bot.say(
                ":warning: **You didn't specify a user identifier, so the bot will not mention the user that joins. "
                "\n Good example message: `Hi, {} and welcome to our discord server`**")

        wmessage = [ctx.message.channel.id, message]
        db.table('serverdata').insert({"id": ctx.message.server.id, "wmessage": wmessage}, conflict="update").run()

        await self.bot.say(
            "\U00002705 **Welcome message saved successfully, and will be posted to this channel every time a new "
            "user joins.**")

    @checks.mod_or_permissions(manage_server=True)
    @commands.command(pass_context=True, aliases=['rss'])
    async def rssnotifs(self, ctx, rss_link: str = None):
        """Get notifs from RSS sources."""
        # DB STRUCTURE
        # table : subdata
        # rows : rss/rsslp
        # columns : [channel1ID, channel2ID]

        channel_rss_subs = []
        complete_rss_db = db.table("subdata").get("rss").run()

        channel_id = ctx.message.channel.id

        if complete_rss_db is None:
            complete_rss_db = {}

        # Get a list of RSS feeds for that channel

        for k, v in complete_rss_db.items():
            if ctx.message.channel.id in v:
                channel_rss_subs.append(k)

        prefix = getprefix(self.bot, ctx.message)

        if not rss_link:
            if len(channel_rss_subs) > 0:
                await self.bot.say(
                    ":bell: **This channel is subscribed to the following RSS feeds: \n`{}`"
                    "\n\n Use `{}rss [RSS feed link] ` to add or remove feeds.**".format(
                        "\n".join(channel_rss_subs), prefix))
            else:
                await self.bot.say(
                    ":no_bell: **This channel isn't subscribed to any RSS feeds.\n"
                    "Use `{}rss [RSS feed link]` to subscribe to some. "
                    "subreddits.**")
            return

        # Check if the RSS Feed exists

        feed = feedparser.parse(rss_link)
        rss_link = rss_link.lower()

        if len(feed['entries']) == 0:
            await self.bot.say("❌ **This feed doesn't exist, or it is unreachable.**")
            return

        try:
            sub_list = db.table("subdata").get("rss").get_field(rss_link).run()
        except (db.ReqlNonExistenceError, KeyError):
            sub_list = []

        if channel_id in sub_list:
            sub_list.remove(channel_id)
            await self.bot.say(
                ":no_bell: **This channel will no longer be notified of new posts from `{}`**".format(rss_link))
        else:
            sub_list.append(channel_id)
            await self.bot.say(":bell: **This channel will be notified of new posts from `{}`**".format(rss_link))

        db.table("subdata").insert({"id": "rss", rss_link: sub_list}, conflict="update").run()

    @checks.mod_or_permissions(manage_server=True)
    @commands.command(pass_context=True, aliases=['twitter'])
    async def twitternotifs(self, ctx, subname: str = None):
        """Toggle new tweet notifications from chosen Twitter accounts.."""
        # DB STRUCTURE
        # table : subdata
        # rows : reddit/twitter/twitterlp/redditlp
        # columns : [channel1ID, channel2ID]

        channel_twitter_subs = []
        completetwitterdb = db.table("subdata").get("twitter").run()

        if not completetwitterdb:
            completetwitterdb = {}

        for k, v in completetwitterdb.items():
            if ctx.message.channel.id in v:
                channel_twitter_subs.append(k)
        prefix = getprefix(self.bot, ctx.message)

        if not subname:
            if len(channel_twitter_subs) > 0:
                await self.bot.say(
                    ":bell: **This channel receives Twitter notifications from: `@{}.`"
                    "\n\n Use `{}twitter [Twitter Username]` to add more.**".format(
                        ", @".join(channel_twitter_subs), prefix))
            else:
                await self.bot.say(
                    ":no_bell: **This channel doesn't receive notifications from any subreddits.\n"
                    "Use `{}twitter [Twitter Username]` to be notified of new posts from your chosen "
                    "subreddits.**")
            return

        subname = subname.lower()
        channelid = ctx.message.channel.id

        try:
            twitterapi.GetUserTimeline(screen_name=subname, count=1)
        except twitter.error.TwitterError:
            await self.bot.say("\U0000274C **The twitter user `@{}` does not exist.**".format(subname))
            return
        try:
            sublist = db.table("subdata").get("twitter").get_field(subname).run()
        except (db.ReqlNonExistenceError, KeyError):
            sublist = []

        if ctx.message.channel.id in sublist:
            sublist.remove(channelid)
            await self.bot.say(
                ":no_bell: **This channel will no longer be notified of new tweets from `@{}`**".format(subname))
        else:
            sublist.append(ctx.message.channel.id)
            await self.bot.say(":bell: **This channel will be notified of new tweets from `@{}`**".format(subname))

        db.table("subdata").insert({"id": "twitter", subname: sublist}, conflict="update").run()

    @checks.mod_or_permissions(manage_server=True)
    @commands.command(pass_context=True, aliases=['reddit'])
    async def redditnotifs(self, ctx, subname: str = None):
        """Toggle new post notifications from chosen subreddits."""

        # DB STRUCTURE
        # table : subdata
        # rows : reddit/twitter/twitterlp/redditlp
        # columns : [channel1ID, channel2ID]

        channel_reddit_subs = []

        completeredditdb = db.table("subdata").get("reddit").run()

        if not completeredditdb:
            print("empty rdb")
            completeredditdb = {}

        for k, v in completeredditdb.items():
            if ctx.message.channel.id in v:
                channel_reddit_subs.append(k)

        prefix = getprefix(self.bot, ctx.message)

        if not subname:
            if len(channel_reddit_subs) > 0:
                await self.bot.say(
                    ":bell: **This channel receives reddit notifications from: `{}.`"
                    "\n\n Use `{}reddit [subreddit name]` to add more.**".format(
                        ", ".join(channel_reddit_subs), prefix))
            else:
                await self.bot.say(
                    ":no_bell: **This channel doesn't receive notifications from any subreddits.\n"
                    "Use `{}reddit [subreddit name]` to be notified of new posts from your chosen "
                    "subreddits.**")
            return

        subname = subname.lower()

        if subname[0:1] == "/":
            subname = subname[1:]
        elif subname[0:2] == "r/":
            subname = subname[2:]
        elif subname[0:3] == "/r/":
            subname = subname[3:]

        async with self.session.get("https://www.reddit.com/r/{}/new.json?sort=new".format(subname)) as resp:
            tdict = await resp.json()
            if len(tdict["data"]["children"]) == 0:
                await self.bot.say("❌ **This sub doesn't exist, or has 0 posts.**")
                return

        try:
            sublist = db.table("subdata").get("reddit").get_field(subname).run()
        except (db.ReqlNonExistenceError, KeyError):
            sublist = []

        if ctx.message.channel.id in sublist:
            await self.bot.say(
                ":no_bell: **This channel will no longer be notified of new posts from `r/{}`**".format(subname))
            sublist.remove(ctx.message.channel.id)
        else:
            sublist.append(ctx.message.channel.id)
            await self.bot.say(":bell: **This channel will be notified of new posts from `r/{}`**".format(subname))

        db.table("subdata").insert({"id": "reddit", subname: sublist}, conflict="update").run()

    @commands.command(pass_context=True)
    async def l(self, ctx, serverid: str):
        """Restricted Command."""
        if not str(ctx.message.author.id) == "146357631760596993":
            return
        await self.bot.leave_server(self.bot.get_server(serverid))

    @commands.command(pass_context=True)
    async def getinvite(self, ctx, serverid: str, invlength: int):
        if str(ctx.message.author.id) == "146357631760596993":
            try:
                invite = str(await self.bot.create_invite(self.bot.get_server(serverid), max_age=invlength))
            except discord.errors.Forbidden:
                invite = "Couldn't manage to create invite"

            await self.bot.say("yes master {}".format(invite))

    @commands.command(pass_context=True)
    async def getall(self, ctx):
        if str(ctx.message.author.id) == "146357631760596993":
            users = sum([len(r.members) for r in self.bot.servers])
            bots = sum([len([x for x in r.members if x.bot]) for r in self.bot.servers])
            await self.bot.say(
                "I am in **{}** servers, that overall have **{}** members and **{}** bots.".format(
                    len(self.bot.servers), users - bots, bots))

            message = ""
            counter = 0
            for server in self.bot.servers:
                counter += 1
                bots = 0
                for member in server.members:
                    if member.bot:
                        bots += 1
                message = message + "\n Server id: {}\n Server name: {} \n Members: {} \n Bots: {}\n----------------------------".format(
                    server.id, server.name, len(server.members) - bots, bots)

            r = requests.post("https://pastebin.com/api/api_post.php",
                              data={'api_dev_key': tokens["pastebin_api_dev_key"], 'api_option': 'paste',
                                    'api_paste_code': message})

            await self.bot.say("Pastebin data here: {}".format(r.text))

    @commands.command(pass_context=True, no_pm=True, aliases=["gifs", "graphicsinterchangeformat"])
    async def gif(self, ctx, gifname: str = None, *, gifmessage: str = None):
        """Allows the user to set custom response gifs with the bot."""
        prefix = getprefix(self.bot, ctx.message)
        user_perms = ctx.message.author.permissions_in(ctx.message.channel).manage_server
        # Try to get the welcome message
        gifs = {}
        try:
            gifs = db.table("serverdata").get(ctx.message.server.id).get_field("gifs").run()
        except db.ReqlNonExistenceError:
            # If the user didn't try to assign any gifs,
            if gifname is None or gifmessage is None:
                if user_perms:
                    await self.bot.say(
                        "ℹ **This server has no custom gifs. \n\nTo set some, use `{}gif "
                        "[gifname] [gifurl]`**".format(prefix))
                else:
                    await self.bot.say(
                        "ℹ **This server has no custom gifs.\n Ask your admins to set some.**")
                return

        # If they didn't request any gifs, display the list.
        if not gifname:
            if len(gifs) > 0:
                giflist = ""
                # This code gets a list of gifs, and encapsulates only the url part of the gif in non-embed carets for discord.
                for k, v in gifs.items():
                    if v.find("http") != -1:
                        giflist += "\n-`{}`: {}<{}>".format(k, v[0:v.find("http")], v[v.find("http"):])
                    else:
                        giflist += "\n-`{}`: {}".format(k, v)
                if user_perms:
                    giflist += "\n To add more, use `{0}gif [gifname] [gifurl]` or `{0}gif remove [gifname] to remove.`".format(
                        prefix)
                if len(giflist) < 1750:  # discord limit is 2000
                    message_to_delete = await self.bot.send_message(ctx.message.channel,
                                                                    "ℹ **This server has the following gifs:**"
                                                                    "{}  \n:alarm_clock: **This message will be deleted in 3 minutes.**".format(
                                                                        giflist))
                    delay_time = 180
                else:
                    r = requests.post("https://pastebin.com/api/api_post.php",
                                      data={'api_dev_key': tokens["pastebin_api_dev_key"], 'api_option': 'paste',
                                            'api_paste_code': giflist})
                    message_to_delete = await self.bot.send_message(ctx.message.channel,
                                                                    "ℹ **This server has too many gifs to display, so they are stored in pastebin: {}**"
                                                                    "\n:alarm_clock: **This message will be deleted in 1 minute.**".format(
                                                                        r.text))
                    delay_time = 60
                await asyncio.sleep(delay_time)
                await self.bot.delete_message(message_to_delete)
                await self.bot.delete_message(ctx.message)

            elif user_perms:
                await self.bot.say(
                    "ℹ **This server has no custom gifs. \n\n To set one, use {}gif "
                    "[gifname] [gifurl]\n **".format(prefix))
            else:
                await self.bot.say(
                    "ℹ **This server has no custom gifs.\n Ask your admins to set some.**")
            return
        # If the user requested a gif, but didn't try to set one.
        if not gifmessage or not user_perms:
            await self.bot.say(gifs.get(gifname, "❌ **Gif not found!**\nUse {}gifs to see the list.".format(prefix)))
            return

        if gifname == "remove":
            if gifmessage in gifs:
                del gifs[gifmessage]
                await self.bot.say("🚮 Removed `{}`.".format(gifmessage))
            else:
                await self.bot.say(
                    "❌ `{}` isn't a gif in this server. Could you have misspelled it?".format(gifmessage))
        else:
            gifs[gifname] = gifmessage
            await self.bot.say(":white_check_mark: Set `{}` to `{}`.".format(gifname, gifmessage))

        db.table('serverdata').insert({"id": ctx.message.server.id, "gifs": gifs}, conflict="update").run()

    async def toggle_notify(self, notify_role, member):
        if notify_role in member.roles:
            await self.bot.remove_roles(member, notify_role)
            return False
        else:
            await self.bot.add_roles(member, notify_role)
            return True

    @commands.command(pass_context=True)
    async def fh(self, ctx):
        # launch_time = 00000
        # time_to_launch = self.get_time_to(launch_time)

        fullmessage = "Vehicle: __**Falcon Heavy**__ | Payload: __**Elon's Midnight Cherry Roadster**__"

        fullmessage += " | Time: __**February 6, 20:45 UTC**__\n"

        fullmessage += "Pad: __**Historic LC-39A**__ \nStatus : **Resounding Success!**"

        fullmessage += "\n"

        # if time_to_launch["days"] != 1:
        #    fullmessage += "**In {} days,".format(time_to_launch["days"])
        # else:
        #    fullmessage += "**In 1 day,"

        # fullmessage += " {} hours, and {} minutes.**".format(time_to_launch["hours"], time_to_launch["minutes"])

        # We check if there is an available live stream.
        fullmessage += "\n**[Recording available!](https://www.youtube.com/watch?v=wbSwFU6tY1c)**"

        fullmessage += "\n**Thanks to everyone who joined us. We hope to see you on the next launches!**"

        em = discord.Embed(description=fullmessage, color=discord.Color.dark_blue())
        em.set_thumbnail(
            url="https://cdn.teslarati.com/wp-content/uploads/2017/12/Roadster-and-Falcon-Heavy-Elon-Musk-2-e1513972707360.jpg")
        em.set_author(name="Falcon Heavy:",
                      icon_url="https://mk0spaceflightnoa02a.kinstacdn.com/wp-content/uploads/2017/01/C1pzAfrWEAIi7RU.png")
        await self.bot.send_message(ctx.message.channel, embed=em)

    @commands.command(pass_context=True)
    async def notifyme(self, ctx, *, agency_list_raw: str = "Launch"):
        if int(ctx.message.server.id) != 316186751565824001:
            return
        agency_list = agency_list_raw.split(" ")
        # Lowering the cases
        agency_list = [r.lower() for r in agency_list]

        agency_roles = []
        reverse_shortcuts = {v.lower(): k.lower() for k, v in SHORTCUTS.items()}
        for r in ctx.message.server.roles:
            for j in agency_list:
                if j == r.name.lower()[:-7] or reverse_shortcuts.get(j, "invalid") == r.name.lower()[:-7]:
                    agency_roles.append(r)

        # No input
        if len(agency_roles) == 0:
            # Getting role list
            role_list = [r.name for r in ctx.message.server.roles if "-notify" in r.name.lower()]
            # Removing "-notify"s
            role_list = [r[:-7] for r in role_list]
            # Removing All
            role_list = [r for r in role_list if r != "All" and r != "Launch"]
            # Handling shortcuts
            role_list = [(r + " - **" + SHORTCUTS.get(r, r)) + "**" for r in role_list]

            await self.bot.say(
                "ℹ **This agency does not exist. \n Usage: `{}notifyme [agency] [agency] [agency]...`\n __Available agencies__**: "
                "\n **All - All launch updates and agency updates.**"
                "\n **Launch - All launch updates.**\n"
                "\n*{}* "
                "\n `lowercase` works too."
                .format(getprefix(bot, ctx.message), "\n".join(role_list)))
            return

        member = ctx.message.author
        added_roles = []
        removed_roles = []

        try:
            for r in agency_roles:
                # Checks if it has been added or removed
                toggle = await self.toggle_notify(r, member)
                if toggle:
                    added_roles.append(r.name[:-7])
                else:
                    removed_roles.append(r.name[:-7])

        except discord.Forbidden:
            await self.bot.say("❌ I cannot manage roles.")
            return

        message = ""
        if len(added_roles) > 0:
            if len(added_roles) == 1 and added_roles[0] == "Launch":
                message += ":bell: You will be `@mentioned on launches.` \n\n**You can sign up for more frequent and diverse updates using `.notifyme all`, or for updates for specific agencies only - use `.notifyme ?` to display full list.**\n"
            else:
                message += ":bell: **You will be `@mentioned` on launches, launch updates, news and events related to `{}`.**\n".format(
                    ", ".join(added_roles))

        if len(removed_roles) > 0:
            if len(removed_roles) == 1 and removed_roles[0] == "Launch":
                message += ":no_bell: **You will no longer be `@mentioned` on launches or launch updates.**\n"
            else:
                message += ":no_bell: **You will no longer be `@mentioned` on launches, launch updates, news and events related to `{}`.**\n".format(
                    ", ".join(removed_roles))

        if len(removed_roles) + len(added_roles) < len(agency_list):
            removed = len(agency_list) - (len(removed_roles) + len(added_roles))
            message += "*{} invalid roles have been omitted.*".format(removed)

        await self.bot.say(message)

    async def update_launch_data(self):
        while not self.bot.is_closed:
            await self.get_launch_data()
            await asyncio.sleep(600)

    async def get_launch_data(self):
        """Returns a list containing launch data from www.launchlibrary.net
            Thank you LL devs!"""

        if time.time() - self.last_fetch > 1800:
            resp = await self.fetch("https://launchlibrary.net/1.3/launch/next/10")
            fetch_data = (await resp.json())["launches"]

            self.last_fetch = time.time()
            self.launch_data = fetch_data
        else:
            fetch_data = self.launch_data
        if not fetch_data:
            # This makes sure that the receiving end doesnt freak out from an empty array
            fetch_data = []
        return fetch_data

    @commands.command(pass_context=True, aliases=['nl'])
    async def nextlaunch(self, ctx):
        """Get information on the next launch."""
        launch_info = await self.get_launch_data()
        if len(launch_info) == 0:
            await self.bot.say(
                "❌ Unable to establish a link with launchlibrary. **Please contact Cakeofdestiny#2318 immediately.**")
            return
        nldata = None
        for r in launch_info:
            if r["wsstamp"] == 0:
                continue

            if r["status"] == 1:
                nldata = r
                break

        if not nldata:
            await self.bot.say(
                ":rocket: Currently there are 0 listed launches with accurate dates. Check back soon :alarm_clock: !")
            return

        time_to_launch = self.get_time_to(nldata["wsstamp"])

        fullmessage = "Vehicle: __**{0[0]}**__| Payload: __**{0[1]}**__".format(nldata["name"].split('|'))

        ws = nldata["windowstart"][:-7]
        ws = ws[0:ws.index(str(datetime.now().year))] + ws[-5:] + " UTC"

        fullmessage += " | Time: __**{}**__\n".format(ws)

        try:
            # The launch site will be one line down from the time and other things
            launchsite = nldata["location"]["pads"][0]["name"]
            fullmessage += "Pad: __**{}**__".format(launchsite)
        except KeyError:
            pass
        fullmessage += "\n\n"  # We print those here to make sure it newlines twice

        if time_to_launch["days"] != 1:
            fullmessage += "**In {} days,".format(time_to_launch["days"])
        else:
            fullmessage += "**In 1 day,"

        fullmessage += " {} hours, and {} minutes.**".format(time_to_launch["hours"], time_to_launch["minutes"])

        # We check if there is an available live stream.
        if len(nldata["vidURLs"]) > 0:
            vidurl = nldata["vidURLs"][0]
            fullmessage += "\n**[Livestream available!]({})**".format(vidurl)

        if int(ctx.message.server.id) == 316186751565824001:
            fullmessage += "\n\n**To be notified on launches and special events, use the command `.notifyme`**"

        em = discord.Embed(description=fullmessage, color=discord.Color.dark_blue())
        em.set_author(name="Next launch:",
                      icon_url="https://images-ext-1.discordapp.net/eyJ1cmwiOiJodHRwOi8vaS5pbWd1ci5jb20vVk1kRGo2Yy5wbmcifQ.CmIVz3NKC91ria81ae45bo4yEiA")
        await self.bot.send_message(ctx.message.channel, embed=em)

    @commands.command(aliases=['ll', 'launchlist'])
    async def listlaunches(self):
        """Get a list of launches"""

        launch_info = await self.get_launch_data()
        if len(launch_info) == 0:
            await self.bot.say(
                ":( Unable to establish a link with launchlibrary. **Please contact Cakeofdestiny#2318 immediately.**")
            return

        fullmessage = ""
        actlaunches = 0
        for launch in launch_info:
            if launch["status"] != 1 and actlaunches == 0:
                continue

            actlaunches += 1
            fullmessage += "Vehicle: __**{0[0]}**__| Payload: __**{0[1]}**__".format(launch["name"].split('|'))

            ws = launch["windowstart"][:-7]
            # If the launch was not assigned an accurate date yet, display the month only.
            if launch["status"] == 2:
                ws = ws[0:ws.index(' ')] + " - Day TBD"
            else:
                # ws now: December 30, 2017 00:00
                ws = ws[0:ws.index(',') + 2] + ws[-5:] + " UTC"
                # ws now: December 30, 00:00 UTC

            fullmessage += " | Time: {}\n".format(ws)

        em = discord.Embed(description=fullmessage, color=discord.Color.dark_blue())
        em.set_author(name="Next {} spacecraft launches:".format(actlaunches),
                      icon_url="https://images-ext-1.discordapp.net/eyJ1cmwiOiJodHRwOi8vaS5pbWd1ci5jb20vVk1kRGo2Yy5wbmcifQ.CmIVz3NKC91ria81ae45bo4yEiA")
        await self.bot.say(embed=em)

    @commands.command(pass_context=True, aliases=['elonquote', 'eq'])
    async def elon(self):
        with open('./elonquotes.txt') as data_file:
            quotes = data_file.readlines()

        n = random.randrange(0, len(quotes))
        desc = "**{}**".format(quotes[n])
        em = discord.Embed(description=desc, color=discord.Color.blue())
        em.set_author(name="And for today, quote number {}:".format(n), icon_url="http://i.imgur.com/hBbuHbq.png")
        await self.bot.say(embed=em)

    @commands.command(pass_context=True, aliases=['decr'])
    async def decronym(self, ctx, acronym: str = None):
        """Get the definition of your favorite acronyms!"""
        # Big thanks to /u/OrangeredStilton for his acronym list!
        with open('./decronym.json') as decronymFile:
            decronym = json.load(decronymFile)
        if not acronym:
            await self.bot.say("❌ **Invalid Syntax!** \n Correct usage: `{}decronym/decr [acronym]`".format(
                getprefix(self.bot, ctx.message)))
            return

        matching_values = [value for key, value in decronym.items() if key.upper() == acronym.upper()]
        if len(matching_values) == 0:
            await self.bot.say("❌ **0 Matching definitions found**. \n Could you have misspelled the acronym?")
            return

        matching_values = matching_values[0]
        acronym_message = "\n".join(
            ["{}. **{}**".format(i + 1, matching_values[i]) for i in range(len(matching_values))])
        if len(matching_values) == 1:
            em = discord.Embed(description=acronym_message,
                               title="I found 1 definition for the acronym **{}**:".format(acronym.upper()),
                               color=discord.Color.blue())
        else:
            em = discord.Embed(description=acronym_message,
                               title="I found {} definitions for the acronym **{}**:".format(len(matching_values),
                                                                                             acronym.upper()),
                               color=discord.Color.blue())
        await self.bot.say(embed=em)

    @checks.mod_or_permissions(manage_server=True)
    @commands.command(pass_context=True, no_pm=True)
    async def prefix(self, ctx, newprefix: str = None):
        """Change or view server prefix."""

        if not newprefix:
            await self.bot.say("ℹ **The current prefix for this server is: `{}`**".format(
                getprefix(self.bot, ctx.message)))
            return

        if "@" in newprefix:
            await self.bot.say("❌ **INVALID PREFIX**")
            return

        db.table('serverdata').insert({"id": ctx.message.server.id, "prefix": newprefix}, conflict="update").run()

        await self.bot.say(
            "**The prefix for this server has been set to: {}**".format(getprefix(self.bot, ctx.message)))

    @checks.mod_or_permissions(manage_roles=True)
    @commands.command(pass_context=True, no_pm=True)
    async def ping(self, ctx, *roles_str_list:str):
        """Use this command to ping un-pingable roles. The bot will make them pingable and ping, then toggle them back."""
        member = ctx.message.server.get_member(self.bot.user.id)
        if not member.permissions_in(ctx.message.channel).manage_roles:
            await self.bot.say("❌ **I don't have the necessary permissions for this command.**\nPlease give me the **Manage Roles** permission.")
            return
        roles = []
        for role_string in roles_str_list:
            # Easier role matching
            matching_roles = [r for r in ctx.message.server.roles if role_string.lower() in r.name.lower()]
            if len(matching_roles) == 1:
                # If only one role matches, pick that one
                roles.append(matching_roles[0])
        if len(roles) == 0:
            await self.bot.say("ℹ To use this command, give it a list of roles as arguments. It will mention them and make them unmentionable again."
                               "\n**If they are already mentionable, it'll make them unmentionable.**")
            return
        unlocked_roles = []
        roles_to_mention = []
        for role in roles:
            if role.mentionable:
                unlocked_roles.append(role)
            else:
                roles_to_mention.append(role)
        for role in roles_to_mention:
            await self.bot.edit_role(server=ctx.message.server, role=role, mentionable=True)

        all_roles = roles_to_mention+unlocked_roles
        mention_string = " | ".join(r.mention for r in all_roles)
        message = "Mentioning | {} |...".format(mention_string)
        if len(unlocked_roles) > 0:
            message += "\nℹ I've gone ahead and **removed** mentionability for the following roles: **`{}`**".format(", ".join([r.name for r in unlocked_roles]))

        await self.bot.say(message)
        for role in all_roles:
            await self.bot.edit_role(server=ctx.message.server, role=role, mentionable=False)












bot.add_cog(main(bot))
bot.load_extension("redditcontent")
bot.load_extension("twittercontent")
bot.load_extension("rsscontent")

bot.run(tokens["bot_token"])
