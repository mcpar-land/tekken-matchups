[parallel]
dev: dev-webserver dev-build-html

dev-webserver:
    live-server ./output -p 5000
    
dev-build-html:
    watchexec -e .py -e .jinja -e .css -- just build

build:
    mkdir -p output
    uv run python -m tekken-matchups.build
    cp -r ./static/. ./output/

scrape:
    uv run python src/scrape_forward.py

aggregate:
    uv run python src/aggregate_matchups.py
