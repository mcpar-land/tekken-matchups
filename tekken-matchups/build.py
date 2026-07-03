import polars as pl
from typing import Any
from jinja2 import Environment, PackageLoader, select_autoescape
import os.path

templ_env = Environment(
    loader=PackageLoader("tekken-matchups"),
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

COLOR_MIN = (0xFF, 0x00, 0x00)
COLOR_MAX = (0x00, 0xFF, 0x00)


def lerp(a: int | float, b: int | float, t: float) -> float:
    return (1 - t) * a + (t * b)


class MatchupCell:
    def __init__(
        self,
        c1: str,
        c2: str,
        matchup_diff: float,
        n_games: int,
        global_min_diff: float,
        global_max_diff: float,
    ):
        self.c1 = c1
        self.c2 = c2
        self.matchup_diff = matchup_diff
        self.n_games = n_games
        self.cell_body = f"{matchup_diff: >+4.1f}".replace(" ", "&nbsp;")

        if matchup_diff < 0.0:
            global_max_diff = 0.0
            color_min = (0xFF, 0x00, 0x00)
            color_max = (0xFF, 0xFF, 0xFF)
        else:
            global_min_diff = 0.0
            color_min = (0xFF, 0xFF, 0xFF)
            color_max = (0x00, 0xFF, 0x00)

        if matchup_diff == global_min_diff:
            diff_t = 0.0
        elif self.matchup_diff == global_max_diff:
            diff_t = 1.0
        else:
            diff_t = (self.matchup_diff - global_min_diff) / (
                global_max_diff - global_min_diff
            )
        r = round(lerp(color_min[0], color_max[0], diff_t))
        g = round(lerp(color_min[1], color_max[1], diff_t))
        b = round(lerp(color_min[2], color_max[2], diff_t))

        self.cell_color = "#{:02x}{:02x}{:02x}".format(r, g, b)


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

    matchup_diffs: dict[tuple[str, str], MatchupCell] = {}
    for chara_name, chara_name_opp, matchup_diff, n_games in df.iter_rows():
        matchup_diffs[(chara_name, chara_name_opp)] = MatchupCell(
            chara_name,
            chara_name_opp,
            matchup_diff,
            n_games,
            global_min_diff,
            global_max_diff,
        )

    chara_names: list[str] = [*df["chara_name"].unique().sort()]

    write_page(
        "chart.html.jinja",
        os.path.join("chart", str(significant_version) + ".html"),
        game_versions=game_versions,
        df_test=df,
        selected_game_version=significant_version,
        chara_names=chara_names,
        matchup_diffs=matchup_diffs,
    )
