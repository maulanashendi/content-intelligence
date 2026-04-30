# Singleton LLM loader.
# Loads Gemma 2 2B (or successor model from core.config.LLM_MODEL_NAME) with 4-bit
# quantization via bitsandbytes. Loaded once per pipeline run, reused across all
# cluster labelings. RAM footprint ~1.5GB.
