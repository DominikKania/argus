"""MongoDB connection for Argus API."""

import os
from pymongo import MongoClient

DB_NAME = "argus"

_client = None


def get_db():
    global _client
    if _client is None:
        uri = os.environ.get(
            "ARGUS_MONGO_URI",
            "mongodb://root:root@host.docker.internal:27017/?authSource=admin",
        )
        _client = MongoClient(uri)
    return _client[DB_NAME]
