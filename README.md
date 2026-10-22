# torinblair-sitepages

Static Bootstrap 5 site for Torin Blair, hosted on Cloudflare Pages. Content was imported from
https://torinblair.wordpress.com.

## Layout

```
public/                 Deployed site (Cloudflare Pages output directory)
  index.html            Home
  blog/                 Blog index
    ai/                 index.html + one <post-slug>.html per AI post
    secure-development/ index.html + one <post-slug>.html per other post
  assets/css/site.css   Custom styles (hand-edited; never overwritten)
  feed.xml              RSS feed
  _redirects            Old WordPress permalinks -> /blog/<section>/<slug>
  404.html
templates/layout.html   Shared page shell (nav, footer, Bootstrap includes)
tools/import_wordpress.py  Pulls posts from WordPress.com and rebuilds public/
```

## Preview locally

```sh
python3 tools/serve.py
# open http://localhost:8000
```

Posts are linked without the `.html` extension (`/blog/ai/<slug>`), as Cloudflare Pages serves
them. `tools/serve.py` resolves those the same way; plain `python3 -m http.server` does not.

To preview with Cloudflare's own behavior (including `_redirects`):

```sh
npx wrangler pages dev public
```

## Re-import from WordPress

```sh
python3 tools/import_wordpress.py
```

This regenerates everything in `public/` except `public/assets/`, so put layout changes in
`templates/layout.html` and set `SITE_URL` at the top of the script to your real domain.
Posts in the "Artificial Intelligence Security" category go to `blog/ai/`; everything else goes to
`blog/secure-development/`. Edit `SECTIONS` in the script to change or add sections.

## Deploy to Cloudflare Pages

`.github/workflows/deploy.yml` deploys `public/` with Wrangler:

- Push to `main` → production
- Pull request from this repo → preview at `https://pr-<number>.torinblair-sitepages.pages.dev`
- Manual run (Actions tab → Run workflow) from `main` → production

One-time setup:

1. Create the Pages project (Direct Upload, not Git-connected):
   `npx wrangler pages project create torinblair-sitepages --production-branch main`
2. Create a Cloudflare API token with **Account → Cloudflare Pages → Edit** permission.
3. Add repository secrets `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`
   (Settings → Secrets and variables → Actions).

The workflow deploys whatever is committed in `public/`; it does not run the WordPress import.
