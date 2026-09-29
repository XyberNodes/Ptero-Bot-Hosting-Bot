import discord
from discord.ext import commands
from discord.ui import Button, View, Select
import aiohttp
import asyncio
import json
import os
import secrets
import string
import ssl
import re
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

CONFIG_FILE = "config.json"
LINKS_FILE = "links.json"
_processing = set()

BOT_PREFIX = os.getenv("BOT_PREFIX", "-")


def env_int(name: str, default: int = 0) -> int:
    value = os.getenv(name, "").strip()
    return int(value) if value.isdigit() else default


def env_list_int(name: str) -> list[int]:
    value = os.getenv(name, "").strip()
    if not value:
        return []
    result = []
    for item in value.split(","):
        item = item.strip()
        if item.isdigit():
            result.append(int(item))
    return result


DEFAULT_CONFIG = {
    "token": os.getenv("DISCORD_TOKEN", ""),
    "owner_id": env_int("OWNER_ID", 0),
    "admins": env_list_int("ADMINS"),
    "panel_url": os.getenv("PTERO_PANEL_URL", "").rstrip("/"),
    "api_key": os.getenv("PTERO_API_KEY", ""),
    "node_id": env_int("PTERO_NODE_ID", 1),
    "logo_url": os.getenv("LOGO_URL", "https://i.postimg.cc/q7vsNmbg/Chat-GPT-Image-Aug-20-2026-06-22-18-PM.png"),
    "bot_status": os.getenv("BOT_STATUS", "Managing Servers"),
    "bot_name": os.getenv("BOT_NAME", "APMANAGER"),
    "egg_ids": {},
    "docker_images": {
        "paper": "ghcr.io/pterodactyl/yolks:java_25",
        "spigot": "ghcr.io/pterodactyl/yolks:java_25",
        "vanilla": "ghcr.io/pterodactyl/yolks:java_25",
        "purpur": "ghcr.io/pterodactyl/yolks:java_25",
        "fabric": "ghcr.io/pterodactyl/yolks:java_25",
        "forge": "ghcr.io/pterodactyl/yolks:java_25",
        "waterfall": "ghcr.io/pterodactyl/yolks:java_25",
        "velocity": "ghcr.io/pterodactyl/yolks:java_25",
        "bungeecord": "ghcr.io/pterodactyl/yolks:java_25",
        "sponge": "ghcr.io/pterodactyl/yolks:java_25",
    },
}

SUPPORTED_MINECRAFT_VERSIONS = {
    "1.21.1": "java_21",
    "1.21.4": "java_21",
    "26.2": "java_25",
    "26.3": "java_25",
}
DEFAULT_MINECRAFT_VERSION = "26.3"

C_SUCCESS = 0x10B981
C_ERROR = 0xEF4444
C_INFO = 0x3B82F6
C_WARNING = 0xF59E0B
C_PRIMARY = 0x8B5CF6


def load_config():
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            config.update(saved)
        except Exception:
            print("⚠️ config.json unreadable, using defaults.")

    config["token"] = os.getenv("DISCORD_TOKEN", config.get("token", ""))
    config["owner_id"] = env_int("OWNER_ID", config.get("owner_id", 0))
    config["admins"] = env_list_int("ADMINS") if os.getenv("ADMINS") is not None else config.get("admins", [])
    config["panel_url"] = os.getenv("PTERO_PANEL_URL", config.get("panel_url", "")).rstrip("/")
    config["api_key"] = os.getenv("PTERO_API_KEY", config.get("api_key", ""))
    config["node_id"] = env_int("PTERO_NODE_ID", config.get("node_id", 1))
    config["logo_url"] = os.getenv("LOGO_URL", config.get("logo_url", DEFAULT_CONFIG["logo_url"]))
    config["bot_status"] = os.getenv("BOT_STATUS", config.get("bot_status", "Managing Servers"))
    config["bot_name"] = os.getenv("BOT_NAME", config.get("bot_name", "APMANAGER"))
    return config


def save_config(cfg):
    safe_cfg = dict(cfg)
    safe_cfg.pop("token", None)
    safe_cfg.pop("api_key", None)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(safe_cfg, f, indent=4)


