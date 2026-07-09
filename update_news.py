import os, json, requests, re, time
from datetime import datetime, timedelta

NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY")
GROQ_KEY = os.environ.get("GROQ_KEY")

PAYS = [
    {"id": "monde",  "query": "geopolitics NATO diplomacy sanctions 2026", "lang": "en"},
    {"id": "france", "query": "France Macron gouvernement economie 2026", "lang": "fr"},
    {"id": "usa",    "query": "Trump White House Congress Washington 2026", "lang": "en"},
    {"id": "chine",  "query": "China Beijing Xi Jinping Taiwan 2026", "lang": "en"},
    {"id": "russie", "query": "Russia Putin Kremlin Ukraine Kyiv Moscow 2026", "lang": "en"},
    {"id": "iran",   "query": "Iran Tehran nuclear Khamenei Hormuz 2026", "lang": "en"},
]

IMGS = {
    "monde":  "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&q=80",
    "france": "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?w=800&q=80",
    "usa":    "https://images.unsplash.com/photo-1485738422979-f5c462d49f74?w=800&q=80",
    "chine":  "https://images.unsplash.com/photo-1547981609-4b6bfe67ca0b?w=800&q=80",
    "russie": "https://images.unsplash.com/photo-1513326738677-b964603b136d?w=800&q=80",
    "iran":   "https://images.unsplash.com/photo-1527576539890-dfa815648363?w=800&q=80",
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

def get_one_article(query, lang, existing_titles, pays_id=None):
    try:
        r = requests.get("https://newsapi.org/v2/everything", params={
            "q": query, "language": lang, "sortBy": "publishedAt",
            "pageSize": 10, "apiKey": NEWSAPI_KEY,
            "from": (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        }, timeout=10)
        if r.status_code == 200:
            for a in r.json().get("articles", []):
                titre = (a.get("title") or "").strip()
                if is_valid(titre, a.get("description"), pays_id) and normalize(titre) not in existing_titles:
                    return a
    except Exception as e:
        print(f"  NewsAPI: {e}")
    return None

def groq_call(prompt):
    for model in ["llama-3.3-70b-versatile", "llama3-70b-8192", "mixtral-8x7b-32768"]:
        try:
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 4000
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

    prompt = f"""You are a journalist for Veritass.fr (French news site). Analyze these {len(lines)} news articles.
Return ONLY a valid JSON array, no markdown, no explanation.

Articles to analyze:
{chr(10).join(f"{i+1}. {l}" for i,l in enumerate(lines))}

Return exactly {len(lines)} objects in this JSON array:
[
  {{
    "pays": "pays_id",
    "titre_fr": "titre français max 12 mots",
    "titre_en": "english title max 12 words",
    "titre_zh": "中文标题最多12字",
    "titre_ru": "заголовок на русском максимум 12 слов",
    "titre_fa": "عنوان به فارسی حداکثر 12 کلمه",
    "titre_ar": "عنوان بالعربية 12 كلمة كحد أقصى",
    "resume_fr": "Résumé 3 phrases complètes en français.",
    "resume_en": "Summary 3 complete sentences in English.",
    "resume_zh": "3句完整的中文摘要。",
    "resume_ru": "Резюме 3 полных предложения на русском языке.",
    "resume_fa": "خلاصه 3 جمله کامل به فارسی.",
    "resume_ar": "ملخص 3 جمل كاملة باللغة العربية.",
    "analyse_fr": "Analyse 5 phrases en français: contexte historique, enjeux principaux, conséquences à court terme, perspectives à long terme, position des acteurs.",
    "analyse_en": "Analysis 5 sentences in English: historical context, main stakes, short-term consequences, long-term prospects, position of actors.",
    "analyse_zh": "5句中文分析：历史背景、主要影响、短期后果、长期前景、各方立场。",
    "analyse_ru": "Анализ 5 предложений на русском: исторический контекст, основные проблемы, краткосрочные последствия, долгосрочные перспективы, позиции сторон.",
    "analyse_fa": "تحلیل 5 جمله به فارسی: زمینه تاریخی، مسائل اصلی، پیامدهای کوتاه‌مدت، چشم‌اندازهای بلندمدت، موضع بازیگران.",
    "analyse_ar": "تحليل 5 جمل بالعربية: السياق التاريخي، القضايا الرئيسية، العواقب قصيرة المدى، الآفاق طويلة المدى، مواقف الأطراف.",
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

    text = groq_call(prompt)
    if not text:
        return {}

    m = re.search(r'\[[\s\S]*\]', text)
    if not m:
        print("  ⚠ Pas de JSON array trouvé")
        return {}

    try:
        results = json.loads(m.group())
        out = {}
        for i, obj in enumerate(results):
            pid = obj.get("pays") or (pays_order[i] if i < len(pays_order) else None)
            if pid:
                out[pid] = obj
        return out
    except Exception as e:
        print(f"  ⚠ Erreur JSON: {e}")
        return {}

def load_existing():
    try:
        with open("news_data.json", "r", encoding="utf-8") as f:
            return json.load(f).get("articles", {})
    except:
        return {}

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

def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Démarrage (Groq)...")
    existing = clean(load_existing())

    # Collecter un article par pays
    articles_bruts = {}
    for pays in PAYS:
        pid = pays["id"]
        existing_titles = {normalize(a.get("titre_original") or a.get("titre",""))
                          for a in existing.get(pid, [])}
        art = get_one_article(pays["query"], pays["lang"], existing_titles, pid)
        if art:
            titre = (art.get("title") or "").strip()
            print(f"→ {pid.upper()}: {titre[:60]}...")
            articles_bruts[pid] = art
        else:
            print(f"→ {pid.upper()}: aucun nouvel article")

    # Une seule requête Groq pour tout analyser
    nouveaux_analysés = {}
    if articles_bruts:
        print(f"\nAnalyse Groq ({len(articles_bruts)} articles)...")
        resultats = analyser_tous(articles_bruts)

        for pid, r in resultats.items():
            if not r or not r.get("titre_en") or not r.get("resume_en"):
                print(f"  {pid}: ❌ résultat invalide")
                continue
            art = articles_bruts.get(pid, {})
            titre = (art.get("title") or "").strip()
            nouveaux_analysés[pid] = {
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
            print(f"  {pid}: ✅ {r.get('titre_fr','')[:50]}")

    # Fusionner nouveaux + anciens (6 mois)
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

    with open("news_data.json", "w", encoding="utf-8") as f:
        json.dump({
            "last_updated": datetime.now().strftime("%d/%m/%Y à %Hh%M"),
            "articles": new_articles
        }, f, ensure_ascii=False, indent=2)

    total = sum(len(v) for v in new_articles.values())
    print(f"\n✅ Terminé — {total} articles (6 mois conservés)")

if __name__ == "__main__":
    main()
