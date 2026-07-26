import os, json, requests, re, time
from datetime import datetime, timedelta

NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY")
MISTRAL_KEY = os.environ.get("MISTRAL_KEY")

PAYS = [
    {"id": "monde",  "query": "geopolitics NATO diplomacy sanctions 2026", "lang": "en"},
    {"id": "france", "query": "France Macron gouvernement economie 2026", "lang": "fr"},
    {"id": "usa",    "query": "Trump White House Congress Washington 2026", "lang": "en"},
    {"id": "chine",  "query": "China Beijing Xi Jinping Taiwan 2026", "lang": "en"},
    {"id": "russie", "query": "Russia Putin Kremlin Ukraine Kyiv Moscow 2026", "lang": "en"},
    {"id": "iran",   "query": "Iran Tehran nuclear Khamenei Hormuz 2026", "lang": "en"},
]

POLITIQUE = [
    {"id": "pol_femmes", "sous_categorie": "femmes"},
    {"id": "pol_enfants", "sous_categorie": "enfants"},
    {"id": "pol_env", "sous_categorie": "environnement"},
]

IMGS = {
    "monde":  "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&q=80",
    "france": "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?w=800&q=80",
    "usa":    "https://images.unsplash.com/photo-1485738422979-f5c462d49f74?w=800&q=80",
    "chine":  "https://images.unsplash.com/photo-1547981609-4b6bfe67ca0b?w=800&q=80",
    "russie": "https://images.unsplash.com/photo-1513326738677-b964603b136d?w=800&q=80",
    "iran":   "https://images.unsplash.com/photo-1527576539890-dfa815648363?w=800&q=80",
    "pol_femmes":  "https://loremflickr.com/800/450/womensrights,protest",
    "pol_enfants": "https://loremflickr.com/800/450/childcare,family",
    "pol_env":     "https://loremflickr.com/800/450/pollution,environment",
}

EXCLUS = ["market report","market size","market research","global market","forecasted",
          "show hn","hili dialogue","tutorial","subscribe","podcast","nfl","nba","sports","fireworks",
          "sensex","nifty","bse","bombay","mumbai","india stock","rupee","dalal street",
          "cricket","ipl","bollywood","weather","recipe","horoscope","lottery"]

def normalize(t):
    return re.sub(r'\s+', ' ', (t or "").lower().strip())[:80]

PAYS_KEYWORDS = {
    "monde":  [],  # pas de filtre strict pour monde
    "france": ["france","french","paris","macron","élysée","gouvernement","assemblée"],
    "usa":    ["trump","united states","washington","congress","american","white house","biden","democrat","republican"],
    "chine":  ["china","chinese","beijing","xi jinping","taiwan","hong kong","shanghai"],
    "russie": ["russia","russian","putin","kremlin","ukraine","kyiv","moscow","nato","zelensky"],
    "iran":   ["iran","iranian","tehran","khamenei","hormuz","nuclear","persian","irgc"],
}

def is_valid(title, desc, pays_id=None):
    if not title or title == "[Removed]" or len(title) < 20:
        return False
    text = (title + " " + (desc or "")).lower()
    if any(m in text for m in EXCLUS):
        return False
    # Vérifier que l'article est bien lié au pays concerné
    if pays_id and PAYS_KEYWORDS.get(pays_id):
        if not any(kw in text for kw in PAYS_KEYWORDS[pays_id]):
            return False
    return True

POL_KEYWORDS = {
    "femmes": ["féminicide","violence conjugale","violences faites aux femmes","femme battue","gynécolog"],
    "enfants": ["aide sociale à l'enfance","protection de l'enfance","enfant placé","pédopsychiatr","écran enfant","mineur"],
    "environnement": ["pesticide","pfas","polluant éternel","artificialisation","pollution de l'eau","zéro artificialisation"],
}

