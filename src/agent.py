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

def _parse_post(text, provider):
    if not text:
        raise RuntimeError(f"{provider} returned no text.")
    text = text.strip()
    fence = chr(96) * 3
    if text.startswith(fence):
        text = text.split("\n", 1)[1].rsplit(fence, 1)[0].strip()
    try:
        post = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"{provider} returned invalid JSON: {e}. Raw response: {text[:1500]}")
    required = {"title", "body", "cta", "hashtags"}
    if not required.issubset(post):
        raise RuntimeError(f"{provider} response is missing required post fields.")
    return post


def _generate_openai(prompt):
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")
    r = requests.post(
        "https://api.openai.com/v1/responses",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": "gpt-5.6-luna", "input": prompt},
        timeout=60,
    )
    if not r.ok:
        raise RuntimeError(f"OpenAI HTTP {r.status_code}: {r.text[:1500]}")
    data = r.json()
    text = data.get("output_text")
    if not text:
        chunks = []
        for item in data.get("output", []):
            for part in item.get("content", []):
                if isinstance(part, dict) and part.get("text"):
                    chunks.append(part["text"])
        text = "".join(chunks).strip()
    return _parse_post(text, "OpenAI")


def _generate_gemini(prompt):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "title": {"type": "STRING"},
                    "body": {"type": "STRING"},
                    "cta": {"type": "STRING"},
                    "hashtags": {"type": "ARRAY", "items": {"type": "STRING"}}
                },
                "required": ["title", "body", "cta", "hashtags"]
            }
        }
    }
    r = requests.post(
        url,
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    if not r.ok:
        raise RuntimeError(f"Gemini HTTP {r.status_code}: {r.text[:1500]}")
    data = r.json()
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError(f"Gemini returned no usable text: {json.dumps(data)[:1500]}")
    return _parse_post(text, "Gemini")


def content():
    prompt = f"""
Create ONE original social-media post for Fund Kuber for the {SLOT} slot.

Brand: Fund Kuber
Website: https://fundkuberai.com/
Contact: 7982475291
Audience: Indian retail investors
Language: natural Hindi/Hinglish, simple and professional.
Purpose: financial education + brand awareness.
Do not promise returns. Do not give personalized investment advice. Do not give buy/sell recommendations.
Do not mention expense ratio.
Do not claim to be a SEBI-registered investment adviser.
Return ONLY valid JSON with exactly these keys:
title: short headline
body: 2-4 short sentences
cta: one short call to action
hashtags: array of 5-8 hashtags
"""

    try:
        post = _generate_openai(prompt)
        print("Content provider: OpenAI")
        return post
    except Exception as openai_error:
        print(f"OpenAI failed; switching to Gemini: {openai_error}")

    try:
        post = _generate_gemini(prompt)
        print("Content provider: Gemini")
        return post
    except Exception as gemini_error:
        raise SystemExit(
            "Both content providers failed. "
            f"OpenAI: {openai_error}; Gemini: {gemini_error}"
        )

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

post=content(); (ROOT/'post.json').write_text(json.dumps(post,ensure_ascii=False,indent=2),encoding='utf-8'); make_image(post); print(json.dumps(post,ensure_ascii=False))