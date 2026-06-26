import os, json, requests, re
from datetime import datetime, timedelta

NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

PAYS = [
    {"id": "monde",  "query": "international diplomacy war economy 2026", "lang": "en"},
    {"id": "france", "query": "France Macron politique économie 2026", "lang": "fr"},
    {"id": "usa",    "query": "Trump United States policy 2026", "lang": "en"},
    {"id": "chine",  "query": "China Xi Jinping economy 2026", "lang": "en"},
    {"id": "russie", "query": "Russia Putin Ukraine war 2026", "lang": "en"},
    {"id": "iran",   "query": "Iran nuclear Middle East 2026", "lang": "en"},
]

FALLBACK_IMAGES = {
    "monde":  "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&q=80",
    "france": "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?w=800&q=80",
    "usa":    "https://images.unsplash.com/photo-1485738422979-f5c462d49f74?w=800&q=80",
    "chine":  "https://images.unsplash.com/photo-1547981609-4b6bfe67ca0b?w=800&q=80",
    "russie": "https://images.unsplash.com/photo-1513326738677-b964603b136d?w=800&q=80",
    "iran":   "https://images.unsplash.com/photo-1527576539890-dfa815648363?w=800&q=80",
}

MOTS_EXCLUS = ["essay","draft","how to","tutorial","subscribe","newsletter","my thoughts","podcast","memoir","hili dialogue","show hn:","links 6/"]

def is_valid(title, desc):
    if not title or title == "[Removed]" or len(title) < 20:
        return False
    text = (title + " " + (desc or "")).lower()
    return not any(m in text for m in MOTS_EXCLUS)

def normalize(title):
    return re.sub(r'\s+', ' ', title.lower().strip())[:80]

def get_articles(query, lang, nb=8):
    try:
        r = requests.get("https://newsapi.org/v2/everything", params={
            "q": query, "language": lang, "sortBy": "publishedAt",
            "pageSize": nb, "apiKey": NEWSAPI_KEY,
            "from": (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
        }, timeout=10)
        if r.status_code == 200:
            arts = [a for a in r.json().get("articles", []) if is_valid(a.get("title"), a.get("description"))]
            seen, unique = set(), []
            for a in arts:
                k = normalize(a.get("title",""))
                if k not in seen:
                    seen.add(k)
                    unique.append(a)
            return unique
    except Exception as e:
        print(f"  NewsAPI error: {e}")
    return []

def gemini(prompt):
    for model in ["gemini-2.0-flash", "gemini-1.5-flash"]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY}"
        try:
            r = requests.post(url, json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 3500}
            }, timeout=40)
            if r.status_code == 200:
                text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                # Nettoyer markdown
                if "```" in text:
                    for p in text.split("```"):
                        p = p.replace("json","",1).strip()
                        if p.startswith("{"): text = p; break
                return json.loads(text)
        except Exception as e:
            print(f"  {model} error: {e}")
    return None

def analyser(titre, desc, pays_id):
    prompt = f"""You are a journalist for Veritass.fr, a French news site.

Article:
TITLE: {titre}
DESCRIPTION: {desc}
REGION: {pays_id}

Return ONLY this exact JSON (no markdown, no text before or after):
{{
  "titre_fr": "French title max 15 words",
  "titre_en": "English title max 15 words",
  "titre_zh": "中文标题最多15字",
  "resume_fr": "4 sentences in French: main fact, context, immediate consequence, reaction.",
  "resume_en": "Same 4 sentences in English.",
  "resume_zh": "同样的4句话，中文。",
  "analyse_fr": "7 sentences in French: historical context, stakes, causes, short-term consequences, medium-term, long-term, positions of parties.",
  "analyse_en": "Same 7 sentences in English.",
  "analyse_zh": "同样的7句话，中文。",
  "categorie": "one of: Politique,Économie,Géopolitique,Énergie,Tech,Justice,Social,Diplomatie,Environnement,Santé,Sécurité",
  "s1_nom_fr": "precise financial sector name in French (e.g. Pétrole Brent, Actions défense, CAC 40, EUR/USD, Or)",
  "s1_nom_en": "same sector in English",
  "s1_nom_zh": "同一行业中文名",
  "s1_effet_fr": "one French sentence explaining why this sector is impacted",
  "s1_effet_en": "same in English",
  "s1_effet_zh": "中文解释",
  "s1_hausse": true,
  "s2_nom_fr": "second different precise financial sector in French",
  "s2_nom_en": "same in English",
  "s2_nom_zh": "中文",
  "s2_effet_fr": "one French sentence for second sector",
  "s2_effet_en": "same in English",
  "s2_effet_zh": "中文",
  "s2_hausse": false
}}

Rules:
- ALL text fields must be filled with real content, never empty
- resume_fr minimum 100 characters
- analyse_fr minimum 300 characters
- sector names must be specific (never just "international markets")
"""
    result = gemini(prompt)
    if not result:
        return None

    # Validation
    required = ["titre_fr","titre_en","titre_zh","resume_fr","resume_en","resume_zh",
                "analyse_fr","analyse_en","analyse_zh","s1_nom_fr","s2_nom_fr"]
    for k in required:
        if not result.get(k) or len(str(result[k])) < 3:
            print(f"  ⚠ Champ manquant ou vide: {k}")
            return None
    if len(result.get("resume_fr","")) < 80:
        print(f"  ⚠ résumé trop court: {len(result.get('resume_fr',''))}")
        return None
    if len(result.get("analyse_fr","")) < 200:
        print(f"  ⚠ analyse trop courte: {len(result.get('analyse_fr',''))}")
        return None

    return result

