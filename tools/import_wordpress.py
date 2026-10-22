#!/usr/bin/env python3
"""Import posts from the WordPress.com blog and build the static site in public/.

Usage:
    python3 tools/import_wordpress.py

Re-running regenerates every page under public/ (except public/assets/), so
make layout changes in templates/layout.html rather than in generated files.
"""

import datetime
import html
import json
import re
import shutil
import urllib.parse
import urllib.request
from email.utils import format_datetime
from pathlib import Path
from string import Template

WP_SITE = "torinblair.wordpress.com"
SITE_URL = "https://torinblair-sitepages.pages.dev"  # change to your custom domain
SITE_NAME = "Torin Blair"

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public"
LAYOUT = Template((ROOT / "templates" / "layout.html").read_text(encoding="utf-8"))

API = "https://public-api.wordpress.com/rest/v1.1/sites/" + WP_SITE


def fetch_json(path, **params):
    url = API + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "sitepages-import/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def fetch_posts():
    posts, page = [], 1
    fields = "ID,title,date,modified,slug,URL,content,excerpt,categories,tags"
    while True:
        data = fetch_json("/posts", number=100, page=page, fields=fields, order_by="date")
        posts.extend(data["posts"])
        if len(posts) >= data["found"] or not data["posts"]:
            return posts
        page += 1


def clean_content(raw):
    """Strip WordPress block markup down to plain semantic HTML."""
    out = re.sub(r'\s*class="wp-block-[a-z-]+"', "", raw)
    out = re.sub(r"<p>\s*<br\s*/?>", "<p>", out)
    out = re.sub(r"<p>(\s|&nbsp;)*</p>", "", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def plain_text(fragment):
    text = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def summarize(text, limit=220):
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",.;:") + "…"


def esc(value):
    return html.escape(value, quote=True)


def slugify(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


# Blog sections, each a folder under /blog/. A post goes in the first section whose
# categories it matches; the last section (no categories) catches everything else.
SECTIONS = [
    {"slug": "ai", "name": "AI", "categories": {"artificial-intelligence-security"},
     "intro": "Writing on AI security, agentic systems and AI-assisted engineering."},
    {"slug": "secure-development", "name": "Secure Development", "categories": None,
     "intro": "Writing on secure engineering, secrets handling and cryptography."},
]


def section_for(categories):
    slugs = {c["slug"] for c in categories}
    return next(s for s in SECTIONS if s["categories"] is None or slugs & s["categories"])


def to_post(raw):
    content = clean_content(raw["content"])
    text = plain_text(content)
    date = datetime.datetime.fromisoformat(raw["date"])
    categories = sorted(
        ({"name": html.unescape(c["name"]), "slug": c["slug"]} for c in raw["categories"].values()),
        key=lambda c: c["name"],
    )
    section = section_for(categories)
    return {
        "slug": raw["slug"],
        "section": section,
        "url": f"/blog/{section['slug']}/{raw['slug']}",
        "title": html.unescape(raw["title"]).strip(),
        "date": date,
        "old_path": urllib.parse.urlparse(raw["URL"]).path,
        "content": content,
        "summary": summarize(plain_text(raw["excerpt"]) or text),
        "minutes": max(1, round(len(text.split()) / 200)),
        "categories": categories,
    }


def render(path, title, description, content, nav=""):
    # Cloudflare Pages serves foo.html at /foo and dir/index.html at /dir/.
    url_path = "/" + re.sub(r"(index)?\.html$", "", path)
    page = LAYOUT.substitute(
        title=esc(title),
        description=esc(description),
        canonical=SITE_URL + url_path,
        site_name=SITE_NAME,
        site_tagline=esc(TAGLINE),
        year=datetime.date.today().year,
        nav_home=" active" if nav == "home" else "",
        nav_blog=" active" if nav == "blog" else "",
        content=content,
    )
    target = OUT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page, encoding="utf-8")


def category_badges(post):
    return " ".join(f'<span class="tag">{esc(c["name"])}</span>' for c in post["categories"])


def post_meta(post):
    return (
        f'<time datetime="{post["date"].date().isoformat()}">{post["date"]:%B %-d, %Y}</time>'
        f' &middot; {post["minutes"]} min read'
    )


def post_card(post):
    return f"""
      <div class="col">
        <article class="card h-100 post-card">
          <div class="card-body d-flex flex-column">
            <p class="small text-body-secondary mb-2">{post_meta(post)}</p>
            <h2 class="h5 card-title">
              <a class="stretched-link" href="{post["url"]}">{esc(post["title"])}</a>
            </h2>
            <p class="card-text text-body-secondary mb-0">{esc(post["summary"])}</p>
          </div>
        </article>
      </div>"""


def post_grid(posts):
    return '<div class="post-list">' + "".join(post_card(p) for p in posts) + "\n      </div>"


def build_home(posts):
    content = f"""
      <section class="hero mb-5">
        <h1 class="display-title mb-4">The jaws of software design risk</h1>
        <p class="lead text-body-secondary">{esc(TAGLINE)}</p>
        <a class="link-arrow" href="/blog/">Read the blog</a>
      </section>
      <section>
        <h2 class="h4 mb-4">Recent posts</h2>
        {post_grid(posts[:4])}
      </section>"""
    render("index.html", SITE_NAME, TAGLINE, content, nav="home")


