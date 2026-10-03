#!/usr/bin/env python3
"""Pull the last year of public GitHub activity into data/stats.json.

Runs inside GitHub Actions with the workflow's GITHUB_TOKEN; build.py then
turns the JSON into assets/activity-*.svg.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.request
from pathlib import Path

QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    repositories(first: 100, after: $after, ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes { stargazerCount }
    }
  }
}
"""


def gql(token: str, variables: dict) -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "profile-assets"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.load(resp)
    if body.get("errors"):
        raise RuntimeError(body["errors"])
    return body["data"]["user"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--login", required=True)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "data" / "stats.json"))
    args = ap.parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is not set")

    user = gql(token, {"login": args.login, "after": None})
    cal = user["contributionsCollection"]["contributionCalendar"]
    days = [{"date": d["date"], "count": d["contributionCount"]}
            for w in cal["weeks"] for d in w["contributionDays"]]
    repos = user["repositories"]
    stars = sum(n["stargazerCount"] for n in repos["nodes"])
    while repos["pageInfo"]["hasNextPage"]:
        repos = gql(token, {"login": args.login, "after": repos["pageInfo"]["endCursor"]})["repositories"]
        stars += sum(n["stargazerCount"] for n in repos["nodes"])

    out = {
        "total": cal["totalContributions"],
        "repos": user["repositories"]["totalCount"],
        "stars": stars,
        "days": days,
        "updated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    Path(args.out).write_text(json.dumps(out, indent=1) + "\n")
    print(f"{out['total']} contributions, {out['repos']} repos, {stars} stars")


if __name__ == "__main__":
    main()
