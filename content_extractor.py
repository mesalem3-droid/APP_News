# content_extractor.py
# استخراج محتوى المقالات

import trafilatura
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_and_extract_content(article: dict) -> dict:
    url = article.get('url')  # مهم: كان 'link'
    if not url:
        return article

    print(f"جاري جلب المحتوى من: {url}")

    # بعض إصدارات trafilatura لا تدعم no_fallback؛ نستخدم الاستدعاء البسيط المتوافق
    try:
        downloaded_text = trafilatura.fetch_url(
            url,
            include_comments=False,   # مدعوم عادةً
            target_language='ar'      # تحسين للاحتواء العربي؛ لا يضر بالإنجليزي
        )
    except TypeError:
        # توافق للخلف إذا لم يدعم include_comments/target_language
        downloaded_text = trafilatura.fetch_url(url)

    if downloaded_text:
        article['content'] = downloaded_text
        print(f"تم استخراج المحتوى بنجاح من: {url}")
    else:
        print(f"فشل استخراج المحتوى من: {url}.")
    return article

def process_articles_in_parallel(articles: list) -> list:
    updated = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_and_extract_content, a): a for a in articles}
        for fut in as_completed(futures):
            try:
                updated.append(fut.result())
            except Exception as e:
                print(f"خطأ أثناء معالجة {futures[fut].get('url')}: {e}")
                updated.append(futures[fut])
    print(f"اكتملت معالجة {len(updated)} مقال.")
    return updated
