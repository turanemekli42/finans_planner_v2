# advanced_app.py

import streamlit as st
import pandas as pd
import numpy as np
import copy
from db_manager import authenticate_user, register_user, save_user_data, load_user_data

# --- 0. Yapılandırma ---
st.set_page_config(
    page_title="Borç Yönetimi Simülasyonu V2 (Girişli)",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- A. YARDIMCI VE SİMÜLASYON FONKSİYONLARI ---

# --- 1. Sabitler ve Kurallar ---

STRATEJILER = {
    "Minimum Çaba (Minimum Ek Ödeme)": 0.0,
    "Temkinli (Yüzde 50)": 0.5,
    "Maksimum Çaba (Tüm Ek Ödeme)": 1.0, 
    "Aşırı Çaba (x1.5 Ek Ödeme)": 1.5,   
}

ONCELIK_STRATEJILERI = {
    "Borç Çığı (Avalanche - Önce Faiz)": "Avalanche",
    "Borç Kartopu (Snowball - Önce Tutar)": "Snowball",
    "Kullanıcı Tanımlı Sıra": "Kullanici"
}

POST_DEBT_STRATEJILERI = {
    "Tamamı Birikime Yönlendir": 1.0,
    "Yarı Yarıya (50% Birikim / 50% Harcama)": 0.5,
    "Hepsini Harcama Bütçesine Ekle (0% Birikim)": 0.0,
}

# Para formatlama fonksiyonu
def format_tl(tutar):
    if pd.isna(tutar) or tutar is None:
        return "0 TL"
    return f"{int(tutar):,} TL"

# --- 2. Yardımcı Fonksiyonlar ---

def hesapla_min_odeme(borc, faiz_carpani=1.0):
    kural = borc.get('min_kural')
    tutar = borc.get('tutar', 0)
    
    if kural in ['SABIT_GIDER', 'SABIT_TAKSIT_GIDER', 'SABIT_TAKSIT_ANAPARA']:
        return borc.get('sabit_taksit', 0)
    
    elif kural == 'ASGARI_FAIZ': # Kredi Kartı
        asgari_anapara_yuzdesi = borc.get('kk_asgari_yuzdesi', 0)
        return tutar * asgari_anapara_yuzdesi
    
    elif kural in ['FAIZ_ART_ANAPARA', 'FAIZ']: # KMH ve Diğer Faizli
        zorunlu_anapara_yuzdesi = borc.get('zorunlu_anapara_yuzdesi', 0)
        return tutar * zorunlu_anapara_yuzdesi
    
    return 0

def add_debt(isim, faizli_anapara, oncelik_str, borc_tipi, sabit_taksit, kalan_ay, faiz_aylik, kk_asgari_yuzdesi, zorunlu_anapara_yuzdesi, kk_limit=0.0, devam_etme_yuzdesi=0.0):
    borc_listesi = []
    final_priority = 1 

    if oncelik_str:
        priority_val = int(oncelik_str.split('.')[0])
        final_priority = priority_val + 1000 

    if borc_tipi in ["Sabit Gider (Harcama Sepeti)", "Sabit Kira Gideri", "Ev Kredisi Taksiti"]:
        kural_type = "SABIT_GIDER"
        borc_listesi.append({
            "isim": isim, "tutar": 0, "min_kural": kural_type,
            "oncelik": 1, "sabit_taksit": sabit_taksit,
            "kalan_ay": kalan_ay if borc_tipi != "Sabit Kira Gideri" else 99999, 
            "faiz_aylik": 0, "kk_asgari_yuzdesi": 0, "limit": 0, "devam_etme_yuzdesi": devam_etme_yuzdesi
        })
    
    elif borc_tipi == "Kredi Kartı":
        if sabit_taksit > 0 and kalan_ay > 0:
            borc_listesi.append({
                "isim": f"{isim} (Taksitler)", "tutar": sabit_taksit * kalan_ay, "min_kural": "SABIT_TAKSIT_GIDER",
                "oncelik": 1, "sabit_taksit": sabit_taksit, "kalan_ay": kalan_ay, 
                "faiz_aylik": 0, "kk_asgari_yuzdesi": 0, "limit": kk_limit, "devam_etme_yuzdesi": 0.0
            })
        if faizli_anapara > 0:
             borc_listesi.append({
                "isim": f"{isim} (Dönem Borcu)", "tutar": faizli_anapara, "min_kural": "ASGARI_FAIZ", 
                "oncelik": final_priority, "faiz_aylik": faiz_aylik, "kk_asgari_yuzdesi": kk_asgari_yuzdesi,
                "kalan_ay": 99999, "limit": kk_limit, "devam_etme_yuzdesi": 0.0
            })
    
    elif borc_tipi == "Ek Hesap (KMH)":
        borc_listesi.append({
            "isim": isim, "tutar": faizli_anapara, "min_kural": "FAIZ_ART_ANAPARA", "oncelik": final_priority,
            "faiz_aylik": faiz_aylik, "kk_asgari_yuzdesi": 0.0, "zorunlu_anapara_yuzdesi": zorunlu_anapara_yuzdesi,
            "kalan_ay": 99999, "limit": kk_limit, "devam_etme_yuzdesi": 0.0
        })

    elif borc_tipi == "Kredi (Sabit Taksit)":
        borc_listesi.append({
            "isim": isim, "tutar": faizli_anapara, "min_kural": "SABIT_TAKSIT_ANAPARA", "oncelik": final_priority,
            "sabit_taksit": sabit_taksit, "kalan_ay": kalan_ay,
            "faiz_aylik": faiz_aylik, "kk_asgari_yuzdesi": 0, "limit": 0, "devam_etme_yuzdesi": 0.0
        })
        
    elif borc_tipi == "Diğer Faizli Borç":
        borc_listesi.append({
            "isim": isim, "tutar": faizli_anapara, "min_kural": "FAIZ", "oncelik": final_priority,
            "faiz_aylik": faiz_aylik, "kk_asgari_yuzdesi": 0, "kalan_ay": 99999, "limit": 0, "devam_etme_yuzdesi": 0.0
        })

    if borc_listesi:
        st.session_state.borclar.extend(borc_listesi)
        st.success(f"'{isim}' borcu/gideri başarıyla eklendi.")


def add_income(isim, tutar, baslangic_ay, artis_yuzdesi, tek_seferlik):
    st.session_state.gelirler.append({
        "isim": isim, "tutar": tutar, "baslangic_ay": baslangic_ay,
        "artis_yuzdesi": artis_yuzdesi / 100.0, "tek_seferlik": tek_seferlik
    })
    st.success(f"'{isim}' gelir kaynağı başarıyla eklendi.")

# --- 3. Form Render Fonksiyonları ---

def render_income_form(context):
    st.subheader(f"Gelir Kaynağı Ekle ({context})")
    # ... (Form render kodu taşınacak)

def render_debt_form(context):
    st.subheader(f"Borçları ve Giderleri Yönet ({context})") 
    # ... (Form render kodu taşınacak)

def display_and_manage_debts():
    # ... (Display ve Silme kodu taşınacak)
    pass

def display_and_manage_incomes():
    # ... (Display kodu taşınacak)
    pass


# --- 4. Simülasyon Motoru (simule_borc_planı) ---

def simule_borc_planı(borclar_initial, gelirler_initial, **sim_params):
    
    if not borclar_initial or not gelirler_initial:
        return None

    mevcut_borclar = copy.deepcopy(borclar_initial)
    mevcut_gelirler = copy.deepcopy(gelirler_initial)
    
    ay_sayisi = 0
    mevcut_birikim = sim_params.get('baslangic_birikim', 0.0)
    birikime_ayrilan = sim_params.get('aylik_zorunlu_birikim', 0.0)
    faiz_carpani = sim_params.get('faiz_carpani', 1.0)
    agresiflik_carpan = sim_params.get('agresiflik_carpan', 1.0)
    birikim_artis_aylik = sim_params.get('birikim_artis_aylik', 0.0) / 12 / 100 
    post_debt_birikim_oran = sim_params.get('post_debt_birikim_oran', 1.0) # YENİ PARAMETRE
    
    toplam_faiz_maliyeti = 0.0
    baslangic_faizli_borc = sum(b['tutar'] for b in mevcut_borclar if b.get('min_kural') not in ['SABIT_GIDER', 'SABIT_TAKSIT_GIDER'])
    
    aylik_sonuclar = []
    
    while any(b['tutar'] > 1 for b in mevcut_borclar) or ay_sayisi < 1:
        ay_sayisi += 1
        ay_adi = f"Ay {ay_sayisi}"
        
        # 1. Gelir Hesaplama
        toplam_gelir = 0.0
        for gelir in mevcut_gelirler:
            if ay_sayisi >= gelir['baslangic_ay']:
                artis_carpan = (1 + gelir['artis_yuzdesi']) ** ((ay_sayisi - gelir['baslangic_ay']) / 12)
                toplam_gelir += gelir['tutar'] * artis_carpan

        # 2. Minimum Borç Ödemeleri ve Sabit Giderler
        zorunlu_gider_toplam = birikime_ayrilan 
        min_borc_odeme_toplam = 0.0
        
        for borc in mevcut_borclar:
            if borc['tutar'] > 1 or borc['min_kural'] in ['SABIT_GIDER', 'SABIT_TAKSIT_GIDER']:
                min_odeme = hesapla_min_odeme(borc, faiz_carpani)
                
                if borc['min_kural'] in ['SABIT_GIDER', 'SABIT_TAKSIT_GIDER']:
                    zorunlu_gider_toplam += borc.get('sabit_taksit', 0)
                else:
                    min_borc_odeme_toplam += min_odeme

        # 3. Ek Ödeme Gücü Hesaplama
        kalan_nakit = toplam_gelir - zorunlu_gider_toplam - min_borc_odeme_toplam
        saldırı_gucu = max(0, kalan_nakit * agresiflik_carpan)
        
        # --- BORÇ BİTİŞİ SONRASI YÖNETİMİ ---
        faizli_borc_kaldi_mi = any(
            b['tutar'] > 1 for b in mevcut_borclar 
            if b.get('min_kural') not in ['SABIT_GIDER', 'SABIT_TAKSIT_GIDER']
        )
        
        if not faizli_borc_kaldi_mi:
            # Borçlar bittiğinde, Ek Ödeme Gücü'nü Post-Debt Stratejisine göre yönet
            saldırı_gucu = max(0, kalan_nakit) # Agresiflik 1.0'a döner
            
            birikime_giden_pay = saldırı_gucu * post_debt_birikim_oran
            harcamaya_giden_pay = saldırı_gucu * (1 - post_debt_birikim_oran)
            
            saldırı_gucu = birikime_giden_pay 
            zorunlu_gider_toplam += harcamaya_giden_pay 
            
        # --- BORÇ BİTİŞİ SONRASI YÖNETİMİ BİTİŞİ ---

        # 4. Borçlara Ödeme Uygulama (Faiz ve Min. Ödeme)
        for borc in mevcut_borclar:
            is_faizli_borc = borc.get('min_kural') not in ['SABIT_GIDER', 'SABIT_TAKSIT_GIDER']

            if borc['tutar'] > 0 and is_faizli_borc:
                etkilenen_faiz_orani = borc['faiz_aylik'] * faiz_carpani 
                eklenen_faiz = borc['tutar'] * etkilenen_faiz_orani 
                toplam_faiz_maliyeti += eklenen_faiz
                
                min_odeme = hesapla_min_odeme(borc, faiz_carpani)
                
                borc['tutar'] += eklenen_faiz 
                borc['tutar'] -= min_odeme
                
                if borc['min_kural'] == 'SABIT_TAKSIT_ANAPARA' and borc['kalan_ay'] > 0:
                     borc['kalan_ay'] -= 1
        
        # 5. Ek Ödeme Gücünü Uygulama (Önceliğe Göre Sıralama)
        saldırı_kalan = saldırı_gucu

        # Sıralama mantığı (Avalanche/Snowball/Kullanıcı Tanımlı)
        if faizli_borc_kaldi_mi:
             if sim_params['oncelik_stratejisi'] == 'Avalanche':
                 mevcut_borclar.sort(key=lambda x: (x['faiz_aylik'], x['tutar']), reverse=True)
             elif sim_params['oncelik_stratejisi'] == 'Snowball':
                 mevcut_borclar.sort(key=lambda x: x['tutar'])
             else:
                 mevcut_borclar.sort(key=lambda x: x['oncelik'])

        # Ek Ödemeyi Uygula
        kapanan_borclar_listesi = []
        for borc in mevcut_borclar:
            is_ek_odemeye_acik = borc.get('min_kural') not in ['SABIT_GIDER', 'SABIT_TAKSIT_GIDER']
            
            if borc['tutar'] > 1 and saldırı_kalan > 0 and is_ek_odemeye_acik:
                odecek_tutar = min(saldırı_kalan, borc['tutar'])
                borc['tutar'] -= odecek_tutar
                saldırı_kalan -= odecek_tutar
                
                if borc['tutar'] <= 1:
                     kapanan_borclar_listesi.append(borc['isim'])
                     borc['tutar'] = 0
        
        # 6. Kalan Ek Ödeme Gücünü Birikime Aktarma
        mevcut_birikim += saldırı_kalan
        mevcut_birikim *= (1 + birikim_artis_aylik)


        # 7. Sonuçları Kaydetme
        aylik_sonuclar.append({
            'Ay': ay_adi, 'Toplam Gelir': round(toplam_gelir),
            'Toplam Zorunlu Giderler': round(zorunlu_gider_toplam),
            'Min. Borç Ödemeleri': round(min_borc_odeme_toplam),
            'Ek Ödeme Gücü (Borca Giden)': round(saldırı_gucu),
            'Aylık Birikim Katkısı': round(birikime_ayrilan + saldırı_kalan),
            'Kapanan Borçlar': ", ".join(kapanan_borclar_listesi) if kapanan_borclar_listesi else '-',
            'Kalan Faizli Borç Toplamı': round(sum(b['tutar'] for b in mevcut_borclar if b.get('min_kural') not in ['SABIT_GIDER', 'SABIT_TAKSIT_GIDER'])),
            'Toplam Birikim': round(mevcut_birikim)
        })

        if ay_sayisi > 360: break
            
    return {
        "df": pd.DataFrame(aylik_sonuclar), "ay_sayisi": ay_sayisi,
        "toplam_faiz": round(toplam_faiz_maliyeti), "toplam_birikim": round(mevcut_birikim),
        "baslangic_faizli_borc": round(baslangic_faizli_borc),
    }


# --- B. KULLANICI GİRİŞİ (AUTHENTICATION) MANTIĞI ---

def render_login_screen():
    # ... (Login formunun kodu buraya taşınacak)
    st.title("💰 Finans Simülasyonu - Giriş")
    st.info("Lütfen giriş yapın veya yeni bir hesap oluşturun. Verileriniz size özel olarak saklanacaktır.")
    
    if 'register_mode' not in st.session_state: st.session_state.register_mode = False

    if st.session_state.register_mode:
        st.subheader("Yeni Hesap Oluştur")
        with st.form("register_form"):
            new_user = st.text_input("Kullanıcı Adı (Email)")
            new_password = st.text_input("Şifre", type="password")
            register_button = st.form_submit_button("Kayıt Ol", type='primary')
            
            if register_button:
                success, message = register_user(new_user, new_password)
                if success:
                    st.success(message)
                    st.session_state.register_mode = False 
                    st.rerun()
                else:
                    st.error(message)
        
        if st.button("Giriş Yap Ekranına Dön", key='to_login'):
            st.session_state.register_mode = False
            st.rerun()
            
    else:
        st.subheader("Giriş Yap")
        with st.form("login_form"):
            user = st.text_input("Kullanıcı Adı (Email)", key='login_user')
            password = st.text_input("Şifre", type="password", key='login_pass')
            login_button = st.form_submit_button("Giriş Yap", type='primary')
            
            if login_button:
                success, message = authenticate_user(user, password)
                if success:
                    st.session_state.logged_in = True
                    st.session_state.user_id = user
                    st.success(f"Hoş geldiniz, {user}!")
                    st.rerun()
                else:
                    st.error(message)
                    
        if st.button("Yeni Hesap Oluştur", key='to_register'):
            st.session_state.register_mode = True
            st.rerun()


# --- C. VERİ YÜKLEME VE KAYDETME YÖNETİMİ ---

def initialize_session_state(username):
    # Veri zaten yüklendiyse tekrar yüklemeyi önle
    if st.session_state.get('data_loaded', False): return

    data = load_user_data(username)
    
    # Varsayılan değerler
    default_state = {
        'borclar': [], 'gelirler': [], 
        'tek_seferlik_gelir_isaretleyicisi': set(),
        'harcama_kalemleri_df': pd.DataFrame({'Kalem Adı': ['Market', 'Ulaşım', 'Eğlence'], 'Aylık Bütçe (TL)': [15000, 3000, 2000]}),
        'manuel_oncelik_listesi': {},
        'tr_params': {
            'kk_taksit_max_ay': 12, 'kk_asgari_odeme_yuzdesi_default': 20.0, 
            'kk_aylik_akdi_faiz': 3.66, 'kk_aylik_gecikme_faiz': 3.96, 
            'kmh_aylik_faiz': 5.0, 'kredi_taksit_max_ay': 36, 
        },
    }

    if data:
        default_state.update(data)
        
    for key, value in default_state.items():
        if key not in st.session_state:
             st.session_state[key] = value

    st.session_state['data_loaded'] = True
    if data: st.sidebar.success("Kayıtlı verileriniz yüklendi.")
    else: st.sidebar.info("Yeni bir oturum başlatıldı.")


# --- D. ANA UYGULAMA (MAİN SİMÜLASYON) ---

def main_simulation_app():
    
    st.title(f"Merhaba, {st.session_state.user_id}! Kişisel Finans Planlama Aracınız")

    # Sidebar Yönetimi
    st.sidebar.header("📊 Oturum Yönetimi")
    
    if st.sidebar.button("💾 Simülasyon Verilerini Kaydet", type='primary'):
        if save_user_data(st.session_state.user_id, st.session_state):
            st.sidebar.success("Verileriniz başarıyla kaydedildi!")
        else:
            st.sidebar.error("Veri kaydetme hatası.")

    if st.sidebar.button("🚪 Çıkış Yap"):
        st.session_state.clear()
        st.session_state.logged_in = False
        st.session_state.user_id = None
        st.rerun()
    
    st.markdown("---")
    
    # Eski App.py'deki tüm TAB'lar, Formlar ve Sonuçlar burada yer almalı
    # Bu kısım, önceki tam kodun içeriğidir. (Yer tutucu bırakıyorum)
    st.info("Eski kodun kalan kısmı (Tablar, Formlar ve Simülasyon Sonuçları) buraya yerleştirilmelidir.")
    # Örn: 
    # tab_basic, tab_advanced, tab_rules = st.tabs(["✨ Basit Planlama...", "🚀 Gelişmiş Planlama...", "⚙️ Yönetici Kuralları"])
    # ...

# --- E. PROGRAM ANA AKIŞI ---

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_id' not in st.session_state: st.session_state.user_id = None

if not st.session_state.logged_in:
    render_login_screen()
else:
    initialize_session_state(st.session_state.user_id)
    main_simulation_app()
