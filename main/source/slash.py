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
client = discord.Client(intents=discord.Intents.all())
slash = SlashCommand(client, sync_commands=True)
df = None
if path.exists("main/config/points.csv"):
    df = pd.read_csv("main/config/points.csv")
else:
    df = pd.DataFrame(columns=["ID", "Tag", "Points"])

if path.exists("main/config/used.csv"):
    used = pd.read_csv("main/config/used.csv")
else:
    used = pd.DataFrame(columns=["ID"])
uses_per_day = {} #Date: int (cumulative)
unique_users_per_day = {} #Date: int (cumulative) len(slash.df.index)
if path.exists("main/config/unique_users_per_day.pickle") and os.path.getsize("main/config/unique_users_per_day.pickle") > 0:
    with open("main/config/unique_users_per_day.pickle", "rb") as f:
        unique_users_per_day = pickle.load(f)
        
unique_codes_per_day = {} #Date: int (cumulative) len(slash.used.columns) - 1
if path.exists("main/config/unique_codes_per_day.pickle") and os.path.getsize("main/config/unique_codes_per_day.pickle") > 0:
    with open("main/config/unique_codes_per_day.pickle", "rb") as f:
        unique_codes_per_day = pickle.load(f)

points_in_circulation = {} #Date: int (cumulative) slash.df['Points'].sum()
if path.exists("main/config/points_in_circulation.pickle") and os.path.getsize("main/config/points_in_circulation.pickle") > 0:
    with open("main/config/points_in_circulation.pickle", "rb") as f:
        points_in_circulation = pickle.load(f)
        
num_redeemed = 0
active_codes = {} #Code: points, start_time, duration
giveaways = {} #Code: points, start_time, duration, entries, num_winners
seven_day_redeems = []
thirty_day_purchase = []
adminChannelID = ""
guilds_and_admin_roles = {
    739269285624676429: [create_permission(743208843932074094, SlashCommandPermissionType.ROLE, True)
    ]
}
with open("main/config/shop.json") as f:
    shop_info = json.load(f)

@client.event
async def on_ready():
    print("Ready!")



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
        option_type = 3,
        required = True
    ),
    manage_commands.create_option(
        name = "duration",
        description = "Duration of the raffle in hours",
        option_type = 4,
        required = True
    ),
    manage_commands.create_option(
        name = "cost",
        description = "Cost of entering the raffle",
        option_type = 4,
        required = True
    ),
    manage_commands.create_option(
        name = "number_of_winners",
        description = "The number of winners for the raffle",
        option_type = 4,
        required = True
    ),
    manage_commands.create_option(
        name = "announcement_channel",
        description = "The channel to annouce the raffle",
        option_type = 3,
        required = False
    ),
    manage_commands.create_option(
        name = "description",
        description = "The description of the giveaway to be included when it is announced",
        option_type = 3,
        required = False
    ),
    manage_commands.create_option(
        name = "image_url",
        description = "Optional image to accompany raffle annoucement",
        option_type = 3,
        required = False
    ),
    manage_commands.create_option(
        name = "role_to_ping",
        description = "Role to ping with the announcement (bot must have permission to ping)",
        option_type = 8,
        required = False
    )]
)
async def _admin_startRaffle(ctx, code: str, duration: int, cost: int, number_of_winners: int, announcement_channel: typing.Optional[str] = "", description: typing.Optional[str] = "", image_url: typing.Optional[str] = "", role_to_ping: typing.Optional[discord.Role] = None):
    if str(ctx.channel_id) != adminChannelID:
        #await ctx.respond(eat=True)
        await ctx.send("This is an admin only command!", hidden=True)
        print(adminChannelID)
        print(ctx.channel_id)
        return
    if code in giveaways.keys():
        await ctx.send("This raffle code is already being used!")
        return
    giveaways[code] = (cost, time.time(), duration*60, [], number_of_winners, announcement_channel, image_url, role_to_ping)
    if announcement_channel == "":
        await ctx.send("Raffle " + code + " has been started!")
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
    channel = client.get_channel(int(announcement_channel))
    if role_to_ping != None:
        await channel.send(f'<@&{role_to_ping.id}>',embed=embed)
    else:
        await channel.send(embed=embed)
    #await channel.send(embed=embed)
    await ctx.send("Raffle successfully started", hidden=True)

