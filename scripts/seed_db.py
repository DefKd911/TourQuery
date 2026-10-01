"""Load real ATP data (2023-2025) and write it into the TourQuery schema."""

import re

import pandas as pd
import psycopg

from tourquery.config import settings

RAW_DIR = "data/raw/tennis_atp/atp"
YEARS = [2023, 2024, 2025]
SET_SCORE_RE = re.compile(r"^(\d+)-(\d+)")


def parse_sets(score) -> list[tuple[int, int]]:
    if not isinstance(score, str):
        return []
    games = []
    for token in score.split():
        m = SET_SCORE_RE.match(token)
        if m:
            games.append((int(m.group(1)), int(m.group(2))))
    return games


def load_and_transform():
    matches = pd.concat(
        [pd.read_csv(f"{RAW_DIR}/atp_matches_{year}.csv") for year in YEARS],
        ignore_index=True,
    )

    player_ids = pd.unique(pd.concat([matches["winner_id"], matches["loser_id"]]))
    all_players = pd.read_csv(f"{RAW_DIR}/atp_players.csv")
    players = all_players[all_players["player_id"].isin(player_ids)].copy()

    matches["surface"] = matches.groupby("tourney_id")["surface"].transform(
        lambda s: s.ffill().bfill()
    )
    matches = matches.dropna(subset=["surface"])

    venue_lookup = matches[["tourney_name", "surface"]].drop_duplicates(subset="tourney_name").reset_index(drop=True)
    venue_lookup["venue_id"] = venue_lookup.index + 1
    venue_id_by_name = dict(zip(venue_lookup["tourney_name"], venue_lookup["venue_id"]))

    tournaments = matches.drop_duplicates(subset="tourney_id")[
        ["tourney_id", "tourney_name", "tourney_date", "surface", "tourney_level"]
    ].reset_index(drop=True)
    tournaments["tournament_id"] = tournaments.index + 1
    tournament_id_by_tourney_id = dict(zip(tournaments["tourney_id"], tournaments["tournament_id"]))
    tournaments["start_date"] = pd.to_datetime(tournaments["tourney_date"], format="%Y%m%d")
    tournaments["year"] = tournaments["start_date"].dt.year
    duration_days = {"G": 13, "M": 8}
    tournaments["duration"] = tournaments["tourney_level"].map(duration_days).fillna(6)
    tournaments["end_date"] = tournaments["start_date"] + pd.to_timedelta(
        tournaments["duration"], unit="D"
    )
    tournaments["venue_id"] = tournaments["tourney_name"].map(venue_id_by_name)

    matches_mapped = matches[
        ["tourney_id", "winner_id", "loser_id", "round", "score"]
    ].rename(columns={"winner_id": "player1_id", "loser_id": "player2_id"})
    matches_mapped["winner_id"] = matches["winner_id"]
    matches_mapped = matches_mapped.merge(
        tournaments[["tourney_id", "start_date", "tournament_id"]], on="tourney_id"
    )
    matches_mapped = matches_mapped.rename(columns={"start_date": "match_date"})
    matches_mapped = matches_mapped.reset_index(drop=True)
    matches_mapped["match_id"] = matches_mapped.index + 1

    matches_mapped["parsed_sets"] = matches_mapped["score"].apply(parse_sets)
    sets_rows = []
    for _, row in matches_mapped.iterrows():
        for set_number, (p1_games, p2_games) in enumerate(row["parsed_sets"], start=1):
            sets_rows.append(
                {
                    "match_id": row["match_id"],
                    "set_number": set_number,
                    "player1_games": p1_games,
                    "player2_games": p2_games,
                }
            )
    sets_df = pd.DataFrame(sets_rows)
    zero_zero = (sets_df["player1_games"] == 0) & (sets_df["player2_games"] == 0)
    sets_df = sets_df[~zero_zero].reset_index(drop=True)
    sets_df["set_id"] = sets_df.index + 1

    rankings = pd.read_csv(f"{RAW_DIR}/atp_rankings_20s.csv")
    rankings["ranking_date"] = pd.to_datetime(rankings["ranking_date"], format="%Y%m%d")
    rankings = rankings[
        (rankings["ranking_date"] >= "2023-01-01")
        & (rankings["ranking_date"] <= "2025-12-31")
        & (rankings["player"].isin(player_ids))
    ]

    return players, venue_lookup, tournaments, matches_mapped, sets_df, rankings


