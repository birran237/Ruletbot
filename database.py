from google.cloud import firestore
from google.oauth2 import service_account

credentials = service_account.Credentials.from_service_account_file("firebase_key.json")
db = firestore.Client(credentials=credentials)

async def set_guild_timeout(guild_id: int, minutes: int):
    doc_ref = db.collection("guild_config").document(str(guild_id))
    doc_ref.set({"timeout_minutes": minutes})

async def get_guild_timeout(guild_id: int) -> int:
    doc_ref = db.collection("guild_config").document(str(guild_id))
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict().get("timeout_minutes", 5)
    return 5