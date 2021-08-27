'''
Main IERP script
Attributes
----------
client: discord.Client
    client object from discord.py
slash: discord_slash.SlashCommand
    slash object used for discord slash commands
point_d: defaultdict
    Default dictionary with default value 0 mapping discord id (int) to points
used: defaultdict
    Default dictioanry with default value empty set mapping code/message id to a set of users
uses_per_day: dictionary
    Dictionary mapping date (str) to frequency (int)
unique_users_per_day: dictionary
    Dictionary mapping date (str) to number of users (int)
unique_codes_per_day: dictionary
    Dictionary mapping date (str) to number of codes (int)
points_in_circulation: dictionary
    Dictionary mapping date (str) to number of points (int)
'''
from main.source.constants import ADMIN_CHANNEL, ANNOUNCEMENT_CHANNEL, INTEGER, PATH_TO_CIRCULATION, PATH_TO_POINTS, PATH_TO_POINT_VALUES, PATH_TO_SECRETS, PATH_TO_UNIQUE_CODES, PATH_TO_UNIQUE_USERS, PATH_TO_USED, ROLE, STRING, WEBSITE_URL
import discord
from discord_slash.utils.manage_commands import create_permission
from discord_slash.model import SlashCommandPermissionType
from discord_slash import SlashCommand
from discord_slash.utils import manage_commands
import typing
import pandas as pd
import time
from threading import Thread
import string
import random
from datetime import date
from datetime import datetime
import asyncio
import json
from pytz import timezone
import math
import pickle
import os
from os import path
import requests
from collections import defaultdict
from discord_slash.utils.manage_components import create_button, create_actionrow
from discord_slash.model import ButtonStyle
client = discord.Client(intents=discord.Intents.all())
slash = SlashCommand(client, sync_commands=True)
#df = None
point_d = defaultdict(int)
if path.exists(PATH_TO_POINTS) and os.path.getsize(PATH_TO_POINTS) > 0:
    with open(PATH_TO_POINTS, "rb") as f:
        point_d = pickle.load(f)
used = defaultdict(set)
if path.exists(PATH_TO_USED) and os.path.getsize(PATH_TO_USED) > 0:
    with open(PATH_TO_USED, "rb") as f:
        used = pickle.load(f)
uses_per_day = {} #Date: int (cumulative)
unique_users_per_day = {} #Date: int (cumulative) len(point_d)
if path.exists(PATH_TO_UNIQUE_USERS) and os.path.getsize(PATH_TO_UNIQUE_USERS) > 0:
    with open(PATH_TO_UNIQUE_USERS, "rb") as f:
        unique_users_per_day = pickle.load(f)
        
unique_codes_per_day = {} #Date: int (cumulative) len(slash.used.columns) - 1
if path.exists(PATH_TO_UNIQUE_CODES) and os.path.getsize(PATH_TO_UNIQUE_CODES) > 0:
    with open(PATH_TO_UNIQUE_CODES, "rb") as f:
        unique_codes_per_day = pickle.load(f)
points_in_circulation = {} #Date: int (cumulative) slash.df['Points'].sum()
if path.exists(PATH_TO_CIRCULATION) and os.path.getsize(PATH_TO_CIRCULATION) > 0:
    with open(PATH_TO_CIRCULATION, "rb") as f:
        points_in_circulation = pickle.load(f)

with open(PATH_TO_POINT_VALUES) as f:
    point_values = json.load(f)

num_redeemed = 0
active_codes = {} #Code: points, start_time, duration
giveaways = {} #Code: points, start_time, duration, entries, num_winners
seven_day_redeems = []
thirty_day_purchase = []
adminChannelID = ADMIN_CHANNEL
announcement_channel = ANNOUNCEMENT_CHANNEL
guilds_and_admin_roles = {}
active_pugs = {} #Game: end_time, users
with open('main/config/servers_and_roles.json') as f:
    servers_and_roles = json.load(f)

