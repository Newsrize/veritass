import os, json, requests
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

MOTS_EXCLUS = ["essay","draft","how to","tutorial","subscribe","newsletter","my thoughts","podcast","memoir","i think","opinion:"]

def is_valid(title, desc):
    if not title or title == "[Removed]" or len(title) < 20:
        return False
    text = (title + " " + (desc or "")).lower()
    return not any(m in text for m in MOTS_EXCLUS)

def get_articles(query, lang, nb=5):
    try:
        r = requests.get("https://newsapi.org/v2/everything", params={
            "q": query, "language": lang, "sortBy": "publishedAt",
            "pageSize": nb, "apiKey": NEWSAPI_KEY,
            "from": (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
        }, timeout=10)
        if r.status_code == 200:
            return [a for a in r.json().get("articles", [])
                    if is_valid(a.get("title"), a.get("description"))]
    except Exception as e:
        print(f"  NewsAPI error: {e}")
    return []

def appel_gemini(prompt):
    """Appelle Gemini 1.5 Pro qui suit mieux les instructions"""
    for model in ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0-flash"]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY}"
        try:
            r = requests.post(url, json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2000}
            }, timeout=35)
            if r.status_code == 200:
                text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                # Nettoyer markdown
                if "```" in text:
                    for p in text.split("```"):
                        p = p.replace("json","",1).strip()
                        if p.startswith("{"):
                            text = p
                            break
                return json.loads(text)
            else:
                print(f"  {model}: HTTP {r.status_code}")
        except Exception as e:
            print(f"  {model} error: {e}")
    return None

def analyser(titre, desc, pays_id):
    prompt = f"""Rôle : Tu es journaliste économiste pour Veritass.fr (site d'info français).

Article à analyser :
- Titre : {titre}
- Description : {desc}
- Région : {pays_id}

Produis ce JSON en français (zéro markdown, zéro texte avant/après le JSON) :

{{
  "titre_fr": "{titre[:80]}",
  "resume": "REMPLACE_PAR_3_PHRASES_FACTUELLES_EN_FRANÇAIS",
  "analyse_detaillee": "REMPLACE_PAR_6_PHRASES_MINIMUM_EN_FRANÇAIS_contexte_enjeux_causes_consequences_court_terme_long_terme",
  "categorie": "Géopolitique",
  "secteur1_nom": "Nom précis secteur boursier impacté positivement (ex: Pétrole Brent, Défense, Semi-conducteurs, CAC 40, EUR/USD...)",
  "secteur1_effet": "Phrase expliquant POURQUOI ce secteur précis est en hausse à cause de cet événement",
  "secteur1_hausse": true,
  "secteur2_nom": "Nom précis secteur boursier impacté négativement",
  "secteur2_effet": "Phrase expliquant POURQUOI ce secteur précis est en baisse à cause de cet événement",
  "secteur2_hausse": false,
  "secteur3_nom": "Troisième secteur impacté (positif ou négatif)",
  "secteur3_effet": "Explication de l'impact sur ce troisième secteur",
  "secteur3_hausse": true
}}

IMPORTANT : Remplace TOUS les champs REMPLACE_PAR par du vrai contenu. Les secteurs doivent être précis et liés directement à l'événement de l'article."""

    result = appel_gemini(prompt)
    if not result:
        return None

    # Convertir le format plat en format attendu
    output = {
        "titre_fr": result.get("titre_fr", titre),
        "resume": result.get("resume", ""),
        "analyse_detaillee": result.get("analyse_detaillee", ""),
        "categorie": result.get("categorie", "Actualité"),
        "badges": [],
        "impact_marches": []
    }

    # Reconstruire impact_marches depuis les champs plats
    for i in ["1","2","3"]:
        nom = result.get(f"secteur{i}_nom","").strip()
        effet = result.get(f"secteur{i}_effet","").strip()
        hausse = result.get(f"secteur{i}_hausse", False)
        if nom and effet and len(nom) > 3 and "REMPLACE" not in nom:
            output["impact_marches"].append({
                "secteur": nom,
                "effet": effet,
                "hausse": hausse
            })
            if len(output["badges"]) < 2:
                sym = "▲" if hausse else "▼"
                output["badges"].append({"label": f"{sym} {nom}", "hausse": hausse})

    # Vérifier qualité
    if len(output["impact_marches"]) < 2:
        print(f"  ⚠ Pas assez d'impacts marchés ({len(output['impact_marches'])})")
        return None
    if len(output.get("analyse_detaillee","")) < 150:
        print(f"  ⚠ Analyse trop courte ({len(output.get('analyse_detaillee',''))} chars)")
        return None
    if "REMPLACE" in output.get("resume",""):
        print(f"  ⚠ Résumé non rempli")
        return None

    return output

