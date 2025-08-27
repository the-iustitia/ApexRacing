import discord
from discord.ext import tasks
from discord.ui import Button, View
import random
import os
import json
import asyncio
import re

# ===== CONFIGURATION =====
TOKEN = ""
IMAGE_FOLDER = "images"
USER_DATA_PATH = "jsons/user_data.json"
CAR_LIST_PATH = "jsons/car_list.json"
CONFIG_PATH = "jsons/config.json"

ENTRY_COST = 100
REWARD_AMOUNT = 500

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Bot(intents=intents)

# ===== GLOBAL ACTIVE GUESS TRACKING =====
active_guess_view = None

# ===== JSON HELPERS =====
def load_json(path):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({}, f)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def load_user_data():
    return load_json(USER_DATA_PATH)

def save_user_data(data):
    save_json(USER_DATA_PATH, data)

def load_car_list():
    return load_json(CAR_LIST_PATH)

def load_config():
    return load_json(CONFIG_PATH)

def save_config(data):
    save_json(CONFIG_PATH, data)

def normalize(text):
    return re.sub(r"[^a-zA-Z0-9]", "", text.lower())

def weighted_random_car(car_list):
    return random.choices(car_list, weights=[c["chance"] for c in car_list], k=1)[0]

# ===== SEND CAR GUESS =====
async def send_car_guess():
    global active_guess_view

    config = load_config()
    channel_id = config.get("guess_channel_id")
    if not channel_id:
        print("[!] Guess channel not set.")
        return

    channel = bot.get_channel(channel_id)
    if not channel:
        print("[!] Channel not found.")
        return

    car_list = load_car_list()
    car = weighted_random_car(car_list)
    image_path = os.path.join(IMAGE_FOLDER, car["image"])

    if not os.path.exists(image_path):
        print(f"[!] Image not found: {image_path}")
        return

    embed = discord.Embed(
        title="🚘 Guess the Car!",
        description=f"Press the button below to guess the car. Costs {ENTRY_COST} coins.",
        color=discord.Color.blurple()
    )
    embed.set_image(url="attachment://car.jpg")

    button = Button(label="Guess", style=discord.ButtonStyle.green)

    async def button_callback(interaction: discord.Interaction):
        nonlocal button
        global active_guess_view

        if active_guess_view.guessed:
            await interaction.response.send_message("❌ This car has already been guessed!", ephemeral=True)
            return

        if view != active_guess_view:
            await interaction.response.send_message("❌ This guess is no longer active.", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        user_data = load_user_data()
        user = user_data.get(user_id, {"balance": 1000, "collection": []})

        if user["balance"] < ENTRY_COST:
            await interaction.response.send_message("❌ Not enough coins.", ephemeral=True)
            return

        user["balance"] -= ENTRY_COST
        save_user_data({**user_data, user_id: user})
        await interaction.response.send_message("Type your guess in chat within 30 seconds.", ephemeral=True)

        def check(m):
            return m.author.id == interaction.user.id and m.channel == interaction.channel

        try:
            msg = await bot.wait_for("message", timeout=30.0, check=check)
        except asyncio.TimeoutError:
            await interaction.followup.send("⏰ Time's up!", ephemeral=True)
            return

        guess = normalize(msg.content)
        correct = normalize(car["name"])

        if guess == correct:
            already_has = car["name"] in user["collection"]
            if not already_has:
                user["collection"].append(car["name"])
            user["balance"] += REWARD_AMOUNT
            save_user_data({**user_data, user_id: user})

            reward_msg = (
                f"✅ Correct! You received **{car['name']}** and {REWARD_AMOUNT} coins!"
                if not already_has else
                f"✅ Correct, but you already have {car['name']}. You still get {REWARD_AMOUNT} coins."
            )

            # Deactivate the button globally
            active_guess_view.guessed = True
            for item in active_guess_view.children:
                if isinstance(item, Button):
                    item.disabled = True
            try:
                await active_guess_view.message.edit(view=active_guess_view)
            except:
                pass

            await channel.send(
                f"🎉 {interaction.user.mention} guessed the car and takes **{car['name']}** into their collection!"
            )
            await interaction.followup.send(reward_msg, ephemeral=True)
        else:
            await interaction.followup.send(f"❌ Incorrect. The car was **{car['name']}**.", ephemeral=True)

    button.callback = button_callback
    view = View()
    view.add_item(button)

    file = discord.File(image_path, filename="car.jpg")
    sent_message = await channel.send(embed=embed, file=file, view=view)

    # Save the view globally
    view.message = sent_message
    view.car_name = car["name"]
    view.guessed = False
    global active_guess_view
    active_guess_view = view

# ===== GUESS LOOP =====
@tasks.loop(seconds=1)
async def car_guess_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        wait = random.randint(18, 36)  # 30–60 minutes
        print(f"[INFO] Waiting {wait} seconds before next guess.")
        await asyncio.sleep(wait)
        await send_car_guess()

# ===== SLASH COMMANDS =====
@bot.slash_command(name="set_channel", description="Set the channel for car guesses (admin only)")
async def set_channel(ctx: discord.ApplicationContext):
    if not ctx.author.guild_permissions.administrator:
        await ctx.respond("❌ You need administrator permissions.", ephemeral=True)
        return

    config = load_config()
    config["guess_channel_id"] = ctx.channel.id
    save_config(config)
    await ctx.respond(f"✅ Guess channel set to {ctx.channel.mention}", ephemeral=True)

@bot.slash_command(name="profile", description="View your profile and collection")
async def profile(ctx: discord.ApplicationContext, member: discord.Member = None):
    member = member or ctx.author
    user_id = str(member.id)
    user_data = load_user_data()
    car_list = load_car_list()

    if user_id not in user_data:
        user_data[user_id] = {"balance": 1000, "collection": []}
        save_user_data(user_data)

    user = user_data[user_id]
    chance_map = {car["name"]: car["chance"] for car in car_list}

    embed = discord.Embed(title=f"👤 Profile: {member.display_name}", color=discord.Color.gold())
    if member.avatar:
        embed.set_thumbnail(url=member.avatar.url)

    embed.add_field(name="💰 Balance", value=f"{user['balance']} coins", inline=False)

    if user["collection"]:
        sorted_collection = sorted(user["collection"], key=lambda name: chance_map.get(name, 9999))
        collection_text = "\n".join(f"• {name} (chance: {chance_map.get(name, '?')}%)" for name in sorted_collection)
    else:
        collection_text = "You don't have any cars yet."

    embed.add_field(name="🚗 Collection", value=collection_text, inline=False)
    await ctx.respond(embed=embed)

@bot.slash_command(name="leaderboard", description="Show top players by coin balance")
async def leaderboard(ctx: discord.ApplicationContext):
    user_data = load_user_data()
    sorted_users = sorted(user_data.items(), key=lambda x: x[1].get("balance", 0), reverse=True)[:10]

    embed = discord.Embed(title="🏆 Coin Leaderboard", color=discord.Color.blue())
    for i, (user_id, data) in enumerate(sorted_users, start=1):
        member = ctx.guild.get_member(int(user_id))
        name = member.display_name if member else f"User {user_id}"
        bal = data.get("balance", 0)
        embed.add_field(name=f"{i}. {name}", value=f"💰 {bal} coins", inline=False)

    await ctx.respond(embed=embed)

@bot.slash_command(name="about", description="About Apex Racing Bot")
async def about(ctx: discord.ApplicationContext):
    embed = discord.Embed(
        title="🤖 Apex Racing Bot",
        description=(
            "Welcome to **Apex Racing**!\n\n"
            "**How it works:**\n"
            "- Every 30–60 minutes, a car appears.\n"
            "- Click the button to guess and try your luck!\n"
            "- Entry costs 100 coins; correct guess rewards 500 coins.\n"
            "- Use `/profile` to view your progress.\n\n"
            "Developed by Ilya Sergeevich\n"
            "[GitHub](https://github.com/the-iustitia) | [Discord Server](https://discord.gg/kERheFhqj7)"
        ),
        color=discord.Color.blue()
    )

    view = View()
    view.add_item(discord.ui.Button(label="GitHub", url="https://github.com/the-iustitia"))
    view.add_item(discord.ui.Button(label="Join Discord", url="https://discord.gg/kERheFhqj7"))
    await ctx.respond(embed=embed, view=view)

# ===== ON READY =====
@bot.event
async def on_ready():
    print(f"[READY] Logged in as {bot.user}")
    car_guess_loop.start()

# ===== RUN =====
bot.run(TOKEN)
