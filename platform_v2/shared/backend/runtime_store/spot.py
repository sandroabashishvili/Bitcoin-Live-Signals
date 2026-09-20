"""Central Spot runtime store and family names."""

from .families.spot import *  # noqa: F403
from .families.spot import FAMILY_BY_NAME
from .store import RuntimeStore


store = RuntimeStore(system="spot", family_by_name=FAMILY_BY_NAME)

runtime_root = store.runtime_root
runtime_data_root = store.runtime_data_root
family_dir = store.family_dir
daily_json_path = store.daily_json_path
load_json_list = store.load_json_list
load_json_dict = store.load_json_dict
load_family_rows = store.load_family_rows
load_family_rows_all = store.load_family_rows_all
load_latest_document = store.load_latest_document
load_family_documents = store.load_family_documents
write_json = store.write_json
append_runtime_record = store.append_runtime_record
upsert_runtime_record = store.upsert_runtime_record
store_runtime_snapshot = store.store_runtime_snapshot
missing_required_keys = store.missing_required_keys
validate_runtime_record = store.validate_runtime_record
