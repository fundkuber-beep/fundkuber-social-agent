import os, json
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
WEBSITE = "https://fundkuberai.com/"
PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")
USER_TOKEN = os.getenv("META_ACCESS_TOKEN")
PUBLIC_URL = os.getenv("PUBLIC_IMAGE_URL")
GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v26.0")

if not USER_TOKEN or not PAGE_ID or not PUBLIC_URL:
    raise SystemExit("Missing META_ACCESS_TOKEN, FACEBOOK_PAGE_ID, or PUBLIC_IMAGE_URL.")

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
    # Accept either a Page token or a User token in META_ACCESS_TOKEN.
    # If it is a User token, obtain the Page token for the configured Page.
    r = requests.get(
        f"https://graph.facebook.com/{GRAPH_VERSION}/me/accounts",
        params={
            "fields": "id,name,access_token",
            "access_token": USER_TOKEN,
        },
        timeout=30,
    )
    if r.ok:
        for page in r.json().get("data", []):
            if str(page.get("id")) == str(PAGE_ID) and page.get("access_token"):
                return page["access_token"]
    return USER_TOKEN

PAGE_TOKEN = get_page_token()

# Facebook Page publish only.
# Instagram publishing is intentionally disabled for now while its authentication
# is being fixed separately.
r = requests.post(
    f"https://graph.facebook.com/{GRAPH_VERSION}/{PAGE_ID}/photos",
    data={
        "url": PUBLIC_URL,
        "caption": cap,
        "access_token": PAGE_TOKEN,
    },
    timeout=60,
)

if not r.ok:
    raise SystemExit("Facebook publishing failed. " + graph_error(r))

print("Facebook published:", r.json())
print("Instagram publishing skipped intentionally; authentication will be fixed separately.")
