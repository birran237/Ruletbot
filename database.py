from google.cloud import firestore
from google.oauth2 import service_account
from dotenv import load_dotenv
from collections import OrderedDict
import os
import json
import logging
from typing import Literal

log = logging.getLogger(__name__)


load_dotenv()

db_fields = Literal["timeout_seconds","lose_cooldown","annoy_admins","half_lose_timeout","win_message","win_streak_message","lose_message","lose_penalty_message","wrong_target"]
db_dict = dict[db_fields, int | bool | str]
local_db: OrderedDict[int, db_dict] = OrderedDict()
defaults:db_dict = {
    "timeout_seconds": 120,
    "lose_cooldown": 180,
    "annoy_admins": False,
    "half_lose_timeout": False,
    "win_message": "${k} ha retado a un duelo a ${u} y ha ganado",
    "win_streak_message": "${k} ha retado a un duelo a ${u} y ha ganado con una racha de $r",
    "lose_message": "${k} ha retado a un duelo a ${u} y ha perdido",
    "lose_penalty_message": "${k} ha retado a un duelo a ${u} y ha perdido con penalización extra (hasta dentro de $t)",
    "wrong_target": "${k} tus dos abuelos son la misma persona (no vuelve hasta dentro de $t)",
}


firebase_credentials = os.getenv('FIREBASE_CREDENTIALS')
firebase_project_id = os.getenv('FIREBASE_PROJECT_ID')

creds_dict = json.loads(firebase_credentials)
credentials = service_account.Credentials.from_service_account_info(creds_dict)
db = firestore.Client(credentials=credentials, project=firebase_project_id)
log.info(f"Connected to firebase")


async def save_to_database(guild_id: int, field: db_fields, data: int | bool | str) -> None:
    if guild_id in local_db:
        local_db[guild_id][field] = data

    doc_ref = db.collection("guild_config").document(str(guild_id))
    doc_ref.set(document_data={field: data},merge=True)
    log.debug(f"Updated {field} to {data} on guild {guild_id}")


async def get_from_database(guild_id: int) -> db_dict:
    if guild_id in local_db:
        local_db.move_to_end(guild_id)
        if len(local_db[guild_id]) >= len(defaults): return local_db[guild_id]

    doc_ref = db.collection("guild_config").document(str(guild_id)).get()
    doc = doc_ref.to_dict() if doc_ref.exists else {}


    return_dict:db_dict = defaults | doc
    if "win_streak_message" not in doc:
        return_dict["win_streak_message"] = defaults["win_message"]
    if "lose_penalty_message" not in doc:
        return_dict["lose_penalty_message"] = defaults["lose_message"]
    if len(local_db) >= 2000:
        local_db.popitem(last=False)

    local_db[guild_id] = return_dict
    return return_dict


async def del_guild_database_field(guild_id: int, field: db_fields) -> None:
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
