"""A page of rules wrapped around one request is searched by the request.

Live, 16.07: Maks pasted an NDA/anonymisation policy meaning "write the
onboarding docs, and obey all this". The whole page became the search query, so
the embedder — correctly — found documents about confidentiality rather than
about onboarding, and the rules ate 28% of the context window on the way.

He named the standard himself: paste those instructions to a person and they
write the documentation. A person separates what to do from how to behave.
"""

from app.core.domain.instruction_split import (
    MIN_CHARS_TO_SPLIT,
    retrieval_text,
    split_instructions_from_request,
)

RULES = """
NDA, confidentiality, and anonymization requirements
The analyzed documentation is confidential and protected by NDA.
Do not expose any real project-specific names in the response.
Anonymize all references to:
* project names;
* cluster names;
* bucket names;
* hostnames;
Required placeholder format
Use placeholders such as:
* [PROJECT_NAME]
* [CLIENT_NAME]
Never output the actual project name.
Do not expose original filenames or paths.
Before including a command:
1. Preserve its technical structure.
2. Replace confidential values with placeholders.
Final confidentiality verification
End the response with:
Confidentiality Check
""" * 3

ASK = "составь онбординг документацию для нового девопса в команде"


def test_the_search_uses_the_request_not_the_rulebook():
    query = retrieval_text(f"{ASK}\n{RULES}")

    assert ASK in query
    assert "[PROJECT_NAME]" not in query
    assert "Confidentiality Check" not in query
    assert len(query) < 300


def test_the_rules_are_kept_not_discarded():
    """They are instructions; the model still receives them in the prompt."""
    rules, request = split_instructions_from_request(f"{ASK}\n{RULES}")

    assert "Never output the actual project name." in rules
    assert ASK in request


def test_an_ordinary_question_is_untouched():
    for question in ["где хранятся отчёты?", "where is the retention period set?"]:
        rules, request = split_instructions_from_request(question)
        assert rules == ""
        assert request == question


def test_a_long_question_with_a_few_bullets_is_still_a_question():
    """Rules must dominate before anything is split off. A person writing a long,
    careful question deserves all of it searched."""
    question = (
        "Опиши, как устроен процесс деплоя в этом проекте, и ответь на вопросы: "
        "какие окружения существуют, как выкатывается каждое, что происходит при "
        "откате, и где хранится состояние terraform. Меня интересует именно то, "
        "что написано в документации проекта, а не общая практика. "
    ) * 6 + "\n- окружения\n- откат\n"

    rules, request = split_instructions_from_request(question)

    assert len(question) > MIN_CHARS_TO_SPLIT
    assert rules == ""
    assert request == question


def test_a_message_that_is_only_rules_keeps_all_of_it():
    """It asks for nothing, so we have nothing better to search with — and
    guessing on the person's behalf is worse than searching with everything."""
    rules, request = split_instructions_from_request(RULES)

    assert rules == ""
    assert request == RULES


def test_the_request_survives_when_it_comes_last():
    query = retrieval_text(f"{RULES}\n{ASK}")

    assert ASK in query
    assert "[PROJECT_NAME]" not in query
