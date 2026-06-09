import os, json, requests
from datetime import datetime, timedelta

NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

PAYS = [
    {"id": "monde",  "query": "world international geopolitics economy breaking", "lang": "en"},
    {"id": "france", "query": "France politique économie actualité", "lang": "fr"},
    {"id": "usa",    "query": "United States Trump economy politics", "lang": "en"},
    {"id": "chine",  "query": "China economy Xi Jinping trade", "lang": "en"},
    {"id": "russie", "query": "Russia Ukraine war sanctions", "lang": "en"},
    {"id": "iran",   "query": "Iran nuclear diplomacy Middle East", "lang": "en"},
]

FALLBACK_IMAGES = {
    "monde":  "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&q=80",
    "france": "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?w=800&q=80",
    "usa":    "https://images.unsplash.com/photo-1485738422979-f5c462d49f74?w=800&q=80",
    "chine":  "https://images.unsplash.com/photo-1547981609-4b6bfe67ca0b?w=800&q=80",
    "russie": "https://images.unsplash.com/photo-1513326738677-b964603b136d?w=800&q=80",
    "iran":   "https://images.unsplash.com/photo-1527576539890-dfa815648363?w=800&q=80",
}

def get_articles(query, lang="fr", nb=4):
    url = "https://newsapi.org/v2/everything"
    params = {"q": query, "language": lang, "sortBy": "publishedAt",
              "pageSize": nb, "apiKey": NEWSAPI_KEY}
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            return r.json().get("articles", [])
    except Exception as e:
        print(f"     NewsAPI error: {e}")
    return []

