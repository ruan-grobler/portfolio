#!/usr/bin/env python3
"""Render the data files into index.html, then check the result.

USAGE
    python3 tools/build.py

WHAT IT DOES
    1. Reads data/projects.json and data/site.json.
    2. Rewrites every block between <!-- build:NAME --> and <!-- /build:NAME --> in
       index.html. Everything outside those markers is hand written and left alone.
       The cards are rendered into the HTML at build time, not fetched by JavaScript,
       so crawlers, link preview scrapers and readers without JavaScript see them.
    3. Writes sitemap.xml.
    4. Fails loudly, with a non zero exit, if the result breaks a rule:
         - an en dash or em dash anywhere in index.html or the data files
         - a link that is not https:// or a proof page that exists on disk
         - a finished card with a missing before, after or number source
         - a filter tag that is not in the filters list
         - any pattern in tools/banned.local.txt, checked across every published file.
           That file is local only and never committed, so the terms it guards
           against are never spelled out in public.

To switch on an in build card, edit data/projects.json (its _how block says how)
and run this script again.
"""

from __future__ import annotations

import html
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / 'index.html'
PROJECTS = ROOT / 'data' / 'projects.json'
SITE_DATA = ROOT / 'data' / 'site.json'
BANNED_FILE = ROOT / 'tools' / 'banned.local.txt'
SITE = 'https://portfolio.receva.co.za'

STATUS = {
    'live': ('status-live', 'Live'),
    'demo': ('status-demo', 'Live demo'),
    'built': ('status-built', 'Built'),
    'inbuild': ('status-inbuild', 'In build'),
}
COURSE_GROUPS = {'Anthropic Academy': 'course certificates', 'OpenAI Academy': 'badges, each a course plus an assessment'}
DASHES = re.compile('[\u2013\u2014]')
NEW_TAB = '<span class="visually-hidden"> (opens in a new tab)</span>'

errors: list[str] = []
warnings: list[str] = []


def esc(text: object) -> str:
    return html.escape(str(text if text is not None else ''), quote=True)


def check_url(url: object, where: str) -> str | None:
    """Return the URL if it is safe to publish, otherwise record an error."""
    if not isinstance(url, str) or not url:
        errors.append(f'{where}: empty link')
        return None
    if url.startswith('https://'):
        return url
    if url.startswith('proof/'):
        if not (ROOT / url).is_file():
            errors.append(f'{where}: {url} does not exist on disk')
            return None
        return url
    errors.append(f'{where}: unsafe link {url!r} (only https:// or proof/ allowed)')
    return None


def link(url: str, label: str, cls: str = '') -> str:
    """Render a link. External links open in a new tab and say so."""
    c = f' class="{cls}"' if cls else ''
    if url.startswith('https://'):
        return (
            f'<a{c} href="{esc(url)}" target="_blank" rel="noopener noreferrer">'
            f'{esc(label)} <span class="arrow" aria-hidden="true">&#8599;</span>{NEW_TAB}</a>'
        )
    return f'<a{c} href="{esc(url)}">{esc(label)} <span class="arrow" aria-hidden="true">&#8594;</span></a>'


def validate_project(p: dict[str, Any], filter_ids: set[str]) -> None:
    slug = p.get('slug', '?')
    for tag in p.get('tags') or []:
        if tag not in filter_ids:
            errors.append(f'{slug}: tag {tag!r} is not in the filters list')
    if p.get('status') not in STATUS:
        errors.append(f'{slug}: unknown status {p.get("status")!r}')
    for field in ('title', 'pitch', 'problem', 'built'):
        if not p.get(field):
            errors.append(f'{slug}: {field} is empty')
    if p.get('status') == 'inbuild':
        todo = [f for f in ('before', 'after') if not p.get(f)]
        if p.get('number') is None:
            todo.append('number')
        if todo:
            warnings.append(f'{slug} (in build) still to fill: {", ".join(todo)}')
        return
    for field in ('before', 'after'):
        if not p.get(field):
            errors.append(f'{slug}: finished card has no {field}')
    num = p.get('number')
    if num is None:
        if not p.get('numberNote'):
            errors.append(f'{slug}: number is null, so numberNote must say why')
    else:
        for field in ('value', 'label', 'source'):
            if not num.get(field):
                errors.append(f'{slug}: number.{field} is empty')
    if not p.get('proof') and not p.get('proofNote'):
        errors.append(f'{slug}: no proof links and no proofNote')