def newsapi_call(query, lang, page_size, days):
    """Un seul appel NewsAPI, retourne la liste brute d'articles (ou [] en cas d'échec)"""
    try:
        r = requests.get("https://newsapi.org/v2/everything", params={
            "q": query, "language": lang, "sortBy": "publishedAt",
            "pageSize": page_size, "apiKey": NEWSAPI_KEY,
            "from": (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        }, timeout=15)
        if r.status_code == 200:
            return r.json().get("articles", [])
        elif r.status_code == 429 or r.status_code == 426:
            print(f"  ⚠ QUOTA NewsAPI épuisé (HTTP {r.status_code}) — plus aucune actualité ne pourra être récupérée aujourd'hui.")
        else:
            print(f"  NewsAPI HTTP {r.status_code}: {r.text[:150]}")
    except Exception as e:
        print(f"  NewsAPI: {e}")
    return []

def classify_and_pick(articles, buckets_keywords, existing_titles_by_bucket, default_bucket=None):
    """Répartit une liste d'articles bruts dans des buckets (pays ou sous-catégorie) par mots-clés,
    et retourne au plus 1 nouvel article par bucket (le premier valide et non déjà vu)."""
    picked = {}
    for a in articles:
        titre = (a.get("title") or "").strip()
        desc = a.get("description") or ""
        if not is_valid(titre, desc):
            continue
        text = (titre + " " + desc).lower()
        norm = normalize(titre)

        bucket_found = None
        for bucket, kws in buckets_keywords.items():
            if kws and any(kw in text for kw in kws):
                bucket_found = bucket
                break
        if not bucket_found and default_bucket:
            bucket_found = default_bucket

        if not bucket_found or bucket_found in picked:
            continue
        if norm in existing_titles_by_bucket.get(bucket_found, set()):
            continue
        picked[bucket_found] = a
    return picked

def fetch_pays_articles(existing_by_id, days=2):
    """3 appels NewsAPI max : 1 pour les pays anglophones groupés, 1 pour France, classification locale."""
    existing_titles = {pid: {normalize(a.get("titre_original") or a.get("titre",""))
                             for a in existing_by_id.get(pid, [])} for pid in PAYS_KEYWORDS}

    # Appel 1 : tous les pays anglophones en une requête large
    en_query = "(NATO OR Trump OR \"Xi Jinping\" OR Putin OR Iran OR Kremlin OR Kyiv OR Beijing OR Washington OR Tehran OR Taiwan OR Ukraine)"
    en_articles = newsapi_call(en_query, "en", 50, days)
    en_buckets = {k: v for k, v in PAYS_KEYWORDS.items() if k != "france"}
    picked_en = classify_and_pick(en_articles, en_buckets, existing_titles, default_bucket="monde")

    # Appel 2 : France en français
    fr_articles = newsapi_call("France Macron gouvernement economie", "fr", 20, days)
    picked_fr = classify_and_pick(fr_articles, {"france": []}, existing_titles, default_bucket="france")

    picked = {**picked_en, **picked_fr}
    for pid in PAYS_KEYWORDS:
        if pid in picked:
            print(f"→ {pid.upper()}: {picked[pid].get('title','')[:60]}...")
        else:
            print(f"→ {pid.upper()}: aucun nouvel article")
    return picked

def fetch_politique_articles(existing_by_id, days=14):
    """1 seul appel NewsAPI pour les 3 sous-catégories politique, classification locale par mots-clés."""
    existing_titles = {sc: {normalize(a.get("titre_original") or a.get("titre",""))
                            for a in existing_by_id.get(sc, [])} for sc in POL_KEYWORDS}
    query = "féminicide OR \"protection de l'enfance\" OR pesticides OR PFAS OR \"pollution de l'eau\" OR \"violences conjugales\""
    articles = newsapi_call(query, "fr", 30, days)
    picked = classify_and_pick(articles, POL_KEYWORDS, existing_titles)
    for sc in POL_KEYWORDS:
        if sc in picked:
            print(f"→ POL_{sc.upper()}: {picked[sc].get('title','')[:60]}...")
        else:
            print(f"→ POL_{sc.upper()}: aucun nouvel article")
    return picked

def groq_call(prompt):
    for model in ["mistral-small-latest", "open-mistral-nemo", "mistral-large-latest"]:
        try:
            r = requests.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {MISTRAL_KEY}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 16000
                },
                timeout=60
            )
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"].strip()
            elif r.status_code == 429:
                print(f"  Rate limit {model}, attente 10s...")
                time.sleep(10)
            else:
                print(f"  {model}: HTTP {r.status_code} - {r.text[:100]}")
        except Exception as e:
            print(f"  {model}: {e}")
    return None