def load_links():
    if not os.path.exists(LINKS_FILE):
        return {}
    with open(LINKS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_links(data):
    with open(LINKS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def generate_password(length=16):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def parse_size(value: str) -> int:
    value = str(value).lower().strip()
    match = re.match(r"^(\d+(?:\.\d+)?)(gb|mb|g|m)?$", value)
    if not match:
        raise ValueError(f"Invalid size: {value}")
    num = float(match.group(1))
    unit = match.group(2) or "mb"
    if unit in ["gb", "g"]:
        return int(num * 1024)
    return int(num)


config = load_config()
LOGO_URL = config.get("logo_url", DEFAULT_CONFIG["logo_url"])


def is_owner(ctx):
    return ctx.author.id == int(config.get("owner_id", 0)) or ctx.author.id in config.get("admins", [])


def owner_only():
    async def predicate(ctx):
        if not is_owner(ctx):
            await ctx.send(embed=make_embed("⛔ Access Denied", "Only **Bot Owner / Admin** can use this command.", C_ERROR))
            return False
        return True

    return commands.check(predicate)


def make_bar(percent, length=12):
    percent = max(0.0, min(100.0, percent))
    filled = int(length * percent / 100)
    return f"`{'🟩' * filled}{'⬛' * (length - filled)}` **{percent:.0f}%**"


def make_embed(title, description=None, color=C_PRIMARY):
    bot_name = config.get("bot_name", "APMANAGER")
    e = discord.Embed(title=title, description=description, color=color, timestamp=datetime.utcnow())
    e.set_thumbnail(url=LOGO_URL)
    e.set_footer(text=f"⚡ {bot_name}", icon_url=LOGO_URL)
    return e


async def show_progress(ctx, title, color=C_INFO):
    steps = [(20, "🔄 Connecting..."), (50, "⚙️ Processing..."), (80, "📦 Applying..."), (100, "✅ Done")]
    msg = await ctx.send(embed=make_embed(title, f"{make_bar(0)}\n\n🚀 Starting...", color))
    for percent, text in steps:
        await asyncio.sleep(0.25)
        try:
            await msg.edit(embed=make_embed(title, f"{make_bar(percent)}\n\n{text}", color))
        except Exception:
            pass
    return msg


class PteroAPI:
    def __init__(self, panel_url, api_key):
        self.base = panel_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "Application/vnd.pterodactyl.v1+json",
            "Content-Type": "application/json",
        }
        self.session = None
        self.egg_cache = {}

    async def start(self):
        self.session = aiohttp.ClientSession(headers=self.headers, timeout=aiohttp.ClientTimeout(total=45))

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def _request(self, method, endpoint, **kwargs):
        url = f"{self.base}{endpoint}"
        async with self.session.request(method, url, **kwargs) as resp:
            text = await resp.text()
            if resp.status in (200, 201, 204):
                if resp.status == 204 or not text.strip():
                    return {"success": True}
                return await resp.json()
            try:
                data = json.loads(text)
                err = data.get("errors", [{"detail": text}])[0]
                raise Exception(err.get("detail", text)[:300])
            except Exception:
                raise Exception(f"HTTP {resp.status}: {text[:200]}")

    async def list_nests(self):
        return await self._request("GET", "/api/application/nests?per_page=50")

    async def list_eggs(self, nest_id):
        return await self._request("GET", f"/api/application/nests/{nest_id}/eggs?per_page=50")

    async def find_egg_id(self, keyword: str):
        keyword = keyword.lower().strip()

        if keyword in self.egg_cache:
            return self.egg_cache[keyword]
        if keyword in config.get("egg_ids", {}):
            return config["egg_ids"][keyword]

        search_terms = {
            "paper": ["paper"],
            "spigot": ["spigot", "paper"],
            "purpur": ["purpur", "paper"],
            "vanilla": ["vanilla"],
            "forge": ["forge"],
            "fabric": ["fabric"],
            "waterfall": ["waterfall", "bungeecord"],
            "velocity": ["velocity"],
            "bungeecord": ["bungeecord"],
            "sponge": ["sponge"],
            "node": ["node", "nodejs", "node.js"],
            "nodejs": ["node", "nodejs", "node.js"],
            "node.js": ["node", "nodejs", "node.js"],
            "python": ["python"],
            "php": ["php"],
            "java": ["java"],
            "go": ["go", "golang"],
            "ruby": ["ruby"],
            "rust": ["rust"],
            "dotnet": ["dotnet", ".net"],
            ".net": ["dotnet", ".net"],
        }
        terms = search_terms.get(keyword, [keyword])

        try:
            nests = await self.list_nests()
            best_score = -1
            best_egg_id = None
            best_name = ""

            for nest in nests.get("data", []):
                eggs = await self.list_eggs(nest["attributes"]["id"])
                for egg in eggs.get("data", []):
                    name = egg["attributes"]["name"].lower().strip()
                    egg_id = egg["attributes"]["id"]
                    for term in terms:
                        score = 0
                        if name == term:
                            score = 100
                        elif name.startswith(term):
                            score = 90
                        elif term in name:
                            score = 50
                        if score > best_score:
                            best_score = score
                            best_egg_id = egg_id
                            best_name = name

            if best_egg_id and best_score >= 50:
                self.egg_cache[keyword] = best_egg_id
                config.setdefault("egg_ids", {})[keyword] = best_egg_id
                save_config(config)
                print(f"[EGG] {keyword} → {best_name} (ID {best_egg_id})")
                return best_egg_id
        except Exception as e:
            print(f"Egg search error: {e}")
        return None

    async def get_all_eggs(self):
        result = []
        try:
            nests = await self.list_nests()
            for nest in nests.get("data", []):
                nest_name = nest["attributes"]["name"]
                eggs = await self.list_eggs(nest["attributes"]["id"])
                for egg in eggs.get("data", []):
                    result.append({"id": egg["attributes"]["id"], "name": egg["attributes"]["name"], "nest": nest_name})
        except Exception:
            pass
        return result

    async def create_user(self, email, username, first, last, password, root_admin=False):
        return await self._request("POST", "/api/application/users", json={
            "email": email,
            "username": username,
            "first_name": first,
            "last_name": last,
            "password": password,
            "language": "en",
            "root_admin": root_admin,
        })

    async def delete_user(self, user_id):
        return await self._request("DELETE", f"/api/application/users/{user_id}")

    async def list_users(self):
        return await self._request("GET", "/api/application/users?per_page=100")

    async def get_user(self, user_id):
        return await self._request("GET", f"/api/application/users/{user_id}")

    async def get_free_allocation(self, node_id):
        data = await self._request("GET", f"/api/application/nodes/{node_id}/allocations?per_page=100")
        for item in data.get("data", []):
            if not item["attributes"].get("assigned", True):
                return item["attributes"]["id"]
        return None

    async def list_allocations(self, node_id):
        return await self._request("GET", f"/api/application/nodes/{node_id}/allocations?per_page=100")

    async def create_server(self, payload):
        return await self._request("POST", "/api/application/servers", json=payload)

    async def list_servers(self):
        return await self._request("GET", "/api/application/servers?include=user&per_page=100")

    async def get_server(self, server_id):
        return await self._request("GET", f"/api/application/servers/{server_id}?include=user,allocations")

    async def get_server_by_identifier(self, identifier):
        data = await self.list_servers()
        for s in data.get("data", []):
            if s["attributes"]["identifier"] == identifier:
                return s
        return None

    async def delete_server(self, server_id):
        return await self._request("DELETE", f"/api/application/servers/{server_id}/force")

    async def suspend_server(self, server_id):
        return await self._request("POST", f"/api/application/servers/{server_id}/suspend")

    async def unsuspend_server(self, server_id):
        return await self._request("POST", f"/api/application/servers/{server_id}/unsuspend")

    async def reinstall_server(self, server_id):
        return await self._request("POST", f"/api/application/servers/{server_id}/reinstall")

    async def update_build(self, server_id, memory, disk, cpu, allocation):
        return await self._request("PATCH", f"/api/application/servers/{server_id}/build", json={
            "allocation": allocation,
            "memory": memory,
            "swap": 0,
            "disk": disk,
            "io": 500,
            "cpu": cpu,
            "feature_limits": {"databases": 2, "allocations": 1, "backups": 2},
        })

    async def rename_server(self, server_id, name, user_id):
        return await self._request("PATCH", f"/api/application/servers/{server_id}/details", json={"name": name, "user": user_id})

    async def list_nodes(self):
        return await self._request("GET", "/api/application/nodes?per_page=50")

    async def power(self, identifier, signal):
        return await self._request("POST", f"/api/client/servers/{identifier}/power", json={"signal": signal})

    async def resources(self, identifier):
        return await self._request("GET", f"/api/client/servers/{identifier}/resources")

    async def send_command(self, identifier, command):
        return await self._request("POST", f"/api/client/servers/{identifier}/command", json={"command": command})


async def resolve_identifier(value: str) -> str:
    value = str(value).strip()
    if not value.isdigit():
        return value
    try:
        server = await bot.api.get_server(int(value))
        return server["attributes"]["identifier"]
    except Exception:
        raise Exception(f"Server ID `{value}` not found.")


async def can_control_server(ctx, identifier: str) -> bool:
    if is_owner(ctx):
        return True
    links = load_links()
    ptero_id = links.get(str(ctx.author.id))
    if not ptero_id:
        return False
    try:
        server = await bot.api.get_server_by_identifier(identifier)
        if not server:
            return False
        return str(server["attributes"]["user"]) == str(ptero_id)
    except Exception:
        return False


class PowerSelect(Select):
    def __init__(self, bot, identifier):
        options = [
            discord.SelectOption(label="Start", value="start", emoji="▶️"),
            discord.SelectOption(label="Stop", value="stop", emoji="⏹️"),
            discord.SelectOption(label="Restart", value="restart", emoji="🔄"),
            discord.SelectOption(label="Kill", value="kill", emoji="💀"),
        ]
        super().__init__(placeholder="⚡ Select Power Action...", options=options, row=1)
        self.bot = bot
        self.identifier = identifier

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        fake_ctx = type("obj", (object,), {"author": interaction.user})()
        if not await can_control_server(fake_ctx, self.identifier):
            return await interaction.followup.send(embed=make_embed("⛔ Access Denied", "You don't own this server.", C_ERROR), ephemeral=True)
        try:
            await self.bot.api.power(self.identifier, self.values[0])
            await interaction.followup.send(embed=make_embed("✅ Action Sent", f"**{self.values[0].upper()}** → `{self.identifier}`", C_SUCCESS), ephemeral=True)
        except Exception as e:
            await interaction.followup.send(embed=make_embed("❌ Failed", str(e)[:280], C_ERROR), ephemeral=True)


class CleanPowerView(View):
    def __init__(self, bot, identifier):
        super().__init__(timeout=180)
        self.bot = bot
        self.identifier = identifier
        self.add_item(PowerSelect(bot, identifier))

    async def _do(self, inter, signal):
        await inter.response.defer(ephemeral=True)
        fake_ctx = type("obj", (object,), {"author": inter.user})()
        if not await can_control_server(fake_ctx, self.identifier):
            return await inter.followup.send(embed=make_embed("⛔ Access Denied", "You don't own this server.", C_ERROR), ephemeral=True)
        try:
            await self.bot.api.power(self.identifier, signal)
            await inter.followup.send(embed=make_embed("✅ Done", f"**{signal.upper()}** → `{self.identifier}`", C_SUCCESS), ephemeral=True)
        except Exception as e:
            await inter.followup.send(embed=make_embed("❌ Failed", str(e)[:280], C_ERROR), ephemeral=True)

    @discord.ui.button(label="Start", style=discord.ButtonStyle.success, emoji="▶️", row=0)
    async def start(self, inter, button):
        await self._do(inter, "start")

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji="⏹️", row=0)
    async def stop(self, inter, button):
        await self._do(inter, "stop")

    @discord.ui.button(label="Restart", style=discord.ButtonStyle.primary, emoji="🔄", row=0)
    async def restart(self, inter, button):
        await self._do(inter, "restart")

    @discord.ui.button(label="Kill", style=discord.ButtonStyle.secondary, emoji="💀", row=0)
    async def kill(self, inter, button):
        await self._do(inter, "kill")


