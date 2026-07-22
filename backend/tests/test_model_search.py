"""Finding a model by its name instead of by its exact repository id.

Adding a model used to require knowing `bartowski/Qwen3-8B-GGUF` — the `-GGUF`
suffix and the username of whoever quantized it. Someone who knows they want
Qwen3 8B cannot get there from that knowledge. The field required you to already
have the answer.
"""

from app.core.domain.model_search import (
    ModelSearchResult,
    build_search_query,
    no_results_message,
    rank_search_results,
)


def _result(repo_id, downloads=0, likes=0):
    return ModelSearchResult(repo_id=repo_id, downloads=downloads, likes=likes)


def test_the_query_asks_for_the_format_the_app_can_actually_run():
    """Without this, searching 'qwen3' returns the original weights, which this
    app cannot load — and the person concludes the feature is broken rather than
    that they searched wrong."""
    assert build_search_query("qwen3 8b") == "qwen3 8b GGUF"


def test_someone_who_already_said_gguf_is_not_made_to_say_it_twice():
    assert build_search_query("qwen3 gguf") == "qwen3 gguf"
    assert build_search_query("Qwen3 GGUF") == "Qwen3 GGUF"


def test_an_empty_search_asks_for_nothing():
    assert build_search_query("") == ""
    assert build_search_query("   ") == ""


def test_the_obvious_answer_comes_first():
    results = [
        _result("someone/Qwen2.5-72B-GGUF", downloads=900_000),
        _result("bartowski/Qwen3-8B-GGUF", downloads=50_000),
        _result("other/Qwen3-8B-Instruct-GGUF", downloads=10_000),
    ]

    ranked = rank_search_results(results, "qwen3 8b")

    # Popularity does not get to bury the thing that was actually asked for.
    assert ranked[0].repo_id == "bartowski/Qwen3-8B-GGUF"


def test_among_equally_good_matches_the_one_people_use_wins():
    results = [
        _result("quiet/Qwen3-8B-GGUF", downloads=12),
        _result("popular/Qwen3-8B-GGUF", downloads=400_000),
    ]

    ranked = rank_search_results(results, "qwen3 8b")

    assert ranked[0].repo_id == "popular/Qwen3-8B-GGUF"


def test_repositories_this_app_cannot_load_are_dropped_not_ranked_low():
    """Offering something unusable is worse than offering less."""
    results = [
        _result("Qwen/Qwen3-8B", downloads=5_000_000),
        _result("bartowski/Qwen3-8B-GGUF", downloads=1),
    ]

    ranked = rank_search_results(results, "qwen3 8b")

    assert [r.repo_id for r in ranked] == ["bartowski/Qwen3-8B-GGUF"]


def test_the_order_is_the_same_every_time():
    """Two runs of one search disagreeing is the kind of thing that makes people
    stop trusting a list."""
    results = [_result(f"user{i}/Qwen3-8B-GGUF", downloads=100) for i in range(8)]

    first = [r.repo_id for r in rank_search_results(results, "qwen3")]
    second = [r.repo_id for r in rank_search_results(list(reversed(results)), "qwen3")]

    assert first == second


def test_the_list_is_capped_so_the_screen_stays_readable():
    results = [_result(f"user{i}/Qwen3-GGUF", downloads=i) for i in range(100)]

    assert len(rank_search_results(results, "qwen3", limit=20)) == 20


def test_nothing_found_says_what_might_be_wrong_without_blaming_anyone():
    message = no_results_message("qwen9 900b")

    assert "qwen9 900b" in message
    assert "nobody has published" in message


def test_an_empty_search_box_gets_an_example_rather_than_an_error():
    assert "for example" in no_results_message("")


def test_owner_and_name_are_read_off_the_repository_id():
    result = _result("bartowski/Qwen3-8B-GGUF")

    assert result.owner == "bartowski"
    assert result.model_name == "Qwen3-8B-GGUF"
