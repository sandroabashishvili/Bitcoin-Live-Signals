"""Stable facade for the modular SQLite runtime persistence subsystem."""

from .sqlite_documents import (
    import_json_document,
    mirror_daily_json_path_safely,
    mirror_document,
    mirror_document_safely,
)
from .sqlite_document_queries import (
    clear_system_documents,
    export_document_to_json,
    list_documents,
    parity_for_document,
    read_document,
    read_latest_document,
    remove_family_documents_except,
)
from .sqlite_read_gate import (
    read_daily_json_dict,
    read_daily_json_list,
    read_family_rows,
)
from .sqlite_schema import (
    DEFAULT_DATABASE_PATH,
    MIRROR_ENABLED,
    PRIMARY_READ_ENABLED,
    database_status,
    initialize_database,
)

__all__ = [
    "DEFAULT_DATABASE_PATH",
    "MIRROR_ENABLED",
    "PRIMARY_READ_ENABLED",
    "clear_system_documents",
    "database_status",
    "export_document_to_json",
    "import_json_document",
    "initialize_database",
    "list_documents",
    "mirror_daily_json_path_safely",
    "mirror_document",
    "mirror_document_safely",
    "parity_for_document",
    "read_daily_json_dict",
    "read_daily_json_list",
    "read_document",
    "read_latest_document",
    "read_family_rows",
    "remove_family_documents_except",
]
