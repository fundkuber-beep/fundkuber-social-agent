import os, json, time
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
WEBSITE = 'https://fundkuberai.com/'
PAGE_ID = os.getenv('FACEBOOK_PAGE_ID')
TOKEN = os.getenv('META_ACCESS_TOKEN')
IG_ID = os.getenv('INSTAGRAM_BUSINESS_ACCOUNT_ID')
PUBLIC_URL = os.getenv('PUBLIC_IMAGE_URL')

if not TOKEN or not PAGE_ID or not PUBLIC_URL:
    raise SystemExit('Missing META_ACCESS_TOKEN, FACEBOOK_PAGE_ID, or PUBLIC_IMAGE_URL.')

post = json.loads((ROOT/'post.json').read_text(encoding='utf-8'))
cap = post['title']+'\n\n'+post['body']+'\n\n'+post['cta']+'\n\n'+WEBSITE+'\n\n'+' '.join(post['hashtags'])

r = requests.post(
    f'https://graph.facebook.com/v23.0/{PAGE_ID}/photos',
    data={'url':PUBLIC_URL,'caption':cap,'access_token':TOKEN},
    timeout=45
)
r.raise_for_status()
print('Facebook published:', r.json())

if not IG_ID:
    print('Instagram skipped: INSTAGRAM_BUSINESS_ACCOUNT_ID is not set.')
    raise SystemExit(0)

r = requests.post(
    f'https://graph.facebook.com/v23.0/{IG_ID}/media',
    data={'image_url':PUBLIC_URL,'caption':cap,'access_token':TOKEN},
    timeout=45
)
r.raise_for_status()
creation_id = r.json()['id']
time.sleep(5)

r = requests.post(
    f'https://graph.facebook.com/v23.0/{IG_ID}/media_publish',
    data={'creation_id':creation_id,'access_token':TOKEN},
    timeout=45
)
r.raise_for_status()
print('Instagram published:', r.json())