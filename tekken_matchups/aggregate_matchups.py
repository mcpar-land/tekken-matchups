import polars as pl

df_game_versions = pl.read_csv(
    "game_versions.csv",
    schema={
        "game_version": pl.Int64,
        "version_name": pl.String,
        "release_date": pl.Date,
        "significant_balance_update": pl.Boolean,
        "significant_rank": pl.Int64,
        "patch_notes": pl.String,
    },
).with_columns(
    pl.col("patch_notes").replace(pl.lit(""), pl.lit(None)),
    significant_version=pl.when(pl.col("significant_balance_update"))
    .then(pl.col("game_version"))
    .otherwise(pl.lit(None))
    .cast(pl.String)
    .forward_fill(),
)

with pl.Config(tbl_cols=100, tbl_rows=100):
    print(df_game_versions)

df_chara_names = pl.read_csv("character_ids.csv")
df_ranks = pl.read_csv("ranks.csv")

ranks: list[int] = df_ranks["rank_id"].to_list()

lf_all_data = pl.scan_parquet("./scraped-data/*.parquet")

lf = (
    lf_all_data.join(
        df_game_versions.lazy().select(
            "game_version", "significant_version", "significant_rank"
        ),
        "game_version",
        how="left",
    )
    .filter(pl.max_horizontal("p1_rank", "p2_rank") >= pl.col("significant_rank"))
    .drop("game_version", "significant_rank")
)

print("aggregating weekly buckets of games played...")
df_weekly_games_played = (
    lf_all_data.select(battle_at=pl.from_epoch("battle_at", time_unit="s"))
    .select(year=pl.col("battle_at").dt.year(), week=pl.col("battle_at").dt.week())
    .group_by("year", "week")
    .agg(pl.len().alias("n_games"))
    .sort("year", "week")
    .collect()
)

print(df_weekly_games_played)

output_path = "aggregate/weekly_games_played.parquet"
print("saving to", output_path)
df_weekly_games_played.write_parquet(output_path)
print("done")

print("aggregating games played per game version...")
df_game_counts_by_version = (
    lf.group_by("significant_version").agg(n_games_for_version=pl.len()).collect()
)
print(df_game_counts_by_version)
df_game_counts_by_version.write_parquet("./aggregate/game_counts_by_version.parquet")

# ============== aggregate across ALL game versions

# first we get the global winrates
lf_wins = (
    lf.select("winner", "p1_chara_id", "p2_chara_id")
    .select(
        chara_id=pl.when(pl.col("winner") == 1)
        .then(pl.col("p1_chara_id"))
        .when(pl.col("winner") == 2)
        .then(pl.col("p2_chara_id")),
    )
    .group_by("chara_id")
    .agg(pl.len().alias("n_wins"))
)

lf_losses = (
    lf.select(
        "winner",
        "p1_chara_id",
        "p2_chara_id",
    )
    .select(
        chara_id=pl.when(pl.col("winner") == 2)
        .then(pl.col("p1_chara_id"))
        .when(pl.col("winner") == 1)
        .then(pl.col("p2_chara_id")),
    )
    .group_by("chara_id")
    .agg(pl.len().alias("n_losses"))
)

print("aggregating global winrates...")

df_winrates_global = (
    lf_wins.join(lf_losses, on=["chara_id"], validate="1:1").select(
        "chara_id",
        winrate=pl.col("n_wins") / (pl.col("n_wins") + pl.col("n_losses")) * 100.0
        - 50.0,
    )
).collect()

print(df_winrates_global)

# now we find the per-character winrates
# and their diff from the average winrate
# which will give us a true spread

lf_mu_wins = (
    lf.select(
        chara_id=pl.when(pl.col("winner") == 1)
        .then(pl.col("p1_chara_id"))
        .when(pl.col("winner") == 2)
        .then(pl.col("p2_chara_id")),
        chara_id_opp=pl.when(pl.col("winner") == 1)
        .then(pl.col("p2_chara_id"))
        .when(pl.col("winner") == 2)
        .then(pl.col("p1_chara_id")),
    )
    .group_by("chara_id", "chara_id_opp")
    .agg(pl.len().alias("n_wins"))
)

lf_mu_losses = (
    lf.select(
        chara_id=pl.when(pl.col("winner") == 1)
        .then(pl.col("p2_chara_id"))
        .when(pl.col("winner") == 2)
        .then(pl.col("p1_chara_id")),
        chara_id_opp=pl.when(pl.col("winner") == 1)
        .then(pl.col("p1_chara_id"))
        .when(pl.col("winner") == 2)
        .then(pl.col("p2_chara_id")),
    )
    .group_by("chara_id", "chara_id_opp")
    .agg(pl.len().alias("n_losses"))
)