def build_blog_index(posts):
    filters = " ".join(f'<a class="tag" href="/blog/{s["slug"]}/">{esc(s["name"])}</a>' for s in SECTIONS)
    content = f"""
      <header class="mb-4">
        <h1 class="page-title">Blog</h1>
        <p class="text-body-secondary">Writing on AI security, secure development and cryptography.</p>
        <div class="d-flex flex-wrap gap-2">{filters}</div>
      </header>
      {post_grid(posts)}"""
    render("blog/index.html", f"Blog | {SITE_NAME}", "All posts.", content, nav="blog")


def build_section_pages(posts):
    for section in SECTIONS:
        matches = [p for p in posts if p["section"] is section]
        name = section["name"]
        content = f"""
      <nav aria-label="breadcrumb">
        <ol class="breadcrumb">
          <li class="breadcrumb-item"><a href="/blog/">Blog</a></li>
          <li class="breadcrumb-item active" aria-current="page">{esc(name)}</li>
        </ol>
      </nav>
      <header class="mb-4">
        <h1 class="page-title">{esc(name)}</h1>
        <p class="text-body-secondary">{esc(section["intro"])}</p>
      </header>
      {post_grid(matches)}"""
        render(f"blog/{section['slug']}/index.html", f"{name} | {SITE_NAME}", section["intro"], content, nav="blog")


def build_post(post, newer, older):
    pager = ""
    if newer or older:
        prev_link = (
            f'<a class="pager-link" href="{older["url"]}">&larr; {esc(older["title"])}</a>'
            if older else "<span></span>"
        )
        next_link = (
            f'<a class="pager-link" href="{newer["url"]}">{esc(newer["title"])} &rarr;</a>'
            if newer else "<span></span>"
        )
        pager = f'<nav class="d-flex flex-column flex-md-row justify-content-between gap-3 mt-5 pt-4 border-top">{prev_link}{next_link}</nav>'
    content = f"""
      <article class="mx-auto post-body">
        <nav aria-label="breadcrumb">
          <ol class="breadcrumb">
            <li class="breadcrumb-item"><a href="/blog/">Blog</a></li>
            <li class="breadcrumb-item"><a href="/blog/{post["section"]["slug"]}/">{esc(post["section"]["name"])}</a></li>
            <li class="breadcrumb-item active" aria-current="page">Post</li>
          </ol>
        </nav>
        <header class="mb-4">
          <h1 class="page-title">{esc(post["title"])}</h1>
          <p class="text-body-secondary mb-2">{post_meta(post)}</p>
          <div class="d-flex flex-wrap gap-1">{category_badges(post)}</div>
        </header>
{post["content"]}
        {pager}
      </article>"""
    render(post["url"].lstrip("/") + ".html", f"{post['title']} | {SITE_NAME}", post["summary"], content, nav="blog")


def build_404():
    content = """
      <div class="text-center py-5">
        <h1 class="display-4 fw-bold">Page not found</h1>
        <p class="lead text-body-secondary">That page doesn't exist or has moved.</p>
        <a class="link-arrow" href="/blog/">Go to the blog</a>
      </div>"""
    render("404.html", f"Not found | {SITE_NAME}", "Page not found.", content)


def build_feed(posts):
    items = "".join(
        f"""
    <item>
      <title>{esc(p["title"])}</title>
      <link>{SITE_URL}{p["url"]}</link>
      <guid>{SITE_URL}{p["url"]}</guid>
      <pubDate>{format_datetime(p["date"])}</pubDate>
      <description>{esc(p["summary"])}</description>
    </item>"""
        for p in posts
    )
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{esc(SITE_NAME)}</title>
    <link>{SITE_URL}/</link>
    <description>{esc(TAGLINE)}</description>{items}
  </channel>
</rss>
"""
    (OUT / "feed.xml").write_text(feed, encoding="utf-8")


def build_redirects(posts):
    # Cloudflare Pages: map old WordPress permalinks to the new blog URLs.
    lines = [f'{p["old_path"]} {p["url"]} 301' for p in posts]
    (OUT / "_redirects").write_text("\n".join(lines) + "\n", encoding="utf-8")


def clean_output():
    for child in OUT.iterdir():
        if child.name == "assets":
            continue
        shutil.rmtree(child) if child.is_dir() else child.unlink()


def main():
    global TAGLINE
    site = fetch_json("", fields="description")
    TAGLINE = re.sub(r"\s+", " ", html.unescape(site["description"])).strip()

    posts = sorted((to_post(p) for p in fetch_posts()), key=lambda p: p["date"], reverse=True)

    OUT.mkdir(exist_ok=True)
    clean_output()
    build_home(posts)
    build_blog_index(posts)
    build_section_pages(posts)
    for i, post in enumerate(posts):
        newer = posts[i - 1] if i > 0 else None
        older = posts[i + 1] if i + 1 < len(posts) else None
        build_post(post, newer, older)
    build_404()
    build_feed(posts)
    build_redirects(posts)
    print(f"Built {len(posts)} posts in {len(SECTIONS)} sections into {OUT}")


if __name__ == "__main__":
    main()
