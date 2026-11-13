#!/usr/bin/env python3
"""Build slide decks from content/talks/*.json into public/talks/.

Usage:
    python3 tools/build_talks.py

Each deck becomes:
    /talks/                      list of talks
    /talks/<slug>/               overview with every slide title
    /talks/<slug>/<n>            one page per slide (1-based)

import_wordpress.py wipes public/ and calls build() again, so decks survive a
re-import. Edit the JSON, not the generated HTML.
"""

import datetime
import html
import json
import re
from pathlib import Path
from string import Template

SITE_URL = "https://torinblair-sitepages.pages.dev"  # keep in sync with import_wordpress.py
SITE_NAME = "Torin Blair"

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public"
CONTENT = ROOT / "content" / "talks"
LAYOUT = Template((ROOT / "templates" / "layout.html").read_text(encoding="utf-8"))

# Applies the saved presenting state before the slide paints, so nav doesn't flash.
PRESENT_BOOT = (
    "<script>(function(){var on=location.hash==='#present';"
    "try{on=on||sessionStorage.getItem('deck-present')==='1'}catch(e){}"
    "if(on)document.documentElement.classList.add('presenting')})()</script>"
)


def esc(value):
    return html.escape(str(value), quote=True)


def render(path, title, description, content, tagline):
    url_path = "/" + re.sub(r"(index)?\.html$", "", path)
    page = LAYOUT.substitute(
        title=esc(title),
        description=esc(description),
        canonical=SITE_URL + url_path,
        site_name=SITE_NAME,
        site_tagline=esc(tagline),
        year=datetime.date.today().year,
        nav_home="",
        nav_blog="",
        nav_talks=" active",
        content=content,
    )
    target = OUT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page, encoding="utf-8")


# ---------------------------------------------------------------- slide parts


def items(entries, cls="slide-list"):
    """Render a list whose entries are strings or {"t": text, "c": [children]}."""
    out = []
    for entry in entries:
        if isinstance(entry, dict):
            out.append(f"<li>{esc(entry['t'])}{items(entry.get('c', []), 'slide-sublist')}</li>")
        else:
            out.append(f"<li>{esc(entry)}</li>")
    return f'<ul class="{cls}">' + "".join(out) + "</ul>" if out else ""


def paragraphs(lines, cls="slide-intro"):
    return "".join(f'<p class="{cls}">{esc(line)}</p>' for line in lines or [])


def footnote(slide):
    return f'<p class="slide-footnote">{esc(slide["footnote"])}</p>' if slide.get("footnote") else ""


def priority_badge(cell):
    tone = {"high": "bad", "medium": "warn", "low": "good"}.get(cell.lower())
    return f'<span class="badge-tone tone-{tone}">{esc(cell)}</span>' if tone else esc(cell)


