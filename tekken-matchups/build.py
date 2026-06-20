import polars as pl
from typing import Any
from jinja2 import Environment, PackageLoader, select_autoescape
import os.path

templ_env = Environment(
    loader=PackageLoader("tekken-matchups"),
    autoescape=select_autoescape(),
)

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


def write_page(template_name: str, output_path: str, **params: Any):
    final_path = os.path.join("./output", output_path)
    template = templ_env.get_template(template_name)
    with open(final_path, "w") as f:
        f.write(template.render(**params))
    print("wrote", final_path)


write_page("index.html.jinja", "index.html", game_versions=all_game_versions)