class HelpSelect(Select):
    def __init__(self, owner: bool):
        options = [
            discord.SelectOption(label="Power Commands", value="power", emoji="⚡"),
            discord.SelectOption(label="Status & Info", value="status", emoji="📊"),
            discord.SelectOption(label="Link Account", value="link", emoji="🔒"),
        ]
        if owner:
            options += [
                discord.SelectOption(label="User Management", value="users", emoji="👥"),
                discord.SelectOption(label="Create Minecraft", value="mc", emoji="🧱"),
                discord.SelectOption(label="Create Application", value="bot", emoji="🤖"),
                discord.SelectOption(label="Server Management", value="servers", emoji="💻"),
                discord.SelectOption(label="Advanced", value="manage", emoji="🛠️"),
                discord.SelectOption(label="Bot System", value="botsystem", emoji="⚙️"),
                discord.SelectOption(label="System", value="system", emoji="🔧"),
            ]
        super().__init__(placeholder="✨ Select a category...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guides = {
            "power": f"**⚡ Power Commands**\n\n`{BOT_PREFIX}start <id/identifier>`\n`{BOT_PREFIX}stop <id/identifier>`\n`{BOT_PREFIX}restart <id/identifier>`\n`{BOT_PREFIX}kill <id/identifier>`",
            "status": f"**📊 Status & Info**\n\n`{BOT_PREFIX}status <id/identifier>`\n`{BOT_PREFIX}info <server_id>`",
            "link": f"**🔒 Link Account**\n\n`{BOT_PREFIX}link <pterodactyl_user_id>`\n\n(Auto-linked when you use `{BOT_PREFIX}createuser @user` or `{BOT_PREFIX}mc @user`)",
            "users": f"**👥 User Management**\n\n`{BOT_PREFIX}createuser @user`\n`{BOT_PREFIX}createuser @user admin`\n`{BOT_PREFIX}deleteuser @user` / `{BOT_PREFIX}deleteuser <id>`\n`{BOT_PREFIX}listusers`",
            "mc": (
                "**🧱 Create Minecraft**\n\n"
                f"`{BOT_PREFIX}mc @user <type> <ram> <disk> <cpu> [version]`\n\n"
                "**Types:** paper, forge, vanilla, bungeecord, sponge, spigot, purpur\n\n"
                "**Examples:**\n"
                f"`{BOT_PREFIX}mc @user paper 2gb 10gb 100`\n"
                f"`{BOT_PREFIX}mc @user forge 4gb 20gb 200`\n"
                f"`{BOT_PREFIX}mc @user paper 2gb 10gb 100 26.3`\n\n"
                "Default version: `26.3`\n"
                "Java version: `25` for Minecraft 26.2/26.3\n"
                "Egg ID: automatic detection\n"
                "EULA: auto-accepted\n"
                f"Use `{BOT_PREFIX}types` to see available eggs."
            ),
            "bot": (
                "**🤖 Create Application**\n\n"
                f"`{BOT_PREFIX}bot @user <runtime> <ram> <cpu> <disk>`\n\n"
                "**Examples:**\n"
                f"`{BOT_PREFIX}bot @user node.js 512mb 100 2gb`\n"
                f"`{BOT_PREFIX}bot @user python 1gb 100 5gb`\n"
                f"`{BOT_PREFIX}bot @user php 512mb 100 2gb`\n\n"
                "**Supported runtimes:** node.js, nodejs, python, php, java, go, ruby, rust, dotnet\n\n"
                "The matching Pterodactyl egg is detected automatically."
            ),
            "servers": f"**💻 Server Management**\n\n`{BOT_PREFIX}servers`\n`{BOT_PREFIX}delete <id>`\n`{BOT_PREFIX}free`\n`{BOT_PREFIX}listeggs`\n`{BOT_PREFIX}types`",
            "manage": f"**🛠️ Advanced**\n\n`{BOT_PREFIX}rename` `{BOT_PREFIX}build` `{BOT_PREFIX}reinstall` `{BOT_PREFIX}suspend` `{BOT_PREFIX}unsuspend`",
            "botsystem": f"**⚙️ Bot System**\n\n`{BOT_PREFIX}addadmin @user`\n`{BOT_PREFIX}removeadmin @user`\n`{BOT_PREFIX}admins`\n`{BOT_PREFIX}setlogo`\n`{BOT_PREFIX}setstatus`\n`{BOT_PREFIX}newname`\n`{BOT_PREFIX}botinfo`",
            "system": f"**🔧 System**\n\n`{BOT_PREFIX}setup` `{BOT_PREFIX}nodes` `{BOT_PREFIX}egg` `{BOT_PREFIX}cmd`",
        }
        await interaction.followup.send(embed=make_embed("📖 Command Guide", guides.get(self.values[0], "—"), C_INFO), ephemeral=True)


class HelpView(View):
    def __init__(self, owner: bool):
        super().__init__(timeout=180)
        self.add_item(HelpSelect(owner))


intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents, help_command=None)
bot.api = None


