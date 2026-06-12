from app.core.domain.onboarding import LaptopProfile


class LaptopProfileRegistry:
    def __init__(self, profiles: list[LaptopProfile] | None = None) -> None:
        self.profiles = profiles or DEFAULT_LAPTOP_PROFILES

    def list_profiles(self) -> list[LaptopProfile]:
        return list(self.profiles)

    def find_profile(self, profile_id: str) -> LaptopProfile | None:
        return next(
            (profile for profile in self.profiles if profile.id == profile_id),
            None,
        )

    @staticmethod
    def runtime_recommendation(profile_id: str) -> dict[str, str]:
        return dict(LAPTOP_RUNTIME_RECOMMENDATIONS[profile_id])

    @staticmethod
    def model_recommendation(profile_id: str) -> dict[str, str]:
        return dict(LAPTOP_MODEL_RECOMMENDATIONS[profile_id])


DEFAULT_LAPTOP_PROFILES = [
    LaptopProfile(
        id="low_power",
        name="Low Power",
        description="For older laptops or machines with limited RAM and CPU capacity.",
    ),
    LaptopProfile(
        id="balanced",
        name="Balanced",
        description="Default local setup balancing capability and resource usage.",
    ),
    LaptopProfile(
        id="powerful",
        name="Powerful",
        description="For stronger machines that can run larger local coding models.",
    ),
]


LAPTOP_RUNTIME_RECOMMENDATIONS = {
    "low_power": {
        "VECTOR_STORE": "memory",
        "EMBEDDING_PROVIDER": "fake",
        "LLM_PROVIDER": "fake",
    },
    "balanced": {
        "VECTOR_STORE": "qdrant",
        "EMBEDDING_PROVIDER": "ollama",
        "LLM_PROVIDER": "ollama",
    },
    "powerful": {
        "VECTOR_STORE": "qdrant",
        "EMBEDDING_PROVIDER": "ollama",
        "LLM_PROVIDER": "ollama",
    },
}


LAPTOP_MODEL_RECOMMENDATIONS = {
    "low_power": {
        "OLLAMA_EMBEDDING_MODEL": "nomic-embed-text",
        "OLLAMA_LLM_MODEL": "llama3.2",
    },
    "balanced": {
        "OLLAMA_EMBEDDING_MODEL": "nomic-embed-text",
        "OLLAMA_LLM_MODEL": "llama3.2",
    },
    "powerful": {
        "OLLAMA_EMBEDDING_MODEL": "nomic-embed-text",
        "OLLAMA_LLM_MODEL": "qwen2.5-coder",
    },
}
