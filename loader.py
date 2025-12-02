import signal, sys,  os, time, pickle
from collections import OrderedDict
import database
from utility import Utility

STATE_PATH = "state.pkl"
TMP_PATH = "state.pkl.tmp"

async def str_keys_to_int(d: dict) -> dict:
    out: dict = {}
    for key, value in d.items():
        try:
            ik = int(key)
        except (ValueError, TypeError): continue
        out[ik] = value
    return out

async def purge_expired_entries(d: dict) -> dict:
    out: dict = {}
    for key, value in d.items():
        current_time = time.time()
        if value > current_time:
            out[key] = value
    return out

async def process_temp_dicts():
    if not os.path.isfile(STATE_PATH):
        return OrderedDict(), {}, {}

    with open(STATE_PATH, 'rb') as f:
        try:
            data = pickle.load(f)
        except EOFError:
            print("puta")
            return OrderedDict(), {}, {}

        return (
            data.get("local_db",OrderedDict()),
            await purge_expired_entries(data.get("disabled_servers",{})),
            await purge_expired_entries(data.get("disabled_users",{}))
        )

async def load_temp_dicts() -> None:
    database.local_db,Utility.disabled_servers,Utility.disabled_users = await process_temp_dicts()
    return

def save_temp_dicts(signum, frame) -> None:
    data = {"local_db":database.local_db,"disabled_servers":Utility.disabled_servers,"disabled_users":Utility.disabled_users}
    with open(TMP_PATH, 'wb') as f:
        pickle.dump(data, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(TMP_PATH, STATE_PATH)
    sys.exit(0)


signal.signal(signal.SIGTERM, save_temp_dicts)
signal.signal(signal.SIGINT, save_temp_dicts)