def render_metric(p: dict[str, Any]) -> str:
    if p.get('status') == 'inbuild':
        return (
            '<div class="metric metric-none"><p class="metric-value">No number yet</p>'
            '<p class="metric-source">The before, the after and the number come from the '
            'first demo run, and publish with the code.</p></div>'
        )
    num = p.get('number')
    if num is None:
        return (
            '<div class="metric metric-none"><p class="metric-value">No number claimed</p>'
            f'<p class="metric-source">{esc(p.get("numberNote"))}</p></div>'
        )
    return (
        '<div class="metric">'
        f'<p class="metric-value">{esc(num["value"])}</p>'
        f'<p class="metric-label">{esc(num["label"])}</p>'
        f'<p class="metric-source">Source: {esc(num["source"])}</p>'
        '</div>'
    )


def render_card(p: dict[str, Any], labels: dict[str, str]) -> str:
    slug = p['slug']
    status = p['status']
    cls, status_label = STATUS[status]
    classes = ['card']
    if p.get('featured'):
        classes.append('card-featured')
    if status == 'inbuild':
        classes.append('card-inbuild')

    note = f'<span class="status-note">{esc(p["statusNote"])}</span>' if p.get('statusNote') else ''
    tags = ''.join(f'<li>{esc(labels[t])}</li>' for t in p.get('tags') or [])
    top = (
        '<div class="card-top">'
        f'<p><span class="status {cls}">{esc(status_label)}</span>{note}</p>'
        f'<ul class="tags" aria-label="Type">{tags}</ul>'
        '</div>'
    )
    head = f'<h3 id="t-{esc(slug)}">{esc(p["title"])}</h3><p class="pitch">{esc(p["pitch"])}</p>'
    facts = (
        '<dl class="facts">'
        f'<div><dt>Problem</dt><dd>{esc(p["problem"])}</dd></div>'
        f'<div><dt>{"What I am building" if status == "inbuild" else "What I built"}</dt>'
        f'<dd>{esc(p["built"])}</dd></div>'
        '</dl>'
    )
    if status == 'inbuild':
        ba = ''
    else:
        ba = (
            '<dl class="ba">'
            f'<div class="ba-before"><dt>Before</dt><dd>{esc(p["before"])}</dd></div>'
            f'<div class="ba-after"><dt>After</dt><dd>{esc(p["after"])}</dd></div>'
            '</dl>'
        )
    outcomes = ''
    if p.get('outcomes'):
        items = ''.join(f'<li>{esc(o)}</li>' for o in p['outcomes'])
        outcomes = f'<ul class="outcomes" aria-label="Outcomes">{items}</ul>'
    chips = ''.join(f'<li>{esc(s)}</li>' for s in p.get('stack') or [])
    stack = f'<ul class="chips" aria-label="Stack">{chips}</ul>'

    proof_items = []
    for i, item in enumerate(p.get('proof') or []):
        url = check_url(item.get('url'), f'{slug}.proof[{i}]')
        if url:
            proof_items.append(f'<li>{link(url, item.get("label") or "Open")}</li>')
    if status == 'inbuild':
        proof_note = 'In build. The code, the demo output and the numbers publish together when it ships.'
    else:
        proof_note = p.get('proofNote') or ''
    proof = '<div class="proof"><p class="k">Proof</p>'
    if proof_items:
        proof += f'<ul>{"".join(proof_items)}</ul>'
    if proof_note:
        proof += f'<p class="proof-note">{esc(proof_note)}</p>'
    proof += '</div>'

    if p.get('featured'):
        body = (
            f'{top}<div class="feat-cols">'
            f'<div>{head}{render_metric(p)}{facts}</div>'
            f'<div>{outcomes}{ba}{stack}{proof}</div>'
            '</div>'
        )
    else:
        body = f'{top}{head}{render_metric(p)}{facts}{ba}{outcomes}{stack}{proof}'

    data_tags = ' '.join(p.get('tags') or [])
    return (
        f'<article class="{" ".join(classes)}" id="p-{esc(slug)}" data-tags="{esc(data_tags)}" '
        f'aria-labelledby="t-{esc(slug)}">{body}</article>'
    )


