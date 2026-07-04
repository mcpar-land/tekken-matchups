import polars as pl
import requests
import os
import logging
import time
import glob
from datetime import datetime

REPLAY_SCHEMA = {
    "battle_at": pl.Int64(),
    "battle_id": pl.String(),
    "battle_type": pl.UInt16(),
    "game_version": pl.Int64(),
    "stage_id": pl.UInt32(),
    "winner": pl.UInt16(),
    # p1
    "p1_area_id": pl.UInt16(),
    "p1_chara_id": pl.UInt16(),
    "p1_lang": pl.String(),
    "p1_name": pl.String(),
    "p1_polaris_id": pl.String(),
    "p1_power": pl.Int64(),
    "p1_rank": pl.Int64(),
    "p1_rating_before": pl.Int64(),
    "p1_rating_change": pl.Int64(),
    "p1_region_id": pl.UInt16(),
    "p1_rounds": pl.UInt16(),
    "p1_user_id": pl.Int64(),
    # p2
    "p2_area_id": pl.UInt16(),
    "p2_chara_id": pl.UInt16(),
    "p2_lang": pl.String(),
    "p2_name": pl.String(),
    "p2_polaris_id": pl.String(),
    "p2_power": pl.Int64(),
    "p2_rank": pl.Int64(),
    "p2_rating_before": pl.Int64(),
    "p2_rating_change": pl.Int64(),
    "p2_region_id": pl.UInt16(),
    "p2_rounds": pl.UInt16(),
    "p2_user_id": pl.Int64(),
}

PAGE_SIZE = 700


def fetch_loop(starting_time: int, data_dir: str):
    current_time: int | None = starting_time
    while current_time is not None:
        current_time = fetch_batch(current_time, data_dir)


def fetch_batch(starting_time: int, data_dir: str) -> int | None:
    min_rows = 1_000_000
    dfs: list[pl.LazyFrame] = []
    current_time = starting_time
    current_rows = 0
    while current_rows < min_rows:
        if current_time >= int(time.time()):
            logging.info("got to current time. stopping")
            return None
        req = requests.get(f"https://wank.wavu.wiki/api/replays?before={current_time}")
        df_page = pl.DataFrame(req.json(), schema=REPLAY_SCHEMA).with_columns(
            page=pl.lit(starting_time)
        )
        current_rows += len(df_page)
        current_time += PAGE_SIZE
        logging.info(
            "fetched batch of %s games starting at time %s",
            len(df_page),
            datetime.fromtimestamp(current_time),
        )
        if len(df_page) > 0:
            dfs.append(df_page.lazy())
        else:
            logging.info("this page had zero records")
    file_name = f"{data_dir}/{starting_time}_{current_time}.parquet"

    logging.info("writing to      %s", file_name)
    pl.concat(dfs).sink_parquet(file_name)
    logging.info("done writing to %s", file_name)
    return current_time + PAGE_SIZE


def get_current_latest_page(folder: str) -> int | None:
    if len(glob.glob(f"{folder}/*.parquet")) == 0:
        return None
    latest = (
        pl.scan_parquet(
            f"{folder}/*.parquet",
            cast_options=pl.ScanCastOptions(
                integer_cast="upcast",
            ),
        )
        .select(pl.col("page").max())
        .collect()
        .item()
    )
    assert isinstance(latest, int)
    return latest


START_DATE = "2024-03-27"
DATA_DIRECTORY = "./scraped-data"

if __name__ == "__main__":
    logging.basicConfig(
        encoding="utf-8",
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(message)s",
    )
    data_dir: str = DATA_DIRECTORY
    os.makedirs(data_dir, exist_ok=True)

    start_date = datetime.strptime(START_DATE, "%Y-%m-%d")

    current_latest_page = get_current_latest_page(data_dir)

    if current_latest_page is not None:
        logging.info(
            "RESUMING scraping starting at %s",
            datetime.fromtimestamp(current_latest_page),
        )
        start_at = current_latest_page + PAGE_SIZE
    else:
        logging.info("STARTING scraping from %s", start_date)
        start_at = int(start_date.timestamp()) - PAGE_SIZE

    logging.info("data directory is %s", data_dir)

    fetch_loop(start_at, data_dir)
