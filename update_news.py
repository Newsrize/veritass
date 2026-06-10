import os, json, requests
from datetime import datetime, timedelta

NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

# Sources fiables uniquement — pas de blogs ni d'essais
SOURCES_FIABLES = "bbc-news,reuters,associated-press,le-monde,france-24,bloomberg,the-guardian,euronews,al-jazeera-english,cnn,the-washington-post,les-echos"

PAYS = [
    {"id": "monde",  "queries": ["geopolitics war diplomacy 2026", "economy trade sanctions 2026"], "lang": "en"},
    {"id": "france", "queries": ["France Macron gouvernement 2026", "économie France actualité 2026"], "lang": "fr"},
    {"id": "usa",    "queries": ["Trump White House 2026", "United States economy policy 2026"], "lang": "en"},
    {"id": "chine",  "queries": ["China Xi Jinping 2026", "China economy Taiwan 2026"], "lang": "en"},
    {"id": "russie", "queries": ["Russia Putin Ukraine 2026", "Russia war sanctions 2026"], "lang": "en"},
    {"id": "iran",   "queries": ["Iran nuclear deal 2026", "Iran US Middle East 2026"], "lang": "en"},
]

FALLBACK_IMAGES = {
    "monde":  "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&q=80",
    "france": "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?w=800&q=80",
    "usa":    "https://images.unsplash.com/photo-1485738422979-f5c462d49f74?w=800&q=80",
    "chine":  "https://images.unsplash.com/photo-1547981609-4b6bfe67ca0b?w=800&q=80",
    "russie": "https://images.unsplash.com/photo-1513326738677-b964603b136d?w=800&q=80",
    "iran":   "https://images.unsplash.com/photo-1527576539890-dfa815648363?w=800&q=80",
}

# Mots-clés qui indiquent un article non pertinent (blog, essai, académique)
MOTS_EXCLUS = [
    "essay", "draft", "talk", "memoir", "blog", "podcast", "review",
    "how to", "tutorial", "guide to", "my thoughts", "i think",
    "subscribe", "newsletter", "opinion:", "comment:", "analysis:"
]

def is_valid_article(title, description):
    """Filtre les articles non pertinents"""
    if not title or title == "[Removed]" or len(title) < 15:
        return False
    text = (title + " " + (description or "")).lower()
    for mot in MOTS_EXCLUS:
        if mot in text:
            return False
    return True

def get_articles(queries, lang="en", nb=6):
    """Essaie plusieurs requêtes pour trouver des articles valides"""
    articles = []
    for query in queries:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": query,
            "language": lang,
            "sortBy": "publishedAt",
            "pageSize": nb,
            "apiKey": NEWSAPI_KEY,
            "from": (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        }
        try:
            r = requests.get(url, params=params, timeout=10)
            if r.status_code == 200:
                arts = r.json().get("articles", [])
                for a in arts:
                    if is_valid_article(a.get("title"), a.get("description")):
                        articles.append(a)
        except Exception as e:
            print(f"     NewsAPI error: {e}")
    # Dédupliquer par titre
    seen = set()
    unique = []
    for a in articles:
        t = a.get("title","")[:50]
        if t not in seen:
            seen.add(t)
            unique.append(a)
    return unique[:4]

