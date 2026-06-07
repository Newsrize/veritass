import os, json, requests
from datetime import datetime

NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

PAYS = [
    {"id": "monde",  "query": "world international geopolitics economy breaking", "lang": "en"},
    {"id": "france", "query": "France politique économie actualité", "lang": "fr"},
    {"id": "usa",    "query": "United States Trump economy politics", "lang": "en"},
    {"id": "chine",  "query": "China economy geopolitics trade", "lang": "en"},
    {"id": "russie", "query": "Russia Ukraine war sanctions economy", "lang": "en"},
    {"id": "iran",   "query": "Iran nuclear diplomacy Middle East", "lang": "en"},
]

def get_articles(query, lang="fr", nb=4):
    url = "https://newsapi.org/v2/everything"
    params = {"q": query, "language": lang, "sortBy": "publishedAt", "pageSize": nb, "apiKey": NEWSAPI_KEY}
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            return r.json().get("articles", [])
    except: pass
    return []

def gemini_analyse(titre, description, pays, image_url=""):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"
    prompt = f"""Tu es journaliste expert pour Veritass.fr, site d'information anti-désinformation français.

Actualité :
Titre : {titre}
Description : {description}
Région : {pays}

Réponds UNIQUEMENT en JSON valide, sans markdown :
{{
  "resume": "Résumé factuel en 2-3 phrases, ton neutre et direct, sans formulation IA",
  "analyse_detaillee": "Analyse approfondie en 4-5 phrases : contexte historique, enjeux géopolitiques ou économiques, conséquences possibles à court et long terme",
  "categorie": "Politique|Économie|Géopolitique|Énergie|Tech|Justice|Social|Diplomatie|Environnement|Santé",
  "badges": [
    {{"label": "▲ Secteur concerné", "hausse": true}},
    {{"label": "▼ Secteur concerné", "hausse": false}}
  ],
  "impact_marches": [
    {{"secteur": "Nom du secteur financier", "effet": "Peut potentiellement progresser/reculer", "hausse": true}},
    {{"secteur": "Nom du secteur financier", "effet": "Peut potentiellement être impacté", "hausse": false}}
  ],
  "mots_cles": ["mot1", "mot2", "mot3"]
}}

Si pas d'impact direct sur les marchés, mets impact_marches et badges comme tableaux vides [].
Maximum 2 badges et 3 impacts marchés.
"""
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1000}}
    try:
        r = requests.post(url, json=body, timeout=20)
        if r.status_code == 200:
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"): text = text[4:]
            return json.loads(text.strip())
    except Exception as e:
        print(f"     Gemini error: {e}")
    return None

def main():
    print(f"[{datetime.now()}] Démarrage mise à jour Veritass...")
    all_articles = {}

    for pays in PAYS:
        print(f"  → {pays['id']}")
        bruts = get_articles(pays["query"], pays["lang"], nb=4)
        if not bruts:
            print(f"     Aucun article")
            continue

        traites = []
        for i, art in enumerate(bruts[:4]):
            titre = (art.get("title") or "")[:150]
            desc = (art.get("description") or art.get("content") or "")[:500]
            source = art.get("source", {}).get("name", "Source inconnue")
            date = (art.get("publishedAt") or "")[:10]
            url = art.get("url", "#")
            image = art.get("urlToImage") or ""

            print(f"     [{i+1}] {titre[:60]}...")
            analyse = gemini_analyse(titre, desc, pays["id"], image)

            traites.append({
                "id": f"{pays['id']}_{abs(hash(titre)) % 100000}",
                "titre": titre,
                "resume": analyse["resume"] if analyse else desc[:250],
                "analyse_detaillee": analyse["analyse_detaillee"] if analyse else "",
                "categorie": analyse["categorie"] if analyse else "Actualité",
                "source": source,
                "url": url,
                "image": image,
                "date": date,
                "pays": pays["id"],
                "badges": analyse["badges"] if analyse else [],
                "impact_marches": analyse["impact_marches"] if analyse else [],
                "mots_cles": analyse["mots_cles"] if analyse else [],
                "featured": (i == 0)
            })

        all_articles[pays["id"]] = traites

    output = {
        "last_updated": datetime.now().strftime("%d/%m/%Y à %Hh%M"),
        "articles": all_articles
    }

    with open("news_data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[{datetime.now()}] ✅ news_data.json mis à jour")

if __name__ == "__main__":
    main()
