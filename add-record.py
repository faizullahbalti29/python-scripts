#!/usr/bin/env python3
"""
import_nineth.py
---------------
Reads results-analyzer.nineth.json and bulk-inserts all documents
into the `nineth` collection of the `results-analyzer` MongoDB database.

Usage:
    python import_nineth.py                          # uses default paths
    python import_nineth.py --file path/to/file.json
    python import_nineth.py --uri mongodb://localhost:27017 --db results-analyzer
"""

import argparse
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    from pymongo import MongoClient, InsertOne
    from pymongo.errors import BulkWriteError
    from bson import json_util          # ships with pymongo — handles Extended JSON
except ImportError:
    sys.exit(
        "pymongo is not installed. Run:  pip install pymongo"
    )

# ── Defaults ────────────────────────────────────────────────────────────────
if load_dotenv is not None:
    load_dotenv()

DEFAULT_URI        = os.getenv("DB_URI")
DEFAULT_DB         = os.getenv("DB_NAME")
DEFAULT_COLLECTION =  "nineth"
DEFAULT_FILE       = "students.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import results-analyzer.nineth.json into MongoDB"
    )
    parser.add_argument(
        "--file", "-f",
        default=DEFAULT_FILE,
        help=f"Path to the JSON file (default: {DEFAULT_FILE})",
    )
    parser.add_argument(
        "--uri",
        default=DEFAULT_URI,
        help=f"MongoDB connection URI (default: {DEFAULT_URI})",
    )
    parser.add_argument(
        "--db",
        default=DEFAULT_DB,
        help=f"Database name (default: {DEFAULT_DB})",
    )
    parser.add_argument(
        "--collection", "-c",
        default=DEFAULT_COLLECTION,
        help=f"Collection name (default: {DEFAULT_COLLECTION})",
    )
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop the collection before inserting (fresh import)",
    )
    return parser.parse_args()


def load_json(file_path: str) -> list[dict]:
    path = Path(file_path)
    if not path.exists():
        sys.exit(f"[ERROR] File not found: {path.resolve()}")

    print(f"[INFO]  Reading {path.resolve()} …")
    raw = path.read_text(encoding="utf-8")

    # bson.json_util.loads converts MongoDB Extended JSON automatically:
    #   { "$oid": "..." }  →  ObjectId("...")
    #   { "$date": ... }   →  datetime
    #   etc.
    data = json_util.loads(raw)

    # Accept both a top-level array  [ {...}, {...} ]
    # and a MongoDB export envelope  { "data": [ {...} ] }  /  { "documents": [...] }
    if isinstance(data, list):
        return data
    for key in ("data", "documents", "results"):
        if isinstance(data.get(key), list):
            return data[key]

    sys.exit(
        "[ERROR] Unexpected JSON shape. "
        "Expected a top-level array or an object with a 'data'/'documents' key."
    )


def main() -> None:
    args = parse_args()

    # ── Load documents ───────────────────────────────────────────────────────
    documents = load_json(args.file)
    if not documents:
        sys.exit("[ERROR] JSON file is empty — nothing to insert.")

    print(f"[INFO]  {len(documents):,} document(s) loaded.")

    # ── Connect ──────────────────────────────────────────────────────────────
    print(f"[INFO]  Connecting to {args.uri} …")
    client  = MongoClient(args.uri, serverSelectionTimeoutMS=5_000)

    # Ping to catch connection errors early
    try:
        client.admin.command("ping")
    except Exception as exc:
        sys.exit(f"[ERROR] Cannot reach MongoDB: {exc}")

    db         = client[args.db]
    collection = db[args.collection]

    # ── Optional drop ────────────────────────────────────────────────────────
    if args.drop:
        collection.drop()
        print(f"[INFO]  Dropped existing '{args.collection}' collection.")

    # ── Bulk insert ──────────────────────────────────────────────────────────
    print(f"[INFO]  Inserting into '{args.db}'.'{args.collection}' …")

    operations = [InsertOne(doc) for doc in documents]

    try:
        result = collection.bulk_write(operations, ordered=False)
        print(f"[OK]    Inserted {result.inserted_count:,} document(s).")
    except BulkWriteError as bwe:
        inserted = bwe.details.get("nInserted", 0)
        errors   = bwe.details.get("writeErrors", [])
        print(f"[WARN]  Inserted {inserted:,} document(s) with {len(errors)} error(s).")
        for err in errors[:10]:          # show first 10 errors at most
            print(f"        • index {err['index']}: {err['errmsg']}")
        if len(errors) > 10:
            print(f"        … and {len(errors) - 10} more.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
