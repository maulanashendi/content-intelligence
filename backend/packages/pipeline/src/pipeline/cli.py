# Click CLI for the daily orchestrator. Invoked by the host's cron / systemd timer.
#
#   python -m pipeline.cli run-daily   — full pipeline (ingest -> embed -> cluster -> label -> score)
#   python -m pipeline.cli ingest      — ingest module only
#   python -m pipeline.cli embed       — embedding module only
#   python -m pipeline.cli cluster     — clustering module only
#   python -m pipeline.cli label       — labeling module only
#   python -m pipeline.cli score       — scoring module only
#
# Each step delegates to the corresponding module's pipeline.run().
