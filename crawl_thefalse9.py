import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Set
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app.rag import build_index_from_corpus


BASE_URL = "https://thefalse9.com"
BEGINNERS_CATEGORY_URL = (
    "https://thefalse9.com/category/football-tactics-for-beginners"
)

# Reasonable limits so you do not hammer the site.
MAX_PAGES = 200
REQUEST_DELAY_SECONDS = 2.0
TIMEOUT = 10


@dataclass
class Article:
    title: str
    url: str
    text: str


def is_same_domain(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc.endswith("thefalse9.com")


def get_soup(url: str) -> BeautifulSoup:
    resp = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "tactical-article-generator/0.1"})
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def extract_article_links(soup: BeautifulSoup) -> List[str]:
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Normalize relative links later via urljoin.
        links.add(href)
    return list(links)


def extract_article_text(url: str, soup: BeautifulSoup) -> Article | None:
    # Heuristic: many blogs wrap content in <article> or a div with "post" in the class.
    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else url

    article_container = soup.find("article")
    if article_container is None:
        # Fallback: look for a div whose class name contains "post" or "entry".
        article_container = soup.find(
            "div",
            class_=lambda c: c and ("post" in c or "entry" in c),
        )

    if article_container is None:
        return None

    paragraphs = [p.get_text(" ", strip=True) for p in article_container.find_all("p")]
    text = "\n\n".join(p for p in paragraphs if p)

    if not text:
        return None

    return Article(title=title, url=url, text=text)


def crawl(start_urls: List[str], restrict_prefix: Optional[str] = None) -> List[Article]:
    to_visit: List[str] = list(start_urls)
    seen: Set[str] = set()
    articles: List[Article] = []

    while to_visit and len(seen) < MAX_PAGES:
        current = to_visit.pop(0)
        if current in seen:
            continue
        seen.add(current)

        # Normalize URL to absolute
        current_url = urljoin(BASE_URL, current)
        if not is_same_domain(current_url):
            continue

        try:
            print(f"Fetching {current_url}")
            soup = get_soup(current_url)
        except Exception as exc:
            print(f"Failed to fetch {current_url}: {exc}")
            continue

        # Try to treat this page as an article.
        article = extract_article_text(current_url, soup)
        if article:
            print(f"Captured article: {article.title!r}")
            articles.append(article)

        # Collect more links to follow.
        for href in extract_article_links(soup):
            abs_url = urljoin(current_url, href)
            if abs_url not in seen and is_same_domain(abs_url):
                to_visit.append(abs_url)

        time.sleep(REQUEST_DELAY_SECONDS)

    return articles


def main() -> None:
    # Read crawl level from config.json (crawllevel: "minimal" or "full")
    config_path = Path("config.json")
    crawllevel = "minimal"
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            level = str(cfg.get("crawllevel", "")).strip().lower()
            if level in {"minimal", "full"}:
                crawllevel = level
        except Exception:
            # Fall back to default if config is malformed.
            pass

    if crawllevel == "minimal":
        # Start from the beginners category page but allow following article
        # links across the site (bounded by MAX_PAGES).
        start_urls = [BEGINNERS_CATEGORY_URL]
        restrict_prefix = None
        print(
            "Crawl level: minimal "
            f"(only {BEGINNERS_CATEGORY_URL} and its articles)"
        )
    else:
        # "full" crawl: entire site
        start_urls = [BASE_URL + "/"]
        restrict_prefix = None
        print("Crawl level: full (entire site)")

    print("Starting crawl of thefalse9.com")
    articles = crawl(start_urls, restrict_prefix=restrict_prefix)
    print(f"Collected {len(articles)} articles")

    # Save raw corpus for inspection.
    corpus_path = "thefalse9_corpus.json"
    corpus_data = [asdict(a) for a in articles]
    with open(corpus_path, "w", encoding="utf-8") as f:
        json.dump(corpus_data, f, ensure_ascii=False, indent=2)
    print(f"Saved raw corpus to {corpus_path}")

    # Build the RAG index using your helper.
    corpus_for_index = [
        {"title": a.title, "url": a.url, "text": a.text} for a in articles
    ]
    print("Building embedding index (this may take a while)...")
    build_index_from_corpus(corpus_for_index)
    print("Index written to app/thefalse9_index.json")


if __name__ == "__main__":
    main()
