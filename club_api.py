import os
import requests
from dotenv import load_dotenv
from typing import List, Optional
import pandas as pd
import time

load_dotenv()


class GeoGuessrClubAPI:
    BASE_URL = "https://www.geoguessr.com/api"

    def __init__(self, ncfa_token: Optional[str] = None):
        if not ncfa_token:
            ncfa_token = os.getenv("NCFA_TOKEN")
        if not ncfa_token:
            raise ValueError(
                "NCFA_TOKEN must be provided or set in environment variables")

        self.session = requests.Session()
        self.session.cookies.set(
            "_ncfa", ncfa_token, domain="www.geoguessr.com")
        self.session.headers.update({
            "User-Agent": "GeoStatsClub/1.0",
            "Accept": "application/json"
        })

    def _get(self, path: str, raise_on_error: bool = True) -> Optional[dict]:
        url = f"{self.BASE_URL}{path}"
        resp = self.session.get(url)
        if resp.status_code == 200:
            return resp.json()
        if raise_on_error:
            raise Exception(f"Failed to fetch {path}: HTTP {resp.status_code}")
        return None

    def get_profile(self) -> dict:
        return self._get("/v3/profiles")

    def get_club_members(self, club_id: str) -> List[dict]:
        return self._get(f"/v4/clubs/{club_id}/members")

    def get_user_stats(self, user_id: str) -> Optional[dict]:
        return self._get(f"/v4/stats/users/{user_id}", raise_on_error=False)

    def get_user_peak_rating(self, user_id: str) -> Optional[dict]:
        return self._get(f"/v4/ranked-system/peak-rating/{user_id}", raise_on_error=False)


class ClubMember:
    def __init__(self, data: dict):
        self.raw_membership = {k: v for k, v in data.items() if k != "user"}
        self.raw_user = data.get("user", {})
        self.user_id = self.raw_user.get("userId", "")
        self.stats: dict = {}
        self.peak_rating: dict = {}

    @property
    def nick(self) -> str:
        return self.raw_user.get("nick", "")

    def update_stats(self, stats: dict):
        self.stats = stats or {}

    def update_peak_rating(self, rating: dict):
        self.peak_rating = rating or {}

    def to_dict(self):
        base_user = self.flatten_dict(self.raw_user, parent_key="user")
        base_membership = self.flatten_dict(
            self.raw_membership, parent_key="membership")
        flat_stats = self.flatten_dict(self.stats, parent_key="stats")
        flat_rating = self.flatten_dict(
            self.peak_rating, parent_key="peakRating")

        return {**base_user, **base_membership, **flat_stats, **flat_rating}

    @staticmethod
    def flatten_dict(d: dict, parent_key: str = '', sep: str = '.') -> dict:
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(ClubMember.flatten_dict(
                    v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)


def export_members_to_csv(members: List[ClubMember], filename: str):
    df = pd.DataFrame([m.to_dict() for m in members])
    df.to_csv(filename, index=False)
    print(f"Exported {len(members)} members to {filename}")


if __name__ == "__main__":
    api = GeoGuessrClubAPI()

    profile = api.get_profile()
    CLUB_ID = profile.get("user", {}).get("club", {}).get("clubId")
    if not CLUB_ID:
        raise ValueError(
            "User is not in a club or clubId not found in profile.")

    members_json = api.get_club_members(CLUB_ID)
    members = [ClubMember(m) for m in members_json]

    print("Fetching user stats and ratings...")
    for i, member in enumerate(members, 1):
        stats = api.get_user_stats(member.user_id)
        member.update_stats(stats)

        rating = api.get_user_peak_rating(member.user_id)
        member.update_peak_rating(rating)

        print(f"[{i}/{len(members)}] Fetched stats for {member.nick}")
        time.sleep(0.2)

    export_members_to_csv(members, "club_members_with_all_stats.csv")
