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

def appel_gemini(prompt, max_tokens=2000):
    for model in ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY}"
        try:
            r = requests.post(url, json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": max_tokens}
            }, timeout=35)
            if r.status_code == 200:
                cands = r.json().get("candidates", [])
                if cands and "content" in cands[0]:
                    return cands[0]["content"]["parts"][0]["text"].strip()
            else:
                print(f"  {model}: HTTP {r.status_code}")
        except Exception as e:
            print(f"  {model} error: {e}")
    return None

def parse_section(text, tag):
    """Extrait le contenu entre [TAG] et [/TAG] ou [TAG_FIN]"""
    pattern = rf"\[{tag}\](.*?)(?:\[/{tag}\]|\[{tag}_FIN\]|\[[A-Z_]+\]|\Z)"
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1).strip() if m else ""

def analyser(titre, desc, pays_id):
    prompt = f"""Tu es journaliste économiste pour Veritass.fr (média français sérieux).

ARTICLE SOURCE :
Titre : {titre}
Description : {desc}
Région : {pays_id}

Rédige ta réponse en FRANÇAIS en suivant EXACTEMENT ce format avec les balises (ne change pas les balises) :

[TITRE]
Reformule le titre en français, percutant, maximum 15 mots.
[/TITRE]

[RESUME]
Écris ici un résumé de 3 à 4 phrases complètes en français qui résument factuellement l'article : le fait principal, le contexte, et la conséquence ou réaction immédiate. Sois concret et précis.
[/RESUME]

[ANALYSE]
Écris ici une analyse approfondie de 6 à 8 phrases en français. Explique le contexte historique ou géopolitique de cette situation, les enjeux pour les acteurs concernés, les causes de cette situation, les conséquences probables à court terme, et les perspectives à moyen et long terme. Sois développé et informatif, comme un article de fond.
[/ANALYSE]

[CATEGORIE]
Un seul mot parmi : Politique, Économie, Géopolitique, Énergie, Tech, Justice, Social, Diplomatie, Environnement, Santé, Sécurité
[/CATEGORIE]

[SECTEUR1_NOM]
Nom précis d'un secteur financier ou boursier impacté par cette actualité (exemples : Pétrole Brent, Actions du secteur de la défense, CAC 40, EUR/USD, Obligations d'État américaines, Semi-conducteurs, Compagnies aériennes, Or, Banques européennes)
[/SECTEUR1_NOM]

[SECTEUR1_EFFET]
Une phrase complète expliquant pourquoi ce secteur précis est impacté par cet événement spécifique et dans quel sens (hausse ou baisse).
[/SECTEUR1_EFFET]

[SECTEUR1_SENS]
HAUSSE ou BAISSE
[/SECTEUR1_SENS]

[SECTEUR2_NOM]
Un deuxième secteur financier précis, différent du premier, impacté par cette actualité.
[/SECTEUR2_NOM]

[SECTEUR2_EFFET]
Une phrase complète expliquant l'impact sur ce deuxième secteur.
[/SECTEUR2_EFFET]

[SECTEUR2_SENS]
HAUSSE ou BAISSE
[/SECTEUR2_SENS]

Respecte STRICTEMENT ce format avec les balises. Écris du contenu réel et développé, pas de placeholder."""

    text = appel_gemini(prompt)
    if not text:
        return None

    titre_fr = parse_section(text, "TITRE")
    resume = parse_section(text, "RESUME")
    analyse = parse_section(text, "ANALYSE")
    categorie = parse_section(text, "CATEGORIE")
    s1_nom = parse_section(text, "SECTEUR1_NOM")
    s1_effet = parse_section(text, "SECTEUR1_EFFET")
    s1_sens = parse_section(text, "SECTEUR1_SENS")
    s2_nom = parse_section(text, "SECTEUR2_NOM")
    s2_effet = parse_section(text, "SECTEUR2_EFFET")
    s2_sens = parse_section(text, "SECTEUR2_SENS")

    # Validation
    if len(resume) < 60:
        print(f"  ⚠ Résumé trop court ({len(resume)} chars): {resume[:80]}")
        return None
    if len(analyse) < 200:
        print(f"  ⚠ Analyse trop courte ({len(analyse)} chars)")
        return None
    if not s1_nom or not s2_nom or len(s1_nom) < 3 or len(s2_nom) < 3:
        print(f"  ⚠ Secteurs manquants: '{s1_nom}' / '{s2_nom}'")
        return None

    impact_marches = [
        {"secteur": s1_nom, "effet": s1_effet, "hausse": "HAUSSE" in s1_sens.upper()},
        {"secteur": s2_nom, "effet": s2_effet, "hausse": "HAUSSE" in s2_sens.upper()}
    ]
    badges = [
        {"label": f"{'▲' if i['hausse'] else '▼'} {i['secteur']}", "hausse": i["hausse"]}
        for i in impact_marches
    ]

    return {
        "titre_fr": titre_fr or titre,
        "resume": resume,
        "analyse_detaillee": analyse,
        "categorie": categorie or "Actualité",
        "badges": badges,
        "impact_marches": impact_marches
    }

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
                print(f"  [{i+1}] ❌ Ignoré")
                continue

            print(f"  [{i+1}] ✅ résumé={len(analyse['resume'])}c analyse={len(analyse['analyse_detaillee'])}c secteurs={len(analyse['impact_marches'])}")
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
