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


f = open("tokens.json","r")
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
    except db.ReqlNonExistenceError:
        return '?'


description = '''A bot made by @Cakeofdestiny for space-related info, launch timings, tweets, and reddit posts.'''

bot = commands.Bot(command_prefix=getprefix, description=description)


class main:
    def __init__(self, bot):
        self.server = discord.server
        self.newprefix = None
        self.bot = bot
        self.notifstimer = 0
        self.ll = 0
        self.nl = 0
        self.nldata = []
        self.lldata = []
        self.echos = {}


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

        self.llanswers = await self.fetch("https://launchlibrary.net/1.2/launch/next/10")

        self.bot.loop.create_task(self.updateservercount())

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
                if member.nick:
                    await self.bot.send_message(self.bot.get_channel(316188105528836099),
                                                ":outbox_tray:** {0.name}, AKA {0.nick} has left this server.**\n He joined at {0.joined_at}."
                                                .format(member))
                else:
                    await self.bot.send_message(self.bot.get_channel(316188105528836099),
                                                ":outbox_tray:** {0.name} has left this server.**\n He joined at {0.joined_at}."
                                                .format(member))

        except:
            pass

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


            #header = {
            #    'Authorization': tokens["discordbots_token"],
            #    'Content-Type': 'application/json'}

            #async with self.session.post('https://discordbots.org/api/bots/291185373860855808/stats', headers=header,
            #                             data=json.dumps(thepostdata)) as resp:
            #    pass

            await asyncio.sleep(3600)

    async def fetch(self, url):
        with async_timeout.timeout(10):
            async with self.session.get(url) as response:
                return response

    def gettimeto(self, timestamp: int):
        if timestamp == 0:
            return "TBD"

        launchtime = datetime.fromtimestamp(timestamp)
        now = datetime.fromtimestamp(time.time())
        td = launchtime - now

        td = td.total_seconds()

        ttime = {"days": 0, "hours": 0, "minutes": 0}
        ttime["days"] = int(td/86400)
        td = td % 86400
        ttime["hours"] = int(td/3600)
        td = td % 3600
        ttime["minutes"] = int(td/60)

        return ttime

    @commands.command(aliases=['addme'])
    async def invite(self):
        em = discord.Embed(description="**Spacebot** by Cakeofdestiny.\n"
                                       "[Invite Link](https://discordapp.com/oauth2/authorize?client_id=291185373860855808&scope=bot&permissions=27648)\n"
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

    @checks.mod_or_permissions(manage_channels=True)
    @commands.command(pass_context=True)
    async def echo(self, ctx, *, message: str = None):
        """Repeat a message."""
        if not message:
            return

        if ctx.message.author.id in self.echos:
            if time.time() - self.echos[ctx.message.author.id] < 30 and not ctx.message.author.permissions_in(
                    ctx.message.channel).manage_channels:
                await self.bot.delete_message(ctx.message)
                return
        self.echos[ctx.message.author.id] = time.time()
        await self.bot.delete_message(ctx.message)
        r = lambda: random.randrange(1, 244)
        em = discord.Embed(description=message, color=discord.Colour.dark_blue())
        await self.bot.say(embed=em)

    @checks.mod_or_permissions(manage_channels=True)
    @commands.command(pass_context=True)
    async def purge(self, ctx, *, amount: str = None):
        """Purge a certain amount of messages from the chat"""
        if not amount.isdigit():
            await self.bot.say("**I WILL DESTROY {}** :boom: :boom:".format(amount.upper()))
            return
        amount = int(amount)
        if not amount or amount > 100:
            return
        await self.bot.purge_from(ctx.message.channel, limit=amount)

    @commands.command(pass_context=True)
    async def notiftimer(self, ctx, amount: int = None):
        """Debug"""
        await self.bot.say(120 - (time.time() - self.notifstimer))

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
                    ":information_source: **This server has no welcome message. \n\n To set one, use {}welcomemessage "
                    "[message]\n Curly Brackets `{}` in your message will be replaced with a mention of the user.**".format(
                        prefix, '{}'))
                return

        if message == "clear":
            db.table("serverdata").get(ctx.message.server.id).delete().run()
            await self.bot.say(":negative_squared_cross_mark: Welcome messages disabled successfully.")
            return

        # If it exists, and the user did not enter one, reply with the message.
        if message is None:
            await self.bot.say(
                ":information_source: **The welcome message for this server is: {0} \n\n To change it, "
                "use {1}wm [message]"
                "\n Curly Brackets `{2}` in your message will be replaced with a mention of the user."
                "\n Type `{1}wm clear`** ".format(wmessage[1], prefix, '{}'))
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
    async def rssnotifs(self, ctx, rssLink: str = None):
        await self.bot.say("This is not ready yet :(")
        return

        # DB STRUCTURE
        # table : subdata
        # rows : rss/rsslp
        # columns : [channel1ID, channel2ID]

        channel_rss_subs = []
        completerssdb = db.table("subdata").get("rss").run()

        if completerssdb == None:
            completerssdb = {}

        for k, v in completerssdb.items():
            if ctx.message.channel.id in v:
                channel_rss_subs.append(k)

        prefix = getprefix(self.bot, ctx.message)

        if not rssLink:
            if len(channel_rss_subs) > 0 :
                await self.bot.say(
                    ":bell: **This channel is subscribed to the following RSS feeds: \n`{}`"
                    "\n Use `{}rss [RSS feed link] ` to add or remove feeds.**".format(
                    prefix, "\n".join(channel_twitter_subs)))
            else:
                await self.bot.say(
                    ":no_bell: **This channel isn't subscribed to any RSS feeds.\n"
                    "Use `{}rss [RSS feed link]` to subscribe to some. "
                    "subreddits.**")
            return

        rssLink = rssLink.lower()
        channelid = ctx.message.channel.id

        #check if the feed exists

        feed = feedparser.parse(rssLink)

        if len(feed['feed']) == 0:
            return









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

        if completetwitterdb == None:
            completetwitterdb = {}

        for k, v in completetwitterdb.items():
            if ctx.message.channel.id in v:
                channel_twitter_subs.append(k)
        prefix = getprefix(self.bot, ctx.message)

        if not subname:
            if len(channel_twitter_subs) > 0 :
                await self.bot.say(
                    ":bell: **This channel receives Twitter notifications from: `{}.`"
                    "\n\n Use `{}twitter [Twitter Username]` to add more.**".format(
                    prefix, ", @".join(channel_twitter_subs)))
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

        db.table("subdata").insert({"id": "twitter", subname:sublist}, conflict="update").run()





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
            if len(channel_reddit_subs) > 0 :
                await self.bot.say(
                    ":bell: **This channel receives reddit notifications from: `{}.`"
                    "\n\n Use `{}reddit [subreddit name]` to add more.**".format(
                    prefix, ", ".join(channel_reddit_subs)))
            else:
                await self.bot.say(
                    ":no_bell: **This channel doesn't receive notifications from any subreddits.\n"
                    "Use `{}reddit [subreddit name]` to be notified of new posts from your chosen "
                    "subreddits.**")
            return

        subname = subname.lower()
        channelid = ctx.message.channel.id

        if subname[0:1] == "/":
            subname = subname[1:]
        elif subname[0:2] == "r/":
            subname = subname[2:]
        elif subname[0:3] == "/r/":
            subname = subname[3:]

        async with self.session.get("https://www.reddit.com/r/{}/new.json?sort=new".format(subname)) as resp:
            tdict = await resp.json()
            if len(tdict["data"]["children"]) == 0:
                await self.bot.say(":x: **This sub doesn't exist, or has 0 posts.**")
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
        if not str(ctx.message.author.id) == "146357631760596993":
            await self.bot.say(":x: **Restricted!**")
            return
        try:
            invite = str(await self.bot.create_invite(self.bot.get_server(serverid), max_age=invlength))
        except discord.errors.Forbidden:
            invite = "Couldn't manage to create invite"

        await self.bot.say("yes master {}".format(invite))

    @commands.command(pass_context=True)
    async def getall(self, ctx):
        if not str(ctx.message.author.id) == "146357631760596993":
            await self.bot.say(":x: **Restricted!**")
            return

        users = sum([len(r.members) for r in self.bot.servers])
        bots = sum([len([x for x in r.members if x.bot]) for r in self.bot.servers])
        await self.bot.say(
            "I am in **{}** servers, that overall have **{}** members and **{}** bots.".format(len(self.bot.servers),
                                                                                               users - bots, bots))

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
                          data={'api_dev_key': '53f35aa049c27370155d4c4e7db0de86', 'api_option': 'paste',
                                'api_paste_code': message})

        await self.bot.say("Pastebin data here: {}".format(r.text))

    @commands.command(pass_context=True, aliases=['amos'])
    async def amos6(self, ctx):
        """rip"""
        await self.bot.say("Rip :( http://pop.h-cdn.co/assets/16/35/1472752799-ezgifcom-optimize-2.gif")

    @commands.command(pass_context=True)
    async def sfr2(self, ctx):
        """rip2"""
        await self.bot.say("Rip2 :( https://i.imgur.com/O86IDwm.gifv")

    @commands.command(pass_context=True)
    async def launchnotify(self, ctx, *, agency: str = None):
        if "jamie" in agency.lower():
            await self.bot.say("no")
            return

        # Get agencies from rethink db -- add filter
        ulndata = db.table("launchnotify").get(ctx.message.server.id).run()
        useragencies = [ulndata[k]["data"]["name"] for k, v in ulndata.items() if ctx.message.author.id in v]
        print(useragencies)

        if not agency:
            if len(useragencies) > 0:
                await self.bot.say(":bell: **You're subscribed to the following agencies: `{}`** "
                                   "\n To toggle an agency subscription: `{}launchnotify [agency_name]`"
                                   "\n You'll be notified **24 hours, 6 hours, and 1 hour** before any launch by that agency.".format(
                    ", ".join(useragencies), getprefix(self.bot, ctx.message)))
                return
            else:
                await self.bot.say(":no_bell: **You're not subscribed to any agency.** "
                                   "\n To toggle an agency subscription: `{}launchnotify [agency_name]`"
                                   "\n You'll be notified **24 hours, 6 hours, and 1 hour** before any launch by that agency.".format(
                    getprefix(self.bot, ctx.message)))
                return

        agency = agency.replace(" ", "_")
        async with self.session.get("https://launchlibrary.net/1.2/agency?name={}".format(agency)) as resp:
            agencydata = (await resp.json())["agencies"]

        if len(agencydata) > 1:
            await self.bot.say(":x: **The search returned more than one agency that fits this name. "
                               "\nPlease pick a more descriptive name**.")
            return
        elif len(agencydata) == 0:
            await self.bot.say(":x: **The search returned 0 agencies that fit this name. "
                               "\nPlease pick a more accurate/ less descriptive name**.")
            return

        agencydata = agencydata[0]
        agencydata['id'] = str(agencydata['id'])
        if agencydata['id'] not in ulndata:
            ulndata[agencydata['id']] = []

        if ctx.message.author.id in ulndata[agencydata['id']]:
            await self.bot.say(
                ":no_bell: **You will no longer receive launch notifications from {}.**".format(agencydata["name"]))
            ulndata[agencydata['id']].remove(ctx.message.author.id)
        else:
            await self.bot.say(
                ":bell: **You will get notified for launches by {}.**"
                "\n You'll be notified **24 hours, 6 hours, and 1 hour** before any launch by that agency.".format(
                    agencydata["name"]))
            ulndata[agencydata['id']].append(agencydata)

        db.table('launchnotify').insert({"id": ctx.message.server.id, agencydata['id']: ulndata[agencydata['id']]},
                                        conflict="update").run()

    @commands.command(aliases=['falconheavy','fh'])
    async def whenisfalconheavylaunching(self):
        await self.bot.say("In **6 months.**")

    @commands.command(pass_context=True)
    async def notifyme(self, ctx):
        if int(ctx.message.server.id) != 316186751565824001:
           return

        LNRole = [r for r in ctx.message.server.roles if r.name == "LaunchNotify"][0]
        member = ctx.message.author

        if LNRole in member.roles:
            await self.bot.remove_roles(member, LNRole)
            await self.bot.say(":no_bell: **You will no longer be `@mentioned` on launches and special events.**")

        else:
            await self.bot.add_roles(member, LNRole)
            await self.bot.say(":bell: **You will be `@mentioned` on launches and special events.**")

    @commands.command(pass_context=True, aliases=['nl'])
    async def nextlaunch(self, ctx, new=1):
        """Get information on the next launch."""
        xpathquery = []

        if time.time() - self.nl > 900:
            async with self.session.get("https://launchlibrary.net/1.2/launch/next/10") as resp:
                nlinfo = (await resp.json())["launches"]

            for r in nlinfo:
                if (r["wsstamp"] == 0):
                    continue

                date = datetime.fromtimestamp(r["wsstamp"])

                month = dict((v, k) for k, v in self.mnames.items())[date.month]
                ttime = self.gettimeto(r["wsstamp"])

                if r["status"] == 1:
                    nldata = r
                    break

            self.nldata = nldata
            self.nl = time.time()

        else:
            nldata = self.nldata
            date = datetime.fromtimestamp(nldata["wsstamp"])

            month = dict((v, k) for k, v in self.mnames.items())[date.month]
            ttime = self.gettimeto(nldata["wsstamp"])

        fullmessage = "Vehicle: __**{0[0]}**__| Payload: __**{0[1]}**__".format(nldata["name"].split('|'))

        ws = nldata["windowstart"][:-7]
        ws = ws[0:ws.index(str(datetime.now().year))] + ws[-5:] + " UTC"

        fullmessage += " | Time: {} \n\n".format(ws)

        if ttime["days"] != 1:
            fullmessage += "**In {} days,".format(ttime["days"])
        else:
            fullmessage += "**In 1 day,"

        fullmessage += " {} hours, and {} minutes.**".format(ttime["hours"], ttime["minutes"])

        if int(ctx.message.server.id) == 316186751565824001:
            fullmessage += "\n\n**To be notified on launches and special events, use the command `.notifyme`.**"

        em = discord.Embed(description=fullmessage, color=discord.Color.dark_blue())
        em.set_author(name="Next launch:",
                      icon_url="https://images-ext-1.discordapp.net/eyJ1cmwiOiJodHRwOi8vaS5pbWd1ci5jb20vVk1kRGo2Yy5wbmcifQ.CmIVz3NKC91ria81ae45bo4yEiA")
        await self.bot.send_message(ctx.message.channel, embed=em)

    @commands.command(pass_context=True, aliases=['ll', 'launchlist'])
    async def listlaunches(self, ctx):
        """Get a list of launches"""
        xpathquery = []
        actnumber = 0
        if time.time() - self.ll > 1800:
            async with self.session.get("https://launchlibrary.net/1.2/launch/next/10") as resp:
                lldata = (await resp.json())["launches"]

            self.lldata = lldata
            self.ll = time.time()
        else:
            lldata = self.lldata

        fullmessage = ""
        actlaunches = 0
        for launch in lldata:
            if launch["status"] != 1 and actlaunches == 0:
                continue

            actlaunches += 1
            fullmessage += "Vehicle: __**{0[0]}**__| Payload: __**{0[1]}**__".format(launch["name"].split('|'))

            ws = launch["windowstart"][:-7]
            ws = ws[0:ws.index(str(datetime.now().year))] + ws[-5:] + " UTC"

            fullmessage += " | Time: {}\n".format(ws)

        em = discord.Embed(description=fullmessage, color=discord.Color.dark_blue())
        em.set_author(name="Next {} spacecraft launches:".format(actlaunches),
                      icon_url="https://images-ext-1.discordapp.net/eyJ1cmwiOiJodHRwOi8vaS5pbWd1ci5jb20vVk1kRGo2Yy5wbmcifQ.CmIVz3NKC91ria81ae45bo4yEiA")
        await self.bot.say(embed=em)

    @commands.command(pass_context=True, aliases=['elonquote', 'eq'])
    async def elon(self):
        with open('./elonquotes.txt') as data_file:
            eql = data_file.readlines()

        equotes = []
        for r in range(0, len(eql), 3):
            equotes.append(eql[r][1:])

        print(equotes)
        n = random.randrange(0, len(equotes))
        desc = "**{}**".format(equotes[n])
        em = discord.Embed(description=desc, color=discord.Color.blue())
        em.set_author(name="And for today, quote number {}:".format(n), icon_url="http://i.imgur.com/hBbuHbq.png")
        await self.bot.say(embed=em)

    @checks.mod_or_permissions(manage_server=True)
    @commands.command(pass_context=True, no_pm=True)
    async def prefix(self, ctx, newprefix: str = None):
        """Change or view server prefix."""

        if not newprefix:
            await self.bot.say(":information_source: **The current prefix for this server is: `{}`**".format(
                getprefix(self.bot, ctx.message)))
            return

        if "@" in newprefix:
            await self.bot.say(":x: **INVALID PREFIX**")
            return

        db.table('serverdata').insert({"id": ctx.message.server.id, "prefix": newprefix}, conflict="update").run()

        await self.bot.say(
            "**The prefix for this server has been set to: {}**".format(getprefix(self.bot, ctx.message)))


bot.add_cog(main(bot))
bot.load_extension("redditcontent")
bot.load_extension("twittercontent")
bot.load_extension("rsscontent")

bot.run(tokens["bot_token"])
