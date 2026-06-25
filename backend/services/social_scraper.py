"""
Social Media Profile Scraper — v2 (Rebuilt)
============================================
Extracts ONLY profile metadata (bio, display name, website, location, avatar).
Does NOT scan posts, comments, feeds, or system text.

Supported platforms:
  - Reddit   → /user/{username}/about.json  (public JSON, no auth)
  - Instagram → OG meta tags from public profile HTML
  - Twitter/X → Nitter mirror OG tags + profile selectors
  - LinkedIn  → OG meta tags from public profile HTML

Noise filtering removes platform system text before detection.
"""
from __future__ import annotations
import re
import logging
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ── HTTP headers ──────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
TIMEOUT = 15

# ── Noise patterns — strip these lines before detection ──────────────────────
_NOISE_PATTERNS = [
    r"\b(log\s*in|sign\s*in|sign\s*up|create\s*account|register)\b",
    r"\b(forgot\s*password|reset\s*password|change\s*password)\b",
    r"\b(cookie|privacy\s*policy|terms\s*of\s*service|terms\s*of\s*use)\b",
    r"\b(help\s*center|support\s*center|report\s*abuse|contact\s*us)\b",
    r"\b(account\s*safety|two.factor|authenticat(?:ion|or))\b",
    r"\b(download\s*the\s*app|get\s*the\s*app|available\s*on)\b",
    r"\b(reddit\s*inc|instagram\s*llc|twitter\s*inc|meta\s*platforms)\b",
    r"\bone.time\s*password\b",
    r"\benter\s*your\s*(?:username|email|password)\b",
    r"\bwe\s*will\s*never\s*ask\b",
    r"\bwe\s*won.t\s*ask\b",
    r"\bvia\s*direct\s*message\b.{0,40}(?:password|code)\b",
    r"\bverif(?:y|ication)\s*code\b",
]
_NOISE_RE = re.compile("|".join(_NOISE_PATTERNS), re.IGNORECASE)

# ── Platform names to ignore in NER ──────────────────────────────────────────
PLATFORM_IGNORE_ENTITIES = {
    "reddit", "instagram", "twitter", "x", "linkedin", "github",
    "facebook", "youtube", "tiktok", "nitter", "snapchat", "pinterest",
    "discord", "telegram", "whatsapp", "meta",
}


def detect_platform(url: str) -> str:
    h = urlparse(url).netloc.lower().lstrip("www.")
    if "twitter.com" in h or "x.com" in h:
        return "twitter"
    if "linkedin.com" in h:
        return "linkedin"
    if "reddit.com" in h:
        return "reddit"
    if "instagram.com" in h:
        return "instagram"
    if "github.com" in h:
        return "github"
    # Only the 5 platforms allowed.
    return "unsupported platform"


def _clean(text: str) -> str:
    """Remove noise lines from scraped text."""
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _NOISE_RE.search(stripped):
            continue
        if len(stripped) < 4:
            continue
        lines.append(stripped)
    return "\n".join(lines)


# ── Reddit ────────────────────────────────────────────────────────────────────

