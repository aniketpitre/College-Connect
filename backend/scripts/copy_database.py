"""
Copy a whole database (every collection, with its indexes) to another server in big batches.

Used by the "Load demo data" workflow: the demo college is built against a MongoDB on the GitHub
runner (thousands of small requests, fast there) and then copied to Atlas in a few round trips
(slow over a long distance if done request by request).

    cd backend
    TARGET_MONGODB_URI=... python -m scripts.copy_database \\
        --source-uri mongodb://localhost:27017 --source-db collegeconnect_demo \\
        --target-db collegeconnect_demo --replace

The real database ("collegeconnect") is never a target. --replace drops the target database first
(for re-running a demo load); without it the target must be empty.
"""

import argparse
import os
import sys
from typing import Any

from pymongo import IndexModel, MongoClient
from pymongo.database import Database

PRODUCTION_DB = "collegeconnect"
BATCH = 1000


def copy(source: Database[dict[str, Any]], target: Database[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for name in sorted(source.list_collection_names()):
        if name.startswith("system."):
            continue
        docs: list[dict[str, Any]] = []
        counts[name] = 0
        for doc in source[name].find():
            docs.append(doc)
            if len(docs) >= BATCH:
                target[name].insert_many(docs, ordered=False)
                counts[name] += len(docs)
                docs = []
        if docs:
            target[name].insert_many(docs, ordered=False)
            counts[name] += len(docs)
        indexes = []
        for ix in source[name].list_indexes():
            if ix["name"] == "_id_":
                continue
            options = {k: v for k, v in ix.items() if k not in ("v", "key", "ns")}
            indexes.append(IndexModel(list(ix["key"].items()), **options))
        if indexes:
            target[name].create_indexes(indexes)
        elif counts[name] == 0:
            target.create_collection(name)
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source-uri", required=True)
    parser.add_argument("--source-db", required=True)
    parser.add_argument("--target-db", required=True)
    parser.add_argument("--replace", action="store_true", help="drop the target database first")
    args = parser.parse_args(argv)

    target_uri = os.getenv("TARGET_MONGODB_URI")
    if not target_uri:
        print("TARGET_MONGODB_URI is not set.", file=sys.stderr)
        return 1
    if args.target_db == PRODUCTION_DB:
        print(f"Refusing to copy into the real database '{PRODUCTION_DB}'.", file=sys.stderr)
        return 2

    source_client: MongoClient[dict[str, Any]] = MongoClient(args.source_uri)
    source = source_client[args.source_db]
    client: MongoClient[dict[str, Any]] = MongoClient(target_uri)
    target = client[args.target_db]
    if target.list_collection_names():
        if not args.replace:
            print(f"The database '{args.target_db}' is not empty (pass --replace).", file=sys.stderr)
            return 3
        client.drop_database(args.target_db)
        print(f"Emptied '{args.target_db}'")
    counts = copy(source, target)
    print(f"Copied {sum(counts.values())} documents in {len(counts)} collections to '{args.target_db}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
