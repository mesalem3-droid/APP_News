# search_service.py (إضافات مهمّة)

import requests, re, urllib.parse
from datetime import datetime, timedelta
from settings import SETTINGS
from query_builder import (
    generate_precise_query,
    translate_query_for_search,
    expand_query_semantically,
    simplify_and_broaden_query,
    contains_arabic, naive_english_from_arabic
)

MIN_RESULTS = 40
MAX_RESULTS = 60
PER_DOMAIN_CAP = 3  # حد أعلى لكل دومين لزيادة التنويع

def _split_or_query(q: str) -> list[str]:
    parts = [p.strip().strip('"') for p in q.split('OR')]
    return [p for p in parts if p]

def _domain_of(url: str) -> str:
    try:
        from urllib.parse import urlparse
        net = urlparse(url).netloc.lower()
        return net.replace('www.', '')
    except Exception:
        return 'unknown'

def _enforce_diversity_and_limit(articles: list, max_count=MAX_RESULTS, per_domain_cap=PER_DOMAIN_CAP) -> list:
    # ترتيب حسب publishedAt (الأحدث أولاً) إن توفّر، وإلا اترك كما هو
    def _ts(a):
        ts = a.get('publishedAt') or ''
        try:
            return datetime.fromisoformat(ts.replace('Z','+00:00'))
        except Exception:
            return datetime.min
    sorted_list = sorted(articles, key=_ts, reverse=True)

    by_domain_used = {}
    diversified = []
    for a in sorted_list:
        url = a.get('url')
        if not url: 
            continue
        d = _domain_of(url)
        used = by_domain_used.get(d, 0)
        if used >= per_domain_cap:
            continue
        diversified.append(a)
        by_domain_used[d] = used + 1
        if len(diversified) >= max_count:
            break
    return diversified

def _try_newsapi_one_mode(q: str, from_date: str, lang: str, mode: str, api_key: str, base_url: str, timeout_sec=12) -> dict:
    params = {
        'apiKey': api_key,
        'from': from_date,
        'language': lang,
        'pageSize': 100,
        'sortBy': 'publishedAt'
    }
    params[mode] = q
    try:
        r = requests.get(base_url, params=params, timeout=timeout_sec)
        if r.status_code != 200:
            print(f"NewsAPI {lang}/{mode} HTTP {r.status_code}: {r.text[:160]}")
            return {}
        data = r.json() or {}
        arts = data.get('articles', []) or []
        return {a.get('url'): a for a in arts if a.get('url')}
    except Exception as e:
        print(f"NewsAPI error ({lang}/{mode}): {e}")
        return {}

def _fetch_from_newsapi(query: str, period_days: int, timeout_sec=12) -> dict:
    print(f"--- محاولة البحث في NewsAPI عن: '{query}' ---")
    cfg = SETTINGS.get('search_providers', {}).get('newsapi', {})
    api_key, base_url = cfg.get('api_key'), cfg.get('base_url')
    if not api_key or not base_url:
        return {"success": False, "articles": []}

    from_date = (datetime.now() - timedelta(days=period_days)).strftime('%Y-%m-%dT%H:%M:%SZ')
    subqueries = _split_or_query(query) or [query]

    combined = {}
    languages = ['ar', 'en']      # نجرب الاثنين دائمًا
    modes = ['q', 'qInTitle']     # بحث عام + عنوان فقط

    for sq in subqueries:
        for lang in languages:
            for mode in modes:
                got = _try_newsapi_one_mode(sq, from_date, lang, mode, api_key, base_url, timeout_sec=timeout_sec)
                combined.update(got)

    if combined:
        print(f"نجح البحث في NewsAPI: {len(combined)} مقال (مجمّع).")
        return {"success": True, "articles": list(combined.values())}
    print("فشل البحث في NewsAPI.")
    return {"success": False, "articles": []}

def _fetch_from_gnews(query: str, period_days: int, timeout_sec=15) -> dict:
    print(f"--- (احتياطي) محاولة البحث في GNews عن: '{query}' ---")
    cfg = SETTINGS.get('search_providers', {}).get('gnews', {})
    api_key, base_url = cfg.get('api_key'), cfg.get('base_url')
    if not api_key or not base_url:
        return {"success": False, "articles": []}

    from_date = (datetime.now() - timedelta(days=period_days)).strftime('%Y-%m-%dT%H:%M:%SZ')
    subqueries = _split_or_query(query) or [query]

    combined = {}
    for sq in subqueries:
        for lang in ['ar', 'en']:   # صريحتين بدل any
            params = {'q': sq, 'apikey': api_key, 'from': from_date, 'max': 100, 'lang': lang}
            try:
                r = requests.get(base_url, params=params, timeout=timeout_sec)
                if r.status_code != 200:
                    print(f"GNews {lang} HTTP {r.status_code}: {r.text[:160]}")
                    continue
                for a in (r.json() or {}).get('articles', []) or []:
                    url = a.get('url')
                    if not url: continue
                    combined[url] = {
                        'source': {'name': (a.get('source') or {}).get('name', 'غير معروف')},
                        'title': a.get('title'),
                        'url': url,
                        'description': a.get('description'),
                        'publishedAt': a.get('publishedAt'),
                        'urlToImage': a.get('image'),
                        'content': a.get('content')
                    }
            except Exception as e:
                print(f"GNews error ({lang}): {e}")
                continue

    if combined:
        print(f"نجح البحث في GNews: {len(combined)} مقال (مجمّع).")
        return {"success": True, "articles": list(combined.values())}
    print("فشل البحث في GNews.")
    return {"success": False, "articles": []}

