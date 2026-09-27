#!/usr/bin/env python3

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "articles.json"


def main():
    with INDEX_PATH.open(encoding="utf-8") as file:
        articles = json.load(file)

    if not isinstance(articles, list) or not articles:
        raise SystemExit("articles.json must contain a non-empty list")

    seen_urls = set()
    missing_files = []

    for article in articles:
        url = article.get("url")
        if not url or url in seen_urls:
            raise SystemExit(f"Missing or duplicate article URL: {url!r}")
        seen_urls.add(url)

        article_path = ROOT / url
        if not article_path.is_file() or article_path.stat().st_size == 0:
            missing_files.append(url)

    if missing_files:
        preview = ", ".join(missing_files[:5])
        raise SystemExit(f"Missing or empty article files: {preview}")

    project_file = ROOT / "iOS" / "NYTimesReader.xcodeproj" / "project.pbxproj"
    project_text = project_file.read_text(encoding="utf-8")
    required_project_markers = (
        "path = NYTimesReader/NYTimesReader;",
        "INFOPLIST_FILE = NYTimesReader/NYTimesReader/Info.plist;",
        "IPHONEOS_DEPLOYMENT_TARGET = 17.0;",
        "path = ../articles.json;",
        "path = ../articles;",
    )
    for marker in required_project_markers:
        if marker not in project_text:
            raise SystemExit(f"Xcode project is missing expected marker: {marker}")

    duplicate_indexes = (
        ROOT / "iOS" / "NYTimesReader" / "articles.json",
        ROOT / "iOS" / "NYTimesReader" / "NYTimesReader" / "articles.json",
    )
    for path in duplicate_indexes:
        if path.exists():
            raise SystemExit(f"Duplicate iOS article index must not exist: {path}")

    print(f"Validated {len(articles)} unique articles and their HTML files.")
    print("Validated canonical iOS project resources.")


if __name__ == "__main__":
    main()
