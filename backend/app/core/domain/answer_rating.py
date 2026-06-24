"""Answer ratings + the deterministic nudges derived from them.

The user's thumbs-up / thumbs-down are logged locally with a little context
(which model answered, how much project context it had). From the recent history
we derive at most two honest, conservative nudges:

  * model     — answers are getting thumbs-down a lot; a larger model may help.
  * retrieval — low-rated answers had little project context; rebuild the index.

No model is retrained. This is a pure read over a local log — same inputs always
give the same nudges.
"""

from dataclasses import dataclass


class RatingVerdict:
    UP = "up"
    DOWN = "down"


@dataclass(frozen=True)
class AnswerRating:
    id: str
    workspace_id: str
    verdict: str  # up | down
    llm_model: str  # "provider/model", best-effort
    context_chunks: int
    created_at: str  # ISO 8601


@dataclass(frozen=True)
class RatingNudge:
    kind: str  # "model" | "retrieval"
    title: str
    detail: str
    action: str  # "open_models" | "rebuild_context"


def compute_rating_nudges(
    ratings: list[AnswerRating],
    *,
    window: int = 20,
    min_total: int = 5,
    down_rate_threshold: float = 0.4,
) -> list[RatingNudge]:
    """Derive nudges from the most recent ratings (newest first).

    Conservative on purpose: nothing fires until there are at least ``min_total``
    recent ratings, so a couple of thumbs-down never nags the user.
    """
    recent = ratings[:window]
    if len(recent) < min_total:
        return []

    downs = [r for r in recent if r.verdict == RatingVerdict.DOWN]
    if not downs:
        return []

    nudges: list[RatingNudge] = []
    down_rate = len(downs) / len(recent)

    if down_rate >= down_rate_threshold:
        model = _most_common_model(downs)
        model_clause = f" with {model}" if model else ""
        nudges.append(
            RatingNudge(
                kind="model",
                title="Answers are getting thumbs-down a lot",
                detail=(
                    f"{len(downs)} of the last {len(recent)} answers{model_clause} were "
                    "rated not helpful. A larger local model often answers a project "
                    "like this more accurately."
                ),
                action="open_models",
            )
        )

    thin = [r for r in downs if r.context_chunks <= 1]
    if len(thin) / len(downs) >= 0.5:
        nudges.append(
            RatingNudge(
                kind="retrieval",
                title="Low-rated answers had little project context",
                detail=(
                    "Several thumbs-down answers were built from few or no project "
                    "files. Re-scan and rebuild the search context so answers are "
                    "grounded in your code."
                ),
                action="rebuild_context",
            )
        )

    return nudges


def _most_common_model(ratings: list[AnswerRating]) -> str:
    counts: dict[str, int] = {}
    for rating in ratings:
        if rating.llm_model:
            counts[rating.llm_model] = counts.get(rating.llm_model, 0) + 1
    if not counts:
        return ""
    return max(counts.items(), key=lambda kv: (kv[1], kv[0]))[0]
