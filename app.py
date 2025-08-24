# app.py
# النسخة الجديدة التي تدعم المعالجة غير المتزامنة

from flask import Flask, request, jsonify
from celery.result import AsyncResult
from tasks import generate_report_task, celery_app # استيراد المهمة وتطبيق Celery

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health():
    """Endpoint للتأكد من أن الخادم يعمل."""
    return jsonify({"status": "ok", "message": "Server is running"}), 200

@app.route('/start_report_generation', methods=['POST'])
def start_task():
    """
    Endpoint لبدء مهمة توليد التقرير.
    يستجيب فورًا مع معرّف المهمة (task_id).
    """
    data = request.get_json() or {}
    user_query = (data.get('query') or '').strip()
    if not user_query:
        return jsonify({"success": False, "message": "Query parameter is required"}), 400

    # --- بدء المهمة في الخلفية ---
    # .delay() هي الطريقة التي نضيف بها المهمة إلى الطابور
    task = generate_report_task.delay(user_query)

    # --- الاستجابة الفورية ---
    # نرجع معرّف المهمة إلى التطبيق
    return jsonify({"success": True, "task_id": task.id}), 202


@app.route('/report_status/<task_id>', methods=['GET'])
def get_status(task_id):
    """
    Endpoint للتحقق من حالة المهمة باستخدام معرّفها.
    """
    task_result = AsyncResult(task_id, app=celery_app)

    if task_result.ready():
        # إذا كانت المهمة قد انتهت
        if task_result.successful():
            # إذا نجحت المهمة
            result = task_result.get()
            return jsonify({
                "status": "SUCCESS",
                "result": result
            })
        else:
            # إذا فشلت المهمة
            return jsonify({
                "status": "FAILURE",
                "error": str(task_result.info) # .info يحتوي على تفاصيل الخطأ
            })
    else:
        # إذا كانت المهمة لا تزال قيد التشغيل
        return jsonify({"status": "PENDING"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False)

