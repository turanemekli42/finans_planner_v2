# db_manager.py

import psycopg2
from psycopg2 import sql
import bcrypt
import json
import os
import streamlit as st

# --- PostgreSQL BAĞLANTI BİLGİLERİ (Ortam Değişkenlerinden Okuma) ---
# Streamlit Cloud'da ortam değişkenlerini (Secrets) kullanın. 
# Yerel test için varsayılan değerleri kullanır.
DB_HOST = os.environ.get("DB_HOST", "localhost") 
DB_NAME = os.environ.get("DB_NAME", "finans_db") 
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASS = os.environ.get("DB_PASS", "sifreniz") # Lütfen kendi şifrenizi girin!


# --- 1. Veritabanı Bağlantısı ---
def get_db_connection():
    """PostgreSQL veritabanı bağlantısını kurar."""
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

# --- 2. Tablo Oluşturma (Genellikle sadece ilk kurulumda kullanılır) ---
def create_tables():
    """Gerekli 'users' ve 'user_data' tablolarını oluşturur."""
    conn = get_db_connection()
    if conn is None: return False, "Veritabanı bağlantısı yok."

    try:
        with conn.cursor() as cur:
            # users tablosu: Kullanıcı adı ve şifre hash'i
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(100) UNIQUE NOT NULL,
                    hashed_password VARCHAR(255) NOT NULL
                );
            """)
            # user_data tablosu: Kullanıcıya ait tüm simülasyon verileri (JSONB formatında)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_data (
                    username VARCHAR(100) REFERENCES users(username) ON DELETE CASCADE,
                    data JSONB,
                    PRIMARY KEY (username)
                );
            """)
        conn.commit()
        return True, "Tablolar başarıyla oluşturuldu."
    except Exception as e:
        return False, f"Tablo oluşturma hatası: {e}"
    finally:
        if conn: conn.close()

# --- 3. Kullanıcı Kayıt İşlemi ---
def register_user(username, password):
    """Yeni kullanıcıyı kaydeder ve şifresini hashler."""
    conn = get_db_connection()
    if conn is None: return False, "Veritabanı bağlantısı yok."
    
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, hashed_password) VALUES (%s, %s)",
                (username, hashed_password)
            )
        conn.commit()
        return True, "Kayıt başarılı. Şimdi giriş yapabilirsiniz."
    except psycopg2.IntegrityError:
        return False, "Bu kullanıcı adı zaten kayıtlı."
    except Exception as e:
        return False, f"Kayıt sırasında bir hata oluştu: {e}"
    finally:
        if conn: conn.close()

# --- 4. Kullanıcı Giriş İşlemi ---
def authenticate_user(username, password):
    """Kullanıcı adını ve şifreyi kontrol eder."""
    conn = get_db_connection()
    if conn is None: return False, "Veritabanı bağlantısı yok."

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT hashed_password FROM users WHERE username = %s",
                (username,)
            )
            result = cur.fetchone()
            
            if result:
                hashed_password = result[0].encode('utf-8')
                if bcrypt.checkpw(password.encode('utf-8'), hashed_password):
                    return True, "Giriş başarılı."
                else:
                    return False, "Hatalı şifre."
            else:
                return False, "Kullanıcı bulunamadı."
    except Exception as e:
        return False, f"Giriş sırasında bir hata oluştu: {e}"
    finally:
        if conn: conn.close()

# --- 5. Veri Kaydetme ---
def save_user_data(username, session_data):
    """Streamlit session state verilerini JSONB olarak kaydeder."""
    conn = get_db_connection()
    if conn is None: return False
    
    # Kaydedilecek veriyi temizleme: Streamlit'e ait ve hassas bilgileri hariç tutarız.
    data_to_save = {k: v for k, v in session_data.items() if not k.startswith("st.") and k not in ['password', 'username', 'logged_in', 'user_id']}
    
    # Pandas DataFrame'leri JSON'a dönüştürme (gerekirse)
    for key, value in data_to_save.items():
        if isinstance(value, pd.DataFrame):
            data_to_save[key] = value.to_json(orient='split')
        elif isinstance(value, set):
            # Set'leri JSON'a dönüştürmek için listeye çevir
            data_to_save[key] = list(value)
    
    data_json = json.dumps(data_to_save)

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_data (username, data) 
                VALUES (%s, %s)
                ON CONFLICT (username) DO UPDATE SET data = EXCLUDED.data;
                """,
                (username, data_json)
            )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Veri kaydetme hatası: {e}")
        return False
    finally:
        if conn: conn.close()

# --- 6. Veri Yükleme ---
def load_user_data(username):
    """Kayıtlı simülasyon verilerini DB'den yükler."""
    conn = get_db_connection()
    if conn is None: return None
    
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT data FROM user_data WHERE username = %s",
                (username,)
            )
            result = cur.fetchone()
            if result:
                loaded_data = json.loads(result[0])
                
                # JSON'dan yüklenen veriyi tekrar DataFrame ve Set'e dönüştürme
                if 'harcama_kalemleri_df' in loaded_data:
                    loaded_data['harcama_kalemleri_df'] = pd.read_json(loaded_data['harcama_kalemleri_df'], orient='split')
                if 'tek_seferlik_gelir_isaretleyicisi' in loaded_data:
                    loaded_data['tek_seferlik_gelir_isaretleyicisi'] = set(loaded_data['tek_seferlik_gelir_isaretleyicisi'])

                return loaded_data
            return None
    except Exception as e:
        st.error(f"Veri yükleme hatası: {e}")
        return None
    finally:
        if conn: conn.close()
