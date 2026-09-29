# Ptero-Manager

A Discord bot for managing a Pterodactyl panel, creating Minecraft servers, linking Discord users, and running server actions from Discord.

## Important: Java 25 error

Minecraft 26.1 and newer cannot run on Java 21. If an existing server shows `java_21` or prints `openjdk version "21`, change its Docker image to:

```text
ghcr.io/pterodactyl/yolks:java_25
```

### Update an existing server

1. Add `PTERO_PANEL_URL`, `PTERO_API_KEY`, and `JAVA25_IMAGE` to `.env`.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the migration script with the Pterodactyl server ID:

```bash
python update_java25.py 123
```

4. Restart the server in Pterodactyl.
5. Confirm the console shows Java 25:

```text
java -version
openjdk version "25..."
```

You can also change the image manually in the server's Startup/Configuration page. Updating the bot does not change servers that were already created; those servers retain their existing Java 21 image until migrated.

## Features
- Discord bot owner/admin control
- Create and delete Pterodactyl users
- Auto-link Discord users to Pterodactyl users
- Create Minecraft servers with automatic egg detection
- Support for Minecraft 26.2 and 26.3
- Java 25 support for modern Minecraft releases
- Power actions: start, stop, restart, kill
- Server status and info commands
- Create generic app services using `-bot` (Node.js, Python, PHP, Java, Go, etc.)

## Setup
1. Copy `.env.example` to `.env`.
2. Fill in your environment values.
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Run the bot:

```bash
python bot.py
```

## Minecraft support
- `26.2` -> Java 25
- `26.3` -> Java 25

The default Minecraft version is `26.3`.

## Generic app support
Use `-bot` to create app servers with runtimes like:
- `node.js`
- `python`
- `php`
- `java`
- `go`
- `ruby`
- `rust`
- `dotnet`

Example:

```bash
-bot @user node.js 512mb 100 2gb
-bot @user python 1gb 100 5gb
```

## Hosting notes
This project is designed to run on Python hosting platforms that support environment variables and a `python` process. Use the provided `Procfile` for services such as Render, Railway, or similar hosts.
