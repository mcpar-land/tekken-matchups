import polars as pl
from typing import Any
from jinja2 import Environment, PackageLoader, select_autoescape
import os.path
from tekken_matchups.chart import MatchupCell, TotalGamesCell

templ_env = Environment(
    loader=PackageLoader("tekken_matchups"),
    autoescape=select_autoescape(),
)

df_versions = pl.read_csv(
    "game_versions.csv",
    schema={
        "game_version": pl.String,
        "version_name": pl.String,
        "release_date": pl.Date,
        "significant_balance_update": pl.Boolean,
        "significant_rank": pl.Int64,
        "patch_notes": pl.String,
    },
)

df_game_counts_by_version = pl.read_parquet(
    "./aggregate/game_counts_by_version.parquet"
)


df_matchups = pl.read_parquet("./aggregate/matchup_diffs.parquet").join(
    df_versions,
    left_on="significant_version",
    right_on="game_version",
    how="left",
)

game_versions: list[tuple[str, str]] = (
    df_versions.filter(pl.col("significant_balance_update"))
    .select("game_version", "version_name")
    .unique()
    .sort("game_version")
    .rows(named=False)
)


def write_page(template_name: str, output_path: str, **params: Any):
    final_path = os.path.join("./output", output_path)
    path_folder = os.path.dirname(final_path)
    print("making folder", path_folder)
    os.makedirs(path_folder, exist_ok=True)
    template = templ_env.get_template(template_name)
    with open(final_path, "w") as f:
        f.write(template.render(**params))
    print("wrote", final_path)


write_page(
    "index.html.jinja",
    "index.html",
    game_versions=game_versions,
    df_matchups=df_matchups,
    selected_game_verison=None,
)


for (significant_version, version_name), df in df_matchups.group_by(
    "significant_version", "version_name"
):
    df = df.select(
        "chara_name",
        "chara_name_opp",
        pl.col("matchup_diff").round(3),
        "n_games",
    )
    global_min_diff = df["matchup_diff"].min()
    global_max_diff = df["matchup_diff"].max()
    assert isinstance(global_min_diff, float)
    assert isinstance(global_max_diff, float)

    global_max_n_games = df["n_games"].max()
    assert isinstance(global_max_n_games, int)
    print("global max n games is", global_max_n_games)

    cells_matchups: dict[tuple[str, str], MatchupCell] = {}
    cells_totals: dict[tuple[str, str], TotalGamesCell] = {}
    for chara_name, chara_name_opp, matchup_diff, n_games in df.iter_rows():
        cells_matchups[(chara_name, chara_name_opp)] = MatchupCell(
            chara_name,
            chara_name_opp,
            matchup_diff,
            n_games,
            global_min_diff,
            global_max_diff,
        )
        cells_totals[(chara_name, chara_name_opp)] = TotalGamesCell(
            n_games,
            global_max_n_games,
        )

    chara_names: list[str] = [*df["chara_name"].unique().sort()]

    write_page(
        "chart.html.jinja",
        os.path.join("chart", str(significant_version) + ".html"),
        selected_game_version=significant_version,
        game_versions=game_versions,
        chara_names=chara_names,
        cells_matchups=cells_matchups,
        cells_totals=cells_totals,
    )