def _broaden_strategies(user_query: str, stage: int, base_period: int) -> tuple[str, int]:
    """
    استراتيجيات توسيع عندما لا نبلغ الحد الأدنى:
    - stage 0: الاستعلام الدقيق + ترجمة (إن توفرت)
    - stage 1: التوسع الدلالي
    - stage 2: تبسيط/توسيع
    - stage 3: إزالة الاقتباسات + إضافة نسخة إنجليزية بدائية + مضاعفة الفترة
    """
    if stage == 3:
        raw = " ".join(user_query.split())
        eng = naive_english_from_arabic(user_query) if contains_arabic(user_query) else None
        q = f"{raw} OR {eng}" if eng else raw
        return q, min(base_period * 2, 60)  # لا نتجاوز 60 يومًا افتراضيًا
    return user_query, base_period

def fetch_articles_from_all_providers(user_query: str, period_days: int) -> dict:
    try:
        all_found = {}

        # STAGE 0: بحث دقيق + نسخة إنجليزية إن أمكن
        print("\n--- المرحلة 1: البحث الدقيق ---")
        precise = generate_precise_query(user_query)
        translated = translate_query_for_search(user_query)
        if not translated and contains_arabic(user_query):
            naive_eng = naive_english_from_arabic(user_query)
            if naive_eng:
                translated = naive_eng
        precise_mix = precise
        if translated and translated.lower() != user_query.lower():
            precise_mix += f" OR {generate_precise_query(translated)}"

        # جرّب NewsAPI
        res = _fetch_from_newsapi(precise_mix, period_days, timeout_sec=12)
        if res.get('success'):
            for a in res['articles']: all_found[a['url']] = a

        # لو أقل من الحد الأدنى، GNews
        if len(all_found) < MIN_RESULTS:
            res = _fetch_from_gnews(precise_mix, period_days, timeout_sec=15)
            if res.get('success'):
                for a in res['articles']: all_found[a['url']] = a

        # STAGE 1: توسع دلالي
        if len(all_found) < MIN_RESULTS:
            print("\n--- المرحلة 2: التوسع الدلالي ---")
            expanded = expand_query_semantically(user_query)
            res = _fetch_from_newsapi(expanded, period_days, timeout_sec=12)
            if res.get('success'):
                for a in res['articles']: all_found[a['url']] = a
            if len(all_found) < MIN_RESULTS:
                res = _fetch_from_gnews(expanded, period_days, timeout_sec=15)
                if res.get('success'):
                    for a in res['articles']: all_found[a['url']] = a

        # STAGE 2: تبسيط/توسيع
        if len(all_found) < MIN_RESULTS:
            print("\n--- المرحلة 3: التبسيط ---")
            broad = simplify_and_broaden_query(user_query)
            res = _fetch_from_newsapi(broad, period_days, timeout_sec=12)
            if res.get('success'):
                for a in res['articles']: all_found[a['url']] = a
            if len(all_found) < MIN_RESULTS:
                res = _fetch_from_gnews(broad, period_days, timeout_sec=15)
                if res.get('success'):
                    for a in res['articles']: all_found[a['url']] = a

        # STAGE 3: توسيع إضافي قوي (إزالة اقتباسات + مضاعفة المدة)
        if len(all_found) < MIN_RESULTS:
            print("\n--- المرحلة 4: توسيع إضافي ---")
            q4, pd4 = _broaden_strategies(user_query, stage=3, base_period=period_days)
            res = _fetch_from_newsapi(q4, pd4, timeout_sec=15)
            if res.get('success'):
                for a in res['articles']: all_found[a['url']] = a
            if len(all_found) < MIN_RESULTS:
                res = _fetch_from_gnews(q4, pd4, timeout_sec=20)
                if res.get('success'):
                    for a in res['articles']: all_found[a['url']] = a

        if not all_found:
            return {"success": False, "articles": []}

        # تنويع + قطع للحد الأعلى
        diversified = _enforce_diversity_and_limit(list(all_found.values()), max_count=MAX_RESULTS, per_domain_cap=PER_DOMAIN_CAP)
        print(f"\nاكتمل البحث: {len(diversified)} مقال (بعد التنويع والقصّ).")
        return {"success": True, "articles": diversified}
    except Exception as e:
        print(f"[fetch_articles_from_all_providers] خطأ غير متوقع: {e}")
        return {"success": False, "articles": []}