for server in servers_and_roles['servers']:
    guilds_and_admin_roles[server['id']] = []
    for role in server['roles']:
        id = role['id']
        guilds_and_admin_roles[server['id']].append(create_permission(id, SlashCommandPermissionType.ROLE, True))
    guilds_and_admin_roles[server['id']] = [create_permission(x['id'], SlashCommandPermissionType.ROLE, True) for x in server['roles']]

with open("main/config/shop.json") as f:
    shop_info = json.load(f)
'''
Prints Ready! when Discord client is connected
'''
@client.event
async def on_ready():
    print("Ready!")

'''
Discord client event called when a message gets a reaction added to it. (This only applies to messages sent after the start of the bot)
This specific function is designed to award 10 points to a reaction in the announcement channel
Parameters
----------
reaction: discord.Reaction
    https://discordpy.readthedocs.io/en/stable/api.html#reaction
user: discord.User
    https://discordpy.readthedocs.io/en/stable/api.html#id7
'''
@client.event
async def on_reaction_add(reaction, user):
    global num_redeemed
    msg = reaction.message
    if msg.channel.id == announcement_channel:
        if user.id not in used[msg.id]: #make sure code has not already been redeemed!
            point_d[user.id] += 5
            used[msg.id].add(user.id)
            num_redeemed += 1

@slash.subcommand(
    base="admin",
    name="givePoints",
    description="Manually give points to a user. Only do this in the case of a single user or some error happened.",
    base_description="Admin only commands.",
    base_default_permission=False,
    options=[manage_commands.create_option(
        name = "user_id",
        description = "User ID (not tag) of the user getting points",
        option_type = STRING,
        required = True
    ),
    manage_commands.create_option(
        name = "points",
        description = "Amount of points to give",
        option_type = INTEGER,
        required = True
    )]
)
async def admin_givePoints(ctx, user_id: str, points: int):
    try:
        user_id = int(user_id)
    except(ValueError):
        await ctx.send('Thats not a valid user_id (User ID is a number)', hidden=True)
        return
    point_d[user_id] += points
    await ctx.send("Points successfully awarded!", hidden=True)


'''
Command that starts a raffle
Parameters
----------
code: str
    The code of the raffle
duration: int
    The duration of the raffle in hours
cost: int
    The cost in points to enter the raffle
number_of_winners: int
    The number of winners to allow for the raffle. Multiple winners will be outputted in order
announcement_channel: int [OPTIONAL]
    The ID of the channel to announce the winners in
description: str [OPTIONAL]
    The description of the raffle to be included when the winners are announced
image_url: str [OPTIONAL]
    The URL of an image to attatch with the giveaway
role_to_ping: discord.Role [OPTIONAL]
    The role to ping when announcing the winners
'''
@slash.subcommand(
    base="admin",
    name="startRaffle",
    description="Start & optionally announce a raffle in the specified channel",
    base_description="Admin only commands.",
    base_default_permission=False,
    base_permissions=guilds_and_admin_roles,
    options=[manage_commands.create_option(
        name = "code",
        description = "The code of the raffle (keep the code simple)",
        option_type = STRING,
        required = True
    ),
    manage_commands.create_option(
        name = "duration",
        description = "Duration of the raffle in hours",
        option_type = INTEGER,
        required = True
    ),
    manage_commands.create_option(
        name = "cost",
        description = "Cost of entering the raffle",
        option_type = INTEGER,
        required = True
    ),
    manage_commands.create_option(
        name = "number_of_winners",
        description = "The number of winners for the raffle",
        option_type = INTEGER,
        required = True
    ),
    manage_commands.create_option(
        name = "announcement_channel",
        description = "The channel to annouce the raffle",
        option_type = STRING,
        required = False
    ),
    manage_commands.create_option(
        name = "description",
        description = "The description of the giveaway to be included when it is announced",
        option_type = STRING,
        required = False
    ),
    manage_commands.create_option(
        name = "image_url",
        description = "Optional image to accompany raffle annoucement",
        option_type = STRING,
        required = False
    ),
    manage_commands.create_option(
        name = "role_to_ping",
        description = "Role to ping with the announcement (bot must have permission to ping)",
        option_type = ROLE,
        required = False
    )]
)
async def _admin_startRaffle(ctx, code: str, duration: int, cost: int, number_of_winners: int, announcement_channel: typing.Optional[str] = '0', description: typing.Optional[str] = "", image_url: typing.Optional[str] = "", role_to_ping: typing.Optional[discord.Role] = None):
    if code in giveaways.keys():
        await ctx.send("This raffle code is already being used!", hidden=True)
        return
    try:
        announcement_channel = int(announcement_channel)
    except(ValueError):
        ctx.send('That is not a valid Channel ID (Channel ID is a number)', hidden=True)
    giveaways[code] = (cost, time.time(), duration*60, set(), number_of_winners, announcement_channel, image_url, role_to_ping)
    if announcement_channel == 0:
        await ctx.send("Raffle " + code + " has been started!", hidden=True)
        return
    #we announce it
    embed=discord.Embed(title=f'Enter now via /enterraffle {code}', color=0xf58f19)
    if description != "":
        embed.description = description
    embed.set_author(name="Raffle has started!", icon_url="https://pbs.twimg.com/profile_images/1378045236845412355/TjjZcbbu_400x400.jpg")
    embed.set_thumbnail(url="https://pbs.twimg.com/profile_images/1378045236845412355/TjjZcbbu_400x400.jpg")
    embed.set_footer(text=f'The winners will be posted in this channel in {duration} hours. If you win, open a ticket under #contact-admin.')
    embed.add_field(name = f'Duration: {duration} hours', value='\u200b', inline = False)
    embed.add_field(name = f'Cost: {cost} points', value='Check your points via /points', inline = False)
    if image_url != "":
        embed.set_image(url=image_url)
    channel = client.get_channel(announcement_channel)
    if role_to_ping != None:
        await channel.send(f'<@&{role_to_ping.id}>',embed=embed)
    else:
        await channel.send(embed=embed)
    await ctx.send("Raffle successfully started", hidden=True)
