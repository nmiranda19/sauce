"""
Compares two teams' weekly totals across all 10 categories.
Returns a per-category result dict and a W-L-T summary for each team.
"""
from __future__ import annotations

# Categories where LOWER value wins
_LOWER_WINS = {"gaa"}

# The 10 scored categories in display order
CATEGORIES = [
    "goals",
    "assists",
    "plus_minus",
    "shots_on_goal",
    "defenseman_points",
    "special_teams_points",
    "average_toi",
    "goalie_wins",
    "gaa",
    "save_pct",
]

_MIN_GOALIES = 3  # teams must start at least this many goalies per week


def _determine_winner(category: str, home_val, away_val) -> str:
    """Return 'home', 'away', or 'tie'. None values always produce a 'tie'."""
    if home_val is None and away_val is None:
        return "tie"
    # If only one team has a value (e.g. goalie didn't play), that team wins
    if home_val is None:
        return "away"
    if away_val is None:
        return "home"

    lower_wins = category in _LOWER_WINS
    if lower_wins:
        if home_val < away_val:
            return "home"
        elif away_val < home_val:
            return "away"
        return "tie"
    else:
        if home_val > away_val:
            return "home"
        elif away_val > home_val:
            return "away"
        return "tie"


def score_categories(
    home_totals: dict,
    away_totals: dict,
) -> list[dict]:
    """
    Apply the 3-goalie minimum rule then compare all 10 categories.

    Returns a list of dicts (one per category):
      {category, home_value, away_value, winner}
    """
    home_started = home_totals.get("goalies_started", 0)
    away_started = away_totals.get("goalies_started", 0)
    home_goalie_penalty = home_started < _MIN_GOALIES
    away_goalie_penalty = away_started < _MIN_GOALIES

    results = []
    for cat in CATEGORIES:
        home_val = home_totals.get(cat)
        away_val = away_totals.get(cat)

        # Apply 3-goalie penalty: GAA and SV% become auto-losses
        if cat in ("gaa", "save_pct"):
            if home_goalie_penalty and away_goalie_penalty:
                winner = "tie"
            elif home_goalie_penalty:
                # Home loses both goalie rate categories
                winner = "away"
                home_val = None
            elif away_goalie_penalty:
                winner = "home"
                away_val = None
            else:
                winner = _determine_winner(cat, home_val, away_val)
        else:
            winner = _determine_winner(cat, home_val, away_val)

        results.append({
            "category": cat,
            "home_value": home_val,
            "away_value": away_val,
            "winner": winner,
        })

    return results


def tally_record(category_results: list[dict]) -> tuple[dict, dict]:
    """
    Given the 10-category results list, return (home_record, away_record).
    Each record is a dict: {wins, losses, ties}.
    """
    home = {"wins": 0, "losses": 0, "ties": 0}
    away = {"wins": 0, "losses": 0, "ties": 0}

    for r in category_results:
        w = r["winner"]
        if w == "home":
            home["wins"] += 1
            away["losses"] += 1
        elif w == "away":
            away["wins"] += 1
            home["losses"] += 1
        else:
            home["ties"] += 1
            away["ties"] += 1

    return home, away
