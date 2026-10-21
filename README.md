# portfolio.receva.co.za

The source of my portfolio site: [portfolio.receva.co.za](https://portfolio.receva.co.za).

A static site on GitHub Pages. No framework: one HTML page, one stylesheet and a small script.

## How it is built

Content lives in `data/projects.json` and `data/site.json`. Running

```
python3 tools/build.py
```

writes the cards, headline numbers and credentials into `index.html` and rebuilds `sitemap.xml`.

The build fails if:

- any copy contains an em dash or an en dash
- a link is not `https://` or a local file
- a finished card is missing a field
- a number has no source

Numbers appear only where they were measured, and each card names where its number came from.

## Checks

- WCAG 2.1 AA with axe-core, light and dark themes, at 1440 px and 375 px
- No horizontal scroll at 375 px
- Every card readable with JavaScript off