def gemini_analyse(titre, description, pays_id):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"

    prompt = f"""Tu es rédacteur en chef de Veritass.fr, site d'information français.

Article source :
TITRE: {titre}
DESCRIPTION: {description}
ZONE GÉOGRAPHIQUE: {pays_id}

Produis une analyse journalistique COMPLÈTE en français. JSON strict uniquement, zéro markdown :

{{
  "titre_fr": "Reformule le titre en français journalistique percutant (max 15 mots)",
  "resume": "3 phrases factuelles en français. 1ère phrase: le fait central de cet article. 2ème phrase: le contexte qui explique pourquoi c'est important. 3ème phrase: la réaction principale ou conséquence immédiate.",
  "analyse_detaillee": "Rédige un paragraphe journalistique de 6 à 8 phrases en français. Commence par le contexte historique ou géopolitique de cet événement. Explique ensuite les enjeux pour les acteurs principaux (pays, institutions, citoyens). Développe les causes profondes de la situation. Décris les conséquences probables à court terme (semaines à venir). Analyse l'impact à moyen terme (3-6 mois). Conclus sur les perspectives à long terme et ce que les experts anticipent.",
  "categorie": "Géopolitique",
  "badges": [
    {{"label": "▲ Secteur bénéficiaire précis", "hausse": true}},
    {{"label": "▼ Secteur perdant précis", "hausse": false}}
  ],
  "impact_marches": [
    {{
      "secteur": "Nom du secteur boursier précis (ex: Pétrole Brent, Actions défense, CAC 40, EUR/USD, Obligations d'État, Semi-conducteurs, Compagnies aériennes, Banques européennes...)",
      "effet": "Phrase complète expliquant POURQUOI ce secteur spécifique est impacté par cet événement précis et dans quel sens",
      "hausse": true
    }},
    {{
      "secteur": "Deuxième secteur précis différent du premier",
      "effet": "Explication précise et argumentée de l'impact négatif sur ce secteur en lien direct avec l'article",
      "hausse": false
    }},
    {{
      "secteur": "Troisième secteur si pertinent",
      "effet": "Explication de l'impact avec lien direct à l'événement",
      "hausse": true
    }}
  ]
}}

RÈGLES IMPÉRATIVES :
- Tout le contenu doit être en FRANÇAIS
- analyse_detaillee : minimum 6 phrases, minimum 200 mots
- impact_marches : EXACTEMENT 2 ou 3 secteurs, NOMMÉS PRÉCISÉMENT (jamais de termes génériques comme "marchés internationaux" seuls)
- Chaque secteur doit être différent
- L'effet doit expliquer le lien causal entre l'événement et le secteur
"""

    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.15, "maxOutputTokens": 1800}
    }
    try:
        r = requests.post(url, json=body, timeout=30)
        if r.status_code == 200:
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            if "```" in text:
                for part in text.split("```"):
                    part = part.replace("json","",1).strip()
                    if part.startswith("{"):
                        text = part
                        break
            result = json.loads(text.strip())
            # Validation
            if not result.get("impact_marches") or len(result["impact_marches"]) < 2:
                print("     ⚠ Impact marchés insuffisant")
                return None
            if not result.get("analyse_detaillee") or len(result["analyse_detaillee"]) < 150:
                print("     ⚠ Analyse trop courte")
                return None
            return result
        else:
            print(f"     Gemini HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"     Gemini error: {e}")
    return None

def load_existing():
    try:
        with open("news_data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("articles", {})
    except:
        return {}

def clean_old(articles_by_country, months=6):
    cutoff = datetime.now() - timedelta(days=months*30)
    cleaned = {}
    for pays, arts in articles_by_country.items():
        kept = []
        for a in arts:
            try:
                d = datetime.strptime(a.get("date","2020-01-01"), "%Y-%m-%d")
                if d >= cutoff:
                    kept.append(a)
            except:
                kept.append(a)
        cleaned[pays] = kept
    return cleaned

def main():
    print(f"[{datetime.now()}] Démarrage mise à jour Veritass...")
    existing = clean_old(load_existing())
    new_articles = {}

    for pays in PAYS:
        print(f"\n→ {pays['id']}")
        bruts = get_articles(pays["queries"], pays["lang"], nb=6)

        if not bruts:
            print(f"  Aucun article valide — conservation des anciens")
            new_articles[pays["id"]] = existing.get(pays["id"], [])
            continue

        print(f"  {len(bruts)} articles valides trouvés")
        existing_ids = {a["id"] for a in existing.get(pays["id"], [])}
        nouveaux = []

        for i, art in enumerate(bruts[:4]):
            titre = (art.get("title") or "")[:200].strip()
            desc = (art.get("description") or art.get("content") or "")[:600].strip()
            source = art.get("source", {}).get("name", "Source inconnue")
            date_raw = (art.get("publishedAt") or "")[:10]
            url_art = art.get("url", "#")
            image = art.get("urlToImage") or ""
            if not image or len(image) < 15 or "http" not in image:
                image = FALLBACK_IMAGES.get(pays["id"], "")

            art_id = f"{pays['id']}_{abs(hash(titre)) % 1000000}"
            if art_id in existing_ids:
                print(f"  [{i+1}] Doublon — ignoré")
                continue

            print(f"  [{i+1}] Analyse Gemini: {titre[:60]}...")
            analyse = gemini_analyse(titre, desc, pays["id"])

            if not analyse:
                print(f"  [{i+1}] ⚠ Gemini échoué — article ignoré")
                continue  # On ignore plutôt que d'afficher du contenu vide

            nouveaux.append({
                "id": art_id,
                "titre": analyse.get("titre_fr") or titre,
                "titre_original": titre,
                "resume": analyse.get("resume", ""),
                "analyse_detaillee": analyse.get("analyse_detaillee", ""),
                "categorie": analyse.get("categorie", "Actualité"),
                "source": source,
                "url": url_art,
                "image": image,
                "date": date_raw,
                "pays": pays["id"],
                "badges": analyse.get("badges", []),
                "impact_marches": analyse.get("impact_marches", []),
                "created_at": datetime.now().isoformat()
            })
            print(f"  [{i+1}] ✅ OK — {len(analyse.get('impact_marches',[]))} impacts, {len(analyse.get('analyse_detaillee',''))} chars")

        # Fusionner nouveaux + anciens
        old = [a for a in existing.get(pays["id"], []) if a["id"] not in {n["id"] for n in nouveaux}]
        new_articles[pays["id"]] = nouveaux + old
        print(f"  Total: {len(nouveaux)} nouveaux + {len(old)} conservés = {len(new_articles[pays['id']])} articles")

    output = {
        "last_updated": datetime.now().strftime("%d/%m/%Y à %Hh%M"),
        "articles": new_articles
    }

    with open("news_data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    total = sum(len(v) for v in new_articles.values())
    print(f"\n[{datetime.now()}] ✅ Terminé — {total} articles au total")

if __name__ == "__main__":
    main()