'''
Command that enters the user into a raffle
Parameters
----------
code: str
    The unique code required in order to enter a raffle
'''
@slash.slash(
    name = "enterRaffle",
    description="Enter an ongoing raffle",
    options = [manage_commands.create_option(
        name = "code",
        description = "The code of the raffle",
        option_type = STRING,
        required = True
    )]
)
async def _enterRaffle(ctx, code: str):
    if code not in giveaways.keys():
        await ctx.send("Invalid code!", hidden=True)
        return
    cost = giveaways[code][0]
    if ctx.author_id in giveaways[code][3]:
        await ctx.send("You have already entered this raffle!", hidden=True)
        return
    if point_d[ctx.author_id] >= cost:
        giveaways[code][3].add(ctx.author_id)
        point_d[ctx.author_id] -= cost
        await ctx.send(f'You have entered the raffle! You have {point_d[ctx.author_id]} points remaining!', hidden=True)
    else:
        await ctx.send(f'{cost} points are required to enter this raffle, you only have {point_d[ctx.author_id]} points!', hidden=True)


'''
Command that displays the number of points a user has
'''
@slash.slash(
  name="points",
  description="Returns the user's points"
)
async def _points(ctx):
    points = point_d[ctx.author_id]
    if points == 0:
        await ctx.send("You have <:OMEGALUL:417825307605860353> points!", hidden=True) 
    else:
        await ctx.send(f'You have {points} points!', hidden=True)

'''
Command that starts a Pick Up Game/10/12 man
Parameters
----------
game: str
    The name of the game being played. This corresponds to the list defined in point_values.json
'''
@slash.subcommand(
    base="admin",
    name="startPUG",
    description="Start a PUG, be sure to announce the code to participants",
    base_description="Admin only commands.",
    base_default_permission=False,
    #base_permissions=guilds_and_admin_roles,
    options=[manage_commands.create_option(
        name = "game",
        description = "Game being played",
        option_type = STRING,
        required = True,
        choices=[x['name'] for x in point_values['events']]
    )]
)
async def _admin_startPUG(ctx, game: str):
    for current in point_values['events']:
        if current['name'] == game:
            active_pugs[game] = (time.time() + current['duration']*60, set())
            await ctx.send(f'The {game} PUG has been started. Anyone who joins a voice channel under the {game} category in the next {current["duration"]/60} hours will recieve {current["value"]} points.', hidden=True)
            break
    else:
        await ctx.send("[ERROR] Could not find event!", hidden=True)