def _fetch_reddit(url: str) -> dict:
    """
    Scrape ONLY profile metadata from Reddit public JSON API.
    Does NOT fetch posts or comments (major source of false positives).
    """
    m = re.search(r"(?:u/|user/)([^/?#]+)", url)
    if not m:
        return _empty("reddit", url)

    username = m.group(1)
    title = f"u/{username}"
    texts = []
    avatar_url = None
    profile_fields = {"username": username}

    try:
        about_url = f"https://www.reddit.com/user/{username}/about.json"
        r = requests.get(
            about_url,
            headers={**HEADERS, "Accept": "application/json"},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            body = r.json()
            data = body.get("data", {})
            if not data:
                # Some users return {"kind":"t2","data":{}} — try top-level fields
                data = body
            subreddit = data.get("subreddit", {})

            # Bio / description — try multiple keys
            bio = (
                subreddit.get("public_description", "") or
                data.get("subreddit", {}).get("description", "") or
                ""
            ).strip()

            # Custom display name (user-set, may differ from u/username)
            custom_title = subreddit.get("title", "").strip()
            display_name_prefixed = subreddit.get("display_name_prefixed", f"u/{username}").strip()
            display_name = (
                custom_title
                if custom_title and custom_title.lower() not in (username.lower(), f"u/{username}".lower())
                else display_name_prefixed
            )

            # Avatar: icon_img first, then snoovatar fallback
            icon = (
                data.get("icon_img") or data.get("snoovatar_img")
                or subreddit.get("icon_img") or ""
            )
            if icon and icon.startswith("http"):
                avatar_url = icon.split("?")[0]  # strip CDN query params

            # Karma counts
            link_karma    = data.get("link_karma", 0)
            comment_karma = data.get("comment_karma", 0)

            profile_fields = {
                "username":      username,
                "display_name":  display_name,
                "bio":           bio,
                "link_karma":    link_karma,
                "comment_karma": comment_karma,
            }

            if bio:
                texts.append(bio)
            if custom_title and custom_title.lower() not in (username.lower(), f"u/{username}".lower()):
                texts.append(custom_title)

    except Exception as e:
        logger.warning(f"Reddit fetch failed for {username}: {e}")

    return {
        "texts": texts,
        "avatar_url": avatar_url,
        "title": title,
        "username": username,
        "platform": "reddit",
        "profile_fields": profile_fields,
    }


# ── Instagram ─────────────────────────────────────────────────────────────────

def _fetch_instagram(url: str) -> dict:
    """
    Scrape Instagram via Facebook's externalhit bot UA (primary) then regular UA.
    Instagram serves OG tags to Facebook's own scraper.
    """
    m = re.search(r"instagram\.com/([^/?#]+)", url)
    username = m.group(1) if m else ""
    title = f"@{username}"
    texts = []
    avatar_url = None
    profile_fields = {"username": username}

    profile_url = f"https://www.instagram.com/{username}/"

    # Try Facebook bot UA first — Instagram serves OG tags to its parent company's crawler
    for attempt_headers in [_INSTAGRAM_BOT_HEADERS, HEADERS]:
        try:
            r = requests.get(profile_url, headers=attempt_headers, timeout=TIMEOUT)
            soup = BeautifulSoup(r.text, "html.parser")

            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                raw = og_title["content"]
                # Strip " • Instagram ..." suffix
                display = re.sub(r"\s*[•·]\s*Instagram.*$", "", raw).strip()
                # Strip "(@handle)" from end of display name
                display = re.sub(r"\s*\(@[^)]+\)\s*$", "", display).strip()
                if display and display.lower() != username.lower():
                    profile_fields["display_name"] = display
                    texts.append(display)

            og_desc = soup.find("meta", property="og:description")
            if og_desc and og_desc.get("content"):
                raw_bio = og_desc["content"]
                # Strip follower/following/post stats including K/M suffixes
                # e.g. "650K Followers, 68 Following, 3,218 Posts - See Instagram..."
                bio = re.sub(
                    r"^[\d,\.]+[KkMmBb]?\s*Followers.*?-\s*",
                    "", raw_bio, flags=re.IGNORECASE
                ).strip()
                # Also strip any remaining Instagram boilerplate
                bio = re.sub(r"See Instagram photos and videos from.*$", "", bio, flags=re.IGNORECASE).strip()
                # Only store if there’s actual bio content (not just stats)
                if bio and len(bio) > 10 and not re.match(r'^\d', bio):
                    profile_fields["bio"] = bio
                    texts.append(bio)

            og_img = soup.find("meta", property="og:image")
            if og_img and og_img.get("content"):
                avatar_url = og_img["content"]

            # Check scripts for external_url / business contact
            for s in soup.find_all("script"):
                content = s.string or ""
                ext = re.search(r'"external_url"\s*:\s*"([^"]+)"', content)
                if ext and ext.group(1):
                    profile_fields["website"] = ext.group(1).replace("\\/", "/")
                    texts.append(profile_fields["website"])
                email_m = re.search(r'"business_email"\s*:\s*"([^"]+)"', content)
                if email_m and email_m.group(1):
                    profile_fields["email"] = email_m.group(1)
                    texts.append(profile_fields["email"])
                phone_m = re.search(r'"business_phone_number"\s*:\s*"([^"]+)"', content)
                if phone_m and phone_m.group(1):
                    profile_fields["phone"] = phone_m.group(1)
                    texts.append(profile_fields["phone"])

            if texts:
                break  # got data, stop trying headers

        except Exception as e:
            logger.warning(f"Instagram fetch attempt failed for {username}: {e}")

    return {
        "texts": texts, "avatar_url": avatar_url, "title": title,
        "username": username, "platform": "instagram", "profile_fields": profile_fields,
    }


# ── Twitter / X ───────────────────────────────────────────────────────────────

_NITTER_MIRRORS = [
    "https://nitter.catsarch.com",
    "https://nitter.moomoo.me",
    "https://n.hyperborea.cloud",
    "https://nitter.1d4.us",
    "https://nitter.kavin.rocks",
]

# Twitter/X Twitterbot UA — x.com serves OG tags to its own bot
_TWITTER_BOT_HEADERS = {
    "User-Agent": "Twitterbot/1.0",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Instagram fbexternalhit UA — Instagram serves OG tags to Facebook's scraper
_INSTAGRAM_BOT_HEADERS = {
    "User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _fetch_twitter(url: str) -> dict:
    """
    Scrape Twitter/X profile metadata.
    PRIMARY: Twitterbot/1.0 UA — x.com serves full OG tags to its own bot.
    FALLBACK: Nitter mirrors (mostly dead but try as backup).
    """
    m = re.search(r"(?:twitter\.com|x\.com)/([^/?#]+)", url)
    username = m.group(1) if m else ""
    title = f"@{username}"
    texts = []
    avatar_url = None
    profile_fields = {"username": username}

    # ── PRIMARY: Twitterbot UA ──────────────────────────────────────────────
    try:
        xurl = f"https://x.com/{username}"
        r = requests.get(xurl, headers=_TWITTER_BOT_HEADERS, timeout=TIMEOUT)
        soup = BeautifulSoup(r.text, "html.parser")

        # og:title = "Display Name (@handle) on X"
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            raw_title = og_title["content"]
            # Strip " on X" or " on Twitter" suffix, and extract display name before "(@handle)"
            display = re.sub(r"\s*\(@?[^)]+\)\s*on\s*(X|Twitter).*$", "", raw_title).strip()
            if not display:  # fallback: just strip " on X"
                display = re.sub(r"\s+on\s+(X|Twitter).*$", "", raw_title).strip()
            if display and display.lower() != username.lower():
                profile_fields["display_name"] = display
                texts.append(display)

        # og:description = bio (handle emoji safely)
        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content"):
            bio_raw = og_desc["content"]
            # Encode to ASCII ignoring unrepresentable chars, then decode back
            bio_safe = bio_raw.encode("ascii", "ignore").decode("ascii").strip()
            bio = _clean(bio_safe)
            if not bio:  # fallback: keep emoji but still clean
                bio = _clean(bio_raw)
            if bio and len(bio) > 5:
                profile_fields["bio"] = bio
                texts.append(bio)

        # og:image = avatar
        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            avatar_url = og_img["content"]

        if texts:
            logger.debug(f"Twitter Twitterbot UA succeeded for @{username}")
            return {
                "texts": texts, "avatar_url": avatar_url, "title": title,
                "username": username, "platform": "twitter", "profile_fields": profile_fields,
            }

    except Exception as e:
        logger.debug(f"Twitter Twitterbot UA failed for @{username}: {e}")

    # ── FALLBACK: Nitter mirrors ────────────────────────────────────────────
    for mirror in _NITTER_MIRRORS:
        try:
            r = requests.get(f"{mirror}/{username}", headers=HEADERS, timeout=8)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            # Skip Anubis bot-protection pages
            if "Making sure you" in r.text or "Anubis" in r.text:
                continue

            bio_el   = soup.select_one(".profile-bio, [data-testid='bio']")
            name_el  = soup.select_one(".profile-card-fullname, .fullname")
            loc_el   = soup.select_one(".profile-location, [data-testid='UserLocation']")
            web_el   = soup.select_one(".profile-website a, [data-testid='UserUrl'] a")
            av_el    = soup.select_one(".profile-card-avatar img, .avatar img")

            if bio_el:
                bio = _clean(bio_el.get_text(" ", strip=True))
                if bio: profile_fields["bio"] = bio; texts.append(bio)
            if name_el:
                dn = name_el.get_text(" ", strip=True)
                if dn: profile_fields["display_name"] = dn; texts.append(dn)
            if loc_el:
                loc = loc_el.get_text(" ", strip=True)
                if loc: profile_fields["location"] = loc; texts.append(loc)
            if web_el:
                ws = web_el.get("href") or web_el.get_text(strip=True)
                if ws: profile_fields["website"] = ws; texts.append(ws)
            if av_el and av_el.get("src"):
                src = av_el["src"]
                avatar_url = (mirror + src) if src.startswith("/") else src

            if texts:
                break
        except Exception as e:
            logger.debug(f"Nitter mirror {mirror} failed: {e}")

    return {
        "texts": texts, "avatar_url": avatar_url, "title": title,
        "username": username, "platform": "twitter", "profile_fields": profile_fields,
    }


# ── LinkedIn ──────────────────────────────────────────────────────────────────

def _fetch_linkedin(url: str) -> dict:
    """
    Scrape LinkedIn company and profile pages.
    Uses mobile UA to bypass some login walls, and checks JSON-LD data.
    """
    texts = []
    avatar_url = None
    username = ""
    profile_fields = {}

    # Extract handle from URL
    m = re.search(r"linkedin\.com/(?:in|company)/([^/?#]+)", url)
    if m:
        username = m.group(1)
        profile_fields["username"] = username

    # LinkedIn is more likely to serve content with mobile UA
    mobile_headers = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        r = requests.get(url, headers=mobile_headers, timeout=TIMEOUT, allow_redirects=True)
        soup = BeautifulSoup(r.text, "html.parser")

        # --- JSON-LD (best source for company pages) ---
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                import json as _json
                data = _json.loads(script.string or "")

                # Handle @graph structure (LinkedIn uses this)
                items = data.get("@graph", []) if isinstance(data, dict) else []
                if not items:
                    items = [data]  # top-level object

                for item in items if items else [data]:
                    if not isinstance(item, dict):
                        continue
                    itype = item.get("@type", "")

                    # Extract from Organization / Person
                    name = item.get("name") or item.get("legalName", "")
                    description = item.get("description", "")
                    website = item.get("url", "")
                    logo = item.get("logo", "") if isinstance(item.get("logo"), str) else ""

                    # Also check nested author/org
                    if not name:
                        author = item.get("author", {}) or item.get("publisher", {})
                        if isinstance(author, dict):
                            name = author.get("name", "")
                            website = website or author.get("url", "")

                    location = ""
                    addr = item.get("address", {})
                    if isinstance(addr, dict):
                        parts = [addr.get("addressLocality", ""), addr.get("addressRegion", ""), addr.get("addressCountry", "")]
                        location = ", ".join(p for p in parts if p)

                    if name and not profile_fields.get("display_name"):
                        profile_fields["display_name"] = name
                        texts.append(name)
                    if description and not profile_fields.get("bio"):
                        profile_fields["bio"] = description[:300]
                        texts.append(description[:300])
                    if website and "linkedin.com" not in website and not profile_fields.get("website"):
                        profile_fields["website"] = website
                        texts.append(website)
                    if location and not profile_fields.get("location"):
                        profile_fields["location"] = location
                        texts.append(location)
                    if logo and not avatar_url:
                        avatar_url = logo
            except Exception:
                pass

        # --- OG tags fallback ---
        if not profile_fields.get("display_name"):
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                dn = re.sub(r"\s*\|\s*LinkedIn.*$", "", og_title["content"]).strip()
                if dn:
                    profile_fields["display_name"] = dn
                    texts.append(dn)

        if not profile_fields.get("bio"):
            og_desc = soup.find("meta", property="og:description")
            if og_desc and og_desc.get("content"):
                desc = _clean(og_desc["content"])
                if desc:
                    profile_fields["headline"] = desc
                    profile_fields.setdefault("bio", desc)
                    texts.append(desc)

        if not avatar_url:
            og_img = soup.find("meta", property="og:image")
            if og_img and og_img.get("content"):
                avatar_url = og_img["content"]

    except Exception as e:
        logger.warning(f"LinkedIn fetch failed: {e}")

    return {
        "texts": texts,
        "avatar_url": avatar_url,
        "title": profile_fields.get("display_name", username or url),
        "username": username,
        "platform": "linkedin",
        "profile_fields": profile_fields,
    }


# ── GitHub ────────────────────────────────────────────────────────────────────

def _fetch_github(url: str) -> dict:
    """
    Scrape GitHub profile using the free public GitHub API.
    No authentication required for public profiles.
    Returns: name, bio, location, company, email, blog, followers, public_repos.
    """
    m = re.search(r"github\.com/([^/?#]+)", url)
    if not m:
        return _empty("github", url)

    username = m.group(1)
    # Skip org subpages like /orgs/, /repos/, etc.
    if username.lower() in ("orgs", "repos", "issues", "pulls", "settings", "login", "join"):
        return _empty("github", url)

    title = f"@{username}"
    texts = []
    avatar_url = None
    profile_fields = {"username": username}

    try:
        api_url = f"https://api.github.com/users/{username}"
        r = requests.get(
            api_url,
            headers={
                **HEADERS,
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            data = r.json()

            name     = (data.get("name") or "").strip()
            bio      = (data.get("bio") or "").strip()
            location = (data.get("location") or "").strip()
            company  = (data.get("company") or "").strip().lstrip("@")
            email    = (data.get("email") or "").strip()
            blog     = (data.get("blog") or "").strip()
            twitter  = (data.get("twitter_username") or "").strip()
            followers     = data.get("followers", 0)
            public_repos  = data.get("public_repos", 0)
            avatar        = data.get("avatar_url", "")

            if avatar:
                avatar_url = avatar

            # Build profile_fields — all public fields
            profile_fields = {
                "username":     username,
                "display_name": name or username,
                "bio":          bio,
                "location":     location,
                "company":      company,
                "email":        email,
                "website":      blog,
                "twitter":      twitter,
                "followers":    followers,
                "public_repos": public_repos,
            }

            # Build text corpus for regex/NER scanning
            for val in [name, bio, location, company, email, blog, twitter]:
                if val:
                    texts.append(val)

            title = f"{name} (@{username})" if name else f"@{username}"

        elif r.status_code == 404:
            logger.warning(f"GitHub user not found: {username}")
        else:
            logger.warning(f"GitHub API returned {r.status_code} for {username}")

    except Exception as e:
        logger.warning(f"GitHub fetch failed for {username}: {e}")

    return {
        "texts":         texts,
        "avatar_url":    avatar_url,
        "title":         title,
        "username":      username,
        "platform":      "github",
        "profile_fields": profile_fields,
    }


# ── Raw text (GitHub raw, Pastebin, etc.) ────────────────────────────────────

def _fetch_rawtext(url: str) -> dict:
    texts = []
    title = url
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        content_type = r.headers.get("Content-Type", "")
        if "html" in content_type:
            soup = BeautifulSoup(r.text, "html.parser")
            t = soup.find("title")
            title = t.get_text(strip=True) if t else url
            raw_text = soup.get_text(" ", strip=True)
        else:
            raw_text = r.text
            title = url.split("/")[-1] or url
        for i in range(0, min(len(raw_text), 8000), 500):
            chunk = raw_text[i:i + 500].strip()
            if chunk:
                texts.append(chunk)
    except Exception as e:
        logger.warning(f"Raw text fetch failed: {e}")
    return {
        "texts": texts, "avatar_url": None, "title": title,
        "username": "", "platform": "rawtext", "profile_fields": {},
    }


# ── Entry point ───────────────────────────────────────────────────────────────

def _empty(platform: str, url: str) -> dict:
    return {
        "texts": [], "avatar_url": None, "title": url,
        "username": "", "platform": platform, "profile_fields": {},
    }


def scrape_profile(url: str) -> dict:
    """
    Scrape a public social media profile.
    Returns: { texts, avatar_url, title, username, platform, profile_fields }
    """
    platform = detect_platform(url)
    if platform == "reddit":
        result = _fetch_reddit(url)
    elif platform == "instagram":
        result = _fetch_instagram(url)
    elif platform == "twitter":
        result = _fetch_twitter(url)
    elif platform == "linkedin":
        result = _fetch_linkedin(url)
    elif platform == "github":
        result = _fetch_github(url)
    else:
        # Platform unsupported or unknown
        return _empty("unsupported platform", url)

    # Final noise filter
    result["texts"] = [cleaned for raw in result["texts"] if (cleaned := _clean(raw))]
    return result


def download_avatar(avatar_url: str) -> bytes | None:
    """Download profile image bytes (max 5 MB)."""
    if not avatar_url:
        return None
    try:
        r = requests.get(avatar_url, headers=HEADERS, timeout=10, stream=True)
        size = 0
        chunks = []
        for chunk in r.iter_content(8192):
            size += len(chunk)
            if size > 5 * 1024 * 1024:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    except Exception as e:
        logger.warning(f"Avatar download failed: {e}")
        return None


def classify_profile_exposure(platform: str, profile_fields: dict, findings: list[dict]) -> dict:
    """
    Classify the overall profile into one of 4 exposure categories.

    Returns:
      {
        "category": "public_business" | "professional_public" | "personal_exposure" | "anonymous",
        "label": str,             # human-readable label
        "score_modifier": float,  # adjustment to the score
        "description": str,       # brief description of the classification
      }
    """
    bio = str(profile_fields.get("bio", "") or profile_fields.get("headline", "")).lower()
    username = str(profile_fields.get("username", "") or profile_fields.get("handle", "")).lower()
    display_name = str(profile_fields.get("display_name", "")).lower()
    location = str(profile_fields.get("location", "")).lower()

    # ── Category 1: public_business ─────────────────
    is_linkedin = str(platform).lower() == "linkedin"
    business_keywords = ["company", "ceo", "founder", "official", "business", "corp", "inc", "co-founder", "director"]
    has_business_kw = any(kw in bio for kw in business_keywords)

    # ── Category 3: personal_exposure ───────────────
    # Personal email (@gmail/@yahoo etc), phone, and location all present
    has_personal_email = False
    has_phone = False
    has_location = bool(location and len(location) > 2)

    personal_domains = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "protonmail.com"]
    for f in findings:
        ftype = f.get("type", "")
        fval = str(f.get("value", "")).lower()
        if ftype == "email":
            if any(dom in fval for dom in personal_domains):
                has_personal_email = True
        elif ftype == "phone":
            has_phone = True

    # ── Category 4: anonymous ───────────────────────
    # No real name, generic username, no bio, no contact info
    no_real_name = not display_name or display_name == username
    no_bio = not bio or len(bio.strip()) < 5
    no_contact = not any(f.get("type") in ("email", "phone") for f in findings)
    is_anonymous_username = any(x in username for x in ["bot", "anon", "user", "guest", "temp"]) or len(username) < 3

    if is_linkedin or has_business_kw:
        return {
            "category": "public_business",
            "label": "Public Business Profile",
            "score_modifier": 0.0,
            "description": "Professional business profile; public contact details are lower risk."
        }
    elif has_personal_email and has_phone and has_location:
        return {
            "category": "personal_exposure",
            "label": "Personal Exposure Profile",
            "score_modifier": 10.0,
            "description": "High privacy risk: personal contact info, location, and identity are fully exposed."
        }
    elif no_real_name and no_bio and no_contact and (is_anonymous_username or not username):
        return {
            "category": "anonymous",
            "label": "Anonymous / Private Profile",
            "score_modifier": 0.0,
            "description": "Low privacy risk: anonymous or bot profile with no PII exposed."
        }
    else:
        return {
            "category": "professional_public",
            "label": "Professional Public Profile",
            "score_modifier": 0.0,
            "description": "Standard public profile exposing basic identity and professional details."
        }

