# tasks.py
# هذا الملف يحتوي على المهمة الطويلة التي سيتم تشغيلها في الخلفية بواسطة Celery

import time
import urllib.parse
import numpy as np
from celery import Celery

# --- استيراد مكونات المشروع ---
# تأكد من أن هذه الملفات موجودة في نفس المجلد
from search_service import fetch_articles_from_all_providers
from deduplicator import (
    deduplicate_articles_simple,
    deduplicate_articles_semantic,
    get_unique_chunk_indices
)
from content_extractor import process_articles_in_parallel
from semantic_searcher import create_vector_index
from clusterer import cluster_chunks
from llm_summarizer import (
    extract_key_facts_with_sources,
    write_topic_content,
    assemble_final_report,
    format_references
)

# --- إعداد Celery ---
# نحن نتصل بـ Redis الذي يعمل كوسيط
celery_app = Celery('tasks', broker='redis://localhost:6379/0', backend='redis://localhost:6379/0')

@celery_app.task
def generate_report_task(user_query, period_days=14):
    """
    هذه هي المهمة الرئيسية التي تقوم بكل العمل الشاق.
    """
    start_time = time.time()

    # 1) جلب المقالات
    search_result = fetch_articles_from_all_providers(user_query, period_days)
    if not search_result.get('success') or not search_result.get('articles'):
        raise Exception("لم يتم العثور على مقالات حول هذا الموضوع.")

    # 2) تنقية مبدئية
    articles = deduplicate_articles_simple(search_result['articles'])

    # 3) استخراج المحتوى الكامل
    articles_full = process_articles_in_parallel(articles)

    # 4) إزالة تكرار دلالي
    unique_articles = deduplicate_articles_semantic(articles_full)

    # 5) استخلاص حقائق
    all_facts = extract_key_facts_with_sources(unique_articles)
    if not all_facts:
        return {
            "summary": "لم يتم العثور على معلومات كافية لبناء تقرير.",
            "articles": unique_articles,
            "total_time": round(time.time() - start_time, 2)
        }

    # 6) فهرسة المتجهات وإزالة تكرار الحقائق
    vector_index, _, all_embeddings = create_vector_index(all_facts)
    if not vector_index or all_embeddings is None:
        raise Exception("Failed to create vector index for facts.")

    unique_fact_indices = get_unique_chunk_indices(all_facts, all_embeddings)
    unique_facts = [all_facts[i] for i in unique_fact_indices]
    unique_embeddings = np.array([all_embeddings[i] for i in unique_fact_indices])

    # 7) عنقدة الحقائق
    clustered_topics = cluster_chunks(unique_facts, unique_embeddings)
    if not clustered_topics:
        raise Exception("فشل في بناء هيكل للمقال.")

    # 8) كتابة المحاور وتجميع التقرير
    used_urls = sorted(list({fact['source_url'] for fact in unique_facts if fact.get('source_url')}))
    reference_map = {url: i + 1 for i, url in enumerate(used_urls)}

    written_topics = {}
    for topic_title, topic_facts in clustered_topics.items():
        topic_content = write_topic_content(topic_title, topic_facts, reference_map)
        written_topics[topic_title] = topic_content
        time.sleep(4) # تهدئة لمراعاة حدود API

    final_report_body = assemble_final_report(user_query, written_topics)
    articles_for_citation = [a for a in unique_articles if a.get('url') in used_urls]
    references_section = format_references(articles_for_citation, reference_map)
    full_report = f"{final_report_body}{references_section}"

    # --- النتيجة النهائية التي سيتم إرجاعها ---
    return {
        "summary": full_report,
        "articles": unique_articles,
        "total_time": round(time.time() - start_time, 2)
    }
