"""SQLite-backed store for Project Intelligence graph snapshots.

The whole role-neutral graph is stored as a JSON payload per snapshot. The graph
is small and always read as a unit (and rebuilt on demand), so a single
JSON-per-snapshot table keeps M1 simple. A future milestone can normalise into
entity/relation tables if graph querying ("ask the graph") needs it.
"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.domain.project_graph import (
    ProjectEntity,
    ProjectFinding,
    ProjectGraph,
    ProjectRelation,
    ProjectSnapshotMeta,
    SourceRange,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _entity_to_dict(entity: ProjectEntity) -> dict:
    return {
        "id": entity.id,
        "type": entity.type,
        "name": entity.name,
        "analyzer": entity.analyzer,
        "confidence": entity.confidence,
        "status": entity.status,
        "source_file": entity.source_file,
        "source_range": (
            {"start_line": entity.source_range.start_line, "end_line": entity.source_range.end_line}
            if entity.source_range is not None
            else None
        ),
        "metadata": dict(entity.metadata),
    }


def _entity_from_dict(data: dict) -> ProjectEntity:
    source_range = data.get("source_range")
    return ProjectEntity(
        id=data["id"],
        type=data["type"],
        name=data["name"],
        analyzer=data["analyzer"],
        confidence=data.get("confidence", "high"),
        status=data.get("status", "confirmed"),
        source_file=data.get("source_file"),
        source_range=(
            SourceRange(source_range["start_line"], source_range["end_line"])
            if source_range
            else None
        ),
        metadata=dict(data.get("metadata") or {}),
    )


def _relation_to_dict(rel: ProjectRelation) -> dict:
    return {
        "id": rel.id,
        "source_entity_id": rel.source_entity_id,
        "target_entity_id": rel.target_entity_id,
        "relation_type": rel.relation_type,
        "analyzer": rel.analyzer,
        "confidence": rel.confidence,
        "source_file": rel.source_file,
        "evidence": list(rel.evidence),
    }


def _relation_from_dict(data: dict) -> ProjectRelation:
    return ProjectRelation(
        id=data["id"],
        source_entity_id=data["source_entity_id"],
        target_entity_id=data["target_entity_id"],
        relation_type=data["relation_type"],
        analyzer=data["analyzer"],
        confidence=data.get("confidence", "high"),
        source_file=data.get("source_file"),
        evidence=list(data.get("evidence") or []),
    )


def _finding_to_dict(finding: ProjectFinding) -> dict:
    return {
        "id": finding.id,
        "category": finding.category,
        "severity": finding.severity,
        "title": finding.title,
        "explanation": finding.explanation,
        "analyzer": finding.analyzer,
        "confidence": finding.confidence,
        "source_file": finding.source_file,
        "evidence": list(finding.evidence),
        "recommendation": finding.recommendation,
    }


def _finding_from_dict(data: dict) -> ProjectFinding:
    return ProjectFinding(
        id=data["id"],
        category=data["category"],
        severity=data["severity"],
        title=data["title"],
        explanation=data["explanation"],
        analyzer=data["analyzer"],
        confidence=data.get("confidence", "high"),
        source_file=data.get("source_file"),
        evidence=list(data.get("evidence") or []),
        recommendation=data.get("recommendation"),
    )


def _graph_to_payload(graph: ProjectGraph) -> str:
    return json.dumps(
        {
            "entities": [_entity_to_dict(e) for e in graph.entities],
            "relations": [_relation_to_dict(r) for r in graph.relations],
            "findings": [_finding_to_dict(f) for f in graph.findings],
            "analyzers_run": list(graph.analyzers_run),
            "analyzers_skipped": list(graph.analyzers_skipped),
        }
    )


def _graph_from_payload(workspace_id: str, payload: str) -> ProjectGraph:
    data = json.loads(payload)
    return ProjectGraph(
        workspace_id=workspace_id,
        entities=[_entity_from_dict(e) for e in data.get("entities", [])],
        relations=[_relation_from_dict(r) for r in data.get("relations", [])],
        findings=[_finding_from_dict(f) for f in data.get("findings", [])],
        analyzers_run=list(data.get("analyzers_run") or []),
        analyzers_skipped=list(data.get("analyzers_skipped") or []),
    )


class SQLiteProjectGraphRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS project_intelligence_snapshots (
                    id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    scan_signature TEXT,
                    entity_count INTEGER NOT NULL,
                    relation_count INTEGER NOT NULL,
                    finding_count INTEGER NOT NULL,
                    analyzers_run TEXT NOT NULL,
                    analyzers_skipped TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_pi_snapshots_ws "
                "ON project_intelligence_snapshots (workspace_id, created_at)"
            )
            connection.commit()

    def save_graph(
        self, graph: ProjectGraph, scan_signature: str | None = None
    ) -> ProjectSnapshotMeta:
        snapshot_id = str(uuid.uuid4())
        created_at = _utc_now_iso()
        meta = ProjectSnapshotMeta(
            id=snapshot_id,
            workspace_id=graph.workspace_id,
            created_at=created_at,
            entity_count=len(graph.entities),
            relation_count=len(graph.relations),
            finding_count=len(graph.findings),
            analyzers_run=list(graph.analyzers_run),
            analyzers_skipped=list(graph.analyzers_skipped),
            scan_signature=scan_signature,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO project_intelligence_snapshots (
                    id, workspace_id, created_at, scan_signature,
                    entity_count, relation_count, finding_count,
                    analyzers_run, analyzers_skipped, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    meta.id,
                    meta.workspace_id,
                    meta.created_at,
                    meta.scan_signature,
                    meta.entity_count,
                    meta.relation_count,
                    meta.finding_count,
                    json.dumps(meta.analyzers_run),
                    json.dumps(meta.analyzers_skipped),
                    _graph_to_payload(graph),
                ),
            )
            connection.commit()
        return meta

    def _latest_row(self, workspace_id: str) -> sqlite3.Row | None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT * FROM project_intelligence_snapshots
                WHERE workspace_id = ?
                ORDER BY created_at DESC, rowid DESC
                LIMIT 1
                """,
                (workspace_id,),
            )
            return cursor.fetchone()

    def get_latest_graph(self, workspace_id: str) -> ProjectGraph | None:
        row = self._latest_row(workspace_id)
        if row is None:
            return None
        return _graph_from_payload(workspace_id, row["payload_json"])

    def get_latest_snapshot_meta(self, workspace_id: str) -> ProjectSnapshotMeta | None:
        row = self._latest_row(workspace_id)
        if row is None:
            return None
        return ProjectSnapshotMeta(
            id=row["id"],
            workspace_id=row["workspace_id"],
            created_at=row["created_at"],
            entity_count=row["entity_count"],
            relation_count=row["relation_count"],
            finding_count=row["finding_count"],
            analyzers_run=json.loads(row["analyzers_run"]),
            analyzers_skipped=json.loads(row["analyzers_skipped"]),
            scan_signature=row["scan_signature"],
        )

    def clear(self, workspace_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM project_intelligence_snapshots WHERE workspace_id = ?",
                (workspace_id,),
            )
            connection.commit()
