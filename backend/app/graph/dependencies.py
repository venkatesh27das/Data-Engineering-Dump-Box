from fastapi import Depends

from app.config import Settings, get_settings
from app.graph.neo4j_store import Neo4jGraphStore


def get_graph_store(settings: Settings = Depends(get_settings)) -> Neo4jGraphStore:
    return Neo4jGraphStore(uri=settings.neo4j_uri, username=settings.neo4j_username, password=settings.neo4j_password, database=settings.neo4j_database)
