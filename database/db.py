import motor.motor_asyncio
from config import DB_URL, DB_NAME


class Database:
    def __init__(self):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(DB_URL)
        self.db     = self.client[DB_NAME]
        self.users  = self.db.users

    # ── User ──────────────────────────────────────────────────────────────────
    async def add_user(self, user_id: int):
        if not await self.get_user(user_id):
            await self.users.insert_one({
                "user_id":      user_id,
                "thumbnail":    None,
                "gfx_channels": [],   # [{id, title}]
                "cover_channels": [], # [{id, title, command}]
            })

    async def get_user(self, user_id: int):
        return await self.users.find_one({"user_id": user_id})

    async def _ensure(self, user_id: int):
        await self.add_user(user_id)

    # ── Thumbnail ─────────────────────────────────────────────────────────────
    async def set_thumbnail(self, user_id: int, file_id: str):
        await self._ensure(user_id)
        await self.users.update_one(
            {"user_id": user_id}, {"$set": {"thumbnail": file_id}}
        )

    async def get_thumbnail(self, user_id: int):
        u = await self.get_user(user_id)
        return u.get("thumbnail") if u else None

    async def del_thumbnail(self, user_id: int):
        await self.users.update_one(
            {"user_id": user_id}, {"$set": {"thumbnail": None}}
        )

    async def total_users(self) -> int:
        return await self.users.count_documents({})

    # ── GFX channels ──────────────────────────────────────────────────────────
    async def get_gfx_channels(self, user_id: int) -> list:
        await self._ensure(user_id)
        u = await self.get_user(user_id)
        return u.get("gfx_channels", [])

    async def add_gfx_channel(self, user_id: int, ch_id: int, title: str):
        await self._ensure(user_id)
        channels = await self.get_gfx_channels(user_id)
        if any(c["id"] == ch_id for c in channels):
            return False
        await self.users.update_one(
            {"user_id": user_id},
            {"$push": {"gfx_channels": {"id": ch_id, "title": title}}}
        )
        return True

    async def remove_gfx_channel(self, user_id: int, ch_id: int):
        await self.users.update_one(
            {"user_id": user_id},
            {"$pull": {"gfx_channels": {"id": ch_id}}}
        )

    # ── Cover channels ────────────────────────────────────────────────────────
    async def get_cover_channels(self, user_id: int) -> list:
        await self._ensure(user_id)
        u = await self.get_user(user_id)
        return u.get("cover_channels", [])

    async def add_cover_channel(self, user_id: int, ch_id: int, title: str, command: str):
        await self._ensure(user_id)
        channels = await self.get_cover_channels(user_id)
        if any(c["id"] == ch_id for c in channels):
            return False
        await self.users.update_one(
            {"user_id": user_id},
            {"$push": {"cover_channels": {"id": ch_id, "title": title, "command": command}}}
        )
        return True

    async def remove_cover_channel(self, user_id: int, ch_id: int):
        await self.users.update_one(
            {"user_id": user_id},
            {"$pull": {"cover_channels": {"id": ch_id}}}
        )
