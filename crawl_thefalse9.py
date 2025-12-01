import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List, Optional, Set
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
DEFAULT_ARTICLE_LIMIT = 15
CORPUS_PATH = Path("thefalse9_corpus.json")
CONFIG_PATH = Path("config.json")


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


def _normalize_classes(value: Optional[Iterable[str] | str]) -> List[str]:
    if not value:
        return []
    if isinstance(value, str):
        return value.split()
    return [cls for cls in value if cls]


def _extract_text_from_node(node: BeautifulSoup) -> str:
    paragraphs = [
        p.get_text(" ", strip=True)
        for p in node.find_all("p")
    ]
    return "\n\n".join(p for p in paragraphs if p)


def extract_article_text(url: str, soup: BeautifulSoup) -> Article | None:
    title_tag = soup.find("h1")
    if not title_tag:
        og_title = soup.find("meta", attrs={"property": "og:title"})
        title = og_title["content"].strip() if og_title and og_title.get("content") else url
    else:
        title = title_tag.get_text(strip=True)

    candidate_selectors = [
        "[class*='entry-content']",
        "[class*='post-content']",
        "[class*='article-content']",
        "[class*='post-body']",
        "article",
    ]

    seen_nodes: Set[int] = set()
    best_text = ""

    keywords = ("entry", "post", "article")

    for selector in candidate_selectors:
        for node in soup.select(selector):
            identifier = id(node)
            if identifier in seen_nodes:
                continue
            seen_nodes.add(identifier)

            classes = _normalize_classes(node.get("class"))
            if selector == "article" and classes and not any(
                keyword in cls for cls in classes for keyword in keywords
            ):
                # Skip generic <article> wrappers that aren't actual content.
                continue

            text = _extract_text_from_node(node)
            if len(text) > len(best_text):
                best_text = text

    if not best_text.strip():
        return None

    return Article(title=title or url, url=url, text=best_text.strip())


def load_config() -> tuple[str, int]:
    crawllevel = "minimal"
    article_limit = DEFAULT_ARTICLE_LIMIT
    if CONFIG_PATH.exists():
        try:
            cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            level = str(cfg.get("crawllevel", "")).strip().lower()
            if level in {"minimal", "full"}:
                crawllevel = level

            limit_val = cfg.get("max_articles_per_run")
            if isinstance(limit_val, int) and limit_val > 0:
                article_limit = limit_val
        except Exception as exc:
            print(f"Warning: failed to parse {CONFIG_PATH}: {exc}")

    return crawllevel, article_limit


def load_existing_corpus(path: Path) -> List[Article]:
    if not path.exists():
        return []

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Warning: could not read existing corpus: {exc}")
        return []

    articles: List[Article] = []
    items = raw if isinstance(raw, list) else []
    for item in items:
        url = item.get("url")
        text = item.get("text")
        if not url or not text:
            continue
        title = item.get("title") or url
        articles.append(Article(title=title, url=url, text=text))
    return articles


def save_corpus(path: Path, articles: List[Article]) -> None:
    payload = [asdict(article) for article in articles]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def crawl(
    start_urls: List[str],
    restrict_prefix: Optional[str] = None,
    *,
    existing_urls: Optional[Set[str]] = None,
    max_new_articles: Optional[int] = None,
) -> List[Article]:
    to_visit: List[str] = list(start_urls)
    seen: Set[str] = set()
    articles: List[Article] = []
    known_articles = set(existing_urls or set())

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
            if article.url in known_articles:
                print(f"Skipping already indexed article: {article.url}")
            else:
                print(f"Captured article: {article.title!r}")
                articles.append(article)
                known_articles.add(article.url)
                if max_new_articles and len(articles) >= max_new_articles:
                    print(
                        f"Reached per-run article limit of {max_new_articles}. "
                        "Stopping crawl."
                    )
                    break

        # Collect more links to follow.
        for href in extract_article_links(soup):
            abs_url = urljoin(current_url, href)
            if abs_url not in seen and is_same_domain(abs_url):
                to_visit.append(abs_url)

        time.sleep(REQUEST_DELAY_SECONDS)

    return articles


def main() -> None:
    crawllevel, article_limit = load_config()

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

    existing_articles = load_existing_corpus(CORPUS_PATH)
    if existing_articles:
        print(f"Loaded {len(existing_articles)} existing articles from corpus.")

    print("Starting crawl of thefalse9.com")
    articles = crawl(
        start_urls,
        restrict_prefix=restrict_prefix,
        existing_urls={article.url for article in existing_articles},
        max_new_articles=article_limit,
    )
    print(f"Collected {len(articles)} new articles")

    if not articles:
        print("No new content found. Existing corpus and index remain unchanged.")
        return

    # Save raw corpus for inspection.
    combined_articles = existing_articles + articles
    save_corpus(CORPUS_PATH, combined_articles)
    print(f"Saved {len(combined_articles)} total articles to {CORPUS_PATH}")

    # Build the RAG index using your helper.
    corpus_for_index = [
        {"title": a.title, "url": a.url, "text": a.text} for a in articles
    ]
    print("Updating embedding index with new content (this may take a while)...")
    build_index_from_corpus(corpus_for_index)
    print("Index updated at app/thefalse9_index.json")


if __name__ == "__main__":
    main()
