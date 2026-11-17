"""配置加载与校验（pydantic 模型 + YAML 来源）。"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class TargetConfig(BaseModel):
    base_url: str
    mirror_url: str
    boards: list[int]
    crawl_order: list[int] = Field(default_factory=list)
    corpus_boards: list[int] = Field(default_factory=list)
    moderators: list[str]
    known_uids: dict[str, int] = Field(default_factory=dict)
    require_image: bool = True
    digest_search_expected: dict[str, int] = Field(default_factory=dict)
    expected_min_threads: int = 74
    digest_only: bool = False
    target_author_uid: int = 1
    digest_boards: list[int] = Field(default_factory=list)


class RateLimitConfig(BaseModel):
    min_interval_seconds: float = 2.0
    jitter_ratio: float = 0.15
    max_concurrent_images: int = 3
    retry_attempts: int = 3
    retry_backoff_seconds: list[float] = Field(default_factory=lambda: [5.0, 15.0, 45.0])
    consecutive_5xx_pause_threshold: int = 5
    pause_seconds: int = 600
    # 跨进程共享令牌桶（文件锁）：图片/正文并行采集时合计仍 ≤0.5 req/s
    shared_bucket_file: str | None = None


class AuthorizationConfig(BaseModel):
    text_crawl_approved: bool = True
    image_download_approved: bool = False


class HttpConfig(BaseModel):
    user_agent: str
    timeout_seconds: float = 30.0
    ca_bundle: str | None = None


class PathsConfig(BaseModel):
    data_dir: Path = Path("data")
    raw_dir: Path = Path("data/raw")
    images_dir: Path = Path("data/images")
    db_path: Path = Path("data/fs.sqlite")
    manifest_csv: Path = Path("data/tid_manifest.csv")
    report_path: Path = Path("data/collection_report.md")
    logs_dir: Path = Path("logs")


class AppConfig(BaseModel):
    target: TargetConfig
    rate_limit: RateLimitConfig = RateLimitConfig()
    authorization: AuthorizationConfig = AuthorizationConfig()
    http: HttpConfig
    paths: PathsConfig = PathsConfig()
    license_note: str
    config_dir: Path = Field(default=Path("."), exclude=True)

    def resolve_paths(self, base: Path | None = None) -> "AppConfig":
        """把相对路径锚定到项目根（config.yaml 所在目录）。"""
        root = base if base is not None else self.config_dir
        p = self.paths
        resolved = p.model_copy(
            update={
                "data_dir": (root / p.data_dir).resolve(),
                "raw_dir": (root / p.raw_dir).resolve(),
                "images_dir": (root / p.images_dir).resolve(),
                "db_path": (root / p.db_path).resolve(),
                "manifest_csv": (root / p.manifest_csv).resolve(),
                "report_path": (root / p.report_path).resolve(),
                "logs_dir": (root / p.logs_dir).resolve(),
            }
        )
        return self.model_copy(update={"paths": resolved})


def load_config(config_path: str | Path = "config.yaml") -> AppConfig:
    path = Path(config_path).resolve()
    with open(path, "rb") as f:
        payload = yaml.safe_load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"config.yaml 顶层必须是映射: {path}")
    cfg = AppConfig.model_validate({**payload, "config_dir": str(path.parent)})
    return cfg.resolve_paths()


DownloadStatus = Literal[
    "PENDING", "DONE", "SKIPPED_PENDING_AUTHORIZATION", "FAILED",
    # 两线实际都在写这两个状态（龙坛 200 空体=DEAD，fs168 404=DEAD、
    # 200-HTML=EXTERNAL_UNAVAILABLE），枚举必须与实际数据一致。
    "DEAD", "EXTERNAL_UNAVAILABLE",
]
