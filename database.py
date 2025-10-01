from google.cloud import firestore
from google.oauth2 import service_account
from dotenv import load_dotenv
import os
import json

load_dotenv()
local_db = {}
defaults = {
    "timeout_minutes":5,
    "annoy_admins":True,
    "win_message":"{k} ha retado a un duelo a {u} y ha ganado",
    "lose_message":"{k} ha retado a un duelo a {u} y ha perdido",
    "lose_penalty_message":"{k} ha retado a un duelo a {u} y ha perdido con penalización extra"
}


firebase_credentials = os.getenv('FIREBASE_CREDENTIALS')
firebase_project_id = os.getenv('FIREBASE_PROJECT_ID')

creds_dict = json.loads(firebase_credentials)
credentials = service_account.Credentials.from_service_account_info(creds_dict)
db = firestore.Client(credentials=credentials, project=firebase_project_id)
print(f"Connected to firebase")


async def save_to_database(guild_id: int, field: str, data: int | bool | str) -> None:
    if field not in defaults:
        raise Exception(f"Field {field} is not defined")
    if guild_id in local_db:
        local_db[guild_id][field] = data

    doc_ref = db.collection("guild_config").document(str(guild_id))
    doc_ref.set(document_data={field: data},merge=True)


async def get_from_database(guild_id: int, field: str) -> int | bool | str:
    if field not in defaults:
        raise Exception(f"Field {field} is not defined")

    if guild_id in local_db:
        return local_db[guild_id].get(field, defaults[field])

    doc_ref = db.collection("guild_config").document(str(guild_id))
    doc = doc_ref.get()


    if len(local_db) < 100:
        local_db[guild_id] = defaults|doc.to_dict() #save db contents to local_db, and fill with defaults
    else:
        local_db.clear()

    if doc.exists:
        return doc.to_dict().get(field, defaults[field])

    return defaults[field]

async def del_guild_database_field(guild_id: int, field: str) -> None:
    if field not in defaults:
        raise Exception(f"Field {field} is not defined")

    try:
        del local_db[guild_id][field]
    except KeyError:
        pass
    doc_ref = db.collection("guild_config").document(str(guild_id))
    doc = doc_ref.get()
    if doc.exists:
        doc_ref.update({field: firestore.DELETE_FIELD})

async def del_guild_database(guild_id: int):
    try:
        del local_db[guild_id]
    except KeyError:
        pass

    doc_ref = db.collection("guild_config").document(str(guild_id))
    for docs in doc_ref.get().to_dict():
        doc_ref.update({docs: firestore.DELETE_FIELD})
    doc_ref.delete()