print("aggregating matchup winrates...")
df_result_global = (
    lf_mu_wins.join(
        lf_mu_losses,
        on=["chara_id", "chara_id_opp"],
        validate="1:1",
    )
    .select(
        "chara_id",
        "chara_id_opp",
        n_games=pl.col("n_wins") + pl.col("n_losses"),
        winrate=pl.col("n_wins") / (pl.col("n_wins") + pl.col("n_losses")) * 100.0
        - 50.0,
    )
    .join(
        df_winrates_global.lazy(),
        left_on=["chara_id"],
        right_on=["chara_id"],
        suffix="_global",
    )
    .join(
        df_winrates_global.lazy(),
        left_on=["chara_id_opp"],
        right_on=["chara_id"],
        suffix="_global_opp",
    )
    .with_columns(
        matchup_diff=pl.col("winrate")
        + pl.col("winrate_global_opp")
        - pl.col("winrate_global")
    )
    .drop("winrate", "winrate_global", "winrate_global_opp")
    .join(
        df_chara_names.lazy(),
        on="chara_id",
    )
    .join(
        df_chara_names.lazy(),
        left_on="chara_id_opp",
        right_on="chara_id",
        suffix="_opp",
    )
    .collect()
)

print(df_result_global)

# ============== aggregate across specific game versions

# first we get the global winrates
lf_wins = (
    lf.select(
        "winner",
        "p1_chara_id",
        "p2_chara_id",
        "significant_version",
    )
    .select(
        "significant_version",
        chara_id=pl.when(pl.col("winner") == 1)
        .then(pl.col("p1_chara_id"))
        .when(pl.col("winner") == 2)
        .then(pl.col("p2_chara_id")),
    )
    .group_by("chara_id", "significant_version")
    .agg(pl.len().alias("n_wins"))
)

lf_losses = (
    lf.select(
        "winner",
        "p1_chara_id",
        "p2_chara_id",
        "significant_version",
    )
    .select(
        "significant_version",
        chara_id=pl.when(pl.col("winner") == 2)
        .then(pl.col("p1_chara_id"))
        .when(pl.col("winner") == 1)
        .then(pl.col("p2_chara_id")),
    )
    .group_by("chara_id", "significant_version")
    .agg(pl.len().alias("n_losses"))
)

print("aggregating global winrates...")
df_winrates_global = (
    lf_wins.join(
        lf_losses, on=["chara_id", "significant_version"], validate="1:1"
    ).select(
        "chara_id",
        "significant_version",
        winrate=pl.col("n_wins") / (pl.col("n_wins") + pl.col("n_losses")) * 100.0
        - 50.0,
    )
).collect()

print(df_winrates_global)

# now we find the per-character winrates
# and their diff from the average winrate
# which will give us a true spread

lf_mu_wins = (
    lf.select(
        "significant_version",
        chara_id=pl.when(pl.col("winner") == 1)
        .then(pl.col("p1_chara_id"))
        .when(pl.col("winner") == 2)
        .then(pl.col("p2_chara_id")),
        chara_id_opp=pl.when(pl.col("winner") == 1)
        .then(pl.col("p2_chara_id"))
        .when(pl.col("winner") == 2)
        .then(pl.col("p1_chara_id")),
    )
    .group_by("significant_version", "chara_id", "chara_id_opp")
    .agg(pl.len().alias("n_wins"))
)

lf_mu_losses = (
    lf.select(
        "significant_version",
        chara_id=pl.when(pl.col("winner") == 1)
        .then(pl.col("p2_chara_id"))
        .when(pl.col("winner") == 2)
        .then(pl.col("p1_chara_id")),
        chara_id_opp=pl.when(pl.col("winner") == 1)
        .then(pl.col("p1_chara_id"))
        .when(pl.col("winner") == 2)
        .then(pl.col("p2_chara_id")),
    )
    .group_by("significant_version", "chara_id", "chara_id_opp")
    .agg(pl.len().alias("n_losses"))
)

print("aggregating matchup winrates...")
df_result_by_version = (
    lf_mu_wins.join(
        lf_mu_losses,
        on=["significant_version", "chara_id", "chara_id_opp"],
        validate="1:1",
    )
    .select(
        "significant_version",
        "chara_id",
        "chara_id_opp",
        n_games=pl.col("n_wins") + pl.col("n_losses"),
        winrate=pl.col("n_wins") / (pl.col("n_wins") + pl.col("n_losses")) * 100.0
        - 50.0,
    )
    .join(
        df_winrates_global.lazy(),
        left_on=["chara_id", "significant_version"],
        right_on=["chara_id", "significant_version"],
        suffix="_global",
    )
    .join(
        df_winrates_global.lazy(),
        left_on=["chara_id_opp", "significant_version"],
        right_on=["chara_id", "significant_version"],
        suffix="_global_opp",
    )
    .with_columns(
        matchup_diff=pl.col("winrate")
        + pl.col("winrate_global_opp")
        - pl.col("winrate_global")
    )
    .drop("winrate", "winrate_global", "winrate_global_opp")
    .sort("significant_version")
    .join(
        df_chara_names.lazy(),
        on="chara_id",
    )
    .join(
        df_chara_names.lazy(),
        left_on="chara_id_opp",
        right_on="chara_id",
        suffix="_opp",
    )
    .collect()
)

print(df_result_by_version)

df = pl.concat([df_result_global, df_result_by_version], how="diagonal")

print(df)

output_path = "aggregate/matchup_diffs.parquet"
print("writing to", output_path)
df.write_parquet(output_path)
print("done")