def gemini_analyse(titre, description, pays_id):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"

    # Exemples concrets d'impacts par secteur pour guider Gemini
    exemples_impact = """
Exemples d'impacts sectoriels précis :
- Guerre/conflit militaire → Défense (Thales, Airbus Defence), Pétrole (Brent), Or (valeur refuge), Compagnies aériennes (négatif)
- Décision BCE/Fed sur les taux → Banques (marges), Immobilier (crédit), Obligations souveraines, EUR/USD
- Résultats tech (Apple, Nvidia, Meta) → Semi-conducteurs (SOX), Cloud computing, ETF Tech (QQQ)
- Accord commercial → Automobile, Agroalimentaire, Logistique/Transport
- Crise pétrolière → Pétrole (Brent/WTI), Compagnies aériennes (négatif), Énergies renouvelables
- Élection/instabilité politique → Devise du pays, Obligations d'État, Bourse nationale
- Sanction économique → Matières premières, Énergie, Devises des pays sanctionnés
- Catastrophe naturelle → Assurances (négatif), Reconstruction/BTP, Énergie
"""

    prompt = f"""Tu es un journaliste économiste expert pour Veritass.fr.

Article source (peut être en anglais) :
TITRE: {titre}
DESCRIPTION: {description}
PAYS/RÉGION: {pays_id}

MISSION : Analyser cet article et produire une réponse COMPLÈTE en JSON.

{exemples_impact}

Réponds UNIQUEMENT avec ce JSON valide (pas de markdown, pas de texte avant/après) :
{{
  "titre_fr": "Titre traduit/reformulé en français journalistique (obligatoire, même si déjà en français)",
  "resume": "Résumé en 3 phrases factuelles en français. Phrase 1 : le fait principal. Phrase 2 : le contexte immédiat. Phrase 3 : la réaction ou conséquence directe.",
  "analyse_detaillee": "Analyse en 5 phrases minimum en français. Explique : 1) Le contexte historique ou géopolitique de cet événement. 2) Les enjeux principaux pour les acteurs concernés. 3) Les raisons profondes qui ont mené à cette situation. 4) Les conséquences probables à court terme (1-3 mois). 5) Les conséquences possibles à long terme et l'impact sur l'équilibre géopolitique ou économique mondial.",
  "categorie": "UN SEUL MOT parmi : Politique, Économie, Géopolitique, Énergie, Tech, Justice, Social, Diplomatie, Environnement, Santé, Sécurité",
  "badges": [
    {{"label": "▲ NOM_SECTEUR_PRÉCIS", "hausse": true}},
    {{"label": "▼ NOM_SECTEUR_PRÉCIS", "hausse": false}}
  ],
  "impact_marches": [
    {{
      "secteur": "NOM PRÉCIS DU SECTEUR (ex: Pétrole Brent, Défense européenne, Semi-conducteurs, CAC 40, EUR/USD, Banques françaises...)",
      "effet": "Explication en 1 phrase précise de POURQUOI ce secteur est impacté et dans quel sens",
      "hausse": true
    }},
    {{
      "secteur": "DEUXIÈME SECTEUR PRÉCIS",
      "effet": "Explication précise de l'impact négatif sur ce secteur",
      "hausse": false
    }},
    {{
      "secteur": "TROISIÈME SECTEUR SI PERTINENT",
      "effet": "Explication de l'impact",
      "hausse": true
    }}
  ],
  "mots_cles": ["mot1", "mot2", "mot3"]
}}

RÈGLES ABSOLUES :
1. Tout doit être en FRANÇAIS
2. impact_marches doit avoir MINIMUM 2 secteurs NOMMÉS PRÉCISÉMENT (jamais "marchés internationaux" tout seul)
3. analyse_detaillee doit faire minimum 5 phrases
4. badges : maximum 2
5. impact_marches : minimum 2, maximum 3
"""

    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1500}
    }
    try:
        r = requests.post(url, json=body, timeout=30)
        if r.status_code == 200:
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            # Nettoyer le markdown si présent
            if "```" in text:
                for part in text.split("```"):
                    part = part.strip()
                    if part.startswith("json"):
                        part = part[4:].strip()
                    if part.startswith("{"):
                        text = part
                        break
            result = json.loads(text.strip())
            # Vérifier que les champs critiques existent
            if not result.get("impact_marches") or len(result["impact_marches"]) == 0:
                raise ValueError("Pas d'impact marchés généré")
            if not result.get("analyse_detaillee") or len(result["analyse_detaillee"]) < 100:
                raise ValueError("Analyse trop courte")
            return result
        else:
            print(f"     Gemini HTTP error: {r.status_code}")
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
                d = datetime.strptime(a.get("date", "2020-01-01"), "%Y-%m-%d")
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
        print(f"\n  → {pays['id']}")
        bruts = get_articles(pays["query"], pays["lang"], nb=4)
        if not bruts:
            print(f"     Aucun article — conservation des anciens")
            new_articles[pays["id"]] = existing.get(pays["id"], [])
            continue

        existing_ids = {a["id"] for a in existing.get(pays["id"], [])}
        nouveaux = []

        for i, art in enumerate(bruts[:4]):
            titre = (art.get("title") or "")[:200]
            desc = (art.get("description") or art.get("content") or "")[:600]
            if not titre or titre == "[Removed]":
                continue

            source = art.get("source", {}).get("name", "Source inconnue")
            date_raw = (art.get("publishedAt") or "")[:10]
            url_art = art.get("url", "#")
            image = art.get("urlToImage") or ""
            if not image or len(image) < 15:
                image = FALLBACK_IMAGES.get(pays["id"], "")

            art_id = f"{pays['id']}_{abs(hash(titre)) % 1000000}"
            if art_id in existing_ids:
                print(f"     [{i+1}] Doublon ignoré")
                continue

            print(f"     [{i+1}] Analyse: {titre[:55]}...")
            analyse = gemini_analyse(titre, desc, pays["id"])

            # Si Gemini échoue, fallback manuel détaillé
            if not analyse:
                print(f"     ⚠ Gemini failed — fallback")
                analyse = {
                    "titre_fr": titre,
                    "resume": f"{desc[:250]}",
                    "analyse_detaillee": f"Cet article traite de {titre}. La situation concerne le pays/région {pays['id']}. Les développements récents montrent une évolution significative de la situation. Les experts suivent de près les implications géopolitiques et économiques. Des développements supplémentaires sont attendus dans les prochains jours.",
                    "categorie": "Actualité",
                    "badges": [],
                    "impact_marches": [
                        {"secteur": {"monde":"Marchés boursiers mondiaux","france":"CAC 40 (Bourse de Paris)","usa":"S&P 500 (Bourse américaine)","chine":"Shanghai Composite","russie":"Pétrole Brent & Rouble","iran":"Pétrole Brent & Or"}.get(pays["id"], "Marchés financiers"), "effet": "Peut potentiellement être affecté selon l'évolution de la situation", "hausse": False}
                    ],
                    "mots_cles": []
                }

            nouveaux.append({
                "id": art_id,
                "titre": analyse.get("titre_fr") or titre,
                "titre_original": titre,
                "resume": analyse.get("resume", desc[:250]),
                "analyse_detaillee": analyse.get("analyse_detaillee", ""),
                "categorie": analyse.get("categorie", "Actualité"),
                "source": source,
                "url": url_art,
                "image": image,
                "date": date_raw,
                "pays": pays["id"],
                "badges": analyse.get("badges", []),
                "impact_marches": analyse.get("impact_marches", []),
                "mots_cles": analyse.get("mots_cles", []),
                "created_at": datetime.now().isoformat()
            })

        # Fusionner nouveaux + anciens (6 mois)
        old = [a for a in existing.get(pays["id"], [])
               if a["id"] not in {n["id"] for n in nouveaux}]
        new_articles[pays["id"]] = nouveaux + old
        print(f"     Total conservé: {len(new_articles[pays['id']])} articles")

    output = {
        "last_updated": datetime.now().strftime("%d/%m/%Y à %Hh%M"),
        "articles": new_articles
    }

    with open("news_data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    total = sum(len(v) for v in new_articles.values())
    print(f"\n[{datetime.now()}] ✅ Terminé — {total} articles conservés au total")

if __name__ == "__main__":
    main()
