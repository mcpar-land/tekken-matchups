import polars as pl

df_chara_names = pl.read_csv("character_ids.csv")
df_ranks = pl.read_csv("ranks.csv")

ranks: list[int] = df_ranks["rank_id"].to_list()

lf_all_data = pl.scan_parquet("./scraped-data/*.parquet")


def mus_over_min_rank(lf: pl.LazyFrame, rank: int) -> pl.DataFrame:
    lf = lf.filter(pl.max_horizontal("p1_rank", "p2_rank") >= rank)

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

    df_winrates_global = (
        lf_wins.join(lf_losses, on=["chara_id", "game_version"], validate="1:1").select(
            "chara_id",
            "game_version",
            winrate=pl.col("n_wins") / (pl.col("n_wins") + pl.col("n_losses")) * 100.0
            - 50.0,
        )
    ).collect()

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
            chara_id_opp=pl.when(pl.col("winner") == 1)
            .then(pl.col("p2_chara_id"))
            .when(pl.col("winner") == 2)
            .then(pl.col("p1_chara_id")),
        )
        .group_by("game_version", "chara_id", "chara_id_opp")
        .agg(pl.len().alias("n_wins"))
    )

    lf_mu_losses = (
        lf.select(
            "game_version",
            chara_id=pl.when(pl.col("winner") == 1)
            .then(pl.col("p2_chara_id"))
            .when(pl.col("winner") == 2)
            .then(pl.col("p1_chara_id")),
            chara_id_opp=pl.when(pl.col("winner") == 1)
            .then(pl.col("p1_chara_id"))
            .when(pl.col("winner") == 2)
            .then(pl.col("p2_chara_id")),
        )
        .group_by("game_version", "chara_id", "chara_id_opp")
        .agg(pl.len().alias("n_losses"))
    )

    print("aggregating for rank", rank)
    df = (
        lf_mu_wins.join(
            lf_mu_losses,
            on=["game_version", "chara_id", "chara_id_opp"],
            validate="1:1",
        )
        .select(
            "game_version",
            "chara_id",
            "chara_id_opp",
            n_games=pl.col("n_wins") + pl.col("n_losses"),
            winrate=pl.col("n_wins") / (pl.col("n_wins") + pl.col("n_losses")) * 100.0
            - 50.0,
        )
        .join(
            df_winrates_global.lazy(),
            left_on=["chara_id", "game_version"],
            right_on=["chara_id", "game_version"],
            suffix="_global",
        )
        .join(
            df_winrates_global.lazy(),
            left_on=["chara_id_opp", "game_version"],
            right_on=["chara_id", "game_version"],
            suffix="_global_opp",
        )
        .with_columns(
            matchup_diff=pl.col("winrate")
            + pl.col("winrate_global_opp")
            - pl.col("winrate_global")
        )
        .drop("winrate", "winrate_global", "winrate_global_opp")
        .with_columns(min_rank=pl.lit(rank))
    ).collect()
    print("done aggregating for rank", rank)
    return df


output_path = "aggregate/matchup_diffs.parquet"
print("aggregating...")
df = (
    pl.concat([mus_over_min_rank(lf_all_data, r).lazy() for r in ranks])
    .sort(
        "min_rank",
        "game_version",
    )
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
print(df)
print("writing to", output_path)
df.write_parquet(output_path)
print("done")
