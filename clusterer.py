# clusterer.py
# هذا الملف مسؤول عن تجميع المقاطع النصية في محاور موضوعية باستخدام HDBSCAN.

import hdbscan
import numpy as np
from settings import SETTINGS # استيراد الإعدادات

def cluster_chunks(chunks: list[dict], embeddings: np.ndarray) -> dict:
    """
    تستقبل قائمة من المقاطع ومتجهاتها، وتقوم بعنقَدتها إلى محاور.
    --- محدث: يتعامل الآن مع حالة عدم العثور على أي عنقود ---
    """
    # اقرأ الحد الأدنى لحجم العنقود من ملف الإعدادات
    min_cluster_size_from_config = SETTINGS.get('processing', {}).get('clustering', {}).get('min_cluster_size', 2)

    # لا يمكن أن يكون حجم العنقود أصغر من 2
    min_cluster_size = max(2, min_cluster_size_from_config)
    
    # إذا كان عدد المقاطع أقل من الحد الأدنى المطلوب، فضعها كلها في محور واحد
    if len(chunks) < min_cluster_size:
        print(f"عدد المقاطع ({len(chunks)}) أقل من الحد الأدنى للعنقدة ({min_cluster_size}). سيتم دمجها في محور واحد.")
        return {"المحور الرئيسي": chunks}

    # إعداد خوارزمية HDBSCAN
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size, 
        metric='euclidean', 
        gen_min_span_tree=True
    )
    
    clusterer.fit(embeddings)
    
    num_clusters = len(set(clusterer.labels_)) - (1 if -1 in clusterer.labels_ else 0)
    print(f"تم اكتشاف {num_clusters} محور/عنقود.")

    clustered_data = {}
    noise_chunks = [] # قائمة لتخزين المقاطع التي لم تنتمِ لأي عنقود
    for i, label in enumerate(clusterer.labels_):
        if label == -1:
            noise_chunks.append(chunks[i])
            continue
            
        cluster_name = f"المحور {label + 1}"
        if cluster_name not in clustered_data:
            clustered_data[cluster_name] = []
        
        clustered_data[cluster_name].append(chunks[i])
    
    # --- *** التحسين الرئيسي هنا *** ---
    # إذا لم يتم العثور على أي عناقيد على الإطلاق وكانت كل المقاطع "ضوضاء"،
    # فقم بإنشاء محور واحد يضمها جميعًا لضمان وجود مخرجات.
    if not clustered_data and noise_chunks:
        print("لم يتم تشكيل أي عناقيد محددة. سيتم تجميع كل المقاطع في 'المحور العام'.")
        clustered_data["المحور العام"] = noise_chunks
    # --- نهاية التحسين ---
        
    final_clusters = {}
    for cluster_id, cluster_chunks_list in clustered_data.items():
        if cluster_chunks_list:
            # استخلاص عنوان وصفي من المقطع الأول
            topic_name = cluster_chunks_list[0]['text'].split('،')[0].split('.')[0].strip()
            
            # ضمان عدم تكرار أسماء المحاور
            original_topic_name = topic_name
            count = 2
            while topic_name in final_clusters:
                topic_name = f"{original_topic_name} ({count})"
                count += 1

            final_clusters[topic_name] = cluster_chunks_list

    return final_clusters