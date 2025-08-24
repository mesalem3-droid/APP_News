# text_processor.py
# هذا الملف مسؤول عن تنظيف النص الكامل وتجزئته إلى فقرات.

import re

def clean_text(text: str) -> str:
    """
    تستقبل نصًا وتزيل منه الأنماط غير المرغوب فيها باستخدام Regex.
    """
    if not text:
        return ""

    # قائمة بالأنماط التي سيتم البحث عنها وحذفها
    # يمكن توسيع هذه القائمة بسهولة في المستقبل
    noise_patterns = [
        r'اقرأ أيضا[^\n]*',      # إزالة "اقرأ أيضًا" وأي شيء بعدها في نفس السطر
        r'اقرأ أيضًا[^\n]*',     # صيغة أخرى
        r'Read also[^\n]*',     # النسخة الإنجليزية
        r'شارك المقال[^\n]*',   # إزالة "شارك المقال"
        r'Share this article[^\n]*',
        r'المصدر:[^\n]*',        # إزالة "المصدر:"
        r'Source:[^\n]*',
        r'^\s*https?://[^\s]+\s*$', # إزالة الروابط التي تكون في سطر لوحدها
    ]

    cleaned_text = text
    for pattern in noise_patterns:
        # re.IGNORECASE يجعل البحث غير حساس لحالة الأحرف
        # re.MULTILINE يسمح للنمط ^ بالبحث في بداية كل سطر
        cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE | re.MULTILINE)

    # إزالة الأسطر الفارغة الزائدة
    cleaned_text = re.sub(r'\n\s*\n', '\n', cleaned_text)
    
    return cleaned_text.strip()

def chunk_text_by_paragraph(text: str) -> list[str]:
    """
    تقسم النص إلى قائمة من الفقرات.
    """
    if not text:
        return []

    # الفقرات غالبًا ما تكون مفصولة بسطرين فارغين (أو أكثر)
    paragraphs = text.split('\n')
    
    # إزالة أي فقرات فارغة أو تحتوي على مسافات فقط
    # والتأكد من أن طول الفقرة معقول (أكثر من 10 كلمات مثلاً)
    chunks = [p.strip() for p in paragraphs if p.strip() and len(p.split()) > 10]
    
    return chunks

def process_and_chunk_articles(articles: list) -> list:
    """
    تأخذ قائمة من المقالات، وتنظف وتجزئ محتوى كل مقال.
    """
    processed_articles = []
    for article in articles:
        # التأكد من أن المحتوى موجود وهو نص
        if 'content' in article and isinstance(article['content'], str):
            # 1. تنظيف النص
            cleaned_content = clean_text(article['content'])
            # 2. تجزئة النص النظيف إلى فقرات
            content_chunks = chunk_text_by_paragraph(cleaned_content)
            
            # إضافة قائمة المقاطع إلى المقال
            article['content_chunks'] = content_chunks
            # يمكننا حذف المحتوى الأصلي لتوفير المساحة
            # del article['content'] 
        else:
            # إذا لم يكن هناك محتوى، أضف قائمة مقاطع فارغة
            article['content_chunks'] = []
            
        processed_articles.append(article)
        
    return processed_articles
