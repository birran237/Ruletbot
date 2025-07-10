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

async def set_guild_annoy(guild_id: int, annoy: bool):
    doc_ref = db.collection("guild_config").document(str(guild_id))
    doc_ref.set({"annoy_admins": annoy})

async def get_guild_annoy(guild_id: int) -> bool:
    doc_ref = db.collection("guild_config").document(str(guild_id))
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict().get("annoy_admins", True)
    return True


async def del_guild_database(guild_id: int):
    doc_ref = db.collection("guild_config").document(str(guild_id))
    for docs in doc_ref.get().to_dict():
        doc_ref.update({docs: firestore.DELETE_FIELD})
    doc_ref.delete()