def load_existing():
    try:
        with open("news_data.json","r",encoding="utf-8") as f:
            return json.load(f).get("articles",{})
    except:
        return {}

def clean_old(data, months=6):
    cutoff = datetime.now() - timedelta(days=months*30)
    cleaned = {}
    for pays, arts in data.items():
        kept = []
        for a in arts:
            try:
                d = datetime.strptime(a.get("date","2020-01-01"),"%Y-%m-%d")
                if d >= cutoff:
                    kept.append(a)
            except:
                kept.append(a)
        cleaned[pays] = kept
    return cleaned

def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Démarrage Veritass update...")
    existing = clean_old(load_existing())
    new_articles = {}

    for pays in PAYS:
        print(f"\n→ {pays['id'].upper()}")
        bruts = get_articles(pays["query"], pays["lang"], nb=5)
        print(f"  {len(bruts)} articles valides trouvés")

        if not bruts:
            new_articles[pays["id"]] = existing.get(pays["id"],[])
            continue

        existing_ids = {a["id"] for a in existing.get(pays["id"],[])}
        nouveaux = []

        for i, art in enumerate(bruts[:4]):
            titre = (art.get("title") or "")[:200].strip()
            desc = (art.get("description") or art.get("content") or "")[:600].strip()
            source = art.get("source",{}).get("name","Source inconnue")
            date_raw = (art.get("publishedAt") or "")[:10]
            url_art = art.get("url","#")
            image = art.get("urlToImage") or ""
            if not image or len(image) < 10 or "http" not in image:
                image = FALLBACK_IMAGES.get(pays["id"],"")

            art_id = f"{pays['id']}_{abs(hash(titre)) % 1000000}"
            if art_id in existing_ids:
                print(f"  [{i+1}] Doublon ignoré")
                continue

            print(f"  [{i+1}] {titre[:65]}...")
            analyse = analyser(titre, desc, pays["id"])

            if not analyse:
                print(f"  [{i+1}] ❌ Ignoré (analyse insuffisante)")
                continue

            print(f"  [{i+1}] ✅ {len(analyse['impact_marches'])} secteurs, {len(analyse['analyse_detaillee'])} chars")
            nouveaux.append({
                "id": art_id,
                "titre": analyse["titre_fr"] or titre,
                "titre_original": titre,
                "resume": analyse["resume"],
                "analyse_detaillee": analyse["analyse_detaillee"],
                "categorie": analyse["categorie"],
                "source": source,
                "url": url_art,
                "image": image,
                "date": date_raw,
                "pays": pays["id"],
                "badges": analyse["badges"],
                "impact_marches": analyse["impact_marches"],
                "created_at": datetime.now().isoformat()
            })

        old = [a for a in existing.get(pays["id"],[]) if a["id"] not in {n["id"] for n in nouveaux}]
        new_articles[pays["id"]] = nouveaux + old
        print(f"  → {len(nouveaux)} nouveaux + {len(old)} conservés")

    with open("news_data.json","w",encoding="utf-8") as f:
        json.dump({
            "last_updated": datetime.now().strftime("%d/%m/%Y à %Hh%M"),
            "articles": new_articles
        }, f, ensure_ascii=False, indent=2)

    total = sum(len(v) for v in new_articles.values())
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ✅ Terminé — {total} articles")

if __name__ == "__main__":
    main()