def analyser_tous(articles_par_pays):
    lines = []
    pays_order = []
    for pid, art in articles_par_pays.items():
        titre = (art.get("title") or "")[:150]
        desc = (art.get("description") or "")[:200]
        lines.append(f"PAYS:{pid} | TITRE:{titre} | DESC:{desc}")
        pays_order.append(pid)

    articles_txt = chr(10).join(f"{i+1}. {l}" for i,l in enumerate(lines))

    # ===== APPEL 1 : FR / EN / ZH + secteurs financiers =====
    prompt1 = f"""You are a journalist for Veritass.fr (French news site). Analyze these {len(lines)} news articles.
Return ONLY a valid JSON array, no markdown, no explanation.

Articles to analyze:
{articles_txt}

Return exactly {len(lines)} objects in this JSON array:
[
  {{
    "pays": "pays_id",
    "titre_fr": "titre français max 12 mots",
    "titre_en": "english title max 12 words",
    "titre_zh": "中文标题最多12字",
    "resume_fr": "Résumé 3 phrases complètes en français.",
    "resume_en": "Summary 3 complete sentences in English.",
    "resume_zh": "3句完整的中文摘要。",
    "analyse_fr": "Analyse 7 phrases en français: contexte historique, enjeux principaux, causes profondes, conséquences à court terme, conséquences à moyen terme, perspectives à long terme, position des acteurs.",
    "analyse_en": "Analysis 7 sentences in English: historical context, main stakes, root causes, short-term consequences, medium-term consequences, long-term prospects, position of actors.",
    "analyse_zh": "7句中文分析：历史背景、主要影响、深层原因、短期后果、中期后果、长期前景、各方立场。",
    "categorie": "Géopolitique",
    "s1_fr": "nom précis secteur financier impacté",
    "s1_en": "precise name of impacted financial sector",
    "s1_zh": "受影响金融行业的具体名称",
    "s1_effet_fr": "Une phrase expliquant l'impact sur ce secteur.",
    "s1_effet_en": "One sentence explaining the impact on this sector.",
    "s1_effet_zh": "一句话解释对该行业的影响。",
    "s1_hausse": true,
    "s2_fr": "second secteur financier différent",
    "s2_en": "second different financial sector",
    "s2_zh": "第二个不同的金融行业",
    "s2_effet_fr": "Une phrase pour le second secteur.",
    "s2_effet_en": "One sentence for the second sector.",
    "s2_effet_zh": "第二行业一句话。",
    "s2_hausse": false
  }}
]"""

    text1 = groq_call(prompt1)
    out = {}
    if text1:
        m1 = re.search(r'\[[\s\S]*\]', text1)
        if m1:
            try:
                results1 = json.loads(m1.group())
                for i, obj in enumerate(results1):
                    if i < len(pays_order):
                        out[pays_order[i]] = obj
            except Exception as e:
                print(f"  ⚠ Erreur JSON (appel 1 FR/EN/ZH): {e}")
        else:
            print("  ⚠ Pas de JSON array (appel 1 FR/EN/ZH)")
    else:
        print("  ⚠ Appel 1 FR/EN/ZH: aucune réponse")

    time.sleep(3)

    # ===== APPEL 2 : RU / FA / AR uniquement (léger, moins de risque de troncature) =====
    prompt2 = f"""You are a journalist. Translate these {len(lines)} news articles into Russian, Persian (Farsi) and Arabic.
Return ONLY a valid JSON array, no markdown, no explanation, no commentary.

Articles:
{articles_txt}

Return exactly {len(lines)} objects, in the SAME ORDER as the articles above:
[
  {{
    "pays": "pays_id",
    "titre_ru": "заголовок на русском максимум 12 слов",
    "titre_fa": "عنوان به فارسی حداکثر 12 کلمه",
    "titre_ar": "عنوان بالعربية 12 كلمة كحد أقصى",
    "resume_ru": "Резюме 3 полных предложения на русском языке.",
    "resume_fa": "خلاصه 3 جمله کامل به فارسی.",
    "resume_ar": "ملخص 3 جمل كاملة باللغة العربية.",
    "analyse_ru": "Анализ 5 предложений на русском: контекст, причины, последствия, перспективы, позиции сторон.",
    "analyse_fa": "تحلیل 5 جمله به فارسی: زمینه، علل، پیامدها، چشم‌انداز، موضع بازیگران.",
    "analyse_ar": "تحليل 5 جمل بالعربية: السياق، الأسباب، العواقب، الآفاق، مواقف الأطراف."
  }}
]"""

    text2 = groq_call(prompt2)
    if text2:
        m2 = re.search(r'\[[\s\S]*\]', text2)
        if m2:
            try:
                results2 = json.loads(m2.group())
                for i, obj in enumerate(results2):
                    if i < len(pays_order):
                        pid = pays_order[i]
                        if pid in out:
                            out[pid].update({
                                "titre_ru": obj.get("titre_ru",""),
                                "titre_fa": obj.get("titre_fa",""),
                                "titre_ar": obj.get("titre_ar",""),
                                "resume_ru": obj.get("resume_ru",""),
                                "resume_fa": obj.get("resume_fa",""),
                                "resume_ar": obj.get("resume_ar",""),
                                "analyse_ru": obj.get("analyse_ru",""),
                                "analyse_fa": obj.get("analyse_fa",""),
                                "analyse_ar": obj.get("analyse_ar",""),
                            })
            except Exception as e:
                print(f"  ⚠ Erreur JSON (appel 2 RU/FA/AR): {e}")
        else:
            print("  ⚠ Pas de JSON array (appel 2 RU/FA/AR)")
    else:
        print("  ⚠ Appel 2 RU/FA/AR: aucune réponse")

    return out

