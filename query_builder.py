# query_builder.py

import re
import google.generativeai as genai
from settings import SETTINGS

AR_LETTERS_RE = re.compile(r'[\u0600-\u06FF]')

# قاموس صغير "مستقر" لتوليد مفاتيح إنجليزية عندما يتعذر Gemini
NAIVE_EN_KEYWORDS = {
    # بلدان شائعة (زد لاحقاً حسب الحاجة)
    'السودان': ['Sudan'],
    'اليمن': ['Yemen'],
    'لبنان': ['Lebanon'],
    'فلسطين': ['Palestine', 'Gaza', 'West Bank'],
    'إسرائيل': ['Israel'],
    'مصر': ['Egypt'],
    # مفاهيم أخبار عامة
    'حرب': ['war', 'conflict', 'fighting'],
    'أهلية': ['civil'],
    'نزاع': ['conflict'],
    'هدنة': ['truce', 'ceasefire'],
    'مجاعة': ['famine', 'hunger'],
    'كوليرا': ['cholera'],
}

def _configure_gemini():
    key = SETTINGS.get('search_providers', {}).get('google_gemini', {}).get('api_key')
    if not key:
        print("تحذير: لا يوجد مفتاح Gemini.")
        return False
    try:
        genai.configure(api_key=key)
        return True
    except Exception as e:
        print(f"خطأ في إعداد Gemini: {e}")
        return False

def contains_arabic(txt: str) -> bool:
    return bool(AR_LETTERS_RE.search(txt or ''))

def generate_precise_query(user_query: str) -> str:
    clean = (user_query or '').strip()
    if len(clean.split()) <= 2:
        final_query = f'"{clean}"'
    else:
        final_query = clean
    print(f"تم بناء استعلام دقيق: {final_query}")
    return final_query

def translate_query_for_search(query: str) -> str | None:
    print(f"--- محاولة ترجمة الاستعلام: '{query} ' ---")
    if not _configure_gemini():
        return None
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"Translate this news search query to English, return only text:\n{query}"
        resp = model.generate_content(prompt)
        return resp.text.strip()
    except Exception as e:
        print(f"حدث خطأ أثناء الترجمة: {e}")
        return None

def naive_english_from_arabic(query: str) -> str | None:
    """إذا فشلت الترجمة، نولّد كلمات إنجليزية عامة بناءً على القاموس."""
    if not contains_arabic(query):
        return None
    keys = []
    for token in re.split(r'\s+', query.strip()):
        token = token.strip('"،.؟!:;()[]{}«»"\'')
        keys.extend(NAIVE_EN_KEYWORDS.get(token, []))
    # إضافة fallback عام لو لم نجد أي كلمة
    if not keys:
        keys = ['news', 'Middle East']  # عام لكنه يفتح لنا نتائج
    # صياغة بسيطة بدون OR (سنفصل subqueries لاحقاً)
    return " ".join(sorted(set(keys)))

def expand_query_semantically(query: str) -> str:
    print(f"--- بدء التوسع الدلالي للاستعلام: '{query} ' ---")
    if not _configure_gemini():
        return generate_precise_query(query)
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = (
            'أنت خبير تحسين استعلامات. ولّد 4 صيغ بديلة بالعربية والإنجليزية؛ '
            'ضع كل صيغة بين علامتي تنصيص وافصلها بـ OR. أعد السطر فقط.\n'
            f'الاستعلام: "{query}"'
        )
        resp = model.generate_content(prompt)
        return resp.text.strip().replace('\n', ' ')
    except Exception as e:
        print(f"حدث خطأ أثناء التوسع الدلالي: {e}")
        return generate_precise_query(query)

def simplify_and_broaden_query(query: str) -> str:
    print(f"--- بدء التبسيط الذكي (المرحلة 3) للاستعلام: '{query}' ---")
    try:
        if _configure_gemini():
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = (
                'Simplify to core keywords in Arabic and English. '
                'Separate with OR. No quotes or extra text.\n'
                f'Original: "{query}"'
            )
            resp = model.generate_content(prompt)
            return resp.text.strip().replace('\n', ' ')
    except Exception as e:
        print(f"حدث خطأ أثناء تبسيط الاستعلام: {e}")

    # Fallback: لو عربي، جرّب توليد مفاتيح إنجليزية بدائية وإلحاق الأصل
    eng = naive_english_from_arabic(query)
    if eng:
        return f"{query} OR {eng}"
    # وإلا نرجع الجملة كما هي
    return " ".join(query.split())
