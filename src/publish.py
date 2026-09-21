import os, json, sys, time
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
WEBSITE = "https://fundkuberai.com/"
PAGE_ID = os.getenv("FACEBOOK_PAGE_ID", "").strip()
IG_ID = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "").strip()
IG_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()
USER_TOKEN = os.getenv("META_ACCESS_TOKEN", "").strip()
PUBLIC_URL = os.getenv("PUBLIC_IMAGE_URL", "").strip()
GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v26.0")
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"
IG_GRAPH = f"https://graph.instagram.com/{GRAPH_VERSION}"
IMAGE_PATH = Path(os.getenv("IMAGE_PATH", ROOT / "post.jpg"))

missing = [
    name
    for name, value in (
        ("META_ACCESS_TOKEN", USER_TOKEN),
        ("FACEBOOK_PAGE_ID", PAGE_ID),
        ("PUBLIC_IMAGE_URL", PUBLIC_URL),
    )
    if not value
]
if missing:
    raise SystemExit("Missing required environment values: " + ", ".join(missing))

post = json.loads((ROOT / "post.json").read_text(encoding="utf-8"))
cap = (
    post["title"]
    + "\n\n"
    + post["body"]
    + "\n\n"
    + post["cta"]
    + "\n\n"
    + WEBSITE
    + "\n\n"
    + " ".join(post["hashtags"])
)


def graph_error(resp):
    try:
        data = resp.json()
    except Exception:
        data = {"raw": resp.text[:1000]}
    return f"HTTP {resp.status_code}: {json.dumps(data, ensure_ascii=False)}"


def get_page_token():
    """Return a token that can post as the configured Page, or exit with a clear reason.

    META_ACCESS_TOKEN may be a Page token (posts directly) or a User token (the
    Page token is looked up through /me/accounts). Tokens are never printed.
    """
    me = requests.get(
        f"{GRAPH}/me",
        params={"fields": "id,name", "access_token": USER_TOKEN},
        timeout=30,
    )
    if not me.ok:
        raise SystemExit(
            "META_ACCESS_TOKEN was rejected by Meta (expired, revoked or malformed). "
            "Generate a new token. " + graph_error(me)
        )
    me_data = me.json()
    print(f"Token identity: {me_data.get('name')} (id {me_data.get('id')})")

    if str(me_data.get("id")) == PAGE_ID:
        print("META_ACCESS_TOKEN is a Page token for the configured Page.")
        return USER_TOKEN

    accounts = requests.get(
        f"{GRAPH}/me/accounts",
        params={"fields": "id,name,access_token", "limit": 100, "access_token": USER_TOKEN},
        timeout=30,
    )
    if not accounts.ok:
        raise SystemExit(
            "Could not list Pages for this token; it probably lacks pages_show_list. "
            + graph_error(accounts)
        )
    pages = accounts.json().get("data", [])
    for page in pages:
        if str(page.get("id")) == PAGE_ID and page.get("access_token"):
            print(f"Using Page token for '{page.get('name')}' ({PAGE_ID}).")
            return page["access_token"]

    visible = ", ".join(f"{p.get('name')} ({p.get('id')})" for p in pages) or "none"
    raise SystemExit(
        f"FACEBOOK_PAGE_ID {PAGE_ID} is not a Page this token can manage. "
        f"Pages visible to the token: {visible}. Check the FACEBOOK_PAGE_ID secret, "
        "that the token's account has Full control of the Page, and that the token "
        "has pages_show_list, pages_manage_posts and pages_read_engagement."
    )


def publish_facebook(page_token):
    data = {"caption": cap, "access_token": page_token}
    if IMAGE_PATH.is_file():
        with IMAGE_PATH.open("rb") as image:
            r = requests.post(
                f"{GRAPH}/{PAGE_ID}/photos",
                data=data,
                files={"source": (IMAGE_PATH.name, image, "image/jpeg")},
                timeout=120,
            )
    else:
        r = requests.post(
            f"{GRAPH}/{PAGE_ID}/photos",
            data={**data, "url": PUBLIC_URL},
            timeout=120,
        )
    if not r.ok:
        raise SystemExit("Facebook publishing failed. " + graph_error(r))
    print("Facebook published:", r.json())


def resolve_instagram_id(page_token):
    """Ask the Page which Instagram account is linked to it.

    The linked account is authoritative; the INSTAGRAM_BUSINESS_ACCOUNT_ID secret is
    only used as a fallback when the lookup returns nothing.
    """
    r = requests.get(
        f"{GRAPH}/{PAGE_ID}",
        params={
            "fields": "instagram_business_account{id,username}",
            "access_token": page_token,
        },
        timeout=30,
    )
    if not r.ok:
        print("Could not look up the linked Instagram account. " + graph_error(r))
        return IG_ID
    linked = r.json().get("instagram_business_account")
    if not linked:
        print(
            "No Instagram account is linked to this Facebook Page. Convert the account "
            "to Business/Creator and link it under Instagram Settings > Account type "
            "and tools > Connect to a Facebook Page."
        )
        return IG_ID
    if IG_ID and str(linked["id"]) != IG_ID:
        print(
            "INSTAGRAM_BUSINESS_ACCOUNT_ID does not match the account linked to the Page; "
            f"using the linked account @{linked.get('username')} instead."
        )
    else:
        print(f"Linked Instagram account: @{linked.get('username')}")
    return str(linked["id"])


def publish_instagram(base, node, token):
    """Publish the image to Instagram.

    base/node/token select the API flavour: Facebook login uses graph.facebook.com
    with a Page token and the Instagram account id; Instagram login uses
    graph.instagram.com with an Instagram user token and the node "me".
    """
    r = requests.post(
        f"{base}/{node}/media",
        data={"image_url": PUBLIC_URL, "caption": cap, "access_token": token},
        timeout=60,
    )
    if not r.ok:
        raise RuntimeError("Instagram media creation failed. " + graph_error(r))
    creation_id = r.json()["id"]

    for _ in range(12):
        s = requests.get(
            f"{base}/{creation_id}",
            params={"fields": "status_code", "access_token": token},
            timeout=30,
        )
        status = s.json().get("status_code") if s.ok else None
        if status == "FINISHED":
            break
        if status == "ERROR":
            raise RuntimeError("Instagram media processing failed. " + graph_error(s))
        time.sleep(5)

    p = requests.post(
        f"{base}/{node}/media_publish",
        data={"creation_id": creation_id, "access_token": token},
        timeout=60,
    )
    if not p.ok:
        raise RuntimeError("Instagram publishing failed. " + graph_error(p))
    print("Instagram published:", p.json())


PAGE_TOKEN = get_page_token()
publish_facebook(PAGE_TOKEN)

if IG_TOKEN:
    print("Instagram: using INSTAGRAM_ACCESS_TOKEN (Instagram login).")
    ig_call = (IG_GRAPH, "me", IG_TOKEN)
else:
    ig_id = resolve_instagram_id(PAGE_TOKEN)
    ig_call = (GRAPH, ig_id, PAGE_TOKEN) if ig_id else None

if ig_call:
    try:
        publish_instagram(*ig_call)
    except Exception as exc:
        # Facebook already succeeded; surface Instagram problems without failing the run.
        print(f"::warning title=Instagram publish failed::{exc}")
        print(f"Instagram publish failed: {exc}", file=sys.stderr)
else:
    print("No Instagram account available; skipping Instagram.")
