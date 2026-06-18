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

Rédige ta réponse en suivant EXACTEMENT ce format avec les balises.
Tout le contenu doit être rédigé en FRANÇAIS sauf les sections EN et ZH indiquées.

[TITRE_FR]
Reformule le titre en français journalistique, maximum 15 mots.
[/TITRE_FR]

[TITRE_EN]
Same title translated in English, maximum 15 words.
[/TITRE_EN]

[TITRE_ZH]
同一标题的中文翻译，最多15个字。
[/TITRE_ZH]

[RESUME]
Écris un résumé de 4 phrases complètes en FRANÇAIS : le fait principal, le contexte, la conséquence immédiate, et la réaction des acteurs concernés.
[/RESUME]

[RESUME_EN]
Write the same summary in English, 4 complete sentences.
[/RESUME_EN]

[RESUME_ZH]
用中文写同样的摘要，4个完整句子。
[/RESUME_ZH]

[ANALYSE]
Rédige en FRANÇAIS une analyse de 7 phrases minimum : contexte historique, enjeux pour les acteurs, causes profondes, conséquences à court terme, conséquences à moyen terme, perspectives à long terme, position des différentes parties.
[/ANALYSE]

[ANALYSE_EN]
Write the same detailed analysis in English, minimum 7 sentences.
[/ANALYSE_EN]

[ANALYSE_ZH]
用中文写同样的详细分析，至少7句话。
[/ANALYSE_ZH]

[CATEGORIE]
Un seul mot parmi : Politique, Économie, Géopolitique, Énergie, Tech, Justice, Social, Diplomatie, Environnement, Santé, Sécurité
[/CATEGORIE]

[SECTEUR1_NOM]
Nom précis d'un secteur financier impacté (ex: Pétrole Brent, Actions défense, CAC 40, EUR/USD, Obligations d'État, Semi-conducteurs, Compagnies aériennes, Or, Banques européennes)
[/SECTEUR1_NOM]

[SECTEUR1_NOM_EN]
Same sector name in English
[/SECTEUR1_NOM_EN]

[SECTEUR1_NOM_ZH]
同一行业的中文名称
[/SECTEUR1_NOM_ZH]

[SECTEUR1_EFFET]
Une phrase en français expliquant pourquoi ce secteur est impacté par cet événement.
[/SECTEUR1_EFFET]

[SECTEUR1_EFFET_EN]
Same explanation in English.
[/SECTEUR1_EFFET_EN]

[SECTEUR1_EFFET_ZH]
同样的解释用中文。
[/SECTEUR1_EFFET_ZH]

[SECTEUR1_SENS]
HAUSSE ou BAISSE
[/SECTEUR1_SENS]

[SECTEUR2_NOM]
Deuxième secteur financier précis différent du premier.
[/SECTEUR2_NOM]

[SECTEUR2_NOM_EN]
Same sector in English
[/SECTEUR2_NOM_EN]

[SECTEUR2_NOM_ZH]
中文名称
[/SECTEUR2_NOM_ZH]

[SECTEUR2_EFFET]
Une phrase en français expliquant l'impact sur ce deuxième secteur.
[/SECTEUR2_EFFET]

[SECTEUR2_EFFET_EN]
Same in English.
[/SECTEUR2_EFFET_EN]

[SECTEUR2_EFFET_ZH]
中文解释。
[/SECTEUR2_EFFET_ZH]

[SECTEUR2_SENS]
HAUSSE ou BAISSE
[/SECTEUR2_SENS]

