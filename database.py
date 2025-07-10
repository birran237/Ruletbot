from google.cloud import firestore
from google.oauth2 import service_account

credentials = service_account.Credentials.from_service_account_file("firebase_key.json")
db = firestore.Client(credentials=credentials)

async def save_to_database(guild_id: int, field: str, data):
    doc_ref = db.collection("guild_config").document(str(guild_id))
    doc_ref.set({field: data})

async def get_from_database(guild_id: int, field: str, default):
    doc_ref = db.collection("guild_config").document(str(guild_id))
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict().get(field, default)
    return default

async def del_guild_database(guild_id: int):
    doc_ref = db.collection("guild_config").document(str(guild_id))
    for docs in doc_ref.get().to_dict():
        doc_ref.update({docs: firestore.DELETE_FIELD})
    doc_ref.delete()