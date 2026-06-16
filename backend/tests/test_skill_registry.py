from app.core.domain.project_scan import ProjectFile
from app.core.domain.skill_registry import SkillRegistry


def test_terraform_file_produces_devops_skill() -> None:
    skills = SkillRegistry().detect_skills([_project_file("main.tf", ".tf", "terraform")])

    assert skills[0].name == "Terraform"
    assert skills[0].category == "devops"
    assert skills[0].confidence == "high"
    assert skills[0].evidence == ["main.tf"]


def test_python_file_produces_developer_skill() -> None:
    skills = SkillRegistry().detect_skills([_project_file("app.py", ".py", "python")])

    assert skills[0].name == "Python"
    assert skills[0].category == "developer"


def test_markdown_file_produces_documentation_skill() -> None:
    skills = SkillRegistry().detect_skills([_project_file("README.md", ".md", "markdown")])

    assert skills[0].name == "Documentation"
    assert skills[0].category == "documentation"


def test_gitlab_ci_file_produces_devops_skill() -> None:
    skills = SkillRegistry().detect_skills([_project_file(".gitlab-ci.yml", ".yml", "gitlab_ci")])
    skills_by_name = {skill.name: skill for skill in skills}

    assert skills_by_name["GitLab CI"].category == "devops"
    assert skills_by_name["GitLab CI"].confidence == "high"
    assert skills_by_name["YAML/Configuration"].category == "general"
    assert skills_by_name["YAML/Configuration"].confidence == "medium"


def test_evidence_list_is_limited() -> None:
    files = [_project_file(f"module_{index}.tf", ".tf", "terraform") for index in range(10)]

    skills = SkillRegistry().detect_skills(files)

    assert skills[0].name == "Terraform"
    assert len(skills[0].evidence) == 5
    assert skills[0].evidence == [
        "module_0.tf",
        "module_1.tf",
        "module_2.tf",
        "module_3.tf",
        "module_4.tf",
    ]


def test_unknown_file_type_produces_no_specific_skill() -> None:
    skills = SkillRegistry().detect_skills([_project_file("notes.txt", ".txt", "unknown")])

    assert skills == []


def _project_file(path: str, extension: str | None, detected_type: str) -> ProjectFile:
    return ProjectFile(
        path=path,
        extension=extension,
        size_bytes=10,
        detected_type=detected_type,
    )
