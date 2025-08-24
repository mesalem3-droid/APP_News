# settings.py
# هذا الملف مسؤول عن قراءة ملف الإعدادات (config.yaml) 
# وملف متغيرات البيئة الحقيقي (.env).

import os
import yaml
from dotenv import load_dotenv

def load_settings():
    """
    تقوم هذه الدالة بتحميل الإعدادات من ملف .env الحقيقي وملف config.yaml
    وتدمجها في كائن واحد (dictionary).
    """
    print("بدء تحميل الإعدادات من الملفات الحقيقية...")

    # الخطوة 1: تحميل متغيرات البيئة من ملف .env
    # دالة load_dotenv() ستبحث تلقائيًا عن ملف اسمه .env في المجلد
    load_dotenv()
    print("تم تحميل متغيرات البيئة من .env")

    # الخطوة 2: قراءة ملف الإعدادات config.yaml
    try:
        # تأكد من وجود ملف config.yaml في نفس المجلد
        with open('config.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        print("تم قراءة ملف config.yaml بنجاح.")
    except FileNotFoundError:
        print("خطأ: لم يتم العثور على ملف config.yaml. تأكد من وجوده في المجلد.")
        return None
    except yaml.YAMLError as e:
        print(f"خطأ في قراءة ملف YAML: {e}")
        return None

    # الخطوة 3: دمج مفاتيح API من متغيرات البيئة في كائن الإعدادات
    for provider, settings in config.get('search_providers', {}).items():
        api_key_env_var = settings.get('api_key_env')
        if api_key_env_var:
            api_key = os.getenv(api_key_env_var)
            if api_key:
                config['search_providers'][provider]['api_key'] = api_key
                print(f"تم تحميل مفتاح API لـ {provider}.")
            else:
                print(f"تحذير: متغير البيئة '{api_key_env_var}' غير موجود في ملف .env")
    
    print("اكتمل تحميل الإعدادات بنجاح.")
    return config

# تحميل الإعدادات عند بدء تشغيل التطبيق
SETTINGS = load_settings()

