import subprocess
import sys
import textwrap


def test_api_mode_imports_no_local_ml_libs():
    """Importing the embedding/labeling code paths with providers=api must not
    pull torch/sentence-transformers/llama-cpp/huggingface-hub into sys.modules.
    Runs in a subprocess so sys.modules is clean and unaffected by the test runner."""
    script = textwrap.dedent(
        """
        import os, sys
        os.environ["EMBEDDING_PROVIDER"] = "api"
        os.environ["LABELING_PROVIDER"] = "api"
        os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
        import embedding.pipeline  # noqa: F401
        import labeling.llm        # noqa: F401
        forbidden = {"torch", "sentence_transformers", "llama_cpp", "huggingface_hub"}
        leaked = forbidden & set(sys.modules)
        assert not leaked, f"local ML libs imported in API mode: {sorted(leaked)}"
        print("OK")
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout
