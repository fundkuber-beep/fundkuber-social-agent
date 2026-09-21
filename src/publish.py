import os, json, time
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
WEBSITE = "https://fundkuberai.com/"
PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")
USER_TOKEN = os.getenv("META_ACCESS_TOKEN")
IG_ID = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")
PUBLIC_URL = os.getenv("PUBLIC_IMAGE_URL")
GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v26.0")

if not USER_TOKEN or not PAGE_ID or not PUBLIC_URL:
    raise SystemExit("Missing META_ACCESS_TOKEN, FACEBOOK_PAGE_ID, or PUBLIC_IMAGE_URL.")

post = json.loads((ROOT / "post.json").read_text(encoding="utf-8"))
cap = post["title"] + "\n\n" + post["body"] + "\n\n" + post["cta"] + "\n\n" + WEBSITE + "\n\n" + " ".join(post["hashtags"])

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
        params={"fields": "id,name,access_token,instagram_business_account", "access_token": USER_TOKEN},
        timeout=30,
    )
    if r.ok:
        for page in r.json().get("data", []):
            if str(page.get("id")) == str(PAGE_ID) and page.get("access_token"):
                return page["access_token"], page.get("instagram_business_account", {}).get("id") if isinstance(page.get("instagram_business_account"), dict) else None
    return USER_TOKEN, None

PAGE_TOKEN, DISCOVERED_IG_ID = get_page_token()
if not IG_ID:
    IG_ID = DISCOVERED_IG_ID

# Facebook Page publish
r = requests.post(
    f"https://graph.facebook.com/{GRAPH_VERSION}/{PAGE_ID}/photos",
    data={"url": PUBLIC_URL, "caption": cap, "access_token": PAGE_TOKEN},
    timeout=60,
)
if not r.ok:
    raise SystemExit("Facebook publishing failed. " + graph_error(r))
print("Facebook published:", r.json())

# Instagram publish
if not IG_ID:
    print("Instagram skipped: no Instagram Business Account ID was supplied or discovered.")
    raise SystemExit(0)

r = requests.post(
    f"https://graph.facebook.com/{GRAPH_VERSION}/{IG_ID}/media",
    data={"image_url": PUBLIC_URL, "caption": cap, "access_token": PAGE_TOKEN},
    timeout=60,
)
if not r.ok:
    raise SystemExit("Instagram media creation failed. " + graph_error(r))

creation_id = r.json()["id"]
for _ in range(12):
    time.sleep(5)
    check = requests.get(
        f"https://graph.facebook.com/{GRAPH_VERSION}/{creation_id}",
        params={"fields": "status_code,status", "access_token": PAGE_TOKEN},
        timeout=30,
    )
    if check.ok:
        status = check.json().get("status_code")
        if status in ("FINISHED", "PUBLISHED"):
            break
        if status == "ERROR":
            raise SystemExit("Instagram media processing failed. " + check.text[:1000])

r = requests.post(
    f"https://graph.facebook.com/{GRAPH_VERSION}/{IG_ID}/media_publish",
    data={"creation_id": creation_id, "access_token": PAGE_TOKEN},
    timeout=60,
)
if not r.ok:
    raise SystemExit("Instagram publishing failed. " + graph_error(r))
print("Instagram published:", r.json())
