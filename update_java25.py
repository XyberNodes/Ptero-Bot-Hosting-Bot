import asyncio
import os
import sys

import aiohttp
from dotenv import load_dotenv

load_dotenv()

PANEL_URL = os.getenv("PTERO_PANEL_URL", "").rstrip("/")
API_KEY = os.getenv("PTERO_API_KEY", "")
JAVA25_IMAGE = os.getenv("JAVA25_IMAGE", "ghcr.io/pterodactyl/yolks:java_25")


async def update_server(server_id: int) -> None:
    if not PANEL_URL or not API_KEY:
        raise RuntimeError("PTERO_PANEL_URL and PTERO_API_KEY must be set in .env")

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "Application/vnd.pterodactyl.v1+json",
        "Content-Type": "application/json",
    }

    timeout = aiohttp.ClientTimeout(total=45)
    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        get_url = f"{PANEL_URL}/api/application/servers/{server_id}"
        async with session.get(get_url) as response:
            body = await response.text()
            if response.status != 200:
                raise RuntimeError(f"Could not read server {server_id}: HTTP {response.status}: {body[:300]}")
            server = await response.json()

        attributes = server["attributes"]
        startup_url = f"{PANEL_URL}/api/application/servers/{server_id}/startup"
        payload = {
            "docker_image": JAVA25_IMAGE,
            "startup": attributes.get("startup", "java -Xms128M -Xmx{{SERVER_MEMORY}}M -jar {{SERVER_JARFILE}}"),
            "egg": attributes.get("egg"),
            "image": JAVA25_IMAGE,
            "environment": attributes.get("environment", {}),
        }

        async with session.patch(startup_url, json=payload) as response:
            body = await response.text()
            if response.status not in (200, 201, 204):
                raise RuntimeError(f"Could not update server {server_id}: HTTP {response.status}: {body[:500]}")

    print(f"Updated server {server_id} to {JAVA25_IMAGE}")
    print("Restart the server and verify with: java -version")


async def main() -> None:
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        print("Usage: python update_java25.py <pterodactyl_server_id>")
        raise SystemExit(2)
    await update_server(int(sys.argv[1]))


if __name__ == "__main__":
    asyncio.run(main())
