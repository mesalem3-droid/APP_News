# semantic_searcher.py
# هذا الملف مسؤول عن تحويل النصوص إلى متجهات وفهرستها للبحث الدلالي.

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# --- تحميل النموذج ---
# يتم تحميل النموذج مرة واحدة فقط عند بدء تشغيل الخادم لتوفير الوقت.
try:
    print("بدء تحميل نموذج تحويل الجمل (قد يستغرق بعض الوقت في المرة الأولى)...")
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    print("تم تحميل النموذج بنجاح.")
except Exception as e:
    print(f"خطأ فادح: فشل تحميل نموذج SentenceTransformer. تأكد من اتصالك بالإنترنت. الخطأ: {e}")
    model = None

def create_vector_index(chunks: list[dict]):
    """
    تستقبل قائمة من مقاطع النص، تنشئ متجهات لها، وتبني فهرس FAISS.
    --- محدث: يعيد الآن مصفوفة المتجهات الكاملة ---
    """
    if not model:
        return None, None, None
    if not chunks:
        return None, None, None

    texts = [chunk['text'] for chunk in chunks]
    embeddings = model.encode(texts, show_progress_bar=False)
    embeddings = np.array(embeddings).astype('float32')
    
    index = faiss.IndexFlatL2(embeddings.shape[1])
    index.add(embeddings)
    
    print(f"تم بناء الفهرس بنجاح ويحتوي على {index.ntotal} متجه.")
    return index, chunks, embeddings

def find_relevant_chunks(query: str, index: faiss.Index, all_embeddings: np.ndarray, chunks_map: list[dict], top_k: int = 5) -> tuple:
    """
    تبحث في الفهرس عن أقرب المقاطع للاستعلام من حيث المعنى.
    --- محدث: يعيد الآن المقاطع ومتجهاتها ---
    """
    if not model or not index:
        return [], np.array([])

    query_vector = model.encode([query])
    query_vector = np.array(query_vector).astype('float32')
    
    distances, indices = index.search(query_vector, top_k)
    
    relevant_indices = [i for i in indices[0] if i < len(chunks_map)]
    relevant_chunks = [chunks_map[i] for i in relevant_indices]
    relevant_embeddings = np.array([all_embeddings[i] for i in relevant_indices])
    
    print(f"تم العثور على {len(relevant_chunks)} مقطع ذي صلة.")
    return relevant_chunks, relevant_embeddings