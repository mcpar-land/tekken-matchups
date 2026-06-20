[parallel]
dev: dev-webserver dev-build-html

dev-webserver:
    live-server ./output -p 5000 --hard
    
dev-build-html:
    watchexec -e .py -e .jinja -- just build

build:
    mkdir -p output
    uv run python -m tekken-matchups.build

scrape:
    uv run python src/scrape_forward.py

aggregate:
    uv run python src/aggregate_matchups.py