def body_html(slide):
    kind = slide.get("kind", "bullets")
    intro = paragraphs(slide.get("intro"))

    if kind == "statement":
        return paragraphs(slide["body"], "slide-statement")

    if kind == "timeline":
        rows = "".join(
            f'<li><span class="when">{esc(when)}</span><span class="what">{esc(what)}</span></li>'
            for when, what in slide["items"]
        )
        return intro + f'<ol class="timeline">{rows}</ol>'

    if kind == "steps":
        rows = []
        for entry in slide["body"]:
            if isinstance(entry, dict):
                rows.append(f"<li><p>{esc(entry['t'])}</p>{items(entry.get('c', []), 'slide-sublist')}</li>")
            else:
                rows.append(f"<li><p>{esc(entry)}</p></li>")
        return intro + '<ol class="steps">' + "".join(rows) + "</ol>" + footnote(slide)

    if kind == "checklist":
        return intro + items(slide["body"], "slide-list checklist")

    if kind == "terms":
        rows = "".join(f"<div><dt>{esc(term)}</dt><dd>{esc(desc)}</dd></div>" for term, desc in slide["items"])
        return intro + f'<dl class="terms">{rows}</dl>'

    if kind == "chips":
        chips = "".join(f"<li>{esc(c)}</li>" for c in slide["body"])
        return intro + f'<ul class="chips">{chips}</ul>'

    if kind in ("groups", "references"):
        tone = slide.get("tone")
        label = {"bad": "Replace now", "warn": "Plan to replace", "good": "Recommended"}.get(tone)
        cards = "".join(
            f'<section class="group">'
            f'<h2>{esc(g["h"])}</h2>'
            f'{items(g["c"], "slide-list")}'
            f"</section>"
            for g in slide["groups"]
        )
        badge = f'<p class="group-status"><span class="badge-tone tone-{tone}">{label}</span></p>' if label else ""
        cls = "groups references" if kind == "references" else f"groups tone-{tone or 'none'}"
        return intro + badge + f'<div class="{cls}">{cards}</div>' + footnote(slide)

    if kind == "table":
        head = "".join(f'<th scope="col">{esc(h)}</th>' for h in slide["head"])
        rows = []
        for row in slide["rows"]:
            placeholder = row[0].startswith("[")
            cells = [f'<th scope="row">{esc(row[0])}</th>']
            for i, cell in enumerate(row[1:], start=1):
                value = priority_badge(cell) if i == 4 and not placeholder else esc(cell)
                cells.append(f"<td>{value}</td>")
            rows.append(f'<tr{' class="row-placeholder"' if placeholder else ""}>' + "".join(cells) + "</tr>")
        return (
            intro + '<div class="table-responsive"><table class="table inventory">'
            f"<thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
        )

    if kind == "phases":
        cols = "".join(
            f'<li class="phase">'
            f'<p class="phase-num">Phase {i}</p>'
            f'<h2>{esc(p["h"])}</h2>'
            f'<p class="phase-when">{esc(p["when"])}</p>'
            f'{items(p["c"], "slide-list")}'
            f"</li>"
            for i, p in enumerate(slide["phases"], start=1)
        )
        return intro + f'<ol class="phases">{cols}</ol>'

    return intro + items(slide["body"]) + footnote(slide)


def text_length(node):
    if isinstance(node, str):
        return len(node)
    if isinstance(node, dict):
        return sum(text_length(v) for v in node.values())
    if isinstance(node, list):
        return sum(text_length(v) for v in node)
    return 0


def density(slide):
    """1 (sparse) to 4 (dense); scales type so heavy slides still fit when presenting."""
    n = text_length({k: v for k, v in slide.items() if k not in ("title", "section", "kind", "tone")})
    return 1 if n < 450 else 2 if n < 800 else 3 if n < 1150 else 4


def eyebrow(slide):
    parts = [slide.get("section")]
    if slide.get("num"):
        parts.append(f"Focus {slide['num']}")
    text = " · ".join(esc(p) for p in parts if p)
    return f'<p class="slide-eyebrow">{text}</p>' if text else ""


def slide_page(deck, index):
    slides = deck["slides"]
    slide = slides[index]
    n, total = index + 1, len(slides)
    base = f"/talks/{deck['slug']}"
    kind = slide.get("kind", "bullets")

    if kind == "cover":
        inner = (
            f'<p class="slide-eyebrow">{esc(SITE_NAME)}</p>'
            f'<h1 class="slide-title cover-title">{esc(slide["title"])}</h1>'
            f'<p class="cover-lead">{esc(slide["lead"])}</p>'
        )
    else:
        inner = (
            eyebrow(slide)
            + f'<h1 class="slide-title">{esc(slide["title"])}</h1>'
            + f'<div class="slide-body">{body_html(slide)}</div>'
        )

    prev_link = (
        f'<a class="pager-link" rel="prev" href="{base}/{n - 1}">&larr; Previous</a>'
        if n > 1 else f'<a class="pager-link" href="{base}/">&larr; Overview</a>'
    )
    next_link = (
        f'<a class="pager-link" rel="next" href="{base}/{n + 1}">Next &rarr;</a>'
        if n < total else f'<a class="pager-link" rel="next" href="{base}/">Overview &rarr;</a>'
    )
    progress = round(n / total * 100, 2)

    content = f"""
      {PRESENT_BOOT}
      <div class="deck" data-deck data-overview="{base}/" data-first="{base}/1" data-last="{base}/{total}">
        <div class="deck-bar">
          <a class="pager-link" href="{base}/">{esc(deck['title'])}</a>
          <span class="deck-count" aria-label="Slide {n} of {total}">{n} / {total}</span>
        </div>
        <article class="slide slide--{kind} dens-{density(slide)}" aria-roledescription="slide" aria-label="{n} of {total}">
          {inner}
        </article>
        <div class="deck-progress" aria-hidden="true"><span style="width:{progress}%"></span></div>
        <nav class="deck-nav" aria-label="Slides">
          {prev_link}
          <button type="button" class="pager-link deck-present" data-present aria-pressed="false">Present</button>
          {next_link}
        </nav>
        <p class="deck-hint">Arrow keys move between slides · P presents · Esc exits · F11 for full screen</p>
      </div>
      <script src="/assets/js/deck.js" defer></script>"""
    return content