def load_existing():
    try:
        with open("news_data.json", "r", encoding="utf-8") as f:
            return json.load(f).get("articles", {})
    except:
        return {}

def load_existing_politique():
    try:
        with open("news_data.json", "r", encoding="utf-8") as f:
            return json.load(f).get("politique", [])
    except:
        return []

def clean_politique(arts):
    cutoff = datetime.now() - timedelta(days=180)
    seen, kept = set(), []
    for a in arts:
        if not a.get("titre_en") or len(a.get("titre_en","")) < 3:
            continue
        if not a.get("resume_en") or len(a.get("resume_en","")) < 10:
            continue
        try:
            if datetime.strptime(a.get("date","2020-01-01"), "%Y-%m-%d") < cutoff:
                continue
        except:
            pass
        k = normalize(a.get("titre_original") or a.get("titre",""))
        if k in seen:
            continue
        seen.add(k)
        kept.append(a)
    kept.sort(key=lambda x: x.get("created_at",""), reverse=True)
    return kept

def clean(data):
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
                if datetime.strptime(a.get("date","2020-01-01"), "%Y-%m-%d") < cutoff:
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

def build_article(pid, r, art, extra_fields=None):
    titre = (art.get("title") or "").strip()
    a = {
        "id": f"{pid}_{abs(hash(titre)) % 1000000}",
        "titre": r.get("titre_fr", titre),
        "titre_en": r.get("titre_en", titre),
        "titre_zh": r.get("titre_zh", titre),
        "titre_ru": r.get("titre_ru", titre),
        "titre_fa": r.get("titre_fa", titre),
        "titre_ar": r.get("titre_ar", titre),
        "titre_original": titre,
        "resume": r.get("resume_fr", ""),
        "resume_en": r.get("resume_en", ""),
        "resume_zh": r.get("resume_zh", ""),
        "resume_ru": r.get("resume_ru", ""),
        "resume_fa": r.get("resume_fa", ""),
        "resume_ar": r.get("resume_ar", ""),
        "analyse_detaillee": r.get("analyse_fr", ""),
        "analyse_en": r.get("analyse_en", ""),
        "analyse_zh": r.get("analyse_zh", ""),
        "analyse_ru": r.get("analyse_ru", ""),
        "analyse_fa": r.get("analyse_fa", ""),
        "analyse_ar": r.get("analyse_ar", ""),
        "categorie": r.get("categorie", "Actualité"),
        "source": art.get("source", {}).get("name", ""),
        "url": art.get("url", "#"),
        "image": art.get("urlToImage") or IMGS.get(pid, ""),
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
    if extra_fields:
        a.update(extra_fields)
    return a

def analyze_and_build(articles_bruts, items_by_id, group_name):
    """Analyse Groq + construction des articles finaux à partir d'un dict {pid: article_brut}"""
    nouveaux = {}
    if articles_bruts:
        print(f"\nAnalyse Groq [{group_name}] ({len(articles_bruts)} articles)...")
        resultats = analyser_tous(articles_bruts)
        for pid, r in resultats.items():
            if not r or not r.get("titre_en") or not r.get("resume_en"):
                print(f"  {pid}: ❌ résultat invalide")
                continue
            art = articles_bruts.get(pid, {})
            extra = {}
            item = items_by_id.get(pid)
            if item and item.get("sous_categorie"):
                extra["sous_categorie"] = item["sous_categorie"]
            nouveaux[pid] = build_article(pid, r, art, extra)
            print(f"  {pid}: ✅ {r.get('titre_fr','')[:50]}")
    return nouveaux

def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Démarrage (3 requêtes NewsAPI max par run)...")
    existing = clean(load_existing())
    existing_pol = clean_politique(load_existing_politique())

    # ===== ACTUALITÉ (6 pays, 2 appels NewsAPI seulement) =====
    picked_pays = fetch_pays_articles(existing)
    pays_items_by_id = {p["id"]: p for p in PAYS}
    nouveaux_analysés = analyze_and_build(picked_pays, pays_items_by_id, "Actualité")

    new_articles = {}
    for pays in PAYS:
        pid = pays["id"]
        nouveau = nouveaux_analysés.get(pid)
        old = existing.get(pid, [])
        if nouveau:
            old_f = [a for a in old if normalize(a.get("titre_original") or a.get("titre",""))
                     != normalize(nouveau.get("titre_original") or nouveau.get("titre",""))]
            new_articles[pid] = ([nouveau] + old_f)[:20]
        else:
            new_articles[pid] = old[:20]
        print(f"  {pid}: {len(new_articles[pid])} articles conservés")

    # ===== POLITIQUE (femmes/enfants/environnement, 1 seul appel NewsAPI) =====
    existing_pol_by_id = {p["sous_categorie"]: [a for a in existing_pol if a.get("sous_categorie") == p["sous_categorie"]] for p in POLITIQUE}
    picked_pol = fetch_politique_articles(existing_pol_by_id)
    pol_items_by_id = {p["sous_categorie"]: p for p in POLITIQUE}
    # picked_pol est keyé par sous_categorie ; on le remappe vers l'id pol_xxx pour build_article
    picked_pol_by_pid = {}
    for sc, art in picked_pol.items():
        item = pol_items_by_id.get(sc)
        if item:
            picked_pol_by_pid[item["id"]] = art
    items_by_pid_for_build = {p["id"]: p for p in POLITIQUE}
    nouveaux_pol = analyze_and_build(picked_pol_by_pid, items_by_pid_for_build, "Politique")

    new_pol_list = list(nouveaux_pol.values())
    for p in POLITIQUE:
        sc = p["sous_categorie"]
        pid = p["id"]
        keep_n = 5 if pid in nouveaux_pol else 6
        new_pol_list.extend(existing_pol_by_id.get(sc, [])[:keep_n])
    print(f"  politique: {len(new_pol_list)} articles au total")

    with open("news_data.json", "w", encoding="utf-8") as f:
        json.dump({
            "last_updated": datetime.now().strftime("%d/%m/%Y à %Hh%M"),
            "articles": new_articles,
            "politique": new_pol_list
        }, f, ensure_ascii=False, indent=2)

    total = sum(len(v) for v in new_articles.values()) + len(new_pol_list)
    print(f"\n✅ Terminé — {total} articles (6 mois conservés) — 3 requêtes NewsAPI utilisées ce run")

if __name__ == "__main__":
    main()