def render_filters(filters: list[dict[str, str]], projects: list[dict[str, Any]]) -> str:
    out = [
        f'<button class="chip" type="button" data-filter="all" data-label="All work" aria-pressed="true">'
        f'All <span class="count">{len(projects)}</span></button>'
    ]
    for f in filters:
        n = sum(1 for p in projects if f['id'] in (p.get('tags') or []))
        if n == 0:
            warnings.append(f'filter {f["id"]} has no visible cards')
        out.append(
            f'<button class="chip" type="button" data-filter="{esc(f["id"])}" '
            f'data-label="{esc(f["label"])}" aria-pressed="false">{esc(f["label"])} '
            f'<span class="count">{n}<span class="visually-hidden"> projects</span></span></button>'
        )
    return ''.join(out)


def render_headline(items: list[dict[str, Any]]) -> str:
    out = []
    for i, h in enumerate(items):
        src = esc(h['source'])
        if h.get('url'):
            url = check_url(h['url'], f'headline[{i}]')
            if url:
                src = link(url, h['source'])
        out.append(
            '<div class="hl">'
            f'<p class="hl-value">{esc(h["value"])}</p>'
            f'<p class="hl-label">{esc(h["label"])}</p>'
            f'<p class="hl-source">{src}</p>'
            '</div>'
        )
    return f'<div class="headline">{"".join(out)}</div>'