'''
Command that creates a redeemable code with a custom duration and point reward. This is used in the case of random events that are not PUGS
Parameters
----------
length: int
    The duration of the code in minutes (0 is infinite)
amount: int
    The amount of points the code is worth
name: str [OPTIONAL]
    The name of the code
'''
@slash.subcommand(
    base="admin",
    name="customGenerateCode",
    description="This generates a reward code",
    base_description="Admin only commands.",
    base_default_permission=False,
    #base_permissions=guilds_and_admin_roles,
    options=[manage_commands.create_option(
        name = "length",
        description= "Length of the code in minutes (0 is infinite)",
        option_type = INTEGER,
        required = True
    ),
    manage_commands.create_option(
        name = "amount",
        description = "Amount of points this code is worth",
        option_type = INTEGER,
        required = True
    ),
    manage_commands.create_option(
        name = "name",
        description = "The custom name for the code",
        option_type = STRING,
        required = False
    )]
)
async def _admin_customGenerateCode(ctx, length: int, amount: int, name: typing.Optional[str] = ""):
    seconds = length*60
    code = name
    if code == "":
        letters = string.ascii_letters
        code = ''.join(random.choice(letters) for i in range(8))
    
    if code not in used.keys():
        active_codes[code] = (amount, time.time(), seconds)
        await ctx.send(f'{code} of value {amount} generated for {length} minutes', hidden=True)
    else:
        await ctx.send("Could not generate code. Code with same name has already been generated!", hidden=True)

'''
Command to redeem a custom generated code
Parameters
----------
code: str
    A unique code generated previously via customGenerateCode
'''
@slash.slash(
    name="redeemCode",
    description="Got a IERP code? Redeem it here!",
    options=[manage_commands.create_option(
        name = "code",
        description = "The name of the code",
        option_type = STRING,
        required = True
    )]
)
async def _redeemCode(ctx, code: str):
    global num_redeemed
    if code in active_codes.keys() and ctx.author_id not in used[code]: #valid key & user has not already redeemed
        point_d[ctx.author_id] += active_codes[code][0]
        used[code].add(ctx.author_id)
        await ctx.send(f'Code redeemed, you now have {point_d[ctx.author_id]} points!', hidden=True)
        num_redeemed += 1
        date_now = datetime.now().astimezone(timezone('US/Central'))
        seven_day_redeems.append((str(ctx.author), code, date_now.strftime("%m/%d/%y"), date_now.strftime("%H:%M:%S"), active_codes[code][0], date_now.replace(tzinfo=None)))
        while len(seven_day_redeems) != 0:
            dt = seven_day_redeems[0][5]
            now = datetime.now()
            if (now - dt).days >= 7:
                del seven_day_redeems[0]
            else:
                break
    elif ctx.author_id not in used[code]: #was a valid user
        await ctx.send("Invalid or expired code!", hidden=True)
    else:
        await ctx.send("Code already redeemed!", hidden=True)

'''
Command to view points of all users participating in the rewards program
Parameters
----------
page: int
    The page of the leaderboard to display. Page 1 displays the top 10 users, while the last page displays the bottom 10 users. Any page number beyond the maximum will display the last page.
'''
@slash.slash(
    name="leaderboard",
    description="Displays the top point earners",
    options=[manage_commands.create_option(
        name = "page",
        description = "Page number of the leaderboard",
        option_type = INTEGER,
        required = False
    )]
)
async def _leaderboard(ctx, page: typing.Optional[int] = 1):
    em = create_leaderboard_embed(page)
    buttons = [create_button(style=ButtonStyle.red, label="Previous page", custom_id = 'previous_page'), create_button(style=ButtonStyle.green, label="Next page", custom_id = 'next_page')]
    await ctx.send(embed = em, components=[create_actionrow(*buttons)])