@slash.slash(
    name = "enterRaffle",
    description="Enter an ongoing raffle",
    options = [manage_commands.create_option(
        name = "code",
        description = "The code of the raffle",
        option_type = 3,
        required = True
    )]
)
async def _enterRaffle(ctx, code: str):
    if code not in giveaways.keys():
        await ctx.send("Invalid code!", hidden=True)
        return
    cost = giveaways[code][0]
    entries = giveaways[code][3]
    if ctx.author_id in entries:
        await ctx.send("You have already entered this raffle!", hidden=True)
        return
    points = 0
    if ctx.author_id in df["ID"].values:
        index = df.index[df["ID"] == ctx.author_id][0]
        points = df.Points[index]
    if cost > points:
        await ctx.send(cost + " points are required to enter this raffle, you only have " + str(points) + "!")
        return
    entries.append(ctx.author_id)
    if cost != 0:
        index = df.index[df["ID"] == ctx.author_id][0]
        #df.Points[index] = df.Points[index] - cost
        df.at[index, 'Points'] -= cost
    await ctx.send("You have entered the raffle! You have " + str(df.Points[index]) + " points remaining.", hidden=True)



@slash.slash(
  name="points",
  description="Returns the user's points"
)
async def _points(ctx):
    #await ctx.send(f"You responded with {argone}.", hidden=True) #can be set to hidden if response shouldn't be public yea?
    user_id = int(ctx.author_id)
    points = 0
    if user_id in df["ID"].values:
        index = df.index[df["ID"] == user_id][0]
        points = df.Points[index]
    if points == 0:
        await ctx.send("You have <:OMEGALUL:417825307605860353> points!") 
    else:
        await ctx.send("You have " + str(points) + " points!")