HAND_TO_PLAYS = {"R": "right", "L": "left"}


def insert_players(cur, players: pd.DataFrame):
    rows = []
    for _, row in players.iterrows():
        dob = None
        if pd.notna(row["dob"]):
            dob = pd.to_datetime(str(int(row["dob"])), format="%Y%m%d").date()
        rows.append(
            (
                int(row["player_id"]),
                row["name_first"],
                row["name_last"],
                row["ioc"],
                dob,
                HAND_TO_PLAYS.get(row["hand"]),
            )
        )
    cur.executemany(
        """
        INSERT INTO players (player_id, first_name, last_name, nationality, date_of_birth, plays)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (player_id) DO NOTHING
        """,
        rows,
    )
    print(f"Inserted {len(rows)} players")


def insert_venues(cur, venue_lookup: pd.DataFrame):
    rows = [
        (int(row["venue_id"]), row["tourney_name"], row["tourney_name"], "Unknown", row["surface"].lower())
        for _, row in venue_lookup.iterrows()
    ]
    cur.executemany(
        """
        INSERT INTO venues (venue_id, name, city, country, surface)
        VALUES (%s, %s, %s, %s, %s)
        """,
        rows,
    )
    print(f"Inserted {len(rows)} venues")


def insert_tournaments(cur, tournaments: pd.DataFrame):
    rows = [
        (
            int(row["tournament_id"]),
            row["tourney_name"],
            int(row["year"]),
            int(row["venue_id"]),
            row["surface"].lower(),
            row["start_date"].date(),
            row["end_date"].date(),
        )
        for _, row in tournaments.iterrows()
    ]
    cur.executemany(
        """
        INSERT INTO tournaments (tournament_id, name, year, venue_id, surface, start_date, end_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        rows,
    )
    print(f"Inserted {len(rows)} tournaments")


def insert_matches(cur, matches_mapped: pd.DataFrame):
    rows = [
        (
            int(row["match_id"]),
            int(row["tournament_id"]),
            int(row["player1_id"]),
            int(row["player2_id"]),
            int(row["winner_id"]),
            row["match_date"].date(),
            row["round"],
        )
        for _, row in matches_mapped.iterrows()
    ]
    cur.executemany(
        """
        INSERT INTO matches (match_id, tournament_id, player1_id, player2_id, winner_id, match_date, round)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        rows,
    )
    print(f"Inserted {len(rows)} matches")


def insert_sets(cur, sets_df: pd.DataFrame):
    rows = [
        (
            int(row["set_id"]),
            int(row["match_id"]),
            int(row["set_number"]),
            int(row["player1_games"]),
            int(row["player2_games"]),
        )
        for _, row in sets_df.iterrows()
    ]
    cur.executemany(
        """
        INSERT INTO sets (set_id, match_id, set_number, player1_games, player2_games)
        VALUES (%s, %s, %s, %s, %s)
        """,
        rows,
    )
    print(f"Inserted {len(rows)} sets")


def insert_rankings(cur, rankings: pd.DataFrame):
    rows = [
        (
            int(row["player"]),
            row["ranking_date"].date(),
            int(row["rank"]),
            int(row["points"]) if pd.notna(row["points"]) else None,
        )
        for _, row in rankings.iterrows()
    ]
    cur.executemany(
        """
        INSERT INTO rankings_history (player_id, ranking_date, rank, points)
        VALUES (%s, %s, %s, %s)
        """,
        rows,
    )
    print(f"Inserted {len(rows)} ranking snapshots")


def fix_sequences(cur):
    for table, id_col in [
        ("venues", "venue_id"),
        ("tournaments", "tournament_id"),
        ("matches", "match_id"),
        ("sets", "set_id"),
    ]:
        cur.execute(
            f"SELECT setval(pg_get_serial_sequence('{table}', '{id_col}'), COALESCE(MAX({id_col}), 1)) FROM {table}"
        )


def main():
    players, venue_lookup, tournaments, matches_mapped, sets_df, rankings = load_and_transform()

    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            insert_players(cur, players)
            insert_venues(cur, venue_lookup)
            insert_tournaments(cur, tournaments)
            insert_matches(cur, matches_mapped)
            insert_sets(cur, sets_df)
            insert_rankings(cur, rankings)
            fix_sequences(cur)
        conn.commit()
    print("\nDone.")


if __name__ == "__main__":
    main()
