serve:
    uv run python src/main.py

scrape:
    uv run python src/scrape_forward.py

aggregate:
    uv run python src/aggregate_matchups.py
