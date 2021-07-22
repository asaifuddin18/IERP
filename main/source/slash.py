import discord
from discord_slash import SlashCommand
from discord_slash.utils import manage_commands
import typing
import pandas as pd
import time
from threading import Thread
import string
import random
from datetime import date
import asyncio
import json
client = discord.Client(intents=discord.Intents.all())
slash = SlashCommand(client, sync_commands=True)
df = pd.read_csv("main/config/points.csv")
used = pd.read_csv("main/config/used.csv")
past_50_uses = []
#print(df)
active_codes = {} #Code: points, start_time, duration
adminChannelID = ""
@client.event
async def on_ready():
    print("Ready!")

@slash.slash(
  name="test",
  description="this returns the bot latency",
  options=[manage_commands.create_option(
    name = "argone",
    description = "description of first argument",
    option_type = 3,
    required = True
  )]
)
async def _test(ctx, argone: str):
    await ctx.respond(eat=True)
    await ctx.send(f"You responded with {argone}.", hidden=True) #can be set to hidden if response shouldn't be public yea?




@slash.slash(
    name="generateCode",
    description="This generates a reward code [ADMIN ONLY]",
    options=[manage_commands.create_option(
        name = "length",
        description= "Length of the code in minutes",
        option_type = 4,
        required = True
    ),
    manage_commands.create_option(
        name = "amount",
        description = "Amount of points this code is worth",
        option_type = 4,
        required = True
    ),
    manage_commands.create_option(
        name = "name",
        description = "The custom name for the code",
        option_type = 3,
        required = False
    )]
)
async def _generateCode(ctx, length: int, amount: int, name: typing.Optional[str] = ""):
    #await ctx.respond()
    global adminChannelID
    if str(ctx.channel_id) != adminChannelID:
        await ctx.respond(eat=True)
        await ctx.send("This is an admin only command!", hidden=True)
        print(adminChannelID)
        print(ctx.channel_id)
        return

    seconds = length*60
    code = name
    if code == "":
        letters = string.ascii_letters
        code = ''.join(random.choice(letters) for i in range(8))
    
    if code not in used.columns:
        active_codes[code] = (amount, time.time(), seconds)
        temp = []
        for i in range(len(used.index)):
            temp.append(False)
        used[code] = temp

        print(df)
        print(used)
        response = code + " of value " + str(amount) + " generated for " + str(length) + " minutes" 
        await ctx.send(response)
    else:
        await ctx.send("Could not generate code. Code with same name has already been generated!")

@slash.slash(
    name="redeemCode",
    description="Got a IERP code? Redeem it here!",
    options=[manage_commands.create_option(
        name = "code",
        description = "The name of the code",
        option_type = 3,
        required = True
    )]
)

async def _redeemCode(ctx, code: str):
    #await ctx.respond(eat=True)
    #await ctx.send("Redeemed Code!")
    username = await client.fetch_user(ctx.author_id)
    user_id = int(ctx.author_id)
    if code in active_codes.keys() and user_id in df["ID"].values: #valid key AND old user

        if not used.at[used.index[used["ID"] == user_id][0], code]: #make sure code has not already been redeemed!
            print("old user")
            index = df.index[df["ID"] == user_id][0]
            df.Points[index] = df.Points[index] + active_codes[code][0]
            used.at[used.index[used["ID"] == user_id], code] = True #marked redeemed
            await ctx.send("Code redeemed!", hidden=True)
            past_50_uses.append((df.Tag[index], code, date.today().strftime("%m/%d/%y"), time.time(), active_codes[code][0]))
            if len(past_50_uses) > 50:
                del past_50_uses[0]
            print(df)
            print(used)
        else:
            await ctx.send("Code already redeemed!", hidden=True)

    elif code in active_codes.keys(): #valid key AND new user
        print("new user")
        index = len(df.index)
        df.loc[len(df.index)] = [user_id, username, active_codes[code][0]]
        temp  = [user_id]
        for i in range(len(used.columns) - 1):
            temp.append(False)
        
        used.loc[len(used.index)] = temp
        used.at[used.index[used["ID"] == user_id], code] = True
        await ctx.send("Code redeemed!", hidden=True)
        past_50_uses.append((df.Tag[index], code, date.today().strftime("%m/%d/%y"), time.time(), active_codes[code][0]))
        if len(past_50_uses) > 50:
            del past_50_uses[0]
        print(df)
        print(used)
    
    else: #invalid key
        await ctx.send("Invalid or expired code!", hidden=True)

@slash.slash(
    name="viewLeaderboard",
    description="Displays the top point earners",
    options=[manage_commands.create_option(
        name = "page",
        description = "Page number of the leaderboard",
        option_type = 4,
        required = False
    )]
)
async def _viewLeaderboard(ctx, page: typing.Optional[int] = 0):
    #await ctx.respond()
    
    dfcpy = df[['Tag', 'Points']].copy()
    dfcpy.sort_values('Points')
    em = discord.Embed(title = f'Top members by points in {ctx.guild.name}', description = 'The highest point members in the server')
    for i in range(len(df.index)):
        temp = dfcpy.Tag[i] + ": " + str(dfcpy.Points[i])
        em.add_field(name = f'{i+1}: {temp}', value='\u200b', inline = False)
    await ctx.send(embed = em)


@slash.slash(
    name="setAdminChannel",
    description="Changes the admin channel.",
    options=[manage_commands.create_option(
        name = "channel_id",
        description = "New Channel ID",
        option_type = 3,
        required = True
    )]
)
async def _setAdminChannel(ctx, channel_id: str):
    global adminChannelID
    if adminChannelID == "":
        #await ctx.respond()
        adminChannelID = str(channel_id)
        await ctx.send("Admin Channel Initialized")
    elif adminChannelID  == str(ctx.channel_id):
        #await ctx.respond()
        adminChannelID = channel_id
        await ctx.send("Admin Channel Changed")
    
    else:
        ctx.respond(eat = True)
        await ctx.send("This is an admin only command!", hidden=True)
    
@slash.slash(
    name="downloadCSV",
    description="Downloads the CSV.",
)
async def _downloadCSV(ctx):

    if str(ctx.channel_id) != adminChannelID:
        await ctx.respond(eat=True)
        await ctx.send("This is an admin only command!", hidden=True)
        return

    await ctx.respond()
    #usedtemp = open("used.csv", "rb")
    
    with open ("main/config/points.csv", "rb") as file:
        await ctx.send("Points: ", file=discord.File(file, "points.csv"))
   


def expired():
    while True:
        time.sleep(1)
        for code in active_codes.keys():
            if active_codes[code][1] + active_codes[code][2] < time.time() and active_codes[code][2] != 0:
                print(code, "expired")
                del active_codes[code]
                break

        df.to_csv("main/config/points.csv", index=False)
        used.to_csv("main/config/used.csv", index=False)

thread = Thread(target = expired)
thread.daemon = True
thread.start()
with open('main/config/secrets.json') as f:
    secrets = json.load(f)
TOKEN = secrets['token']
loop = asyncio.get_event_loop()
loop.create_task(client.start(TOKEN))
Thread(target=loop.run_forever).start()
