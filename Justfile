serve:
    uv run flask --app src/server.py run --debug

scrape:
    uv run python src/scrape_forward.py

aggregate:
    uv run python src/aggregate_matchups.py