def create_leaderboard_embed(page: int):
    total_pages = math.ceil(len(point_d)/10)
    if page < 1:
        page = 1
    em = discord.Embed(title = f'Top members by points in Illini Esports', description = 'The highest point members in the server')
    if page > total_pages:
        page = total_pages
    
    sorted_ids = sorted(point_d, key=point_d.get, reverse=True)
    embed_str = ""
    for i in range(10*(page - 1), min(len(point_d), 10*page)):
        if i < 0:
            break
        temp = f'{client.get_user(sorted_ids[i])}: {point_d[sorted_ids[i]]}'
        if i == 0:
            embed_str += f'**🥇: {temp} points**\n'
        elif i == 1:
            embed_str += f'**🥈: {temp} points**\n'
        elif i == 2:
            embed_str += f'**🥉: {temp} points**\n'
        elif i == len(point_d) - 1:
            embed_str += f'**<:KEKW:637019720721104896>: {temp} points**'
        else:
            embed_str += f'**{i+1}: {temp} points**\n'
    em.add_field(name='\u200b', value=embed_str, inline = False)
    em.set_footer(text=f'Page {page}/{total_pages}')
    em.timestamp = datetime.today()
    em.set_thumbnail(url="https://pbs.twimg.com/profile_images/1378045236845412355/TjjZcbbu_400x400.jpg")
    em.set_author(name="IERP", icon_url="https://pbs.twimg.com/profile_images/1378045236845412355/TjjZcbbu_400x400.jpg")
    return em

@slash.component_callback()
async def previous_page(ctx):
    try:
        footer = str(ctx.origin_message.embeds[0].footer.text)
    except:
        await ctx.edit_origin(embed = create_leaderboard_embed(1))
        return
    page = int(footer[5:footer.index('/')])
    em = create_leaderboard_embed(page - 1)
    await ctx.edit_origin(embed = create_leaderboard_embed(page - 1))

@slash.component_callback()
async def next_page(ctx):
    try:
        footer = str(ctx.origin_message.embeds[0].footer.text)
    except:
        await ctx.edit_origin(embed = create_leaderboard_embed(1))
        return
    page = int(footer[5:footer.index('/')])
    em = create_leaderboard_embed(page + 1)
    await ctx.edit_origin(embed = create_leaderboard_embed(page + 1))
'''
Command to download the CSV file of the users' points TODO
'''
@slash.subcommand(
    base="admin",
    name="downloadCSV",
    description="Downloads the CSV.",
    base_description="Admin only commands.",
    base_default_permission=False,
    #base_permissions=guilds_and_admin_roles
)
async def _admin_downloadCSV(ctx):
    with open (PATH_TO_POINTS, "rb") as file:
        await ctx.send("Points: ", file=discord.File(file, "points.pickle"), hidden=True)

'''
Command to list things available to buy with points. A list of things available is found in servers_and_roles.json
'''
@slash.subcommand(
    base = "shop",
    name="list",
    description="Displays what we are currently selling for rewards points!",
    base_description="IERP shop related commands!"
)
async def _shop_list(ctx):
    embed=discord.Embed(title="IERP Shop", description="The place where you can exchange rewards points for server rewards and merch! Shop is not yet finalized, so stay tuned for more information!", color=0xf58f19)
    embed.set_author(name="IERP", icon_url="https://pbs.twimg.com/profile_images/1378045236845412355/TjjZcbbu_400x400.jpg")
    embed.set_thumbnail(url="https://pbs.twimg.com/profile_images/1378045236845412355/TjjZcbbu_400x400.jpg")
    embed.add_field(name="COLOR ROLES", value='\u200b', inline=False)
    for role in shop_info['roles']:
        embed.add_field(name=role["name"], value = str(role["cost"]) + " points", inline=True)
    #embed.add_field(name="MERCH", value='\u200b', inline=False) #we're broke lmao
    #for item in shop_info['products']:
    #    embed.add_field(name=item['name'], value = str(item['cost']) + " points", inline=True)
    embed.set_footer(text="Purchasing a color role will remove any previously purchased color roles. Contact admin via #contact-admin if you have any questions or concerns.")
    #embed.set_image(url="https://lh5.googleusercontent.com/OQj9OrsHWwKV7MmV2iXduFz3V3yccVX6zi4ECMA5tigaicDUmTShPtPSum2Wh2UsbIuMuuTNKlsGWFqD74ZEhN3tg2Wii2puUi2EJz7NrE8VGj2CNtdJ4SaoS4hnKXLxcA=w5100")
    await ctx.send(embed=embed, hidden=True)

