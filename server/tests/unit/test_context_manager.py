from app.infrastructure.llm.context_manager import ContextManager


def test_context_manager_uses_selected_model_context_window() -> None:
    manager = ContextManager(
        "generation-model",
        [{"id": "generation-model", "context_length": 32_000}],
    )

    assert manager.context_window == 32_000


def test_context_manager_measures_prompt_and_completion_tokens() -> None:
    manager = ContextManager("generation-model")

    usage = manager.measure(
        [{"role": "system", "content": "1234"}],
        "5678",
    )

    assert usage.prompt_tokens == 1
    assert usage.completion_tokens == 1
    assert usage.total_tokens == 2
    assert usage.estimated is True