@bot.event
async def on_ready():
    print(f"\n✅ Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"📌 Prefix: {BOT_PREFIX} | 👑 Owner: {config.get('owner_id')}")
    await bot.change_presence(activity=discord.Game(name=config.get("bot_status", "Managing Servers")))
    if config.get("panel_url") and config.get("api_key"):
        if bot.api is None:
            bot.api = PteroAPI(config["panel_url"], config["api_key"])
            await bot.api.start()
        print("🔗 API Connected")
    else:
        print("⚠️ Run -setup first")
    print("-----------------------------\n")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(embed=make_embed("❌ Missing Argument", f"`{BOT_PREFIX}{ctx.command.name} {ctx.command.signature}`", C_ERROR))
        return
    await ctx.send(embed=make_embed("❌ Error", str(error)[:380], C_ERROR))


@bot.command(name="help")
async def help_cmd(ctx):
    owner = is_owner(ctx)
    e = make_embed(
        f"✨ {config.get('bot_name', 'APMANAGER')} Control Panel",
        f"👋 Welcome **{ctx.author.display_name}**\n"
        f"🎭 Role: `{'👑 Owner/Admin' if owner else '👤 Member'}`\n"
        f"📌 Prefix: `{BOT_PREFIX}`\n\n👇 Select a category below.",
    )
    await ctx.send(embed=e, view=HelpView(owner))


@bot.command(name="addadmin")
@owner_only()
async def addadmin(ctx, member: discord.Member):
    if ctx.author.id != int(config.get("owner_id", 0)):
        return await ctx.send(embed=make_embed("⛔ Only Main Owner", "Only the main owner can add admins.", C_ERROR))
    admins = config.get("admins", [])
    if member.id in admins:
        return await ctx.send(embed=make_embed("⚠️ Already Admin", f"{member.mention} is already admin.", C_WARNING))
    admins.append(member.id)
    config["admins"] = admins
    save_config(config)
    await ctx.send(embed=make_embed("✅ Admin Added", f"{member.mention} is now a **Bot Admin**.", C_SUCCESS))


@bot.command(name="removeadmin")
@owner_only()
async def removeadmin(ctx, member: discord.Member):
    if ctx.author.id != int(config.get("owner_id", 0)):
        return await ctx.send(embed=make_embed("⛔ Only Main Owner", "Only the main owner can remove admins.", C_ERROR))
    admins = config.get("admins", [])
    if member.id not in admins:
        return await ctx.send(embed=make_embed("⚠️ Not Admin", f"{member.mention} is not an admin.", C_WARNING))
    admins.remove(member.id)
    config["admins"] = admins
    save_config(config)
    await ctx.send(embed=make_embed("✅ Admin Removed", f"{member.mention} removed from admins.", C_SUCCESS))


@bot.command(name="admins")
@owner_only()
async def list_admins(ctx):
    admins = config.get("admins", [])
    text = "\n".join([f"• <@{a}>" for a in admins]) or "No additional admins."
    e = make_embed("👑 Bot Admins", text, C_INFO)
    e.add_field(name="Main Owner", value=f"<@{config['owner_id']}>", inline=False)
    await ctx.send(embed=e)


@bot.command(name="setlogo")
@owner_only()
async def setlogo(ctx, url: str):
    global LOGO_URL
    if not url.startswith("http"):
        return await ctx.send(embed=make_embed("❌ Invalid URL", "Valid image URL required.", C_ERROR))
    LOGO_URL = url
    config["logo_url"] = url
    save_config(config)
    e = make_embed("✅ Logo Updated", "Logo changed successfully!", C_SUCCESS)
    e.set_thumbnail(url=url)
    await ctx.send(embed=e)


@bot.command(name="setstatus")
@owner_only()
async def setstatus(ctx, *, text: str):
    await bot.change_presence(activity=discord.Game(name=text))
    config["bot_status"] = text
    save_config(config)
    await ctx.send(embed=make_embed("✅ Status Updated", f"Status: **{text}**", C_SUCCESS))


@bot.command(name="newname")
@owner_only()
async def newname(ctx, *, name: str):
    if len(name) < 2 or len(name) > 32:
        return await ctx.send(embed=make_embed("❌ Invalid Name", "Name must be 2-32 characters.", C_ERROR))
    config["bot_name"] = name
    save_config(config)
    try:
        await bot.user.edit(username=name)
        status = "✅ Discord username updated"
    except Exception as e:
        status = f"⚠️ Username change failed\n`{str(e)[:80]}`"
    e = make_embed("✅ Bot Name Updated", color=C_SUCCESS)
    e.add_field(name="🆕 New Name", value=f"**{name}**", inline=False)
    e.add_field(name="📝 Status", value=status, inline=False)
    await ctx.send(embed=e)


@bot.command(name="botinfo")
@owner_only()
async def botinfo(ctx):
    e = make_embed("⚙️ Bot System Info", color=C_PRIMARY)
    e.add_field(name="👑 Main Owner", value=f"<@{config['owner_id']}>", inline=False)
    admins = config.get("admins", [])
    e.add_field(name="🛡️ Admins", value="\n".join([f"• <@{a}>" for a in admins]) if admins else "None", inline=False)
    e.add_field(name="🤖 Bot Name", value=config.get("bot_name", "APMANAGER"), inline=True)
    e.add_field(name="🎮 Status", value=config.get("bot_status", "Not set"), inline=True)
    e.add_field(name="📌 Prefix", value=f"`{BOT_PREFIX}`", inline=True)
    e.add_field(name="🖥️ Node", value=f"`{config.get('node_id')}`", inline=True)
    await ctx.send(embed=e)


@bot.command(name="link")
async def link(ctx, ptero_user_id: int):
    links = load_links()
    links[str(ctx.author.id)] = ptero_user_id
    save_links(links)
    await ctx.send(embed=make_embed("✅ Account Linked", f"Linked to Pterodactyl User `{ptero_user_id}`.", C_SUCCESS))


@bot.command(name="setup")
@owner_only()
async def setup(ctx, panel_url: str, api_key: str, node_id: int = 1):
    global config
    msg = await show_progress(ctx, "🔧 Setting up Panel...", C_INFO)
    config["panel_url"] = panel_url.rstrip("/")
    config["api_key"] = api_key
    config["node_id"] = node_id
    save_config(config)
    try:
        if bot.api:
            await bot.api.close()
        bot.api = PteroAPI(config["panel_url"], config["api_key"])
        await bot.api.start()
        await msg.edit(embed=make_embed("✅ Panel Connected", f"🌐 `{config['panel_url']}`\n🖥️ Node: `{node_id}`", C_SUCCESS))
    except Exception as e:
        await msg.edit(embed=make_embed("❌ Setup Failed", str(e)[:300], C_ERROR))


@bot.command(name="createuser")
@owner_only()
async def createuser(ctx, member: Optional[discord.Member] = None, *, args: str = None):
    key = f"createuser_{ctx.author.id}"
    if key in _processing:
        return
    _processing.add(key)
    try:
        if not bot.api:
            return await ctx.send(embed=make_embed("⚠️ Not Configured", "Run `-setup` first", C_WARNING))
        is_admin = False
        if member:
            username = "".join(c for c in member.name.lower() if c.isalnum())[:20] or f"u{member.id}"
            email = f"{username}.{member.id}@discord.local"
            first = member.display_name[:40]
            last = "User"
            if args and "admin" in args.lower():
                is_admin = True
        else:
            if not args:
                return await ctx.send(embed=make_embed("❌ Usage", f"`{BOT_PREFIX}createuser @user`", C_ERROR))
            parts = args.strip().split()
            email = parts[0]
            if "@" not in email:
                return await ctx.send(embed=make_embed("❌ Invalid Email", "Provide valid email.", C_ERROR))
            if len(parts) > 1 and parts[1].lower() == "admin":
                is_admin = True
            username = email.split("@")[0][:20]
            first = username.capitalize()
            last = "User"
        msg = await show_progress(ctx, "👤 Creating User...", C_INFO)
        password = generate_password()
        try:
            data = await bot.api.create_user(email, username, first, last, password, root_admin=is_admin)
            a = data["attributes"]

            if member:
                links = load_links()
                links[str(member.id)] = a["id"]
                save_links(links)

            public = make_embed("✅ User Created", color=C_SUCCESS)
            public.add_field(name="🆔 ID", value=f"`{a['id']}`", inline=True)
            public.add_field(name="👤 Username", value=f"`{a['username']}`", inline=True)
            public.add_field(name="🎭 Type", value="👑 Admin" if is_admin else "👤 User", inline=True)
            public.add_field(name="📧 Email", value=f"`{a['email']}`", inline=False)
            if member:
                public.add_field(name="🔗 Linked", value=f"Auto-linked to {member.mention}", inline=False)
            public.add_field(name="📝 Note", value="Login details sent via DM 📩", inline=False)
            await msg.edit(embed=public)
            if member:
                try:
                    dm = make_embed("📩 Your Panel Account", color=C_INFO)
                    dm.add_field(name="👤 Username", value=f"`{a['username']}`", inline=False)
                    dm.add_field(name="📧 Email", value=f"`{a['email']}`", inline=False)
                    dm.add_field(name="🔑 Password", value=f"||{password}||", inline=False)
                    dm.add_field(name="📝 Note", value="⚠️ **Change your password after login in panel.**", inline=False)
                    await member.send(embed=dm)
                except Exception:
                    await ctx.send(embed=make_embed("⚠️ Warning", "Could not DM the user.", C_WARNING))
        except Exception as e:
            await msg.edit(embed=make_embed("❌ Failed", str(e)[:350], C_ERROR))
    finally:
        _processing.discard(key)


@bot.command(name="mc")
@owner_only()
async def mc(ctx, target: str, type: str, ram: str, disk: str, cpu: str, version: str = DEFAULT_MINECRAFT_VERSION):
    key = f"mc_{ctx.author.id}"
    if key in _processing:
        return await ctx.send(embed=make_embed("⏳ Please Wait", "Server creation already in progress...", C_WARNING))
    _processing.add(key)

    try:
        if not bot.api:
            return await ctx.send(embed=make_embed("⚠️ Not Configured", "Run `-setup` first", C_WARNING))

        type = type.lower().strip()
        valid_types = ["paper", "spigot", "vanilla", "purpur", "fabric", "forge", "waterfall", "velocity", "bungeecord", "sponge"]
        if type not in valid_types:
            return await ctx.send(embed=make_embed("❌ Invalid Type", f"Available: `{'`, `'.join(valid_types)}`", C_ERROR))

        version = str(version).strip()
        if version not in SUPPORTED_MINECRAFT_VERSIONS:
            return await ctx.send(
                embed=make_embed(
                    "❌ Unsupported Minecraft Version",
                    "Supported versions are: " + ", ".join(f"`{item}`" for item in SUPPORTED_MINECRAFT_VERSIONS),
                    C_ERROR,
                )
            )

        java_version = SUPPORTED_MINECRAFT_VERSIONS[version]
        docker_image = config["docker_images"].get(type, f"ghcr.io/pterodactyl/yolks:{java_version}")

        try:
            ram_mb = parse_size(ram)
            disk_mb = parse_size(disk)
            cpu_percent = int(cpu)
        except Exception:
            return await ctx.send(embed=make_embed("❌ Invalid Resources", "Example: `-mc @user paper 2gb 10gb 100`", C_ERROR))

        msg = await show_progress(ctx, f"⛏️ Creating {type.upper()} {version}...", C_INFO)

        member = None
        ptero_user_id = None

        if ctx.message.mentions:
            member = ctx.message.mentions[0]
            links = load_links()
            ptero_user_id = links.get(str(member.id))
            if not ptero_user_id:
                username = "".join(c for c in member.name.lower() if c.isalnum())[:20] or f"u{member.id}"
                email = f"{username}.{member.id}@discord.local"
                password = generate_password()
                user_data = await bot.api.create_user(email, username, member.display_name[:40], "User", password)
                ptero_user_id = user_data["attributes"]["id"]
                links[str(member.id)] = ptero_user_id
                save_links(links)
                try:
                    dm_pass = make_embed("📩 Your Panel Account Created", color=C_INFO)
                    dm_pass.add_field(name="👤 Username", value=f"`{username}`", inline=False)
                    dm_pass.add_field(name="📧 Email", value=f"`{email}`", inline=False)
                    dm_pass.add_field(name="🔑 Password", value=f"||{password}||", inline=False)
                    dm_pass.add_field(name="📝 Note", value="⚠️ **Change your password after login in panel.**", inline=False)
                    await member.send(embed=dm_pass)
                except Exception:
                    pass
        else:
            if not target.isdigit():
                return await msg.edit(embed=make_embed("❌ Invalid Input", "Use `@user` or User ID.", C_ERROR))
            ptero_user_id = int(target)

        egg_id = await bot.api.find_egg_id(type)
        if not egg_id:
            return await msg.edit(embed=make_embed("❌ Egg Not Found", f"No egg matching **{type}** found on your panel.\nUse `{BOT_PREFIX}types` or `{BOT_PREFIX}listeggs`.", C_ERROR))

        alloc = await bot.api.get_free_allocation(config["node_id"])
        if not alloc:
            return await msg.edit(embed=make_embed("❌ No Free Port", "No free allocation found.", C_ERROR))

        base_env = {
            "SERVER_JARFILE": "server.jar",
            "EULA": "true",
            "ACCEPT_EULA": "true",
        }

        if type in ["paper", "purpur", "spigot"]:
            environment = {
                **base_env,
                "MINECRAFT_VERSION": version,
                "MC_VERSION": version,
                "VERSION": version,
                "BUILD_NUMBER": "latest",
                "BUILD_TYPE": "recommended",
            }
        elif type == "vanilla":
            environment = {
                **base_env,
                "VANILLA_VERSION": version,
                "MINECRAFT_VERSION": version,
                "MC_VERSION": version,
                "VERSION": version,
            }
        elif type == "forge":
            environment = {
                **base_env,
                "MC_VERSION": version,
                "MINECRAFT_VERSION": version,
                "FORGE_VERSION": "recommended",
                "VERSION": version,
            }
        elif type == "fabric":
            environment = {
                **base_env,
                "MC_VERSION": version,
                "MINECRAFT_VERSION": version,
                "FABRIC_VERSION": "latest",
                "LOADER_VERSION": "latest",
                "VERSION": version,
            }
        elif type in ["waterfall", "bungeecord"]:
            environment = {
                **base_env,
                "BUNGEE_VERSION": "latest",
                "WATERFALL_VERSION": "latest",
                "VERSION": "latest",
            }
        elif type == "velocity":
            environment = {
                **base_env,
                "VELOCITY_VERSION": "latest",
                "VERSION": "latest",
            }
        elif type == "sponge":
            environment = {
                **base_env,
                "SPONGE_VERSION": "latest",
                "MC_VERSION": version,
                "MINECRAFT_VERSION": version,
                "VERSION": version,
            }
        else:
            environment = {
                **base_env,
                "MC_VERSION": version,
                "MINECRAFT_VERSION": version,
                "VERSION": version,
            }

        emoji_map = {
            "paper": "📄",
            "spigot": "⚔️",
            "vanilla": "🌍",
            "purpur": "🟣",
            "fabric": "🧵",
            "forge": "🔥",
            "waterfall": "🌊",
            "velocity": "⚡",
            "bungeecord": "🌊",
            "sponge": "🧽",
        }
        name_part = member.name if member else f"User{ptero_user_id}"

        payload = {
            "name": f"{type.capitalize()}-{name_part}-{secrets.token_hex(2)}",
            "user": int(ptero_user_id),
            "egg": egg_id,
            "docker_image": docker_image,
            "startup": "java -Xms128M -Xmx{{SERVER_MEMORY}}M -jar {{SERVER_JARFILE}}",
            "environment": environment,
            "limits": {"memory": ram_mb, "swap": 0, "disk": disk_mb, "io": 500, "cpu": cpu_percent},
            "feature_limits": {"databases": 2, "allocations": 1, "backups": 2},
            "allocation": {"default": alloc},
            "start_on_completion": False,
        }

        data = await bot.api.create_server(payload)
        a = data["attributes"]

        e = make_embed(f"⛏️ {type.upper()} Server Created!", color=C_SUCCESS)
        if member:
            e.add_field(name="👤 For", value=member.mention, inline=True)
        else:
            e.add_field(name="👤 User ID", value=f"`{ptero_user_id}`", inline=True)
        e.add_field(name="🆔 Server ID", value=f"`{a['id']}`", inline=True)
        e.add_field(name="🔖 Identifier", value=f"`{a['identifier']}`", inline=True)
        e.add_field(name="📛 Name", value=a["name"], inline=False)
        e.add_field(name="🎮 Type", value=f"{emoji_map.get(type, '🎮')} {type.capitalize()}", inline=True)
        e.add_field(name="📦 Version", value=f"`{version}`", inline=True)
        e.add_field(name="🥚 Egg ID", value=f"`{egg_id}` (Auto Detected)", inline=True)
        e.add_field(name="💾 Resources", value=f"`{ram}` RAM • `{disk}` Disk • `{cpu}%` CPU", inline=False)
        e.add_field(name="📝 Note", value="⏳ Wait 1-2 min for install, then `-start <id>`\n✅ EULA auto-accepted", inline=False)
        await msg.edit(embed=e)

        if member:
            try:
                panel_link = f"{config['panel_url']}/server/{a['identifier']}"
                dm = make_embed(f"🎉 Your {type.upper()} Server is Ready!", color=C_SUCCESS)
                dm.add_field(name="🆔 Server ID", value=f"`{a['id']}`", inline=True)
                dm.add_field(name="🔖 Identifier", value=f"`{a['identifier']}`", inline=True)
                dm.add_field(name="🎮 Type", value=f"{emoji_map.get(type, '🎮')} {type.capitalize()} `{version}`", inline=True)
                dm.add_field(name="💾 Specs", value=f"**RAM:** `{ram}`\n**Disk:** `{disk}`\n**CPU:** `{cpu}%`", inline=False)
                dm.add_field(name="🔗 Panel Link", value=f"[Open Panel]({panel_link})", inline=False)
                dm.add_field(name="📝 Note", value="Wait 1-2 minutes for installation, then start the server.", inline=False)
                await member.send(embed=dm)
            except Exception:
                pass

    except Exception as e:
        try:
            await msg.edit(embed=make_embed("❌ Failed", str(e)[:350], C_ERROR))
        except Exception:
            await ctx.send(embed=make_embed("❌ Failed", str(e)[:350], C_ERROR))
    finally:
        _processing.discard(key)


@bot.command(name="bot")
@owner_only()
async def bot_create(ctx, target: str, runtime: str, ram: str, cpu: str, disk: str):
    """
    Create a non-Minecraft application server.

    Usage:
      -bot @user node.js 512mb 100 2gb
      -bot @user python 1gb 100 5gb
      -bot 123 nodejs 512mb 100 2gb
    """
    key = f"bot_{ctx.author.id}"

    if key in _processing:
        return await ctx.send(embed=make_embed("⏳ Please Wait", "Application creation is already in progress.", C_WARNING))

    _processing.add(key)
    msg = None

    try:
        if not bot.api:
            return await ctx.send(embed=make_embed("⚠️ Not Configured", "Run `-setup` first.", C_WARNING))

        runtime_aliases = {
            "node": "nodejs",
            "nodejs": "nodejs",
            "node.js": "nodejs",
            "javascript": "nodejs",
            "js": "nodejs",
            "python": "python",
            "py": "python",
            "php": "php",
            "java": "java",
            "go": "go",
            "golang": "go",
            "ruby": "ruby",
            "rust": "rust",
            "dotnet": "dotnet",
            ".net": "dotnet",
        }

        runtime_input = runtime.lower().strip()
        runtime_name = runtime_aliases.get(runtime_input, runtime_input)

        try:
            ram_mb = parse_size(ram)
            disk_mb = parse_size(disk)
            cpu_percent = int(cpu)

            if ram_mb <= 0 or disk_mb <= 0:
                raise ValueError("RAM and disk must be greater than zero.")

            if cpu_percent <= 0:
                raise ValueError("CPU must be greater than zero.")

        except Exception:
            return await ctx.send(embed=make_embed("❌ Invalid Resources", f"Example:\n`{BOT_PREFIX}bot @user node.js 512mb 100 2gb`", C_ERROR))

        msg = await show_progress(ctx, f"🤖 Creating {runtime_name.upper()} Application...", C_INFO)

        member = None
        ptero_user_id = None

        if ctx.message.mentions:
            member = ctx.message.mentions[0]
            links = load_links()
            ptero_user_id = links.get(str(member.id))

            if not ptero_user_id:
                username = "".join(c for c in member.name.lower() if c.isalnum())[:20] or f"u{member.id}"
                email = f"{username}.{member.id}@discord.local"
                password = generate_password()

                user_data = await bot.api.create_user(email, username, member.display_name[:40], "User", password)
                ptero_user_id = user_data["attributes"]["id"]
                links[str(member.id)] = ptero_user_id
                save_links(links)

                try:
                    dm = make_embed("📩 Your Panel Account Was Created", color=C_INFO)
                    dm.add_field(name="👤 Username", value=f"`{username}`", inline=False)
                    dm.add_field(name="📧 Email", value=f"`{email}`", inline=False)
                    dm.add_field(name="🔑 Password", value=f"||{password}||", inline=False)
                    dm.add_field(name="📝 Note", value="Change your password after logging in.", inline=False)
                    await member.send(embed=dm)
                except Exception:
                    pass
        else:
            if not target.isdigit():
                return await msg.edit(embed=make_embed("❌ Invalid User", "Use a Discord mention or a numeric Pterodactyl user ID.", C_ERROR))
            ptero_user_id = int(target)

        egg_id = await bot.api.find_egg_id(runtime_name)
        if not egg_id:
            return await msg.edit(embed=make_embed("❌ Egg Not Found", f"No Pterodactyl egg matching `{runtime_name}` was found.\nUse `{BOT_PREFIX}listeggs` to view available eggs.", C_ERROR))

        allocation = await bot.api.get_free_allocation(config["node_id"])
        if not allocation:
            return await msg.edit(embed=make_embed("❌ No Free Port", "No free allocation was found on the configured node.", C_ERROR))

        docker_images = {
            "nodejs": "ghcr.io/parkervcp/yolks:nodejs_20",
            "python": "ghcr.io/parkervcp/yolks:python_3.12",
            "php": "ghcr.io/parkervcp/yolks:php_8.3",
            "java": "ghcr.io/pterodactyl/yolks:java_21",
            "go": "ghcr.io/parkervcp/yolks:go_1.22",
            "ruby": "ghcr.io/parkervcp/yolks:ruby_3.3",
            "rust": "ghcr.io/parkervcp/yolks:rust_1.78",
            "dotnet": "ghcr.io/parkervcp/yolks:dotnet_8",
        }

        startup_commands = {
            "nodejs": "npm install && npm start",
            "python": "pip install -r requirements.txt && python main.py",
            "php": "php -S 0.0.0.0:{{SERVER_PORT}}",
            "java": "java -Xms128M -Xmx{{SERVER_MEMORY}}M -jar server.jar",
            "go": "go run .",
            "ruby": "ruby main.rb",
            "rust": "cargo run --release",
            "dotnet": "dotnet run",
        }

        environment = {"STARTUP_CMD": startup_commands.get(runtime_name, "bash")}

        name_part = member.name if member else f"User{ptero_user_id}"

        payload = {
            "name": f"{runtime_name.capitalize()}-{name_part}-{secrets.token_hex(2)}",
            "user": int(ptero_user_id),
            "egg": egg_id,
            "docker_image": docker_images.get(runtime_name, "ghcr.io/parkervcp/yolks:ubuntu_latest"),
            "startup": startup_commands.get(runtime_name, "bash"),
            "environment": environment,
            "limits": {
                "memory": ram_mb,
                "swap": 0,
                "disk": disk_mb,
                "io": 500,
                "cpu": cpu_percent,
            },
            "feature_limits": {
                "databases": 2,
                "allocations": 1,
                "backups": 2,
            },
            "allocation": {
                "default": allocation,
            },
            "start_on_completion": False,
        }

        data = await bot.api.create_server(payload)
        attributes = data["attributes"]

        embed = make_embed(f"✅ {runtime_name.upper()} Application Created", color=C_SUCCESS)

        if member:
            embed.add_field(name="👤 For", value=member.mention, inline=True)
        else:
            embed.add_field(name="👤 User ID", value=f"`{ptero_user_id}`", inline=True)

        embed.add_field(name="🆔 Server ID", value=f"`{attributes['id']}`", inline=True)
        embed.add_field(name="🔖 Identifier", value=f"`{attributes['identifier']}`", inline=True)
        embed.add_field(name="📛 Name", value=attributes["name"], inline=False)
        embed.add_field(name="🤖 Runtime", value=f"`{runtime_name}`", inline=True)
        embed.add_field(name="🥚 Egg ID", value=f"`{egg_id}`", inline=True)
        embed.add_field(name="💾 Resources", value=f"`{ram}` RAM • `{cpu}%` CPU • `{disk}` Disk", inline=False)
        embed.add_field(name="📝 Note", value=("The application was created but is not started automatically.\n"
            f"Use `{BOT_PREFIX}start {attributes['identifier']}` when ready."), inline=False)

        await msg.edit(embed=embed)

        if member:
            try:
                panel_link = f"{config['panel_url']}/server/{attributes['identifier']}"

                dm = make_embed(f"🎉 Your {runtime_name.upper()} Application Is Ready", color=C_SUCCESS)
                dm.add_field(name="🆔 Server ID", value=f"`{attributes['id']}`", inline=True)
                dm.add_field(name="🔖 Identifier", value=f"`{attributes['identifier']}`", inline=True)
                dm.add_field(name="🤖 Runtime", value=f"`{runtime_name}`", inline=True)
                dm.add_field(name="💾 Resources", value=(f"**RAM:** `{ram}`\n**CPU:** `{cpu}%`\n**Disk:** `{disk}`"), inline=False)
                dm.add_field(name="🔗 Panel Link", value=f"[Open Panel]({panel_link})", inline=False)

                await member.send(embed=dm)
            except Exception:
                pass

    except Exception as e:
        error_embed = make_embed("❌ Application Creation Failed", str(e)[:350], C_ERROR)

        if msg:
            await msg.edit(embed=error_embed)
        else:
            await ctx.send(embed=error_embed)

    finally:
        _processing.discard(key)


@bot.command(name="types")
@owner_only()
async def types(ctx):
    if not bot.api:
        return await ctx.send(embed=make_embed("⚠️ Not Configured", "Run `-setup` first", C_WARNING))
    msg = await show_progress(ctx, "🔍 Checking Available Types...", C_INFO)
    check_list = ["paper", "forge", "vanilla", "bungeecord", "sponge", "spigot", "purpur", "fabric", "waterfall", "velocity"]
    available, not_found = [], []
    for t in check_list:
        try:
            egg_id = await bot.api.find_egg_id(t)
            if egg_id:
                available.append(f"✅ `{t}` → Egg `{egg_id}`")
            else:
                not_found.append(f"❌ `{t}`")
        except Exception:
            not_found.append(f"❌ `{t}`")
    e = make_embed("🧱 Available Minecraft Types", color=C_INFO)
    if available:
        e.add_field(name="✅ Found on Panel (Auto Detected)", value="\n".join(available), inline=False)
    if not_found:
        e.add_field(name="❌ Not Found", value="\n".join(not_found), inline=False)
    e.add_field(name="📝 Note", value="Default version `26.3` • Java 25 • EULA auto-accepted • No hardcoded IDs", inline=False)
    await msg.edit(embed=e)


@bot.command(name="listeggs")
@owner_only()
async def listeggs(ctx):
    if not bot.api:
        return await ctx.send(embed=make_embed("⚠️ Not Configured", "Run `-setup` first", C_WARNING))
    msg = await show_progress(ctx, "🥚 Fetching All Eggs...", C_INFO)
    try:
        eggs = await bot.api.get_all_eggs()
        if not eggs:
            return await msg.edit(embed=make_embed("📭 No Eggs Found", "No eggs found.", C_WARNING))
        e = make_embed("🥚 All Available Eggs", color=C_INFO)
        for egg in eggs[:20]:
            e.add_field(name=f"🔹 {egg['name']}", value=f"ID: `{egg['id']}` | Nest: `{egg['nest']}`", inline=False)
        await msg.edit(embed=e)
    except Exception as e:
        await msg.edit(embed=make_embed("❌ Failed", str(e)[:300], C_ERROR))


async def power_cmd(ctx, value: str, signal: str, title: str):
    key = f"power_{ctx.author.id}_{value}_{signal}"
    if key in _processing:
        return
    _processing.add(key)
    try:
        if not bot.api:
            return await ctx.send(embed=make_embed("⚠️ Not Configured", "Run `-setup` first", C_WARNING))
        msg = await show_progress(ctx, title, C_INFO)
        try:
            identifier = await resolve_identifier(value)
            if not await can_control_server(ctx, identifier):
                return await msg.edit(embed=make_embed("⛔ Access Denied", "You don't own this server.", C_ERROR))
            await bot.api.power(identifier, signal)
            titles = {
                "start": "▶️ Server Started Successfully",
                "stop": "⏹️ Server Stopped Successfully",
                "restart": "🔄 Server Restarted Successfully",
                "kill": "💀 Server Killed Successfully",
            }
            e = make_embed(titles.get(signal, "✅ Done"), color=C_SUCCESS)
            e.add_field(name="🔖 Identifier", value=f"`{identifier}`", inline=True)
            e.add_field(name="⚡ Action", value=f"**{signal.upper()}**", inline=True)
            await msg.edit(embed=e)
        except Exception as e:
            await msg.edit(embed=make_embed("❌ Failed", str(e)[:300], C_ERROR))
    finally:
        _processing.discard(key)


@bot.command(name="start")
async def start(ctx, value: str):
    await power_cmd(ctx, value, "start", "▶️ Starting Server")


@bot.command(name="stop")
async def stop(ctx, value: str):
    await power_cmd(ctx, value, "stop", "⏹️ Stopping Server")


@bot.command(name="restart")
async def restart(ctx, value: str):
    await power_cmd(ctx, value, "restart", "🔄 Restarting Server")


@bot.command(name="kill")
async def kill(ctx, value: str):
    await power_cmd(ctx, value, "kill", "💀 Killing Server")


@bot.command(name="status")
async def status(ctx, value: str):
    if not bot.api:
        return await ctx.send(embed=make_embed("⚠️ Not Configured", "Run `-setup` first", C_WARNING))
    msg = await show_progress(ctx, "📊 Fetching Status...", C_INFO)
    try:
        identifier = await resolve_identifier(value)
        if not await can_control_server(ctx, identifier):
            return await msg.edit(embed=make_embed("⛔ Access Denied", "You don't own this server.", C_ERROR))
        data = await bot.api.resources(identifier)
        attrs = data["attributes"]
        state = attrs.get("current_state", "unknown").upper()
        res = attrs.get("resources", {})
        mem = res.get("memory_bytes", 0) / 1024 / 1024
        cpu = res.get("cpu_absolute", 0)
        disk = res.get("disk_bytes", 0) / 1024 / 1024
        state_map = {"RUNNING": ("🟢 Online", C_SUCCESS), "STARTING": ("🟡 Starting", C_WARNING), "STOPPING": ("🟠 Stopping", C_WARNING), "OFFLINE": ("🔴 Offline", C_ERROR)}
        state_text, color = state_map.get(state, (state, C_PRIMARY))
        e = make_embed(f"📊 Status • `{identifier}`", color=color)
        e.add_field(name="⚡ State", value=f"**{state_text}**", inline=False)
        e.add_field(name="⚙️ CPU", value=make_bar(min(cpu, 100)), inline=False)
        e.add_field(name="💾 Memory", value=f"{make_bar(min(mem/40, 100))}\n`{mem:.0f} MB`", inline=False)
        e.add_field(name="📀 Disk", value=f"{make_bar(min(disk/200, 100))}\n`{disk:.0f} MB`", inline=False)
        await msg.edit(embed=e, view=CleanPowerView(bot, identifier))
    except Exception as e:
        await msg.edit(embed=make_embed("❌ Failed", str(e)[:300], C_ERROR))


@bot.command(name="info")
async def info(ctx, server_id: int):
    if not bot.api:
        return await ctx.send(embed=make_embed("⚠️ Not Configured", "Run `-setup` first", C_WARNING))
    msg = await show_progress(ctx, "ℹ️ Fetching Server Info...", C_INFO)
    try:
        data = await bot.api.get_server(server_id)
        a = data["attributes"]
        identifier = a["identifier"]
        if not await can_control_server(ctx, identifier) and not is_owner(ctx):
            return await msg.edit(embed=make_embed("⛔ Access Denied", "You don't own this server.", C_ERROR))
        limits = a.get("limits", {})
        e = make_embed(f"ℹ️ {a['name']}", color=C_PRIMARY)
        e.add_field(name="🆔 ID", value=f"`{a['id']}`", inline=True)
        e.add_field(name="🔖 Identifier", value=f"`{identifier}`", inline=True)
        e.add_field(name="👤 Owner", value=str(a["user"]), inline=True)
        e.add_field(name="💾 Resources", value=f"RAM `{limits.get('memory')}MB` • Disk `{limits.get('disk')}MB` • CPU `{limits.get('cpu')}%`", inline=False)
        e.add_field(name="🚫 Suspended", value="Yes ❌" if a.get("suspended") else "No ✅", inline=True)
        await msg.edit(embed=e, view=CleanPowerView(bot, identifier))
    except Exception as e:
        await msg.edit(embed=make_embed("❌ Failed", str(e)[:300], C_ERROR))


@bot.command(name="delete")
@owner_only()
async def delete(ctx, server_id: int):
    key = f"delete_{ctx.author.id}_{server_id}"
    if key in _processing:
        return
    _processing.add(key)
    try:
        if not bot.api:
            return await ctx.send(embed=make_embed("⚠️ Not Configured", "Run `-setup` first", C_WARNING))
        msg = await show_progress(ctx, "🗑️ Force Deleting Server...", C_WARNING)
        try:
            await bot.api.delete_server(server_id)
            e = make_embed("✅ Server Deleted Successfully", color=C_SUCCESS)
            e.add_field(name="🆔 Server ID", value=f"`{server_id}`", inline=True)
            e.add_field(name="🗑️ Action", value="**Force Deleted**", inline=True)
            await msg.edit(embed=e)
        except Exception as e:
            await msg.edit(embed=make_embed("❌ Failed", str(e)[:300], C_ERROR))
    finally:
        _processing.discard(key)


@bot.command(name="suspend")
@owner_only()
async def suspend(ctx, server_id: int):
    if not bot.api:
        return await ctx.send(embed=make_embed("⚠️ Not Configured", "Run `-setup` first", C_WARNING))
    msg = await show_progress(ctx, "🚫 Suspending...", C_WARNING)
    try:
        await bot.api.suspend_server(server_id)
        await msg.edit(embed=make_embed("🚫 Suspended", f"Server `{server_id}` suspended.", C_WARNING))
    except Exception as e:
        await msg.edit(embed=make_embed("❌ Failed", str(e)[:300], C_ERROR))


@bot.command(name="unsuspend")
@owner_only()
async def unsuspend(ctx, server_id: int):
    if not bot.api:
        return await ctx.send(embed=make_embed("⚠️ Not Configured", "Run `-setup` first", C_WARNING))
    msg = await show_progress(ctx, "✅ Unsuspending...", C_INFO)
    try:
        await bot.api.unsuspend_server(server_id)
        await msg.edit(embed=make_embed("✅ Unsuspended", f"Server `{server_id}` is active.", C_SUCCESS))
    except Exception as e:
        await msg.edit(embed=make_embed("❌ Failed", str(e)[:300], C_ERROR))


@bot.command(name="servers")
@owner_only()
async def servers(ctx):
    if not bot.api:
        return await ctx.send(embed=make_embed("⚠️ Not Configured", "Run `-setup` first", C_WARNING))
    try:
        data = await bot.api.list_servers()
        lst = data.get("data", [])
        if not lst:
            return await ctx.send(embed=make_embed("📭 No Servers", "No servers found.", C_INFO))
        e = make_embed("💻 All Servers", color=C_INFO)
        for s in lst[:12]:
            a = s["attributes"]
            e.add_field(name=f"🔹 {a['name']}", value=f"`{a['id']}` • `{a['identifier']}` • Owner `{a['user']}`", inline=False)
        await ctx.send(embed=e)
    except Exception as e:
        await ctx.send(embed=make_embed("❌ Failed", str(e)[:300], C_ERROR))


@bot.command(name="listusers")
@owner_only()
async def listusers(ctx):
    if not bot.api:
        return await ctx.send(embed=make_embed("⚠️ Not Configured", "Run `-setup` first", C_WARNING))
    try:
        data = await bot.api.list_users()
        e = make_embed("👥 Panel Users", color=C_INFO)
        for u in data.get("data", [])[:15]:
            a = u["attributes"]
            e.add_field(name=f"👤 {a['username']}", value=f"`{a['id']}` • {a['email']}", inline=False)
        await ctx.send(embed=e)
    except Exception as e:
        await ctx.send(embed=make_embed("❌ Failed", str(e)[:300], C_ERROR))


@bot.command(name="user")
@owner_only()
async def user_info(ctx, user_id: int):
    if not bot.api:
        return await ctx.send(embed=make_embed("⚠️ Not Configured", "Run `-setup` first", C_WARNING))
    try:
        data = await bot.api.get_user(user_id)
        a = data["attributes"]
        e = make_embed(f"👤 {a['username']}", color=C_PRIMARY)
        e.add_field(name="🆔 ID", value=f"`{a['id']}`", inline=True)
        e.add_field(name="📧 Email", value=a["email"], inline=True)
        e.add_field(name="👑 Admin", value="Yes" if a.get("root_admin") else "No", inline=True)
        await ctx.send(embed=e)
    except Exception as e:
        await ctx.send(embed=make_embed("❌ Failed", str(e)[:300], C_ERROR))


@bot.command(name="rename")
@owner_only()
async def rename(ctx, server_id: int, *, new_name: str):
    if not bot.api:
        return await ctx.send(embed=make_embed("⚠️ Not Configured", "Run `-setup` first", C_WARNING))
    try:
        srv = await bot.api.get_server(server_id)
        await bot.api.rename_server(server_id, new_name, srv["attributes"]["user"])
        await ctx.send(embed=make_embed("✅ Renamed", f"`{server_id}` → **{new_name}**", C_SUCCESS))
    except Exception as e:
        await ctx.send(embed=make_embed("❌ Failed", str(e)[:300], C_ERROR))


@bot.command(name="reinstall")
@owner_only()
async def reinstall(ctx, server_id: int):
    if not bot.api:
        return await ctx.send(embed=make_embed("⚠️ Not Configured", "Run `-setup` first", C_WARNING))
    msg = await show_progress(ctx, "🔄 Reinstalling...", C_WARNING)
    try:
        await bot.api.reinstall_server(server_id)
        await msg.edit(embed=make_embed("🔄 Reinstall Started", f"Server `{server_id}` reinstalling...", C_WARNING))
    except Exception as e:
        await msg.edit(embed=make_embed("❌ Failed", str(e)[:300], C_ERROR))


@bot.command(name="build")
@owner_only()
async def build(ctx, server_id: int, ram: str, disk: str, cpu: str):
    if not bot.api:
        return await ctx.send(embed=make_embed("⚠️ Not Configured", "Run `-setup` first", C_WARNING))
    try:
        ram_mb = parse_size(ram)
        disk_mb = parse_size(disk)
        cpu_percent = int(cpu)
        srv = await bot.api.get_server(server_id)
        await bot.api.update_build(server_id, ram_mb, disk_mb, cpu_percent, srv["attributes"]["allocation"])
        await ctx.send(embed=make_embed("✅ Resources Updated", f"`{server_id}` → `{ram}` / `{disk}` / `{cpu}%`", C_SUCCESS))
    except Exception as e:
        await ctx.send(embed=make_embed("❌ Failed", str(e)[:300], C_ERROR))


@bot.command(name="free")
@owner_only()
async def free(ctx):
    if not bot.api:
        return await ctx.send(embed=make_embed("⚠️ Not Configured", "Run `-setup` first", C_WARNING))
    try:
        data = await bot.api.list_allocations(config["node_id"])
        free_list = [f"`{i['attributes']['ip']}:{i['attributes']['port']}` (ID `{i['attributes']['id']}`)" for i in data.get("data", []) if not i["attributes"].get("assigned", True)]
        text = "\n".join(free_list[:20]) if free_list else "No free ports found."
        await ctx.send(embed=make_embed("🔌 Free Allocations", text, C_INFO))
    except Exception as e:
        await ctx.send(embed=make_embed("❌ Failed", str(e)[:300], C_ERROR))


@bot.command(name="nodes")
@owner_only()
async def nodes(ctx):
    if not bot.api:
        return await ctx.send(embed=make_embed("⚠️ Not Configured", "Run `-setup` first", C_WARNING))
    try:
        data = await bot.api.list_nodes()
        e = make_embed("🖧 Nodes", color=C_INFO)
        for n in data.get("data", []):
            a = n["attributes"]
            e.add_field(name=f"🔹 {a['name']}", value=f"ID `{a['id']}` • `{a.get('memory')} MB`", inline=False)
        await ctx.send(embed=e)
    except Exception as e:
        await ctx.send(embed=make_embed("❌ Failed", str(e)[:300], C_ERROR))


@bot.command(name="egg")
@owner_only()
async def egg(ctx):
    e = make_embed("🥚 Cached Eggs (Auto Detected)", color=C_INFO)
    eggs = config.get("egg_ids", {})
    if not eggs:
        e.description = "No eggs cached yet. Use `-types`."
    else:
        for name, eid in eggs.items():
            e.add_field(name=f"🎮 {name.capitalize()}", value=f"`{eid}`", inline=True)
    await ctx.send(embed=e)


@bot.command(name="cmd")
@owner_only()
async def cmd(ctx, value: str, *, command: str):
    if not bot.api:
        return await ctx.send(embed=make_embed("⚠️ Not Configured", "Run `-setup` first", C_WARNING))
    try:
        identifier = await resolve_identifier(value)
        await bot.api.send_command(identifier, command)
        await ctx.send(embed=make_embed("⌨️ Command Sent", f"```{command}```", C_SUCCESS))
    except Exception as e:
        await ctx.send(embed=make_embed("❌ Failed", str(e)[:300], C_ERROR))


@bot.command(name="deleteuser")
@owner_only()
async def deleteuser(ctx, target: str = None):
    """Delete a Pterodactyl user by Discord mention or Ptero user ID.
    Usage:
      -deleteuser @user
      -deleteuser 123
    """
    if not bot.api:
        return await ctx.send(embed=make_embed("⚠️ Not Configured", "Run `-setup` first", C_WARNING))
    if target is None and not ctx.message.mentions:
        return await ctx.send(embed=make_embed("❌ Usage", f"`{BOT_PREFIX}deleteuser @user` or `{BOT_PREFIX}deleteuser <ptero_user_id>`", C_ERROR))

    ptero_user_id = None
    member = None

    if ctx.message.mentions:
        member = ctx.message.mentions[0]
        links = load_links()
        ptero_user_id = links.get(str(member.id))
        if not ptero_user_id:
            return await ctx.send(embed=make_embed(
                "⚠️ Not Linked",
                f"{member.mention} has no linked Pterodactyl account.\n"
                f"They must have been created with `{BOT_PREFIX}createuser @user` or `{BOT_PREFIX}mc @user` first,\n"
                f"or pass a Ptero user ID directly: `{BOT_PREFIX}deleteuser <id>`",
                C_WARNING,
            ))
        ptero_user_id = int(ptero_user_id)
    else:
        target = str(target).strip()
        if not target.isdigit():
            return await ctx.send(embed=make_embed(
                "❌ Invalid Input",
                "Provide a Discord mention (`@user`) or a numeric Pterodactyl user ID.",
                C_ERROR,
            ))
        ptero_user_id = int(target)

    msg = await show_progress(ctx, "🗑️ Deleting User...", C_WARNING)
    try:
        await bot.api.delete_user(ptero_user_id)

        links = load_links()
        removed = [did for did, pid in links.items() if int(pid) == ptero_user_id]
        for did in removed:
            del links[did]
        if removed:
            save_links(links)

        e = make_embed("✅ User Deleted", color=C_SUCCESS)
        e.add_field(name="🆔 Ptero User ID", value=f"`{ptero_user_id}`", inline=True)
        if member:
            e.add_field(name="👤 Discord", value=member.mention, inline=True)
        if removed:
            e.add_field(name="🔗 Links Cleared", value=f"{len(removed)} Discord link(s) removed", inline=False)
        await msg.edit(embed=e)
    except Exception as e:
        await msg.edit(embed=make_embed("❌ Failed", str(e)[:300], C_ERROR))


async def main():
    global config
    print("=" * 55)
    print(f" ⚡ {config.get('bot_name', 'APMANAGER')} Made With ❤️ By AyushTheWarrior")
    print(f" 📌 Prefix: {BOT_PREFIX}")
    print("=" * 55)

    token = config.get("token", "").strip()
    if not token:
        print("\n🔧 First-time configuration required")
        token = input("🔑 Bot Token: ").strip()
        owner = input("👑 Owner Discord ID: ").strip()
        if not token or not owner.isdigit():
            print("❌ Invalid input")
            return
        config["token"] = token
        config["owner_id"] = int(owner)
        save_config(config)
        print("✅ Saved\n")

    if not config.get("owner_id"):
        print("❌ OWNER_ID is missing. Add OWNER_ID in your .env file or setup prompt.")
        return

    print("🚀 Starting...")
    try:
        await bot.start(config["token"])
    finally:
        if bot.api:
            await bot.api.close()


if __name__ == "__main__":
    asyncio.run(main())
