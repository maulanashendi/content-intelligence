# Entry function: run() — embed all articles missing an article_embedding row.
# Batches of 32-64 records. CPU inference is acceptable at MVP scale.
# Writes article_embedding rows with model_name + model_version captured.
