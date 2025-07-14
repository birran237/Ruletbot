from google.cloud import firestore
from google.oauth2 import service_account
import datetime
import asyncio

local_db = {}
defaults = {"timeout_minutes":5,"annoy_admins":True}
credentials = service_account.Credentials.from_service_account_file("firebase_key.json")
db = firestore.Client(credentials=credentials)

async def save_to_database(guild_id: int, field: str, data):
    if field not in defaults:
        raise Exception(f"Field {field} is not defined")
    if guild_id in local_db:
        local_db[guild_id][field] = data
    doc_ref = db.collection("guild_config").document(str(guild_id))
    doc_ref.set({field: data},merge=True)

async def get_from_database(guild_id: int, field: str):
    if field not in defaults:
        raise Exception(f"Field {field} is not defined")

    if guild_id in local_db:
        return local_db[guild_id].get(field, defaults[field])

    doc_ref = db.collection("guild_config").document(str(guild_id))
    doc = doc_ref.get()
    if doc.exists:
        local_db[guild_id] = doc.to_dict()
        return doc.to_dict().get(field, defaults[field])
    local_db[guild_id] = doc.to_dict()
    return defaults[field]

async def del_guild_database(guild_id: int):
    try:
        del local_db[guild_id]
    except KeyError:
        pass

    doc_ref = db.collection("guild_config").document(str(guild_id))
    for docs in doc_ref.get().to_dict():
        doc_ref.update({docs: firestore.DELETE_FIELD})
    doc_ref.delete()

async def local_db_cleanup():
    last_run_month = None
    local_db.clear()

    while True:
        now = datetime.datetime.now()
        current_month = (now.year, now.month)

        if current_month != last_run_month and now.day == 1:
            local_db.clear()
            last_run_month = current_month

        # Sleep asynchronously (e.g., check every hour)
        await asyncio.sleep(86400)