def visible_creds(creds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for c in creds:
        if not c.get('show'):
            if c.get('_todo'):
                warnings.append(f'credential hidden until it has a link: {c["short"]}. {c["_todo"]}')
            continue
        if not c.get('verify'):
            errors.append(f'credential {c["name"]!r} is shown without a verify link')
            continue
        check_url(c['verify'], f'credential {c["short"]}')
        out.append(c)
    return out


def render_strip_creds(creds: list[dict[str, Any]]) -> str:
    pills = []
    for c in creds:
        if not c.get('strip'):
            continue
        pills.append(
            f'<li><a class="cred-pill" href="{esc(c["verify"])}" target="_blank" rel="noopener noreferrer">'
            f'<span class="iss">{esc(c["group"])}</span>{esc(c["short"])} '
            f'<span class="arrow" aria-hidden="true">&#8599;</span>'
            f'<span class="visually-hidden"> verify with {esc(c["group"])} (opens in a new tab)</span></a></li>'
        )
    pills.append('<li><a class="strip-more" href="#credentials">All credentials <span class="arrow" aria-hidden="true">&#8595;</span></a></li>')
    return f'<ul class="cred-pills" aria-labelledby="strip-creds-label">{"".join(pills)}</ul>'


def render_creds(creds: list[dict[str, Any]]) -> str:
    assessed = [c for c in creds if c['group'] not in COURSE_GROUPS]
    tiles = ''.join(
        '<li class="cred">'
        f'<span class="iss">{esc(c["group"])}</span>'
        f'<span class="name">{esc(c["name"])}</span>'
        f'<span class="detail">{esc(c["detail"])}</span>'
        f'<span class="meta"><span>{esc(c["date"])}</span>'
        f'<a href="{esc(c["verify"])}" target="_blank" rel="noopener noreferrer">Verify '
        f'<span class="arrow" aria-hidden="true">&#8599;</span>'
        f'<span class="visually-hidden"> {esc(c["short"])} with {esc(c["group"])} (opens in a new tab)</span></a></span>'
        '</li>'
        for c in assessed
    )
    groups = []
    for g in COURSE_GROUPS:
        rows = [c for c in creds if c['group'] == g]
        if not rows:
            continue
        lis = ''.join(
            f'<li><span>{esc(c["name"])}</span>'
            f'<a href="{esc(c["verify"])}" target="_blank" rel="noopener noreferrer">Verify '
            f'<span class="arrow" aria-hidden="true">&#8599;</span>'
            f'<span class="visually-hidden"> {esc(c["name"])} (opens in a new tab)</span></a></li>'
            for c in rows
        )
        groups.append(
            f'<div><h4>{esc(g)} <span class="k">{len(rows)} {esc(COURSE_GROUPS[g])}</span></h4>'
            f'<ul class="course-list">{lis}</ul></div>'
        )
    return (
        '<div class="cred-tier"><h3>Certifications and assessed skills</h3>'
        f'<ul class="cred-grid">{tiles}</ul></div>'
        '<div class="cred-tier"><h3>Course certificates</h3>'
        f'<div class="course-groups">{"".join(groups)}</div></div>'
    )


def replace_block(page: str, name: str, body: str) -> str:
    pattern = re.compile(rf'(<!-- build:{name} -->).*?(<!-- /build:{name} -->)', re.DOTALL)
    if not pattern.search(page):
        errors.append(f'index.html has no build:{name} marker')
        return page
    return pattern.sub(lambda m: m.group(1) + body + m.group(2), page)


def banned_patterns() -> list[re.Pattern[str]]:
    if not BANNED_FILE.is_file():
        warnings.append('tools/banned.local.txt not found, so the banned term gate did not run')
        return []
    out = []
    for line in BANNED_FILE.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            out.append(re.compile(line, re.IGNORECASE))
    return out


def published_files() -> list[Path]:
    files = [INDEX, ROOT / 'sitemap.xml', ROOT / 'robots.txt', PROJECTS, SITE_DATA]
    files += sorted((ROOT / 'proof').glob('*.html'))
    files += sorted((ROOT / 'assets').glob('*'))
    files += sorted((ROOT / 'tools').glob('*.py')) + sorted((ROOT / 'tools').glob('*.html'))
    return [f for f in files if f.is_file()]


def main() -> None:
    projects_doc = json.loads(PROJECTS.read_text(encoding='utf-8'))
    site = json.loads(SITE_DATA.read_text(encoding='utf-8'))
    filters = projects_doc['filters']
    filter_ids = {f['id'] for f in filters}
    labels = {f['id']: f['label'] for f in filters}

    projects = [p for p in projects_doc['projects'] if p.get('show')]
    slugs = [p['slug'] for p in projects]
    if len(slugs) != len(set(slugs)):
        errors.append('duplicate project slug')
    for p in projects:
        validate_project(p, filter_ids)
    if errors:
        finish()

    creds = visible_creds(site['credentials'])
    page = INDEX.read_text(encoding='utf-8')
    page = replace_block(page, 'headline', render_headline(site['headline']))
    page = replace_block(page, 'strip-creds', render_strip_creds(creds))
    page = replace_block(page, 'filters', render_filters(filters, projects))
    page = replace_block(page, 'cards', ''.join(render_card(p, labels) for p in projects))
    page = replace_block(page, 'creds', render_creds(creds))
    INDEX.write_text(page, encoding='utf-8')

    pages = ['/'] + [f'/proof/{f.name}' for f in sorted((ROOT / 'proof').glob('*.html'))]
    today = date.today().isoformat()
    urls = ''.join(f'  <url><loc>{SITE}{u}</loc><lastmod>{today}</lastmod></url>\n' for u in pages)
    (ROOT / 'sitemap.xml').write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'{urls}</urlset>\n',
        encoding='utf-8',
    )

    for f in (INDEX, PROJECTS, SITE_DATA):
        for n, line in enumerate(f.read_text(encoding='utf-8').splitlines(), 1):
            if DASHES.search(line):
                errors.append(f'{f.relative_to(ROOT)}:{n}: en or em dash')
    for pattern in banned_patterns():
        for f in published_files():
            text = f.read_text(encoding='utf-8', errors='ignore')
            for m in pattern.finditer(text):
                line = text.count('\n', 0, m.start()) + 1
                errors.append(f'{f.relative_to(ROOT)}:{line}: banned term matched {pattern.pattern!r}')
    for p in projects:
        if esc(p['title']) not in page:
            errors.append(f'{p["slug"]}: title missing from the rendered page')

    print(f'rendered {len(projects)} cards, {len(creds)} credentials, {len(site["headline"])} headline numbers')
    print(f'wrote sitemap.xml with {len(pages)} pages')
    finish()


def finish() -> None:
    for w in warnings:
        print(f'note: {w}')
    if errors:
        for e in errors:
            print(f'FAIL: {e}', file=sys.stderr)
        sys.exit(1)
    print('all checks passed')
    sys.exit(0)


if __name__ == '__main__':
    main()