buy_choices = []
for role in shop_info['roles']:
    buy_choices.append(manage_commands.create_choice(
        name=role['name'],
        value=role['name']
    ))
for item in shop_info['products']:
    buy_choices.append(manage_commands.create_choice(
        name=item['name'],
        value=item['name']
    ))
'''
Command to buy something from the shop
Parameters
----------
item: str
    The item to buy. This item corresponds to an item defined in servers_and_roles.json. Buying a role will permenantly replace the previously bought role if appliciable
'''
@slash.subcommand(
    base = "shop",
    name = "buy",
    description = "Buy something from the shop!",
    base_description="IERP shop related commands!",
    options = [manage_commands.create_option(
        name = "item",
        description = "The name of the item",
        option_type = STRING,
        required = True,
        choices=buy_choices

    )]
)
async def _shop_buy(ctx, item: str):
    for product in shop_info['products']:
        if product['name'] == item:
            cost = product['cost']
            points = point_d[ctx.author_id]
            if points >= cost:
                point_d[ctx.author_id] -= cost
                await ctx.send(f'Congratulations, you have bought a {product["name"]} !. Open a ticket under #contact-admins for more information about availability and pickup. You now have {point_d[ctx.author_id]} points.', hidden=True)
                channel = client.get_channel(adminChannelID)
                await channel.send(f'{ctx.author} has just purchased a {product["name"]}.')
                date_now = datetime.now().astimezone(timezone('US/Central'))
                thirty_day_purchase.append((str(ctx.author), item, date_now.strftime("%m/%d/%y"), date_now.strftime("%H:%M:%S"), cost, date_now.replace(tzinfo=None)))
                while len(thirty_day_purchase) != 0:
                    dt = thirty_day_purchase[0][5]
                    now = datetime.now()
                    if (now - dt).days >= 30:
                        del seven_day_redeems[0]
                    else:
                        break
                return
            else:
                #await ctx.send("Sorry, you do not have enough points! " + product['name'] + " costs " + str(product['cost']) + " points and you only have " + str(points) + "points!")
                await ctx.send(f'Sorry, you do not have enough points! {product["name"]} costs {product["cost"]} points and you only have {points} points!', hidden=True)
                return
    else:
        for role in shop_info['roles']:
            cost = role['cost']
            points = point_d[ctx.author_id]
            if points >= cost:
                point_d[ctx.author_id] -= cost
                await ctx.send(f'Congratulations, you have bought a {role["name"]}! You now have {point_d[ctx.author_id]} points.', hidden=True)
                #APPLY ROLE HERE
                date_now = datetime.now().astimezone(timezone('US/Central'))
                thirty_day_purchase.append((str(ctx.author), item, date_now.strftime("%m/%d/%y"), date_now.strftime("%H:%M:%S"), cost, date_now.replace(tzinfo=None)))
                while len(thirty_day_purchase) != 0:
                    dt = thirty_day_purchase[0][5]
                    now = datetime.now()
                    if (now - dt).days >= 30:
                        del seven_day_redeems[0]
                    else:
                        break
                return
            else:
                await ctx.send(f'Sorry, you do not have enough points! {role["name"]} costs {role["cost"]} points and you only have {points} points!', hidden=True)
                return
                
        else:
            await ctx.send("ERROR: item not found, open a ticket under #contact-admins for help", hidden=True)
            return

