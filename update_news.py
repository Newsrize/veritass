import os, json, requests, re, time
from datetime import datetime, timedelta

NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

PAYS = [
    {"id": "monde",  "query": "geopolitics war economy 2026", "lang": "en"},
    {"id": "france", "query": "France politique economie 2026", "lang": "fr"},
    {"id": "usa",    "query": "Trump United States politics 2026", "lang": "en"},
    {"id": "chine",  "query": "China Xi economy Taiwan 2026", "lang": "en"},
    {"id": "russie", "query": "Russia Ukraine war NATO 2026", "lang": "en"},
    {"id": "iran",   "query": "Iran Middle East nuclear 2026", "lang": "en"},
]

IMGS = {
    "monde":  "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&q=80",
    "france": "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?w=800&q=80",
    "usa":    "https://images.unsplash.com/photo-1485738422979-f5c462d49f74?w=800&q=80",
    "chine":  "https://images.unsplash.com/photo-1547981609-4b6bfe67ca0b?w=800&q=80",
    "russie": "https://images.unsplash.com/photo-1513326738677-b964603b136d?w=800&q=80",
    "iran":   "https://images.unsplash.com/photo-1527576539890-dfa815648363?w=800&q=80",
}

EXCLUS = ["essay","draft","tutorial","subscribe","newsletter","podcast","show hn","hili dialogue","market report","market size","market research","global market","forecasted","billion market"]

def normalize(t):
    return re.sub(r'\s+', ' ', (t or "").lower().strip())[:80]

def is_valid(title, desc):
    if not title or title == "[Removed]" or len(title) < 20:
        return False
    text = (title + " " + (desc or "")).lower()
    return not any(m in text for m in EXCLUS)

def get_articles(query, lang):
    try:
        r = requests.get("https://newsapi.org/v2/everything", params={
            "q": query, "language": lang, "sortBy": "publishedAt",
            "pageSize": 5, "apiKey": NEWSAPI_KEY,
            "from": (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        }, timeout=10)
        if r.status_code == 200:
            arts = [a for a in r.json().get("articles", []) if is_valid(a.get("title"), a.get("description"))]
            seen, out = set(), []
            for a in arts:
                k = normalize(a["title"])
                if k not in seen:
                    seen.add(k)
                    out.append(a)
            return out
    except Exception as e:
        print(f"  NewsAPI: {e}")
    return []

def gemini_json(prompt, retries=3):
    for attempt in range(retries):
        for model in ["gemini-2.0-flash", "gemini-1.5-flash"]:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY}"
            try:
                r = requests.post(url, json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2000}
                }, timeout=45)
                if r.status_code == 200:
                    text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                    m = re.search(r'\{[\s\S]*\}', text)
                    if m:
                        return json.loads(m.group())
                elif r.status_code == 429:
                    wait = 30 * (attempt + 1)
                    print(f"  Rate limit, attente {wait}s...")
                    time.sleep(wait)
                    break  # Sortir de la boucle models et réessayer
                else:
                    print(f"  {model}: HTTP {r.status_code}")
            except Exception as e:
                print(f"  {model}: {e}")
    return None

def analyser(titre, desc, pays_id):
    prompt = f"""You are a journalist. Translate and analyze this news. Return ONLY valid JSON.

Title: {titre}
Description: {desc[:300]}
Region: {pays_id}

JSON to return (fill ALL fields with real content):
{{
  "titre_fr": "titre français max 12 mots",
  "titre_en": "english title max 12 words",
  "titre_zh": "中文标题最多12字",
  "resume_fr": "Résumé 3 phrases français.",
  "resume_en": "Summary 3 sentences English.",
  "resume_zh": "摘要3句中文。",
  "analyse_fr": "Analyse 5 phrases français avec contexte et enjeux.",
  "analyse_en": "Analysis 5 sentences English with context and stakes.",
  "analyse_zh": "分析5句中文含背景和影响。",
  "categorie": "Géopolitique",
  "s1_fr": "secteur financier précis",
  "s1_en": "precise financial sector",
  "s1_zh": "具体金融行业",
  "s1_effet_fr": "Impact sur ce secteur en 1 phrase.",
  "s1_effet_en": "Impact on this sector in 1 sentence.",
  "s1_effet_zh": "对该行业影响一句话。",
  "s1_hausse": true,
  "s2_fr": "second secteur différent",
  "s2_en": "second different sector",
  "s2_zh": "第二个不同行业",
  "s2_effet_fr": "Impact secteur 2 en 1 phrase.",
  "s2_effet_en": "Impact sector 2 in 1 sentence.",
  "s2_effet_zh": "第二行业影响一句话。",
  "s2_hausse": false
}}"""

    result = gemini_json(prompt)
    if not result:
        return None
    if not result.get("titre_en") or not result.get("resume_en") or len(result.get("resume_fr","")) < 30:
        print(f"  ⚠ Champs insuffisants")
        return None
    return result

def load_existing():
    try:
        with open("news_data.json", "r", encoding="utf-8") as f:
            return json.load(f).get("articles", {})
    except:
        return {}

