[parallel]
dev: dev-webserver dev-build-html

dev-webserver:
    live-server ./output -p 5000
    
dev-build-html:
    watchexec -e .py -e .jinja -e .css -e .csv -i "output/**" -- just build

build:
    mkdir -p output
    uv run python -m tekken_matchups.build
    cp -r ./static/. ./output/
clear_build:
    rm -rf output/*

scrape:
    uv run python -m tekken_matchups.scrape_forward

aggregate:
    uv run python -m tekken_matchups.aggregate_matchups