'''
Runner function to check for active PUGS, active raffles, active codes, save global variables to files, and ping the server. This occurs once every 30 seconds
'''
async def expired():
    global num_redeemed
    while True:
        for code in active_codes.keys():
            if active_codes[code][1] + active_codes[code][2] < time.time() and active_codes[code][2] != 0:
                del active_codes[code]
                break
        
        today = date.today().strftime("%m/%d/%y")
        uses_per_day[today] = num_redeemed
        unique_users_per_day[today] = len(point_d)
        unique_codes_per_day[today] = len(used)
        points_in_circulation[today] = sum(point_d.values())

        for game in active_pugs.keys(): #LOOK AT CHANNELS
            for gameDict in point_values['events']:
                if gameDict['name'] == game:
                    channels = client.get_channel(gameDict['id']).voice_channels
                    for channel in channels:
                        for member in channel.members:
                            if member.id not in active_pugs[game][1]:
                                active_pugs[game][1].add(member.id)
                                point_d[member.id] += gameDict['value']
                                num_redeemed += 1
                            else:
                                point_d[member.id] += 1
              
            if active_pugs[game][0] < time.time():
                del active_pugs[game]
                break
        
        for code in giveaways.keys():
            if giveaways[code][1] + giveaways[code][2] < time.time():
                #select user here
                winners = []
                #cost, start_time, duration, entries, num_winners = giveaways[code]
                num_winners = giveaways[code][4]
                entries = list(giveaways[code][3])
                i = 0
                while i < num_winners:
                    if len(entries) == 0:
                        break
                    idx = random.randint(0, len(entries) - 1)
                    entry = entries[idx]
                    if len(winners) >= len(entries): #dead raffle
                        break
                    if entry not in winners:
                        winners.append(entry)
                        i += 1
                
                channel = client.get_channel(adminChannelID)
                announcement_channel = client.get_channel(int(giveaways[code][5]))
                if announcement_channel == "":
                    await channel.send("Winners for the " + code + " giveaway:")
                    for i in range(len(winners)):
                        await channel.send(str(i + 1) + ". " + str(client.get_user(winners[i])))
                    del giveaways[code]
                    continue
                
                embed=discord.Embed(title=f'{code} Raffle Winners!', description="If there are multiple winners, each will choose a prize in the order listed. Contact admins under #contact-admin to receive your prize!", color=0xf58f19)
                embed.set_author(name="IERP", icon_url="https://pbs.twimg.com/profile_images/1378045236845412355/TjjZcbbu_400x400.jpg")
                embed.set_thumbnail(url="https://pbs.twimg.com/profile_images/1378045236845412355/TjjZcbbu_400x400.jpg")
                for i in range(len(winners)):
                    embed.add_field(name=str(i+1) + ": " + str(client.get_user(winners[i])), value='\u200b')
                embed.set_image(url=giveaways[code][6])
                #await announcement_channel.send(embed=embed)
                role_to_ping = giveaways[code][7]
                if role_to_ping != None:
                    await announcement_channel.send(f'<@&{role_to_ping.id}>',embed=embed)
                else:
                    await announcement_channel.send(embed=embed)
                del giveaways[code]
                break
        
        with open(PATH_TO_USED, "wb") as f:
            pickle.dump(used, f, protocol=pickle.HIGHEST_PROTOCOL)
        with open(PATH_TO_POINTS, "wb") as f:
            pickle.dump(point_d, f, protocol=pickle.HIGHEST_PROTOCOL)
        with open(PATH_TO_UNIQUE_USERS, "wb") as f:
            pickle.dump(unique_users_per_day, f, protocol=pickle.HIGHEST_PROTOCOL)
        with open(PATH_TO_UNIQUE_CODES, "wb") as f:
            pickle.dump(unique_codes_per_day, f, protocol=pickle.HIGHEST_PROTOCOL)
        with open(PATH_TO_CIRCULATION, "wb") as f:
            pickle.dump(points_in_circulation, f, protocol=pickle.HIGHEST_PROTOCOL)
        requests.get(WEBSITE_URL)
        await asyncio.sleep(30)

with open(PATH_TO_SECRETS) as f:
    secrets = json.load(f)
TOKEN = secrets['token']
loop = asyncio.get_event_loop()
loop.create_task(client.start(TOKEN))
loop.create_task(expired())
#loop.run_forever()
Thread(target=loop.run_forever).start() #is this preferred?