import motor.motor_asyncio
from config import DB_URL, DB_NAME


class Database:
    def __init__(self):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(DB_URL)
        self.db = self.client[DB_NAME]
        self.users = self.db.users

    async def add_user(self, user_id: int):
        user = await self.get_user(user_id)
        if not user:
            await self.users.insert_one({"user_id": user_id, "thumbnail": None})

    async def get_user(self, user_id: int):
        return await self.users.find_one({"user_id": user_id})

    async def set_thumbnail(self, user_id: int, file_id: str):
        await self.add_user(user_id)
        await self.users.update_one(
            {"user_id": user_id},
            {"$set": {"thumbnail": file_id}},
        )

    async def get_thumbnail(self, user_id: int):
        user = await self.get_user(user_id)
        if user:
            return user.get("thumbnail")
        return None

    async def del_thumbnail(self, user_id: int):
        await self.users.update_one(
            {"user_id": user_id},
            {"$set": {"thumbnail": None}},
        )

    async def total_users(self) -> int:
        return await self.users.count_documents({})
