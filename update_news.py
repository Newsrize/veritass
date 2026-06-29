import os, json, requests, re, time
from datetime import datetime, timedelta

NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

PAYS = [
    {"id": "monde",  "query": "geopolitics war economy 2026", "lang": "en"},
    {"id": "france", "query": "France politique economie 2026", "lang": "fr"},
    {"id": "usa",    "query": "Trump United States 2026", "lang": "en"},
    {"id": "chine",  "query": "China Xi economy 2026", "lang": "en"},
    {"id": "russie", "query": "Russia Ukraine war 2026", "lang": "en"},
    {"id": "iran",   "query": "Iran Middle East war 2026", "lang": "en"},
]

IMGS = {
    "monde":  "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&q=80",
    "france": "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?w=800&q=80",
    "usa":    "https://images.unsplash.com/photo-1485738422979-f5c462d49f74?w=800&q=80",
    "chine":  "https://images.unsplash.com/photo-1547981609-4b6bfe67ca0b?w=800&q=80",
    "russie": "https://images.unsplash.com/photo-1513326738677-b964603b136d?w=800&q=80",
    "iran":   "https://images.unsplash.com/photo-1527576539890-dfa815648363?w=800&q=80",
}

def normalize(t):
    return re.sub(r'\s+', ' ', (t or "").lower().strip())[:80]

def get_articles(query, lang):
    try:
        r = requests.get("https://newsapi.org/v2/everything", params={
            "q": query, "language": lang, "sortBy": "publishedAt",
            "pageSize": 10, "apiKey": NEWSAPI_KEY,
            "from": (datetime.now() - timedelta(days=4)).strftime("%Y-%m-%d")
        }, timeout=10)
        if r.status_code == 200:
            arts = [a for a in r.json().get("articles", [])
                    if a.get("title") and a["title"] != "[Removed]" and len(a.get("title","")) > 15]
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

def gemini_json(prompt):
    for model in ["gemini-2.0-flash", "gemini-1.5-flash"]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY}"
        try:
            r = requests.post(url, json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2000}
            }, timeout=40)
            if r.status_code == 200:
                text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                # Extraire JSON même s'il y a du texte autour
                m = re.search(r'\{[\s\S]*\}', text)
                if m:
                    return json.loads(m.group())
            elif r.status_code == 429:
                print(f"  Rate limit, attente 10s...")
                time.sleep(10)
        except Exception as e:
            print(f"  {model}: {e}")
    return None

def analyser(titre, desc, pays_id):
    prompt = f"""Translate and analyze this news article. Return ONLY valid JSON, nothing else.

Title: {titre}
Description: {desc[:400]}
Region: {pays_id}

Return this JSON with ALL fields filled:
{{
  "titre_fr": "titre en français (max 12 mots)",
  "titre_en": "title in English (max 12 words)",
  "titre_zh": "中文标题（最多12字）",
  "resume_fr": "Résumé en français en 3 phrases.",
  "resume_en": "Summary in English in 3 sentences.",
  "resume_zh": "中文摘要，3句话。",
  "analyse_fr": "Analyse en français en 5 phrases avec contexte, enjeux et perspectives.",
  "analyse_en": "Analysis in English in 5 sentences with context, stakes and prospects.",
  "analyse_zh": "中文分析，5句话，包括背景、影响和前景。",
  "categorie": "Géopolitique",
  "s1_fr": "Pétrole Brent",
  "s1_en": "Brent Crude Oil",
  "s1_zh": "布伦特原油",
  "s1_effet_fr": "Phrase expliquant l'impact sur ce secteur.",
  "s1_effet_en": "Sentence explaining impact on this sector.",
  "s1_effet_zh": "解释对该行业影响的句子。",
  "s1_hausse": true,
  "s2_fr": "Marchés obligataires",
  "s2_en": "Bond markets",
  "s2_zh": "债券市场",
  "s2_effet_fr": "Phrase pour le deuxième secteur.",
  "s2_effet_en": "Sentence for second sector.",
  "s2_effet_zh": "第二行业的解释。",
  "s2_hausse": false
}}"""

    result = gemini_json(prompt)
    if not result:
        return None
    # Vérification minimale : juste titre_en et resume_en
    if not result.get("titre_en") or not result.get("resume_en"):
        print(f"  ⚠ Champs EN manquants")
        return None
    return result

def load_existing():
    try:
        with open("news_data.json", "r", encoding="utf-8") as f:
            return json.load(f).get("articles", {})
    except:
        return {}

def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Démarrage...")
    existing = load_existing()
    # Nettoyer les anciens articles sans traductions
    for pays in existing:
        existing[pays] = [a for a in existing.get(pays, [])
                          if a.get("titre_en") and len(a.get("titre_en","")) > 3
                          and a.get("resume_en") and len(a.get("resume_en","")) > 10]

    new_articles = {}
    for pays in PAYS:
        pid = pays["id"]
        print(f"\n→ {pid.upper()}")
        bruts = get_articles(pays["query"], pays["lang"])
        existing_titles = {normalize(a.get("titre_original") or a.get("titre",""))
                          for a in existing.get(pid, [])}

        nouveaux = []
        for art in bruts:
            if len(nouveaux) >= 3:
                break
            titre = (art.get("title") or "").strip()
            if normalize(titre) in existing_titles:
                continue
            desc = (art.get("description") or "")[:400]
            source = art.get("source", {}).get("name", "")
            date_raw = (art.get("publishedAt") or "")[:10]
            url_art = art.get("url", "#")
            image = art.get("urlToImage") or IMGS.get(pid, "")

            print(f"  → {titre[:60]}...")
            r = analyser(titre, desc, pid)
            if not r:
                print(f"  ❌ Ignoré")
                continue

            print(f"  ✅ OK")
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
            time.sleep(2)  # éviter rate limit Gemini

        old = existing.get(pid, [])
        combined = nouveaux + [a for a in old if normalize(a.get("titre_original") or a.get("titre",""))
                               not in {normalize(n.get("titre_original") or n.get("titre","")) for n in nouveaux}]
        new_articles[pid] = combined[:20]
        print(f"  Total: {len(nouveaux)} nouveaux + {len(old)} conservés = {len(new_articles[pid])}")

    with open("news_data.json", "w", encoding="utf-8") as f:
        json.dump({"last_updated": datetime.now().strftime("%d/%m/%Y à %Hh%M"),
                   "articles": new_articles}, f, ensure_ascii=False, indent=2)

    total = sum(len(v) for v in new_articles.values())
    print(f"\n✅ {total} articles au total")

if __name__ == "__main__":
    main()
