import os, json, requests, re, time
from datetime import datetime, timedelta

NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

PAYS = [
    {"id": "monde",  "query": "geopolitics war economy 2026", "lang": "en"},
    {"id": "france", "query": "France politique economie 2026", "lang": "fr"},
    {"id": "usa",    "query": "Trump United States politics 2026", "lang": "en"},
    {"id": "chine",  "query": "China Xi economy 2026", "lang": "en"},
    {"id": "russie", "query": "Russia Ukraine war 2026", "lang": "en"},
    {"id": "iran",   "query": "Iran Middle East 2026", "lang": "en"},
]

IMGS = {
    "monde":  "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&q=80",
    "france": "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?w=800&q=80",
    "usa":    "https://images.unsplash.com/photo-1485738422979-f5c462d49f74?w=800&q=80",
    "chine":  "https://images.unsplash.com/photo-1547981609-4b6bfe67ca0b?w=800&q=80",
    "russie": "https://images.unsplash.com/photo-1513326738677-b964603b136d?w=800&q=80",
    "iran":   "https://images.unsplash.com/photo-1527576539890-dfa815648363?w=800&q=80",
}

EXCLUS = ["market report","market size","market research","global market","forecasted","billion market",
          "show hn","hili dialogue","essay","tutorial","subscribe","podcast","fireworks","nfl","nba","sports"]

def normalize(t):
    return re.sub(r'\s+', ' ', (t or "").lower().strip())[:80]

def is_valid(title, desc):
    if not title or title == "[Removed]" or len(title) < 20:
        return False
    text = (title + " " + (desc or "")).lower()
    return not any(m in text for m in EXCLUS)

def get_one_article(query, lang):
    """Récupère UN seul article valide par pays"""
    try:
        r = requests.get("https://newsapi.org/v2/everything", params={
            "q": query, "language": lang, "sortBy": "publishedAt",
            "pageSize": 10, "apiKey": NEWSAPI_KEY,
            "from": (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        }, timeout=10)
        if r.status_code == 200:
            for a in r.json().get("articles", []):
                if is_valid(a.get("title"), a.get("description")):
                    return a
    except Exception as e:
        print(f"  NewsAPI: {e}")
    return None

def gemini_call(prompt):
    """Un seul appel Gemini avec retry"""
    for model in ["gemini-1.5-flash-latest", "gemini-1.5-flash-8b", "gemini-pro"]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY}"
        try:
            r = requests.post(url, json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 4000}
            }, timeout=60)
            if r.status_code == 200:
                text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                return text
            elif r.status_code == 429:
                print(f"  Rate limit sur {model}, essai modèle suivant dans 5s...")
                time.sleep(5)
            else:
                print(f"  {model}: HTTP {r.status_code} - {r.text[:100]}")
        except Exception as e:
            print(f"  {model}: {e}")
    return None

def analyser_tous(articles_par_pays):
    """Une seule requête Gemini pour TOUS les pays"""
    
    # Construire la liste des articles à analyser
    lines = []
    for pid, art in articles_par_pays.items():
        titre = (art.get("title") or "")[:150]
        desc = (art.get("description") or "")[:200]
        lines.append(f'PAYS:{pid}|TITRE:{titre}|DESC:{desc}')
    
    prompt = f"""You are a journalist for Veritass.fr. Translate and analyze these {len(lines)} news articles.
Return a JSON array with one object per article, in the SAME ORDER as input.

Articles:
{chr(10).join(f"{i+1}. {l}" for i,l in enumerate(lines))}

Return ONLY this JSON array (no markdown, no text):
[
  {{
    "pays": "monde",
    "titre_fr": "titre français max 10 mots",
    "titre_en": "english title max 10 words", 
    "titre_zh": "中文标题最多10字",
    "resume_fr": "Résumé 2 phrases français.",
    "resume_en": "Summary 2 sentences English.",
    "resume_zh": "摘要2句中文。",
    "analyse_fr": "Analyse 4 phrases français: contexte, enjeux, conséquences, perspectives.",
    "analyse_en": "Analysis 4 sentences English: context, stakes, consequences, prospects.",
    "analyse_zh": "分析4句中文：背景、影响、后果、前景。",
    "categorie": "Géopolitique",
    "s1_fr": "Secteur financier précis",
    "s1_en": "Precise financial sector",
    "s1_zh": "具体金融行业",
    "s1_effet_fr": "Impact en 1 phrase.",
    "s1_effet_en": "Impact in 1 sentence.",
    "s1_effet_zh": "影响一句话。",
    "s1_hausse": true,
    "s2_fr": "Second secteur différent",
    "s2_en": "Second different sector",
    "s2_zh": "第二个行业",
    "s2_effet_fr": "Impact secteur 2.",
    "s2_effet_en": "Impact sector 2.",
    "s2_effet_zh": "第二行业影响。",
    "s2_hausse": false
  }}
]

Fill all fields with real content. Return exactly {len(lines)} objects."""

    text = gemini_call(prompt)
    if not text:
        return {}
    
    # Extraire le JSON array
    m = re.search(r'\[[\s\S]*\]', text)
    if not m:
        print(f"  ⚠ Pas de JSON array trouvé dans la réponse")
        return {}
    
    try:
        results = json.loads(m.group())
        # Mapper par pays
        out = {}
        pays_list = list(articles_par_pays.keys())
        for i, obj in enumerate(results):
            if i < len(pays_list):
                pid = obj.get("pays") or pays_list[i]
                out[pid] = obj
        return out
    except Exception as e:
        print(f"  ⚠ Erreur parsing JSON: {e}")
        return {}

