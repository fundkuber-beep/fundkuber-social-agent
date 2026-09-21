import os, json, random, time
from pathlib import Path
import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
PHOTO_URL = 'https://ik.imagekit.io/lv4s9n4qr/WhatsApp%20Image%202026-09-21%20at%2008.52.26.jpeg'
WEBSITE = 'https://fundkuberai.com/'
CONTACT = '7982475291'
PAGE_ID = os.getenv('FACEBOOK_PAGE_ID', '1366758593181134')
TOKEN = os.getenv('META_ACCESS_TOKEN')
IG_ID = os.getenv('INSTAGRAM_BUSINESS_ACCOUNT_ID')
SLOT = os.getenv('POST_SLOT', 'morning')

FALLBACKS = {
 'morning': [('SIP ka asli advantage sirf amount nahi, discipline hai.', 'Long-term investing mein consistency aur patience ka role important hota hai.'), ('Goal ke bina investment plan adhura ho sakta hai.', 'Pehle goal, phir time horizon, phir suitable investment approach.')],
 'afternoon': [('Tax planning ko last-minute kaam mat banaiye.', 'Apni income, goals aur applicable tax rules ke context mein planning ko dekhiye.'), ('Insurance aur investment ka purpose alag hota hai.', 'Protection needs aur wealth-creation goals ko alag samajhna useful ho sakta hai.')],
 'night': [('Market se pehle apna behaviour samajhiye.', 'Fear aur excitement ke beech ek written investment plan useful ho sakta hai.'), ('Har trending investment har investor ke liye nahi hota.', 'Risk, horizon aur goal ko samajhkar decision lena important hai.')]
}

def content():
    key = os.getenv('GEMINI_API_KEY')
    if key:
        prompt = 'Create a short Hindi/Hinglish financial education post for Fund Kuber. Return ONLY JSON with title, body, cta, hashtags. No guaranteed returns, no personalized advice, no buy/sell recommendation, and do not mention expense ratio.'
        try:
            r = requests.post('https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent', params={'key': key}, json={'contents':[{'parts':[{'text': prompt}]}]}, timeout=40)
            r.raise_for_status()
            t = r.json()['candidates'][0]['content']['parts'][0]['text'].strip()
            if t.startswith('```'): t = t.split('\n', 1)[1].rsplit('```', 1)[0]
            return json.loads(t)
        except Exception as e: print('Gemini fallback:', e)
    title, body = random.choice(FALLBACKS[SLOT])
    return {'title': title, 'body': body, 'cta': 'Apne financial goals par baat karne ke liye Fund Kuber se connect karein.', 'hashtags': ['#FundKuber','#MutualFunds','#SIP','#FinancialPlanning','#PersonalFinance']}

def font(size, bold=False):
    p = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    return ImageFont.truetype(p, size)

def wrap(draw, text, f, width):
    lines, cur = [], ''
    for word in text.split():
        test = (cur + ' ' + word).strip()
        if draw.textbbox((0,0), test, font=f)[2] <= width: cur = test
        else: lines.append(cur); cur = word
    if cur: lines.append(cur)
    return lines

def make_image(post):
    r = requests.get(PHOTO_URL, timeout=30); r.raise_for_status()
    im = Image.new('RGB', (1080,1350), 'white'); d = ImageDraw.Draw(im)
    d.rectangle((0,0,1080,180), fill=(245,245,245))
    d.text((60,45), 'FUND KUBER', font=font(58,True), fill=(20,20,20))
    d.text((62,112), WEBSITE.replace('https://',''), font=font(28), fill=(70,70,70))
    advisor = ImageOps.fit(Image.open(__import__('io').BytesIO(r.content)).convert('RGB'), (330,430), centering=(.5,.35))
    im.paste(advisor,(690,220))
    y=250; tf=font(60,True); bf=font(34)
    for line in wrap(d,post['title'],tf,580): d.text((60,y),line,font=tf,fill=(15,15,15)); y+=74
    y+=30
    for line in wrap(d,post['body'],bf,580): d.text((60,y),line,font=bf,fill=(55,55,55)); y+=48
    y=max(y,700); d.text((60,y),'Connect with Fund Kuber',font=font(32,True),fill=(15,15,15)); y+=50
    d.text((60,y),CONTACT,font=font(28),fill=(55,55,55)); y+=40; d.text((60,y),WEBSITE,font=font(26),fill=(55,55,55))
    d.text((60,1250),'Educational content only. Mutual fund investments are subject to market risks.',font=font(18),fill=(90,90,90))
    im.save(ROOT/'post.jpg', quality=92)

def publish(post):
    public_url = os.getenv('PUBLIC_IMAGE_URL')
    if not TOKEN or not public_url:
        print('Publishing skipped: Meta credentials or public image URL missing.'); return
    cap = post['title']+'\n\n'+post['body']+'\n\n'+post['cta']+'\n\n'+WEBSITE+'\n\n'+' '.join(post['hashtags'])
    r=requests.post('https://graph.facebook.com/v23.0/'+PAGE_ID+'/photos',data={'url':public_url,'caption':cap,'access_token':TOKEN},timeout=45); r.raise_for_status()
    r=requests.post('https://graph.facebook.com/v23.0/'+IG_ID+'/media',data={'image_url':public_url,'caption':cap,'access_token':TOKEN},timeout=45); r.raise_for_status()
    cid=r.json()['id']; time.sleep(5)
    r=requests.post('https://graph.facebook.com/v23.0/'+IG_ID+'/media_publish',data={'creation_id':cid,'access_token':TOKEN},timeout=45); r.raise_for_status()

post=content(); (ROOT/'post.json').write_text(json.dumps(post,ensure_ascii=False,indent=2),encoding='utf-8'); make_image(post); publish(post); print(json.dumps(post,ensure_ascii=False))