Respecte STRICTEMENT toutes les balises. Rédige du contenu réel développé."""

    text = appel_gemini(prompt, max_tokens=3000)
    if not text:
        return None

    titre_fr   = parse_section(text, "TITRE_FR")
    titre_en   = parse_section(text, "TITRE_EN")
    titre_zh   = parse_section(text, "TITRE_ZH")
    resume_fr  = parse_section(text, "RESUME")
    resume_en  = parse_section(text, "RESUME_EN")
    resume_zh  = parse_section(text, "RESUME_ZH")
    analyse_fr = parse_section(text, "ANALYSE")
    analyse_en = parse_section(text, "ANALYSE_EN")
    analyse_zh = parse_section(text, "ANALYSE_ZH")
    categorie  = parse_section(text, "CATEGORIE")
    s1_nom_fr  = parse_section(text, "SECTEUR1_NOM")
    s1_nom_en  = parse_section(text, "SECTEUR1_NOM_EN")
    s1_nom_zh  = parse_section(text, "SECTEUR1_NOM_ZH")
    s1_eff_fr  = parse_section(text, "SECTEUR1_EFFET")
    s1_eff_en  = parse_section(text, "SECTEUR1_EFFET_EN")
    s1_eff_zh  = parse_section(text, "SECTEUR1_EFFET_ZH")
    s1_sens    = parse_section(text, "SECTEUR1_SENS")
    s2_nom_fr  = parse_section(text, "SECTEUR2_NOM")
    s2_nom_en  = parse_section(text, "SECTEUR2_NOM_EN")
    s2_nom_zh  = parse_section(text, "SECTEUR2_NOM_ZH")
    s2_eff_fr  = parse_section(text, "SECTEUR2_EFFET")
    s2_eff_en  = parse_section(text, "SECTEUR2_EFFET_EN")
    s2_eff_zh  = parse_section(text, "SECTEUR2_EFFET_ZH")
    s2_sens    = parse_section(text, "SECTEUR2_SENS")

    # Validation minimale
    if len(resume_fr) < 60 or len(analyse_fr) < 200 or not s1_nom_fr or not s2_nom_fr:
        print(f"  ⚠ Validation échouée: résumé={len(resume_fr)}, analyse={len(analyse_fr)}, s1='{s1_nom_fr}', s2='{s2_nom_fr}'")
        return None

    s1_hausse = "HAUSSE" in s1_sens.upper()
    s2_hausse = "HAUSSE" in s2_sens.upper()

    return {
        "titre_fr": titre_fr or titre,
        "titre_en": titre_en or titre,
        "titre_zh": titre_zh or titre,
        "resume_fr": resume_fr,
        "resume_en": resume_en or resume_fr,
        "resume_zh": resume_zh or resume_fr,
        "analyse_fr": analyse_fr,
        "analyse_en": analyse_en or analyse_fr,
        "analyse_zh": analyse_zh or analyse_fr,
        "categorie": categorie or "Actualité",
        "badges": [
            {"label": f"{'▲' if s1_hausse else '▼'} {s1_nom_fr}", "hausse": s1_hausse},
            {"label": f"{'▲' if s2_hausse else '▼'} {s2_nom_fr}", "hausse": s2_hausse},
        ],
        "impact_marches": [
            {"secteur_fr": s1_nom_fr, "secteur_en": s1_nom_en, "secteur_zh": s1_nom_zh,
             "effet_fr": s1_eff_fr, "effet_en": s1_eff_en, "effet_zh": s1_eff_zh,
             "hausse": s1_hausse},
            {"secteur_fr": s2_nom_fr, "secteur_en": s2_nom_en, "secteur_zh": s2_nom_zh,
             "effet_fr": s2_eff_fr, "effet_en": s2_eff_en, "effet_zh": s2_eff_zh,
             "hausse": s2_hausse},
        ]
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

            print(f"  [{i+1}] ✅ résumé={len(analyse['resume_fr'])}c analyse={len(analyse['analyse_fr'])}c secteurs={len(analyse['impact_marches'])}")
            nouveaux.append({
                "id": art_id,
                "titre": analyse["titre_fr"] or titre,
                "titre_en": analyse.get("titre_en", titre),
                "titre_zh": analyse.get("titre_zh", titre),
                "titre_original": titre,
                "resume": analyse["resume_fr"],
                "resume_en": analyse.get("resume_en", ""),
                "resume_zh": analyse.get("resume_zh", ""),
                "analyse_detaillee": analyse["analyse_fr"],
                "analyse_en": analyse.get("analyse_en", ""),
                "analyse_zh": analyse.get("analyse_zh", ""),
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
