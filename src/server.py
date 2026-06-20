from flask import Flask, render_template
import polars as pl

app = Flask(__name__)

df_matchups = pl.read_parquet("./aggregate/matchup_diffs.parquet")

all_game_versions: list[str] = (
    df_matchups.lazy()
    .select("game_version")
    .unique()
    .sort("game_version")
    .select(
        pl.col("game_version")
        .cast(pl.String)
        .str.replace(r"(\d)(\d{2})(\d{2})", "$1.$2.$3")
    )
    .collect()["game_version"]
    .to_list()
)


@app.route("/")
def hello_world():
    return render_template("index.html.jinja", game_versions=all_game_versions)
