# db_manager.py (Hassas bilgileri ortam değişkenlerinden okuyacak şekilde güncellendi)

import psycopg2
from psycopg2 import sql
import bcrypt
import json
import os
import streamlit as st 

# --- PostgreSQL BAĞLANTI BİLGİLERİ (Ortam Değişkenlerinden Okuma) ---
# Bu değerleri Streamlit Cloud'un 'Secrets' (Sırlar) bölümüne gireceksiniz.
DB_HOST = os.environ.get("DB_HOST", "localhost") 
DB_NAME = os.environ.get("DB_NAME", "finans_db") 
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASS = os.environ.get("DB_PASS", "sifreniz") # Yerel test için varsayılan şifre


# --- 1. Veritabanı Bağlantısı ---
def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        return conn
    except Exception as e:
        st.error(f"⚠️ Veritabanı Bağlantı Hatası: Ayarlarınızı kontrol edin. Detay: {e}")
        return None

# (Kullanıcı Kayıt, Giriş, Veri Kaydetme/Yükleme fonksiyonları buraya taşınacak. 
# Önceki yanıttaki `db_manager.py` kodunun tamamını buraya ekleyin.)

# ... (register_user, authenticate_user, save_user_data, load_user_data fonksiyonları)