def overview_page(deck):
    base = f"/talks/{deck['slug']}"
    sections, current = [], None
    for n, slide in enumerate(deck["slides"], start=1):
        name = slide.get("section", "Introduction")
        if name != current:
            sections.append((name, []))
            current = name
        label = f"Focus {slide['num']}: {slide['title']}" if slide.get("num") else slide["title"]
        sections[-1][1].append(f'<li value="{n}"><a href="{base}/{n}">{esc(label)}</a></li>')

    groups = "".join(
        f'<section class="mb-4"><h2 class="deck-toc-heading">{esc(name)}</h2>'
        f'<ol class="deck-toc">{"".join(rows)}</ol></section>'
        for name, rows in sections
    )
    return f"""
      <nav aria-label="breadcrumb">
        <ol class="breadcrumb">
          <li class="breadcrumb-item"><a href="/talks/">Talks</a></li>
          <li class="breadcrumb-item active" aria-current="page">{esc(deck['title'])}</li>
        </ol>
      </nav>
      <header class="hero mb-5">
        <h1 class="page-title mb-3">{esc(deck['title'])}</h1>
        <p class="lead">{esc(deck['subtitle'])}</p>
        <p class="small text-body-secondary mb-4">{len(deck['slides'])} slides</p>
        <a class="link-arrow" href="{base}/1">Start the slides</a>
      </header>
      {groups}"""


def talks_index(decks):
    cards = "".join(
        f"""
      <div class="col">
        <article class="card h-100 post-card">
          <div class="card-body d-flex flex-column">
            <p class="small text-body-secondary mb-2">{len(d['slides'])} slides</p>
            <h2 class="h5 card-title">
              <a class="stretched-link" href="/talks/{d['slug']}/">{esc(d['title'])}</a>
            </h2>
            <p class="card-text text-body-secondary mb-0">{esc(d['subtitle'])}</p>
          </div>
        </article>
      </div>"""
        for d in decks
    )
    return f"""
      <header class="mb-4">
        <h1 class="page-title">Talks</h1>
        <p class="text-body-secondary">Slide decks from presentations.</p>
      </header>
      <div class="post-list">{cards}
      </div>"""


def read_tagline():
    home = OUT / "index.html"
    if home.exists():
        match = re.search(r'<meta name="description" content="([^"]*)"', home.read_text(encoding="utf-8"))
        if match:
            return html.unescape(match.group(1))
    return ""


def build(tagline=None):
    tagline = read_tagline() if tagline is None else tagline
    decks = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(CONTENT.glob("*.json"))]
    for deck in decks:
        base = f"talks/{deck['slug']}"
        render(f"{base}/index.html", f"{deck['title']} | {SITE_NAME}", deck["subtitle"], overview_page(deck), tagline)
        for i, slide in enumerate(deck["slides"]):
            title = f"{slide['title']} ({i + 1}/{len(deck['slides'])}) | {deck['title']}"
            render(f"{base}/{i + 1}.html", title, deck["subtitle"], slide_page(deck, i), tagline)
    render("talks/index.html", f"Talks | {SITE_NAME}", "Slide decks from presentations.", talks_index(decks), tagline)
    print(f"Built {len(decks)} deck(s), {sum(len(d['slides']) for d in decks)} slides into {OUT / 'talks'}")


if __name__ == "__main__":
    build()
