"""
Configuration loader for team-insight.
Reads setting.json from the skill folder. Resolves environment variable references.
"""

import json
import os
import getpass
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class EmbeddingConfig:
    provider: str = "openai"  # openai | gemini | cohere | voyage | openai-compatible
    model: str = "text-embedding-3-small"
    base_url: str = "https://api.openai.com/v1"
    api_keys: List[str] = field(default_factory=list)
    batch_size: int = 50
    dimensions: int = 1536


@dataclass
class LanceDBConfig:
    path: str = ".claude/team-insight/db"
    table_name: str = "memories"


@dataclass
class RetrievalConfig:
    mode: str = "hybrid"  # hybrid | vector
    min_score: float = 0.30
    hard_min_score: float = 0.35
    length_norm_anchor: int = 500
    time_decay_half_life_days: int = 60
    mmr_similarity_threshold: float = 0.85
    default_limit: int = 5


@dataclass
class Config:
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    lancedb: LanceDBConfig = field(default_factory=LanceDBConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    json_dir: str = ".claude/team-insight/json"
    user_name: str = "auto"
    project_root: str = ""  # resolved at load time


def _resolve_env_var(value: str) -> str:
    """Resolve $ENV_VAR or ${ENV_VAR} references in a string."""
    if not isinstance(value, str):
        return value
    if value.startswith("$"):
        var_name = value.lstrip("$").strip("{}")
        return os.environ.get(var_name, "")
    return value


def _resolve_api_keys(raw_keys: List[str]) -> List[str]:
    """Resolve environment variable references in API key list."""
    resolved = []
    for key in raw_keys:
        val = _resolve_env_var(key)
        if val:
            resolved.append(val)

    # Fallback: try default env var
    if not resolved:
        for env_var in ["EMBEDDING_API_KEY"]:
            val = os.environ.get(env_var, "")
            if val:
                resolved.append(val)
                break

    return resolved


def resolve_username(config: Config) -> str:
    """Resolve the effective username."""
    if config.user_name and config.user_name != "auto":
        return config.user_name
    return getpass.getuser()


def _resolve_path(path_str: str, project_root: str) -> str:
    """Resolve a path relative to project root if not absolute."""
    if os.path.isabs(path_str):
        return path_str
    return os.path.join(project_root, path_str)


def load_config(setting_path: Optional[str] = None, project_root: Optional[str] = None) -> Config:
    """
    Load configuration from a setting.json file.

    Resolution order:
    1. Explicit setting_path argument
    2. TEAM_INSIGHT_CONFIG env var
    3. Auto-detect from script location
    """
    config = Config()

    # Determine project root
    if project_root:
        config.project_root = os.path.abspath(project_root)
    else:
        config.project_root = os.getcwd()

    # Find setting.json
    candidates = []
    if setting_path:
        candidates.append(setting_path)

    env_config = os.environ.get("TEAM_INSIGHT_CONFIG")
    if env_config:
        candidates.append(env_config)

    # Auto-detect: look relative to this script's location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    skill_dir = os.path.dirname(script_dir)  # scripts/ -> team-insight/
    candidates.append(os.path.join(skill_dir, "setting.json"))

    found_path = None
    for p in candidates:
        if os.path.isfile(p):
            found_path = p
            break

    if not found_path:
        # Use defaults with env-resolved keys
        config.embedding.api_keys = _resolve_api_keys(["$EMBEDDING_API_KEY"])
        return config

    # Load and parse
    with open(found_path, "r") as f:
        raw = json.load(f)

    # Embedding config
    if "embedding" in raw:
        e = raw["embedding"]
        config.embedding.provider = e.get("provider", config.embedding.provider)
        config.embedding.model = e.get("model", config.embedding.model)
        config.embedding.base_url = e.get("base_url", config.embedding.base_url)
        config.embedding.api_keys = _resolve_api_keys(e.get("api_keys", []))
        config.embedding.batch_size = e.get("batch_size", config.embedding.batch_size)
        config.embedding.dimensions = e.get("dimensions", config.embedding.dimensions)

    # LanceDB config
    if "lancedb" in raw:
        db = raw["lancedb"]
        config.lancedb.path = db.get("path", config.lancedb.path)
        config.lancedb.table_name = db.get("table_name", config.lancedb.table_name)

    # Retrieval config
    if "retrieval" in raw:
        r = raw["retrieval"]
        config.retrieval.mode = r.get("mode", config.retrieval.mode)
        config.retrieval.min_score = r.get("min_score", config.retrieval.min_score)
        config.retrieval.hard_min_score = r.get("hard_min_score", config.retrieval.hard_min_score)
        config.retrieval.length_norm_anchor = r.get("length_norm_anchor", config.retrieval.length_norm_anchor)
        config.retrieval.time_decay_half_life_days = r.get("time_decay_half_life_days", config.retrieval.time_decay_half_life_days)
        config.retrieval.mmr_similarity_threshold = r.get("mmr_similarity_threshold", config.retrieval.mmr_similarity_threshold)
        config.retrieval.default_limit = r.get("default_limit", config.retrieval.default_limit)

    # JSON dir
    config.json_dir = raw.get("json_dir", config.json_dir)

    # User
    if "user" in raw:
        config.user_name = raw["user"].get("name", config.user_name)

    # Resolve relative paths
    config.lancedb.path = _resolve_path(config.lancedb.path, config.project_root)
    config.json_dir = _resolve_path(config.json_dir, config.project_root)

    return config
