from app.adapters.memory.in_memory_project_graph_repository import InMemoryProjectGraphRepository
from app.adapters.memory.in_memory_project_memory_repository import InMemoryProjectMemoryRepository
from app.core.domain.project_graph import EntityType, ProjectEntity, ProjectGraph
from app.core.domain.project_memory import MemoryKind
from app.core.use_cases.build_project_handbook import (
    BuildHandbookInput,
    BuildProjectHandbookUseCase,
)
from app.core.use_cases.compose_project_context import ComposeProjectContextUseCase
from app.core.use_cases.manage_project_memory import (
    AddMemoryInput,
    AddMemoryUseCase,
    DeleteMemoryUseCase,
    ListMemoryUseCase,
)


def _graph():
    return ProjectGraph(
        workspace_id="w1",
        entities=[
            ProjectEntity(
                id="cloud_service:aws-lambda",
                type=EntityType.CLOUD_SERVICE,
                name="AWS · Lambda",
                analyzer="terraform",
            ),
            ProjectEntity(
                id="environment:prd", type=EntityType.ENVIRONMENT, name="prod", analyzer="terraform"
            ),
        ],
    )


def test_add_list_delete():
    repo = InMemoryProjectMemoryRepository()
    item = AddMemoryUseCase(repo).execute(
        AddMemoryInput(workspace_id="w1", text="prod is called prd", kind=MemoryKind.CORRECTION)
    )
    assert ListMemoryUseCase(repo).execute("w1")[0].text == "prod is called prd"
    DeleteMemoryUseCase(repo).execute("w1", item.id)
    assert ListMemoryUseCase(repo).execute("w1") == []


def test_handbook_singleton_replaced():
    mem = InMemoryProjectMemoryRepository()
    graphs = InMemoryProjectGraphRepository()
    graphs.save_graph(_graph())
    uc = BuildProjectHandbookUseCase(graphs, mem)
    uc.execute(BuildHandbookInput(workspace_id="w1"))
    uc.execute(BuildHandbookInput(workspace_id="w1"))  # rebuild
    handbooks = [i for i in mem.list("w1") if i.kind == MemoryKind.HANDBOOK]
    assert len(handbooks) == 1 and "Lambda" in handbooks[0].text


def test_compose_context_combines_handbook_memory_graph():
    mem = InMemoryProjectMemoryRepository()
    graphs = InMemoryProjectGraphRepository()
    graphs.save_graph(_graph())
    BuildProjectHandbookUseCase(graphs, mem).execute(BuildHandbookInput(workspace_id="w1"))
    AddMemoryUseCase(mem).execute(
        AddMemoryInput(
            workspace_id="w1", text="lambda timeout is 30s", kind=MemoryKind.FACT, pinned=True
        )
    )
    ctx = ComposeProjectContextUseCase(mem, graphs).compose("w1", "how is lambda configured")
    assert "Project handbook" in ctx
    assert "lambda timeout is 30s" in ctx
    assert "AWS · Lambda" in ctx  # graph fact matched on 'lambda'


def test_compose_empty_when_nothing():
    mem = InMemoryProjectMemoryRepository()
    graphs = InMemoryProjectGraphRepository()
    assert ComposeProjectContextUseCase(mem, graphs).compose("w1", "anything") == ""