def clean(data):
    cutoff = datetime.now() - timedelta(days=180)  # 6 mois
    cleaned = {}
    for pays, arts in data.items():
        seen, kept = set(), []
        for a in arts:
            # Garder seulement si traductions présentes
            if not a.get("titre_en") or len(a.get("titre_en","")) < 3:
                continue
            if not a.get("resume_en") or len(a.get("resume_en","")) < 10:
                continue
            # Vérifier date (6 mois max)
            try:
                d = datetime.strptime(a.get("date","2020-01-01"), "%Y-%m-%d")
                if d < cutoff:
                    continue
            except:
                pass
            k = normalize(a.get("titre_original") or a.get("titre",""))
            if k in seen:
                continue
            seen.add(k)
            kept.append(a)
        kept.sort(key=lambda x: x.get("created_at",""), reverse=True)
        cleaned[pays] = kept[:20]
    return cleaned

def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Démarrage...")
    existing = clean(load_existing())
    new_articles = {}

    for pays in PAYS:
        pid = pays["id"]
        print(f"\n→ {pid.upper()}")
        bruts = get_articles(pays["query"], pays["lang"])
        existing_titles = {normalize(a.get("titre_original") or a.get("titre",""))
                          for a in existing.get(pid, [])}

        nouveaux = []
        for art in bruts:
            if len(nouveaux) >= 2:  # Max 2 nouveaux par pays pour éviter rate limit
                break
            titre = (art.get("title") or "").strip()
            if not titre or normalize(titre) in existing_titles:
                continue
            desc = (art.get("description") or "")[:300]
            source = art.get("source", {}).get("name", "")
            date_raw = (art.get("publishedAt") or "")[:10]
            url_art = art.get("url", "#")
            image = art.get("urlToImage") or IMGS.get(pid, "")

            print(f"  → {titre[:60]}...")
            r = analyser(titre, desc, pid)

            if not r:
                print(f"  ❌ Ignoré")
                continue

            print(f"  ✅ OK ({len(r.get('resume_fr',''))}c FR / {len(r.get('resume_en',''))}c EN)")
            nouveaux.append({
                "id": f"{pid}_{abs(hash(titre)) % 1000000}",
                "titre": r.get("titre_fr", titre),
                "titre_en": r.get("titre_en", titre),
                "titre_zh": r.get("titre_zh", titre),
                "titre_original": titre,
                "resume": r.get("resume_fr", desc),
                "resume_en": r.get("resume_en", desc),
                "resume_zh": r.get("resume_zh", desc),
                "analyse_detaillee": r.get("analyse_fr", ""),
                "analyse_en": r.get("analyse_en", ""),
                "analyse_zh": r.get("analyse_zh", ""),
                "categorie": r.get("categorie", "Actualité"),
                "source": source, "url": url_art, "image": image,
                "date": date_raw, "pays": pid,
                "badges": [
                    {"label": f"{'▲' if r.get('s1_hausse') else '▼'} {r.get('s1_fr','')}", "hausse": r.get("s1_hausse", False)},
                    {"label": f"{'▲' if r.get('s2_hausse') else '▼'} {r.get('s2_fr','')}", "hausse": r.get("s2_hausse", False)},
                ],
                "impact_marches": [
                    {"secteur_fr": r.get("s1_fr",""), "secteur_en": r.get("s1_en",""), "secteur_zh": r.get("s1_zh",""),
                     "effet_fr": r.get("s1_effet_fr",""), "effet_en": r.get("s1_effet_en",""), "effet_zh": r.get("s1_effet_zh",""),
                     "hausse": r.get("s1_hausse", False)},
                    {"secteur_fr": r.get("s2_fr",""), "secteur_en": r.get("s2_en",""), "secteur_zh": r.get("s2_zh",""),
                     "effet_fr": r.get("s2_effet_fr",""), "effet_en": r.get("s2_effet_en",""), "effet_zh": r.get("s2_effet_zh",""),
                     "hausse": r.get("s2_hausse", False)},
                ],
                "created_at": datetime.now().isoformat()
            })
            # Pause entre chaque article pour éviter le rate limit
            time.sleep(5)

        old = [a for a in existing.get(pid, [])
               if normalize(a.get("titre_original") or a.get("titre",""))
               not in {normalize(n.get("titre_original") or n.get("titre","")) for n in nouveaux}]

        # Fusionner : nouveaux en tête + anciens conservés (6 mois)
        new_articles[pid] = (nouveaux + old)[:20]
        print(f"  Total: {len(nouveaux)} nouveaux + {len(old)} conservés = {len(new_articles[pid])}")

    with open("news_data.json", "w", encoding="utf-8") as f:
        json.dump({
            "last_updated": datetime.now().strftime("%d/%m/%Y à %Hh%M"),
            "articles": new_articles
        }, f, ensure_ascii=False, indent=2)

    total = sum(len(v) for v in new_articles.values())
    print(f"\n✅ Terminé — {total} articles (conservation 6 mois)")

if __name__ == "__main__":
    main()
