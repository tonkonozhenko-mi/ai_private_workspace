from pydantic import BaseModel

from app.core.domain.project_todos import ProjectTodos


class ProjectTodoResponse(BaseModel):
    file: str
    line: int
    marker: str
    text: str


class ProjectTodosResponse(BaseModel):
    total: int
    truncated: bool
    items: list[ProjectTodoResponse]


def to_project_todos_response(todos: ProjectTodos) -> ProjectTodosResponse:
    return ProjectTodosResponse(
        total=todos.total,
        truncated=todos.truncated,
        items=[
            ProjectTodoResponse(
                file=item.file,
                line=item.line,
                marker=item.marker,
                text=item.text,
            )
            for item in todos.items
        ],
    )