def load_existing():
    try:
        with open("news_data.json", "r", encoding="utf-8") as f:
            return json.load(f).get("articles", {})
    except:
        return {}

def clean(data):
    """Conserve articles valides des 6 derniers mois"""
    cutoff = datetime.now() - timedelta(days=180)
    cleaned = {}
    for pays, arts in data.items():
        seen, kept = set(), []
        for a in arts:
            if not a.get("titre_en") or len(a.get("titre_en","")) < 3:
                continue
            if not a.get("resume_en") or len(a.get("resume_en","")) < 10:
                continue
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
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Démarrage (1 requête Gemini pour tout)...")
    existing = clean(load_existing())

    # Étape 1 : collecter UN article par pays depuis NewsAPI
    articles_bruts = {}
    existing_titles = {}
    
    for pays in PAYS:
        pid = pays["id"]
        existing_titles[pid] = {normalize(a.get("titre_original") or a.get("titre",""))
                                for a in existing.get(pid, [])}
        art = get_one_article(pays["query"], pays["lang"])
        if art:
            titre = (art.get("title") or "").strip()
            if titre and normalize(titre) not in existing_titles[pid]:
                articles_bruts[pid] = art
                print(f"→ {pid.upper()}: {titre[:60]}...")
            else:
                print(f"→ {pid.upper()}: déjà en base ou invalide")
        else:
            print(f"→ {pid.upper()}: aucun article trouvé")

    # Étape 2 : UNE SEULE requête Gemini pour tous les articles
    nouveaux_analysés = {}
    if articles_bruts:
        print(f"\nAnalyse Gemini ({len(articles_bruts)} articles en 1 requête)...")
        resultats = analyser_tous(articles_bruts)
        
        for pid, r in resultats.items():
            if not r or not r.get("titre_en") or not r.get("resume_en"):
                print(f"  {pid}: ❌ résultat invalide")
                continue
            
            art = articles_bruts.get(pid, {})
            titre = (art.get("title") or "").strip()
            image = art.get("urlToImage") or IMGS.get(pid, "")
            
            nouveaux_analysés[pid] = {
                "id": f"{pid}_{abs(hash(titre)) % 1000000}",
                "titre": r.get("titre_fr", titre),
                "titre_en": r.get("titre_en", titre),
                "titre_zh": r.get("titre_zh", titre),
                "titre_original": titre,
                "resume": r.get("resume_fr", ""),
                "resume_en": r.get("resume_en", ""),
                "resume_zh": r.get("resume_zh", ""),
                "analyse_detaillee": r.get("analyse_fr", ""),
                "analyse_en": r.get("analyse_en", ""),
                "analyse_zh": r.get("analyse_zh", ""),
                "categorie": r.get("categorie", "Actualité"),
                "source": art.get("source", {}).get("name", ""),
                "url": art.get("url", "#"),
                "image": image,
                "date": (art.get("publishedAt") or "")[:10],
                "pays": pid,
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
            }
            print(f"  {pid}: ✅ {r.get('titre_fr','')[:50]}")

    # Étape 3 : fusionner nouveaux + anciens
    new_articles = {}
    for pays in PAYS:
        pid = pays["id"]
        nouveau = nouveaux_analysés.get(pid)
        old = existing.get(pid, [])
        
        if nouveau:
            # Ajouter en tête, éviter doublon
            old_filtered = [a for a in old if normalize(a.get("titre_original") or a.get("titre","")) 
                           != normalize(nouveau.get("titre_original") or nouveau.get("titre",""))]
            new_articles[pid] = ([nouveau] + old_filtered)[:20]
        else:
            new_articles[pid] = old[:20]
        
        print(f"  {pid}: {len(new_articles[pid])} articles (6 mois conservés)")

    with open("news_data.json", "w", encoding="utf-8") as f:
        json.dump({
            "last_updated": datetime.now().strftime("%d/%m/%Y à %Hh%M"),
            "articles": new_articles
        }, f, ensure_ascii=False, indent=2)

    total = sum(len(v) for v in new_articles.values())
    print(f"\n✅ Terminé — {total} articles au total")

if __name__ == "__main__":
    main()