def load_existing():
    try:
        with open("news_data.json","r",encoding="utf-8") as f:
            return json.load(f).get("articles",{})
    except:
        return {}

def clean(data, months=6, max_per=20):
    cutoff = datetime.now() - timedelta(days=months*30)
    cleaned = {}
    for pays, arts in data.items():
        seen, kept = set(), []
        for a in arts:
            # Garder seulement articles avec traductions complètes
            if not a.get("titre_en") or len(a.get("titre_en","")) < 3:
                continue
            if not a.get("resume_en") or len(a.get("resume_en","")) < 10:
                continue
            try:
                if datetime.strptime(a.get("date","2020-01-01"),"%Y-%m-%d") < cutoff:
                    continue
            except: pass
            k = normalize(a.get("titre_original") or a.get("titre",""))
            if k in seen: continue
            seen.add(k)
            kept.append(a)
        kept.sort(key=lambda x: x.get("created_at",""), reverse=True)
        cleaned[pays] = kept[:max_per]
    return cleaned

def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Démarrage...")
    existing = clean(load_existing())
    new_articles = {}

    for pays in PAYS:
        print(f"\n→ {pays['id'].upper()}")
        bruts = get_articles(pays["query"], pays["lang"])
        existing_titles = {normalize(a.get("titre_original") or a.get("titre","")) for a in existing.get(pays["id"],[])}

        nouveaux = []
        for art in bruts:
            if len(nouveaux) >= 4: break
            titre = (art.get("title") or "")[:200].strip()
            if normalize(titre) in existing_titles: continue

            desc = (art.get("description") or "")[:500].strip()
            source = art.get("source",{}).get("name","")
            date_raw = (art.get("publishedAt") or "")[:10]
            url_art = art.get("url","#")
            image = art.get("urlToImage") or FALLBACK_IMAGES.get(pays["id"],"")
            if not image or len(image)<10: image = FALLBACK_IMAGES.get(pays["id"],"")

            print(f"  → {titre[:65]}...")
            r = analyser(titre, desc, pays["id"])
            if not r:
                print(f"  ❌ Ignoré")
                continue

            print(f"  ✅ FR={len(r['resume_fr'])}c EN={len(r['resume_en'])}c ZH={len(r['resume_zh'])}c")
            nouveaux.append({
                "id": f"{pays['id']}_{abs(hash(titre))%1000000}",
                "titre": r["titre_fr"], "titre_en": r["titre_en"], "titre_zh": r["titre_zh"],
                "titre_original": titre,
                "resume": r["resume_fr"], "resume_en": r["resume_en"], "resume_zh": r["resume_zh"],
                "analyse_detaillee": r["analyse_fr"], "analyse_en": r["analyse_en"], "analyse_zh": r["analyse_zh"],
                "categorie": r["categorie"],
                "source": source, "url": url_art, "image": image, "date": date_raw, "pays": pays["id"],
                "badges": [
                    {"label": f"{'▲' if r['s1_hausse'] else '▼'} {r['s1_nom_fr']}", "hausse": r["s1_hausse"]},
                    {"label": f"{'▲' if r['s2_hausse'] else '▼'} {r['s2_nom_fr']}", "hausse": r["s2_hausse"]},
                ],
                "impact_marches": [
                    {"secteur_fr": r["s1_nom_fr"], "secteur_en": r["s1_nom_en"], "secteur_zh": r["s1_nom_zh"],
                     "effet_fr": r["s1_effet_fr"], "effet_en": r["s1_effet_en"], "effet_zh": r["s1_effet_zh"],
                     "hausse": r["s1_hausse"]},
                    {"secteur_fr": r["s2_nom_fr"], "secteur_en": r["s2_nom_en"], "secteur_zh": r["s2_nom_zh"],
                     "effet_fr": r["s2_effet_fr"], "effet_en": r["s2_effet_en"], "effet_zh": r["s2_effet_zh"],
                     "hausse": r["s2_hausse"]},
                ],
                "created_at": datetime.now().isoformat()
            })

        old = [a for a in existing.get(pays["id"],[]) if normalize(a.get("titre_original") or a.get("titre","")) not in {normalize(n.get("titre_original") or n.get("titre","")) for n in nouveaux}]
        new_articles[pays["id"]] = (nouveaux + old)[:20]
        print(f"  Total: {len(nouveaux)} nouveaux + {len(old)} conservés")

    with open("news_data.json","w",encoding="utf-8") as f:
        json.dump({"last_updated": datetime.now().strftime("%d/%m/%Y à %Hh%M"), "articles": new_articles}, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Terminé — {sum(len(v) for v in new_articles.values())} articles")

if __name__ == "__main__":
    main()
