import os, json, requests
from datetime import datetime, timedelta

NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

PAYS = [
    {"id": "monde",  "query": "world international geopolitics economy breaking news", "lang": "en"},
    {"id": "france", "query": "France politique économie actualité", "lang": "fr"},
    {"id": "usa",    "query": "United States Trump economy politics", "lang": "en"},
    {"id": "chine",  "query": "China economy geopolitics Xi Jinping", "lang": "en"},
    {"id": "russie", "query": "Russia Ukraine war sanctions Poutine", "lang": "en"},
    {"id": "iran",   "query": "Iran nuclear diplomacy Middle East", "lang": "en"},
]

# Images de secours par pays (Unsplash - libres de droits)
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

def gemini_analyse(titre, description, pays):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"
    prompt = f"""Tu es journaliste expert pour Veritass.fr, site d'information anti-désinformation français.

Voici une actualité brute (peut être en anglais ou français) :
Titre original : {titre}
Description : {description}
Pays/Région : {pays}

Ta mission : produire une analyse complète en FRANÇAIS.

Réponds UNIQUEMENT en JSON valide strict, sans markdown, sans texte avant ou après :
{{
  "titre_fr": "Titre traduit en français (si déjà en français, garde-le tel quel)",
  "resume": "Résumé factuel en 3 phrases claires en français, sans formulation IA, ton journalistique direct",
  "analyse_detaillee": "Analyse approfondie en 5-6 phrases en français : contexte historique ou géopolitique, enjeux principaux, acteurs concernés, conséquences possibles à court et long terme, position des différentes parties",
  "categorie": "Politique|Économie|Géopolitique|Énergie|Tech|Justice|Social|Diplomatie|Environnement|Santé|Sécurité",
  "badges": [
    {{"label": "▲ Secteur en hausse", "hausse": true}},
    {{"label": "▼ Secteur en baisse", "hausse": false}}
  ],
  "impact_marches": [
    {{"secteur": "Nom précis du secteur financier (ex: Pétrole, Défense, Tech)", "effet": "Peut potentiellement progresser en raison de...", "hausse": true}},
    {{"secteur": "Autre secteur", "effet": "Peut potentiellement reculer en raison de...", "hausse": false}}
  ],
  "mots_cles": ["mot1", "mot2", "mot3"]
}}

IMPORTANT :
- Traduis TOUJOURS le contenu en français même si l'article source est en anglais
- Pour impact_marches : identifie TOUJOURS au moins 1-2 secteurs potentiellement impactés même indirectement (ex: une guerre impacte la défense et l'énergie, une élection impacte les devises, etc.)
- Maximum 2 badges, maximum 3 impacts marchés
- Sois précis et factuel, jamais vague
"""
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1200}
    }
    try:
        r = requests.post(url, json=body, timeout=25)
        if r.status_code == 200:
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            if "```" in text:
                parts = text.split("```")
                for p in parts:
                    if p.startswith("json"): p = p[4:]
                    p = p.strip()
                    if p.startswith("{"): text = p; break
            return json.loads(text.strip())
    except Exception as e:
        print(f"     Gemini error: {e}")
    return None

def load_existing():
    """Charge les articles existants pour conservation 6 mois"""
    try:
        with open("news_data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("articles", {})
    except:
        return {}

def clean_old_articles(articles_by_country, months=6):
    """Supprime les articles de plus de 6 mois"""
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
                kept.append(a)  # garder si date invalide
        cleaned[pays] = kept
    return cleaned

def main():
    print(f"[{datetime.now()}] Démarrage mise à jour Veritass...")

    # Charger les articles existants (conservation 6 mois)
    existing = load_existing()
    existing = clean_old_articles(existing)

    new_articles = {}

    for pays in PAYS:
        print(f"  → {pays['id']}")
        bruts = get_articles(pays["query"], pays["lang"], nb=4)
        if not bruts:
            print(f"     Aucun article trouvé")
            new_articles[pays["id"]] = existing.get(pays["id"], [])
            continue

        # IDs déjà existants pour éviter les doublons
        existing_ids = {a["id"] for a in existing.get(pays["id"], [])}

        nouveaux = []
        for i, art in enumerate(bruts[:4]):
            titre = (art.get("title") or "")[:200]
            desc = (art.get("description") or art.get("content") or "")[:600]
            source = art.get("source", {}).get("name", "Source inconnue")
            date_raw = (art.get("publishedAt") or "")[:10]
            url = art.get("url", "#")
            image = art.get("urlToImage") or FALLBACK_IMAGES.get(pays["id"], "")

            # Nettoyer l'image (certaines URLs sont invalides)
            if image and len(image) < 10:
                image = FALLBACK_IMAGES.get(pays["id"], "")

            art_id = f"{pays['id']}_{abs(hash(titre)) % 1000000}"

            # Éviter les doublons
            if art_id in existing_ids:
                print(f"     [{i+1}] Déjà existant, ignoré")
                continue

            print(f"     [{i+1}] {titre[:60]}...")
            analyse = gemini_analyse(titre, desc, pays["id"])

            # Titre traduit en français par Gemini
            titre_final = titre
            if analyse and analyse.get("titre_fr"):
                titre_final = analyse["titre_fr"]

            # Si Gemini échoue, forcer un impact minimal
            impact = []
            if analyse and analyse.get("impact_marches"):
                impact = analyse["impact_marches"]
            else:
                # Impact minimal par défaut selon le pays
                defaults = {
                    "monde": [{"secteur": "Marchés internationaux", "effet": "Peut potentiellement être impacté", "hausse": False}],
                    "france": [{"secteur": "CAC 40", "effet": "Peut potentiellement être impacté", "hausse": False}],
                    "usa": [{"secteur": "Marchés américains (S&P 500)", "effet": "Peut potentiellement être impacté", "hausse": False}],
                    "chine": [{"secteur": "Marchés asiatiques", "effet": "Peut potentiellement être impacté", "hausse": False}],
                    "russie": [{"secteur": "Énergie & matières premières", "effet": "Peut potentiellement être impacté", "hausse": False}],
                    "iran": [{"secteur": "Pétrole (Brent)", "effet": "Peut potentiellement être impacté", "hausse": False}],
                }
                impact = defaults.get(pays["id"], [])

            nouveaux.append({
                "id": art_id,
                "titre": titre_final,
                "titre_original": titre,
                "resume": analyse["resume"] if analyse else desc[:300],
                "analyse_detaillee": analyse["analyse_detaillee"] if analyse else "",
                "categorie": analyse["categorie"] if analyse else "Actualité",
                "source": source,
                "url": url,
                "image": image,
                "date": date_raw,
                "pays": pays["id"],
                "badges": analyse["badges"] if analyse else [],
                "impact_marches": impact,
                "mots_cles": analyse["mots_cles"] if analyse else [],
                "created_at": datetime.now().isoformat()
            })

        # Fusionner : nouveaux articles en tête + anciens conservés
        old = [a for a in existing.get(pays["id"], []) if a["id"] not in {n["id"] for n in nouveaux}]
        new_articles[pays["id"]] = nouveaux + old

    output = {
        "last_updated": datetime.now().strftime("%d/%m/%Y à %Hh%M"),
        "articles": new_articles
    }

    with open("news_data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    total = sum(len(v) for v in new_articles.values())
    print(f"[{datetime.now()}] ✅ news_data.json mis à jour — {total} articles conservés")

if __name__ == "__main__":
    main()
