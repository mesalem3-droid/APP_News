# llm_summarizer.py
# تمت إضافة دوال محاكاة للاختبار دون استهلاك حصة API

import google.generativeai as genai
from settings import SETTINGS
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- *** دوال المحاكاة (للاختبار فقط) *** ---

def mock_extract_key_facts_with_sources(articles: list) -> list[dict]:
    print("--- [محاكاة] استخلاص حقائق وهمية ---")
    mock_facts = []
    for i, article in enumerate(articles):
        mock_facts.append({'text': f'هذه حقيقة وهمية رقم {i+1} من المقال.', 'source_url': article.get('url')})
        mock_facts.append({'text': f'وهذه معلومة أخرى وهمية رقم {i+1} من نفس المقال.', 'source_url': article.get('url')})
    return mock_facts

def mock_generate_report_outline(query: str, facts: list[dict]) -> list[str]:
    print("--- [محاكاة] إنشاء هيكل وهمي ---")
    return [
        "المحور الوهمي الأول: مقدمة",
        "المحور الوهمي الثاني: التفاصيل",
        "المحور الوهمي الثالث: الخاتمة"
    ]

def mock_write_topic_content(topic_title: str, relevant_facts_with_sources: list[dict], reference_map: dict) -> str:
    print(f"--- [محاكاة] كتابة محتوى وهمي لمحور: '{topic_title}' ---")
    return f"هذا نص وهمي تم إنشاؤه لمحور '{topic_title}'. النص يحتوي على تفاصيل ومعلومات وهمية [1] لغرض اختبار النظام وشكله النهائي [2]."

def mock_assemble_final_report(query: str, written_topics: dict) -> str:
    print("--- [محاكاة] تجميع تقرير وهمي نهائي ---")
    topics_context = ""
    for title, content in written_topics.items():
        topics_context += f"### {title}\n{content}\n\n"
    
    return f"### ملخص تنفيذي\nهذا ملخص تنفيذي وهمي للموضوع '{query}'.\n\n{topics_context}\n### خاتمة\nوهذه خاتمة وهمية تلخص كل المحاور الوهمية."

# --- الدوال الحقيقية (تبقى كما هي) ---

def configure_gemini():
    google_api_key = SETTINGS.get('search_providers', {}).get('google_gemini', {}).get('api_key')
    if not google_api_key: return False
    try:
        genai.configure(api_key=google_api_key)
        return True
    except Exception: return False

def _extract_facts_from_one_article(article: dict) -> list[dict]:
    content, url = article.get('content'), article.get('url')
    if not content or not url: return []
    prompt = SETTINGS.get('llm_prompts', {}).get('fact_extraction_prompt', '').format(context=content)
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        facts_text = [fact.strip() for fact in response.text.split('\n') if fact.strip()]
        return [{'text': fact, 'source_url': url} for fact in facts_text]
    except Exception as e:
        print(f"خطأ أثناء استخلاص الحقائق من {url}: {e}")
        return []

def extract_key_facts_with_sources(articles: list) -> list[dict]:
    print("--- بدء استخلاص الحقائق الأساسية مع مصادرها ---")
    if not configure_gemini(): return []
    all_facts = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futs = {executor.submit(_extract_facts_from_one_article, article) for article in articles}
        for fut in as_completed(futs):
            all_facts.extend(fut.result())
    print(f"تم استخلاص {len(all_facts)} حقيقة من جميع المصادر.")
    return all_facts

def generate_report_outline(query: str, facts: list[dict]) -> list[str]:
    print("--- بدء إنشاء هيكل المقال ---")
    if not facts: return []
    facts_context = "\n".join([fact['text'] for fact in facts])
    prompt = SETTINGS.get('llm_prompts', {}).get('outline_generation_prompt', '').format(query=query, facts=facts_context)
    try:
        if not configure_gemini(): return []
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        outline = [title.strip() for title in response.text.split('\n') if title.strip()]
        print(f"تم إنشاء هيكل مكون من {len(outline)} محور.")
        return outline
    except Exception as e:
        print(f"خطأ أثناء إنشاء الهيكل: {e}")
        return []

def write_topic_content(topic_title: str, relevant_facts_with_sources: list[dict], reference_map: dict) -> str:
    print(f"--- بدء كتابة محتوى محور: '{topic_title}' ---")
    if not relevant_facts_with_sources: return "لم يتم العثور على معلومات كافية."
    facts_context = ""
    for fact in relevant_facts_with_sources:
        ref_num = reference_map.get(fact['source_url'])
        if ref_num: facts_context += f"[{ref_num}] {fact['text']}\n"
    prompt = SETTINGS.get('llm_prompts', {}).get('topic_writing_prompt', '').format(topic_title=topic_title, facts=facts_context)
    try:
        if not configure_gemini(): return "خدمة الذكاء الاصطناعي غير متاحة."
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"خطأ أثناء كتابة المحور '{topic_title}': {e}")
        return f"(فشلت كتابة هذا المحور)"

def assemble_final_report(query: str, written_topics: dict) -> str:
    print("--- بدء تجميع التقرير النهائي ---")
    topics_context = "\n\n".join([f"### {title}\n{content}" for title, content in written_topics.items()])
    prompt = SETTINGS.get('llm_prompts', {}).get('final_report_assembly_prompt', '').format(query=query, written_topics=topics_context)
    try:
        if not configure_gemini(): return "خدمة الذكاء الاصطناعي غير متاحة."
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"خطأ أثناء تجميع التقرير النهائي: {e}")
        return f"(فشل تجميع التقرير)"

def format_references(articles_for_citation: list, reference_map: dict) -> str:
    print("--- إنشاء قائمة المراجع ---")
    sorted_refs = sorted(reference_map.items(), key=lambda item: item[1])
    parts = ["\n\n---\n### المراجع"]
    articles_by_url = {article['url']: article for article in articles_for_citation}
    for url, ref_num in sorted_refs:
        article = articles_by_url.get(url)
        if article:
            try:
                import locale
                locale.setlocale(locale.LC_TIME, 'ar_SA.UTF-8')
                date_obj = datetime.fromisoformat(article['publishedAt'].replace('Z', '+00:00'))
                date = date_obj.strftime('%Y %B %d')
            except Exception: date = "تاريخ غير متوفر"
            source = article.get('source', {}).get('name', 'مصدر غير معروف')
            parts.append(f"[{ref_num}] {source}, {date}.")
    return "\n".join(parts)
