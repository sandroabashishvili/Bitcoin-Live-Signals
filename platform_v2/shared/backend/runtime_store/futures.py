"""Central Futures runtime store and family names."""

from .families.futures import *  # noqa: F403
from .families.futures import FAMILY_BY_NAME
from .store import RuntimeStore


store = RuntimeStore(system="futures", family_by_name=FAMILY_BY_NAME)

runtime_root = store.runtime_root
runtime_data_root = store.runtime_data_root
family_dir = store.family_dir
daily_json_path = store.daily_json_path
load_json_list = store.load_json_list
load_json_dict = store.load_json_dict
def _latest_position_projection(rows):
    latest_by_id = {}
    for row in rows:
        position_id = str(row.get("position_id") or "").strip()
        if position_id:
            latest_by_id[position_id] = row
    return list(latest_by_id.values())


def load_family_rows(family_name, date_iso):
    if family_name == POSITIONS_FAMILY:  # noqa: F405
        return _latest_position_projection(store.load_family_rows(POSITION_EVENTS_FAMILY, date_iso))  # noqa: F405
    return store.load_family_rows(family_name, date_iso)


def load_family_rows_all(family_name):
    if family_name == POSITIONS_FAMILY:  # noqa: F405
        return _latest_position_projection(store.load_family_rows_all(POSITION_EVENTS_FAMILY))  # noqa: F405
    return store.load_family_rows_all(family_name)


load_latest_document = store.load_latest_document
load_family_documents = store.load_family_documents
write_json = store.write_json
append_runtime_record = store.append_runtime_record
upsert_runtime_record = store.upsert_runtime_record
upsert_runtime_row = store.upsert_runtime_row
store_runtime_snapshot = store.store_runtime_snapshot
missing_required_keys = store.missing_required_keys
validate_runtime_record = store.validate_runtime_record
