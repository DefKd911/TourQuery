import re

import pandas as pd

RAW_DIR = "data/raw/tennis_atp/atp"
YEARS = [2023, 2024, 2025]

matches = pd.concat(
    [pd.read_csv(f"{RAW_DIR}/atp_matches_{year}.csv") for year in YEARS],
    ignore_index=True,
)

print(f"Loaded {len(matches)} matches across {YEARS}")
print(matches[["tourney_name", "winner_name", "loser_name", "score", "round"]].head())

player_ids = pd.unique(pd.concat([matches["winner_id"], matches["loser_id"]]))
print(f"\n{len(player_ids)} distinct players appear in these matches")

all_players = pd.read_csv(f"{RAW_DIR}/atp_players.csv")
players = all_players[all_players["player_id"].isin(player_ids)].copy()
print(f"Matched {len(players)} of them in atp_players.csv")
print(players.head())

matches["surface"] = matches.groupby("tourney_id")["surface"].transform(
    lambda s: s.ffill().bfill()
)
missing_surface = matches["surface"].isna().sum()
print(f"\nRows still missing surface after backfill: {missing_surface}")
matches = matches.dropna(subset=["surface"])

venue_lookup = matches[["tourney_name", "surface"]].drop_duplicates(subset="tourney_name")
print(f"{len(venue_lookup)} distinct venues (derived from tourney_name)")
print(venue_lookup.head())

tournaments = matches.drop_duplicates(subset="tourney_id")[
    ["tourney_id", "tourney_name", "tourney_date", "surface", "tourney_level"]
].copy()
tournaments["start_date"] = pd.to_datetime(tournaments["tourney_date"], format="%Y%m%d")
tournaments["year"] = tournaments["start_date"].dt.year

DURATION_DAYS = {"G": 13, "M": 8}
tournaments["duration"] = tournaments["tourney_level"].map(DURATION_DAYS).fillna(6)
tournaments["end_date"] = tournaments["start_date"] + pd.to_timedelta(
    tournaments["duration"], unit="D"
)

print(f"\n{len(tournaments)} distinct tournaments")
print(tournaments[["tourney_name", "year", "start_date", "end_date", "surface"]].head())

matches_mapped = matches[
    ["tourney_id", "winner_id", "loser_id", "round", "score"]
].rename(columns={"winner_id": "player1_id", "loser_id": "player2_id"})
matches_mapped["winner_id"] = matches["winner_id"]
matches_mapped = matches_mapped.merge(
    tournaments[["tourney_id", "start_date"]], on="tourney_id"
)
matches_mapped = matches_mapped.rename(columns={"start_date": "match_date"})

print(f"\n{len(matches_mapped)} matches mapped")
print(matches_mapped.head())

SET_SCORE_RE = re.compile(r"^(\d+)-(\d+)")

def parse_sets(score: str) -> list[tuple[int, int]]:
    if not isinstance(score, str):
        return []
    games = []
    for token in score.split():
        m = SET_SCORE_RE.match(token)
        if m:
            games.append((int(m.group(1)), int(m.group(2))))
    return games

matches_mapped["parsed_sets"] = matches_mapped["score"].apply(parse_sets)

sets_rows = []
for match_idx, row in matches_mapped.iterrows():
    for set_number, (p1_games, p2_games) in enumerate(row["parsed_sets"], start=1):
        sets_rows.append(
            {
                "match_idx": match_idx,
                "set_number": set_number,
                "player1_games": p1_games,
                "player2_games": p2_games,
            }
        )
sets_df = pd.DataFrame(sets_rows)
zero_zero = (sets_df["player1_games"] == 0) & (sets_df["player2_games"] == 0)
print(f"\nDropping {zero_zero.sum()} placeholder 0-0 sets (retirement markers)")
sets_df = sets_df[~zero_zero]

no_sets = (matches_mapped["parsed_sets"].str.len() == 0).sum()
print(f"\n{len(sets_df)} sets parsed from {len(matches_mapped)} matches")
print(f"{no_sets} matches had zero parseable sets (e.g. walkovers)")
print(sets_df.head())
