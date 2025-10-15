from google.cloud import firestore
from google.oauth2 import service_account
from dotenv import load_dotenv
import os
import json
import logging

log = logging.getLogger(__name__)


load_dotenv()
local_db = {}
defaults = {
    "timeout_seconds": 180,
    "lose_cooldown": 0,
    "annoy_admins": True,
    "half_lose_timeout": False,
    "win_message": "${k} ha retado a un duelo a ${u} y ha ganado",
    "lose_message": "${k} ha retado a un duelo a ${u} y ha perdido",
    "lose_penalty_message": "${k} ha retado a un duelo a ${u} y ha perdido con penalización extra"
}


firebase_credentials = os.getenv('FIREBASE_CREDENTIALS')
firebase_project_id = os.getenv('FIREBASE_PROJECT_ID')

creds_dict = json.loads(firebase_credentials)
credentials = service_account.Credentials.from_service_account_info(creds_dict)
db = firestore.Client(credentials=credentials, project=firebase_project_id)
log.info(f"Connected to firebase")


async def save_to_database(guild_id: int, field: str, data: int | bool | str) -> None:
    if field not in defaults:
        raise Exception(f"Field {field} is not defined")
    if guild_id in local_db:
        local_db[guild_id][field] = data

    doc_ref = db.collection("guild_config").document(str(guild_id))
    doc_ref.set(document_data={field: data},merge=True)
    log.debug(f"Updated {field} to {data} on guild {guild_id}")


async def get_from_database(guild_id: int) -> dict:
    if guild_id in local_db:
        log.debug(f"Getting {guild_id} from local database")
        return local_db[guild_id]

    doc_ref = db.collection("guild_config").document(str(guild_id))
    doc = doc_ref.get()


    if len(local_db) < 100:
        local_db[guild_id] = defaults|doc.to_dict() #save db contents to local_db, and fill with defaults
    else:
        local_db.clear()

    log.debug(f"Getting {guild_id} from firebase database/defaults")
    if doc.exists:
        return defaults|doc.to_dict()

    return defaults


async def del_guild_database_field(guild_id: int, field: str) -> None:
    if field not in defaults:
        raise Exception(f"Field {field} is not defined")

    try:
        local_db[guild_id][field] = defaults[field]
    except KeyError:
        pass
    doc_ref = db.collection("guild_config").document(str(guild_id))
    doc = doc_ref.get()
    if doc.exists:
        log.debug(f"Deleting {field} from {guild_id} from firebase database")
        doc_ref.update({field: firestore.DELETE_FIELD})

async def del_guild_database(guild_id: int) -> None:
    try:
        del local_db[guild_id]
    except KeyError:
        pass

    doc_ref = db.collection("guild_config").document(str(guild_id))
    for docs in doc_ref.get().to_dict():
        doc_ref.update({docs: firestore.DELETE_FIELD})
    doc_ref.delete()
    log.debug(f"Deleted {guild_id} from firebase database")
