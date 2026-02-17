from google.cloud import firestore
from google.oauth2 import service_account
from dotenv import load_dotenv
from collections import OrderedDict
import os
import json
import logging

log = logging.getLogger(__name__)


load_dotenv()

db_dict = dict[str, int | bool | str]
local_db: OrderedDict[int, db_dict] = OrderedDict()
defaults = {
    "timeout_seconds": 180,
    "lose_cooldown": 30,
    "annoy_admins": True,
    "half_lose_timeout": False,
    "win_message": "${k} ha retado a un duelo a ${u} y ha ganado",
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

class GuildConfig:
    timeout_seconds: int
    lose_cooldown: int
    annoy_admins: bool
    half_lose_timeout: bool
    win_message: str
    lose_message: str
    lose_penalty_message: str
    wrong_target: str

    def __init__(self, data: db_dict):
        self.__dict__ = defaults | data
        if "lose_penalty_message" not in data:
            self.lose_penalty_message = data["lose_message"]

async def save_to_database(guild_id: int, field: str, data: int | bool | str) -> None:
    if field not in defaults:
        raise Exception(f"Field {field} is not defined")
    if guild_id in local_db:
        local_db[guild_id][field] = data

    doc_ref = db.collection("guild_config").document(str(guild_id))
    doc_ref.set(document_data={field: data},merge=True)
    log.debug(f"Updated {field} to {data} on guild {guild_id}")


async def get_from_database(guild_id: int) -> GuildConfig:
    if guild_id in local_db:
        local_db.move_to_end(guild_id)
        if len(local_db[guild_id]) >= len(defaults): return GuildConfig(local_db[guild_id])

    doc_ref = db.collection("guild_config").document(str(guild_id))
    doc = doc_ref.get()

    return_dict:db_dict = defaults | (doc.to_dict() if doc.exists else {})

    if len(local_db) >= 2000 and guild_id not in local_db:
        local_db.popitem(last=False)

    local_db[guild_id] = return_dict
    return GuildConfig(return_dict)


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
