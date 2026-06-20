import polars as pl
import pathlib

# only use sufficiently high ranks
MIN_RANK = 25  # tekken king

df_chara_names = pl.read_csv("character_ids.csv")

lf = pl.scan_parquet("./scraped-data/*.parquet")

lf = lf.filter((pl.col("p1_rank") >= MIN_RANK) | (pl.col("p2_rank") >= MIN_RANK))

# first we get the global winrates
lf_wins = (
    lf.select(
        "winner",
        "p1_chara_id",
        "p2_chara_id",
        "game_version",
    )
    .select(
        "game_version",
        chara_id=pl.when(pl.col("winner") == 1)
        .then(pl.col("p1_chara_id"))
        .when(pl.col("winner") == 2)
        .then(pl.col("p2_chara_id")),
    )
    .group_by("chara_id", "game_version")
    .agg(pl.len().alias("n_wins"))
)

lf_losses = (
    lf.select(
        "winner",
        "p1_chara_id",
        "p2_chara_id",
        "game_version",
    )
    .select(
        "game_version",
        chara_id=pl.when(pl.col("winner") == 2)
        .then(pl.col("p1_chara_id"))
        .when(pl.col("winner") == 1)
        .then(pl.col("p2_chara_id")),
    )
    .group_by("chara_id", "game_version")
    .agg(pl.len().alias("n_losses"))
)

df_winrates = (
    lf_wins.join(lf_losses, on=["chara_id", "game_version"], validate="1:1")
    .join(df_chara_names.lazy(), on=["chara_id"], validate="m:1")
    .select(
        "chara_name",
        "game_version",
        winrate=pl.col("n_wins") / (pl.col("n_wins") + pl.col("n_losses")) * 100.0
        - 50.0,
    )
    .sort("game_version", "winrate", descending=True)
    .collect()
)


print("total winrates", df_winrates)

# now we find the per-character winrates
# and their diff from the average winrate
# which will give us a true spread

lf_mu_wins = (
    lf.select(
        "game_version",
        chara_id=pl.when(pl.col("winner") == 1)
        .then(pl.col("p1_chara_id"))
        .when(pl.col("winner") == 2)
        .then(pl.col("p2_chara_id")),
        opp_chara_id=pl.when(pl.col("winner") == 1)
        .then(pl.col("p2_chara_id"))
        .when(pl.col("winner") == 2)
        .then(pl.col("p1_chara_id")),
    )
    .group_by("game_version", "chara_id", "opp_chara_id")
    .agg(pl.len().alias("n_wins"))
)

lf_mu_losses = (
    lf.select(
        "game_version",
        chara_id=pl.when(pl.col("winner") == 1)
        .then(pl.col("p2_chara_id"))
        .when(pl.col("winner") == 2)
        .then(pl.col("p1_chara_id")),
        opp_chara_id=pl.when(pl.col("winner") == 1)
        .then(pl.col("p1_chara_id"))
        .when(pl.col("winner") == 2)
        .then(pl.col("p2_chara_id")),
    )
    .group_by("game_version", "chara_id", "opp_chara_id")
    .agg(pl.len().alias("n_losses"))
)

df_mu_winrates = (
    lf_mu_wins.join(
        lf_mu_losses, on=["game_version", "chara_id", "opp_chara_id"], validate="1:1"
    )
    .join(df_chara_names.lazy(), on="chara_id", validate="m:1")
    .join(
        df_chara_names.lazy(),
        left_on="opp_chara_id",
        right_on="chara_id",
        suffix="_opp",
        validate="m:1",
    )
    .select(
        "game_version",
        "chara_name",
        "chara_name_opp",
        winrate=pl.col("n_wins") / (pl.col("n_wins") + pl.col("n_losses")) * 100.0
        - 50.0,
    )
    .join(
        df_winrates.lazy(),
        left_on=["chara_name", "game_version"],
        right_on=["chara_name", "game_version"],
        suffix="_global",
    )
    .join(
        df_winrates.lazy(),
        left_on=["chara_name_opp", "game_version"],
        right_on=["chara_name", "game_version"],
        suffix="_global_opp",
    )
    .with_columns(
        matchup_diff=pl.col("winrate")
        + pl.col("winrate_global_opp")
        - pl.col("winrate_global")
    )
    .drop("winrate", "winrate_global", "winrate_global_opp")
    .sort("game_version", "chara_name", "chara_name_opp")
    .collect()
)

print("matchup winrates", df_mu_winrates)

pathlib.Path("output").mkdir(parents=True, exist_ok=True)
output_path = "aggregate/matchup_diffs.parquet"
print("writing to", output_path)
df_mu_winrates.write_parquet(output_path)
print("done")
