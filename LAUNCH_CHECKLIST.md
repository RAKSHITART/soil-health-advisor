# Launch checklist

Status of each item for this app. "You" means it needs an action outside the code.

| # | Item | Status |
|---|------|--------|
| 1 | Privacy policy page | Done: `views/privacy.py`. Set `CONTACT_EMAIL` so it shows a contact address. |
| 2 | Terms and conditions page | Done: `views/terms.py`. It is a plain template; have someone qualified review it. |
| 3 | Secrets off the front end | Done. The Groq key is read on the server from secrets or `.env`, never rendered. Rotate any key that was ever committed. |
| 4 | Force HTTPS | Automatic on Streamlit Community Cloud and Hugging Face. On your own host, enable TLS at the proxy. |
| 5 | Cookie consent banner | Not added on purpose: the app sets no advertising, analytics or tracking cookies. Add a banner if you add analytics. |
| 6 | Meta titles and descriptions | Page title is set. Streamlit cannot set a meta description or Open Graph tags; use your own host or proxy for those. |
| 7 | Social preview image | `assets/social-preview.png`. Upload it in the GitHub repository settings (Social preview). |
| 8 | Favicon | Done: `assets/favicon.png`, `favicon.ico`, `apple-touch-icon.png`. |
| 9 | Sitemap and robots.txt | Not applicable: a single Streamlit app has no crawlable page content. |
| 10 | Alt text | The app has no photos. Charts sit beside tables or text with the same information. |
| 11 | Compress images | Done: the three images are under 35 KB each. |
| 12 | Page load speed | Crop model is cached and warmed once, weather is cached for 30 minutes, no heavy assets. |
| 13 | Colour contrast | Text and status colours are chosen to pass WCAG AA (4.5:1) on white. |
| 14 | Mobile friendly | Single centred column, large tap targets, tables scroll sideways only when needed. Test on a real phone. |
| 15 | Custom 404 | Streamlit shows its own "page not found". It cannot be customised on Community Cloud. |
| 16 | Broken links | No external links in the app. Check the links in this repository after you publish. |
| 17 | Form validation | Done: required fields, impossible value limits, localised messages, covered by tests. |
| 18 | Spam and bot protection | Per-session cooldown and caps on reports, AI calls and chat messages; input length and file size limits. No CAPTCHA. Add Cloudflare Turnstile in front of a self-hosted copy if abused. |
| 19 | Analytics | None by design. Streamlit usage statistics are off. |
| 20 | One clear call to action | The single primary button: "Get my report". |
| - | Custom domain | You. Community Cloud only gives a `*.streamlit.app` address. Deploy the `Dockerfile` on Render, Fly.io or Cloud Run and point your domain's DNS at it. |

Not used, on purpose: gradients, pill-shaped buttons, fake reviews or customer counters, emoji icons, em dashes,
scroll or cursor animations, stock or AI photos, "made with AI" badges.
