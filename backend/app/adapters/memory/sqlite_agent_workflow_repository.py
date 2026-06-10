import json
from pathlib import Path
import sqlite3

from app.adapters.memory.sqlite_schema import initialize_workspace_schema
from app.core.domain.agent_workflow import AgentWorkflowDraft, AgentWorkflowStep


class SQLiteAgentWorkflowRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        initialize_workspace_schema(self.db_path)

    def save_workflow(self, workflow: AgentWorkflowDraft) -> AgentWorkflowDraft:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO workspace_agent_workflows (
                    id, workspace_id, title, goal, provider, model, readiness, agent_mode,
                    status, steps_json, guardrails_json, unsupported_actions_json,
                    safety_note, created_at, updated_at, archived_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    workflow.id,
                    workflow.workspace_id,
                    workflow.title,
                    workflow.goal,
                    workflow.provider,
                    workflow.model,
                    workflow.readiness,
                    workflow.agent_mode,
                    workflow.status,
                    json.dumps([self._step_to_dict(step) for step in workflow.steps], sort_keys=True),
                    json.dumps(workflow.guardrails, sort_keys=True),
                    json.dumps(workflow.unsupported_actions, sort_keys=True),
                    workflow.safety_note,
                    workflow.created_at,
                    workflow.updated_at,
                    workflow.archived_at,
                ),
            )
            connection.commit()
        return workflow

    def get_workflow(self, workspace_id: str, workflow_id: str) -> AgentWorkflowDraft | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM workspace_agent_workflows WHERE id = ? AND workspace_id = ?",
                (workflow_id, workspace_id),
            ).fetchone()
        return self._from_row(row) if row else None

    def list_workflows(self, workspace_id: str, include_archived: bool = False) -> list[AgentWorkflowDraft]:
        clause = "workspace_id = ?" if include_archived else "workspace_id = ? AND archived_at IS NULL"
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM workspace_agent_workflows WHERE {clause} ORDER BY updated_at DESC, rowid DESC",
                (workspace_id,),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def delete_workflow(self, workspace_id: str, workflow_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM workspace_agent_workflows WHERE id = ? AND workspace_id = ?",
                (workflow_id, workspace_id),
            )
            connection.commit()
            return cursor.rowcount > 0

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _from_row(self, row: sqlite3.Row) -> AgentWorkflowDraft:
        return AgentWorkflowDraft(
            id=row["id"],
            workspace_id=row["workspace_id"],
            title=row["title"],
            goal=row["goal"],
            provider=row["provider"],
            model=row["model"],
            readiness=row["readiness"],
            agent_mode=row["agent_mode"],
            status=row["status"],
            steps=[self._step_from_dict(item) for item in json.loads(row["steps_json"] or "[]")],
            guardrails=list(json.loads(row["guardrails_json"] or "[]")),
            unsupported_actions=list(json.loads(row["unsupported_actions_json"] or "[]")),
            safety_note=row["safety_note"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            archived_at=row["archived_at"],
        )

    def _step_to_dict(self, step: AgentWorkflowStep) -> dict[str, object]:
        return {
            "id": step.id,
            "order": step.order,
            "title": step.title,
            "description": step.description,
            "status": step.status,
            "allowed_execution": step.allowed_execution,
            "verification": step.verification,
            "requires_user_confirmation": step.requires_user_confirmation,
            "approval_status": step.approval_status,
            "approval_note": step.approval_note,
            "proposed_tool": step.proposed_tool,
            "tool_risk": step.tool_risk,
            "execution_hint": step.execution_hint,
            "evidence_hint": step.evidence_hint,
            "approved_at": step.approved_at,
            "evidence_status": step.evidence_status,
            "evidence_summary": step.evidence_summary,
            "evidence_sources": step.evidence_sources or [],
            "notes": step.notes,
            "updated_at": step.updated_at,
        }

    def _step_from_dict(self, item: dict[str, object]) -> AgentWorkflowStep:
        return AgentWorkflowStep(
            id=str(item["id"]),
            order=int(item["order"]),
            title=str(item["title"]),
            description=str(item["description"]),
            status=str(item.get("status") or "todo"),
            allowed_execution=str(item["allowed_execution"]),
            verification=str(item["verification"]),
            requires_user_confirmation=bool(item.get("requires_user_confirmation", True)),
            approval_status=str(item.get("approval_status") or ("pending" if item.get("requires_user_confirmation", True) else "not_required")),
            approval_note=item.get("approval_note") if isinstance(item.get("approval_note"), str) else None,
            proposed_tool=item.get("proposed_tool") if isinstance(item.get("proposed_tool"), str) else None,
            tool_risk=str(item.get("tool_risk") or "manual_review"),
            execution_hint=item.get("execution_hint") if isinstance(item.get("execution_hint"), str) else None,
            evidence_hint=item.get("evidence_hint") if isinstance(item.get("evidence_hint"), str) else None,
            approved_at=item.get("approved_at") if isinstance(item.get("approved_at"), str) else None,
            evidence_status=str(item.get("evidence_status") or "not_provided"),
            evidence_summary=item.get("evidence_summary") if isinstance(item.get("evidence_summary"), str) else None,
            evidence_sources=[str(source) for source in item.get("evidence_sources", [])] if isinstance(item.get("evidence_sources"), list) else [],
            notes=item.get("notes") if isinstance(item.get("notes"), str) else None,
            updated_at=item.get("updated_at") if isinstance(item.get("updated_at"), str) else None,
        )
