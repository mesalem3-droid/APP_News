# deduplicator.py
# هذا الملف مسؤول عن إزالة المقالات والمقاطع النصية المكررة.

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from settings import SETTINGS

# --- استيراد النموذج اللغوي متعدد اللغات من semantic_searcher ---
# هذا النموذج ضروري لفهم معنى النصوص بلغات مختلفة
try:
    from semantic_searcher import model
except ImportError:
    print("تحذير: لم يتم العثور على النموذج اللغوي. الفلترة الدلالية للمقالات لن تعمل.")
    model = None

def deduplicate_articles_simple(articles: list) -> list:
    """
    تزيل المقالات المكررة بناءً على الرابط والعنوان.
    هذه هي أول طبقة من الفلترة السريعة.
    """
    seen_urls = set()
    seen_titles = set()
    unique_articles = []
    
    for article in articles:
        url = article.get('url')
        title = article.get('title', '').strip().lower()
        
        # نعتبر المقال فريدًا فقط إذا لم نرَ رابطه أو عنوانه من قبل
        if url and url not in seen_urls and title and title not in seen_titles:
            unique_articles.append(article)
            seen_urls.add(url)
            seen_titles.add(title)
            
    print(f"إزالة التكرار البسيط: تم تقليص عدد المقالات من {len(articles)} إلى {len(unique_articles)}.")
    return unique_articles

def deduplicate_articles_semantic(articles: list) -> list:
    """
    تزيل المقالات المكررة دلاليًا (مثل الترجمات) عبر مقارنة متجهات محتواها الكامل.
    هذه هي الطبقة الثانية من الفلترة العميقة.
    """
    if not articles or not model or len(articles) < 2:
        return articles

    # استخلاص المحتوى، مع تفضيل المحتوى الكامل على الوصف القصير
    contents = [article.get('content') or article.get('description') or '' for article in articles]
    
    # فلترة المقالات التي لها محتوى كافٍ للمقارنة (أكثر من 25 كلمة)
    valid_indices = [i for i, content in enumerate(contents) if content and len(content.split()) > 25]
    
    if len(valid_indices) < 2:
        return articles # لا يوجد ما يكفي من المقالات للمقارنة

    valid_contents = [contents[i] for i in valid_indices]
    original_valid_articles = [articles[i] for i in valid_indices]
    
    print(f"--- بدء الفلترة الدلالية لـ {len(valid_contents)} مقالًا ... ---")
    
    embeddings = model.encode(valid_contents, show_progress_bar=False, normalize_embeddings=True)
    embeddings = np.array(embeddings).astype('float32')

    # عتبة التشابه، يمكن تعديلها في config.yaml (أعلى تعني تطابقًا أقوى)
    threshold = SETTINGS.get('processing', {}).get('deduplication_threshold', 0.95)
    
    similarity_matrix = cosine_similarity(embeddings)
    
    to_keep_indices = set()
    discarded_indices = set()
    
    for i in range(len(original_valid_articles)):
        if i in discarded_indices:
            continue
        
        to_keep_indices.add(i)
        
        # ابحث عن المقالات المشابهة له وتجاهلها
        for j in range(i + 1, len(original_valid_articles)):
            if similarity_matrix[i, j] > threshold:
                discarded_indices.add(j)

    # بناء القائمة النهائية للمقالات الفريدة
    final_unique_articles = [original_valid_articles[i] for i in sorted(list(to_keep_indices))]
    
    # إضافة المقالات التي لم يتم فحصها (لأن محتواها كان قصيرًا جدًا)
    invalid_indices = set(range(len(articles))) - set(valid_indices)
    for i in invalid_indices:
        final_unique_articles.append(articles[i])

    print(f"الفلترة الدلالية: تم تقليص عدد المقالات من {len(articles)} إلى {len(final_unique_articles)}.")
    return final_unique_articles


def get_unique_chunk_indices(chunks: list[dict], embeddings: np.ndarray) -> list[int]:
    """
    تزيل المقاطع النصية المتشابهة دلاليًا وتعيد فهارس المقاطع الفريدة فقط.
    """
    if len(chunks) < 2:
        return list(range(len(chunks)))

    threshold = SETTINGS.get('processing', {}).get('deduplication_threshold', 0.9)
    
    similarity_matrix = cosine_similarity(embeddings)
    
    to_keep_indices = []
    discarded_indices = set()
    
    for i in range(len(chunks)):
        if i in discarded_indices:
            continue
        
        to_keep_indices.append(i)
        
        for j in range(i + 1, len(chunks)):
            if similarity_matrix[i, j] > threshold:
                discarded_indices.add(j)
                
    print(f"إزالة تكرار المقاطع: تم تحديد {len(to_keep_indices)} مقطع فريد من أصل {len(chunks)}.")
    return to_keep_indices
