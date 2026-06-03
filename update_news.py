import os
import json
import requests
from datetime import datetime

NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

PAYS = [
    {"id": "france", "query": "France politique économie", "lang": "fr"},
    {"id": "monde", "query": "world international geopolitics economy", "lang": "en"},
    {"id": "usa", "query": "United States Trump economy", "lang": "en"},
    {"id": "chine", "query": "China economy geopolitics", "lang": "en"},
    {"id": "russie", "query": "Russia Ukraine war sanctions", "lang": "en"},
    {"id": "iran", "query": "Iran nuclear diplomacy Middle East", "lang": "en"},
]

def get_articles(query, lang="fr", nb=4):
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "language": lang,
        "sortBy": "publishedAt",
        "pageSize": nb,
        "apiKey": NEWSAPI_KEY,
    }
    r = requests.get(url, params=params, timeout=10)
    if r.status_code == 200:
        return r.json().get("articles", [])
    return []

def gemini_analyse(titre, description, pays):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"
    prompt = f"""Tu es un journaliste expert pour le site Veritass.fr, site d'information anti-désinformation français.

Voici une actualité :
Titre : {titre}
Description : {description}
Pays/Région : {pays}

Réponds UNIQUEMENT en JSON valide avec cette structure exacte, sans markdown, sans texte avant ou après :
{{
  "resume": "Résumé factuel en 2 phrases maximum, ton neutre et direct",
  "analyse": "Analyse en 3-4 phrases : contexte, enjeux, conséquences possibles",
  "impact_marches": [
    {{"secteur": "nom du secteur", "effet": "▲ +X% ou ▼ -X% ou → Stable", "hausse": true}},
    {{"secteur": "nom du secteur", "effet": "▲ +X% ou ▼ -X%", "hausse": false}}
  ],
  "categorie": "Politique|Économie|Géopolitique|Énergie|Tech|Justice|Social|Diplomatie",
  "badges": [
    {{"label": "▲ Secteur", "hausse": true}},
    {{"label": "▼ Secteur", "hausse": false}}
  ]
}}

Si l'actualité n'a pas d'impact direct sur les marchés, mets impact_marches et badges comme tableaux vides [].
"""
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 800}
    }
    r = requests.post(url, json=body, timeout=20)
    if r.status_code == 200:
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()
        try:
            return json.loads(text)
        except:
            return None
    return None

def build_article(article, pays_id, is_featured=False):
    titre = article.get("title", "")[:120]
    desc = article.get("description", "") or article.get("content", "") or ""
    desc = desc[:400]
    source = article.get("source", {}).get("name", "Source inconnue")
    published = article.get("publishedAt", "")[:10]
    url = article.get("url", "#")

    analyse = gemini_analyse(titre, desc, pays_id)

    result = {
        "id": f"{pays_id}_{abs(hash(titre)) % 10000}",
        "titre": titre,
        "resume": analyse["resume"] if analyse else desc[:200],
        "analyse": analyse["analyse"] if analyse else "",
        "categorie": analyse["categorie"] if analyse else "Actualité",
        "source": source,
        "url": url,
        "date": published,
        "pays": pays_id,
        "featured": is_featured,
        "badges": analyse["badges"] if analyse else [],
        "impact_marches": analyse["impact_marches"] if analyse else [],
    }
    return result

def main():
    print(f"[{datetime.now()}] Démarrage de la mise à jour...")
    all_articles = {}

    for pays in PAYS:
        print(f"  → Traitement : {pays['id']}")
        articles_bruts = get_articles(pays["query"], pays["lang"], nb=4)
        if not articles_bruts:
            print(f"     Aucun article trouvé pour {pays['id']}")
            continue

        articles_traites = []
        for i, art in enumerate(articles_bruts[:4]):
            print(f"     Article {i+1}: {art.get('title','')[:60]}...")
            a = build_article(art, pays["id"], is_featured=(i == 0))
            articles_traites.append(a)

        all_articles[pays["id"]] = articles_traites

    output = {
        "last_updated": datetime.now().strftime("%d %B %Y à %Hh%M"),
        "articles": all_articles
    }

    with open("news_data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[{datetime.now()}] ✅ news_data.json généré avec succès !")

if __name__ == "__main__":
    main()
