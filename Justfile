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
clear_build:
    rm -rf output/*

scrape:
    uv run python -m tekken-matchups.scrape_forward

aggregate:
    uv run python -m tekken-matchups.aggregate_matchups