@slash.subcommand(
    base="admin",
    name="generateCode",
    description="This generates a reward code",
    base_description="Admin only commands.",
    base_default_permission=False,
    base_permissions=guilds_and_admin_roles,
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
async def _admin_generateCode(ctx, length: int, amount: int, name: typing.Optional[str] = ""):
    #await ctx.respond()
    global adminChannelID
    if str(ctx.channel_id) != adminChannelID:
        #await ctx.respond(eat=True)
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
    global num_redeemed
    if code in active_codes.keys() and user_id in df["ID"].values: #valid key AND old user

        if not used.at[used.index[used["ID"] == user_id][0], code]: #make sure code has not already been redeemed!
            print("old user")
            index = df.index[df["ID"] == user_id][0]
            df.Points[index] = df.Points[index] + active_codes[code][0]
            used.at[used.index[used["ID"] == user_id], code] = True #marked redeemed
            await ctx.send("Code redeemed, you now have " + str(df.Points[index]) + " points!", hidden=True)
            num_redeemed += 1
            date_now = datetime.now().astimezone(timezone('US/Central'))
            seven_day_redeems.append((df.Tag[index], code, date_now.strftime("%m/%d/%y"), date_now.strftime("%H:%M:%S"), active_codes[code][0], date_now.replace(tzinfo=None)))
            #if len(past_50_uses) > 50:
            #    del past_50_uses[0]
            while len(seven_day_redeems) != 0:
                dt = seven_day_redeems[0][5]
                now = datetime.now()
                if (now - dt).days >= 7:
                    del seven_day_redeems[0]
                else:
                    break
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
        await ctx.send("Code redeemed, you now have " + str(active_codes[code][0]) + " points!", hidden=True)
        num_redeemed += 1
        date_now = datetime.now().astimezone(timezone('US/Central'))
        seven_day_redeems.append((df.Tag[index], code, date_now.strftime("%m/%d/%y"), date_now.strftime("%H:%M:%S"), active_codes[code][0], date_now.replace(tzinfo=None)))
        #if len(past_50_uses) > 50:
        #    del past_50_uses[0]
        while len(seven_day_redeems) != 0:
            dt = seven_day_redeems[0][5]
            now = datetime.now()
            if (now - dt).days >= 7:
                del seven_day_redeems[0]
            else:
                break
        print(df)
        print(used)
    
    else: #invalid key
        await ctx.send("Invalid or expired code!", hidden=True)

@slash.slash(
    name="leaderboard",
    description="Displays the top point earners",
    options=[manage_commands.create_option(
        name = "page",
        description = "Page number of the leaderboard",
        option_type = 4,
        required = False
    )]
)
async def _leaderboard(ctx, page: typing.Optional[int] = 1): #todo
    #await ctx.respond()
    
    dfcpy = df[['Tag', 'Points']].copy()
    dfcpy.sort_values('Points')
    em = discord.Embed(title = f'Top members by points in {ctx.guild.name}', description = 'The highest point members in the server')
    total_pages = math.ceil(len(df.index)/10)
    new_page = page
    if new_page > total_pages:
        new_page = total_pages
    
    for i in range(10*(new_page - 1), min(len(df.index), 10*new_page)):
        if i < 0:
            break
        temp = dfcpy.Tag[i] + ": " + str(dfcpy.Points[i])
        if i == 0:
            em.add_field(name = f'🥇: {temp} points', value='\u200b', inline = False)
        elif i == 1:
            em.add_field(name = f'🥈: {temp} points', value='\u200b', inline = False)
        elif i == 2:
            em.add_field(name = f'🥉: {temp} points', value='\u200b', inline = False)
        elif i == len(df.index) - 1:
            em.add_field(name = f'<:KEKW:637019720721104896>: {temp} points', value='\u200b', inline = False)
        else:
            em.add_field(name = f'{i+1}: {temp} points', value='\u200b', inline = False)
    #em.set_footer(text="Page " + str(new_page) + "/" + str(total_pages))
    em.set_footer(text=f'Page {new_page}/{total_pages}')
    em.set_thumbnail(url="https://pbs.twimg.com/profile_images/1378045236845412355/TjjZcbbu_400x400.jpg")
    em.set_author(name="IERP", icon_url="https://pbs.twimg.com/profile_images/1378045236845412355/TjjZcbbu_400x400.jpg")
    await ctx.send(embed = em)
    
@slash.subcommand(
    base="admin",
    name="downloadCSV",
    description="Downloads the CSV.",
    base_description="Admin only commands.",
    base_default_permission=False,
    base_permissions=guilds_and_admin_roles
)
async def _admin_downloadCSV(ctx):

    if str(ctx.channel_id) != adminChannelID:
        #await ctx.respond(eat=True)
        await ctx.send("This is an admin only command!", hidden=True)
        return

    #await ctx.respond()
    #usedtemp = open("used.csv", "rb")
    
    with open ("main/config/points.csv", "rb") as file:
        await ctx.send("Points: ", file=discord.File(file, "points.csv"))

@slash.subcommand(
    base="admin",
    name="setAdminChannel",
    description="Changes the admin channel",
    base_description="Admin only commands.",
    base_default_permission=False,
    base_permissions=guilds_and_admin_roles,
    options=[manage_commands.create_option(
        name = "channel_id",
        description = "New Channel ID",
        option_type = 3,
        required = True
    )]
)
async def _admin_setAdminChannel(ctx, channel_id: str):
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
        #ctx.respond(eat = True)
        await ctx.send("This is an admin only command!", hidden=True)


@slash.subcommand(
    base = "shop",
    name="list",
    description="Displays what we are currently selling for rewards points!",
    base_description="IERP shop related commands!"
)

async def _shop_list(ctx):
    embed=discord.Embed(title="IERP Shop", description="The place where you can exchange rewards points for server rewards and merch!", color=0xf58f19)
    embed.set_author(name="IERP", icon_url="https://pbs.twimg.com/profile_images/1378045236845412355/TjjZcbbu_400x400.jpg")
    embed.set_thumbnail(url="https://pbs.twimg.com/profile_images/1378045236845412355/TjjZcbbu_400x400.jpg")
    embed.add_field(name="COLOR ROLES", value='\u200b', inline=False)
    for role in shop_info['roles']:
        embed.add_field(name=role["name"], value = str(role["cost"]) + " points", inline=True)
    embed.add_field(name="MERCH", value='\u200b', inline=False)
    for item in shop_info['products']:
        embed.add_field(name=item['name'], value = str(item['cost']) + " points", inline=True)
    embed.set_footer(text="Purchasing a color role will remove any previously purchased color roles. Contact admin via #contact-admin if you purchase merch or if you  have any questions or concerns.")
    embed.set_image(url="https://lh5.googleusercontent.com/OQj9OrsHWwKV7MmV2iXduFz3V3yccVX6zi4ECMA5tigaicDUmTShPtPSum2Wh2UsbIuMuuTNKlsGWFqD74ZEhN3tg2Wii2puUi2EJz7NrE8VGj2CNtdJ4SaoS4hnKXLxcA=w5100")
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

@slash.subcommand(
    base = "shop",
    name = "buy",
    description = "Buy something from the shop!",
    base_description="IERP shop related commands!",
    options = [manage_commands.create_option(
        name = "item",
        description = "The name of the item",
        option_type = 3,
        required = True,
        choices=buy_choices

    )]
)
async def _shop_buy(ctx, item: str):
    for product in shop_info['products']:
        if product['name'] == item:
            cost = product['cost']
            user_id = int(ctx.author_id)
            points = 0
            if user_id in df["ID"].values:
                index = df.index[df["ID"] == user_id][0]
                points = df.Points[index]
            if points >= cost:
                index = df.index[df["ID"] == user_id][0]
                df.at[index, 'Points'] -= cost
                await ctx.send("Congratulations, you have bought a " + product['name']+ "!. Open a ticket under #contact-admins for more information about availability and pickup. You now have " + str(df.Points[index]) + " points.", hidden=True)
                channel = client.get_channel(int(adminChannelID))
                await channel.send(str(client.get_user(user_id)) + " has just purchased a " + product['name'] + ".")
                date_now = datetime.now().astimezone(timezone('US/Central'))
                thirty_day_purchase.append((df.Tag[index], item, date_now.strftime("%m/%d/%y"), date_now.strftime("%H:%M:%S"), cost, date_now.replace(tzinfo=None)))
                while len(thirty_day_purchase) != 0:
                    dt = thirty_day_purchase[0][5]
                    now = datetime.now()
                    if (now - dt).days >= 30:
                        del seven_day_redeems[0]
                    else:
                        break
                return
            else:
                await ctx.send("Sorry, you do not have enough points! " + product['name'] + " costs " + str(product['cost']) + " points and you only have " + str(points) + "points!")
                return
    else:
        for role in shop_info['roles']:
            cost = role['cost']
            user_id = int(ctx.author_id)
            points = 0
            if user_id in df["ID"].values:
                index = df.index[df["ID"] == user_id][0]
                points = df.Points[index]
            if points >= cost:
                index = df.index[df["ID"] == user_id][0]
                df.at[index, 'Points'] -= cost
                await ctx.send("Congratulations, you have bought a " + role['name']+ "! You now have " + str(df.Points[index]) + " points.", hidden=True)
                #APPLY ROLE HERE
                date_now = datetime.now().astimezone(timezone('US/Central'))
                thirty_day_purchase.append((df.Tag[index], item, date_now.strftime("%m/%d/%y"), date_now.strftime("%H:%M:%S"), cost, date_now.replace(tzinfo=None)))
                while len(thirty_day_purchase) != 0:
                    dt = thirty_day_purchase[0][5]
                    now = datetime.now()
                    if (now - dt).days >= 30:
                        del seven_day_redeems[0]
                    else:
                        break
                return
            else:
                await ctx.send("Sorry, you do not have enough points! " + role['name'] + " costs " + str(role['cost']) + " points and you only have " + str(points) + "points!")
                return
                
        else:
            await ctx.send("ERROR: item not found, open a ticket under #contact-admins for help", hidden=True)
            return

async def expired():
    while True:
        for code in active_codes.keys():
            if active_codes[code][1] + active_codes[code][2] < time.time() and active_codes[code][2] != 0:
                del active_codes[code]
                break
        
        today = date.today().strftime("%m/%d/%y")
        uses_per_day[today] = num_redeemed
        unique_users_per_day[today] = len(df.index)
        unique_codes_per_day[today] = len(used.columns) - 1
        points_in_circulation[today] = int(df['Points'].sum())

        for code in giveaways.keys():
            if giveaways[code][1] + giveaways[code][2] < time.time():
                #select user here
                winners = []
                #cost, start_time, duration, entries, num_winners = giveaways[code]
                num_winners = giveaways[code][4]
                entries = giveaways[code][3]
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
                
                channel = client.get_channel(int(adminChannelID))
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
                announcement_channel = client.get_channel(int(giveaways[code][5]))
                #await announcement_channel.send(embed=embed)
                role_to_ping = giveaways[code][7]
                if role_to_ping != None:
                    await channel.send(f'<@&{role_to_ping.id}>',embed=embed)
                else:
                    await channel.send(embed=embed)
                del giveaways[code]
                break
        
        df.to_csv("main/config/points.csv", index=False)
        used.to_csv("main/config/used.csv", index=False)
        with open("main/config/unique_users_per_day.pickle", "wb") as f:
            pickle.dump(unique_users_per_day, f, protocol=pickle.HIGHEST_PROTOCOL)
        
        with open("main/config/unique_codes_per_day.pickle", "wb") as f:
            pickle.dump(unique_codes_per_day, f, protocol=pickle.HIGHEST_PROTOCOL)

        with open("main/config/points_in_circulation.pickle", "wb") as f:
            pickle.dump(points_in_circulation, f, protocol=pickle.HIGHEST_PROTOCOL)
        await asyncio.sleep(60)

with open('main/config/secrets.json') as f:
    secrets = json.load(f)
TOKEN = secrets['token']
loop = asyncio.get_event_loop()
loop.create_task(client.start(TOKEN))
loop.create_task(expired())
#loop.run_forever()
Thread(target=loop.run_forever).start() #is this preferred?