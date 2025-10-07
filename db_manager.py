import pandas as pd

# ----------------------------------------------------------------------
# 1. PARAMETRELER VE BORÇLAR (Kullanıcı Tarafından Düzenlenecek Alan)
# ----------------------------------------------------------------------

# Genel Finansal Veriler
GELIR_MAAS_1 = 120000
GELIR_MAAS_2 = 65000
TEK_SEFERLIK_GELIR = 165000 # Ekim 2025'te geliyor
ZORUNLU_SABIT_GIDER = 30000
EV_KREDISI_TAKSIT = 23000
OKUL_TAKSIDI = 34000
GARANTI_KREDILER_TAKSIT = 29991
YASAL_FAIZ_AYLIK = 0.0525 # %5.25

# Borç Listesi (Ana Para, Minimum Ödeme Kuralı ve Öncelik)
# Öncelik 1: Faiz çığının en üstündeki borçtur
borclar = [
    # Ek Hesaplar (Faiz oranı ile minimum ödeme yapılır)
    {"isim": "Is_Bankasi_Ek_Hsp", "tutar": 67416.59, "min_kural": "FAIZ", "oncelik": 1, "kalan_ay": 1},
    {"isim": "Halkbank_Ek_Hsp_2", "tutar": 70000.00, "min_kural": "FAIZ", "oncelik": 2, "kalan_ay": 1},
    {"isim": "Garanti_Ek_Hsp", "tutar": 20825.17, "min_kural": "FAIZ", "oncelik": 6, "kalan_ay": 1},
    {"isim": "Enpara_Ek_Hsp", "tutar": 2500.00, "min_kural": "FAIZ", "oncelik": 9, "kalan_ay": 1},
    
    # Kredi Kartları (Asgari Ödeme ile minimum ödeme yapılır)
    # Akbank KK'nın 44686.89 TL'lik min. ödemesi, BDDK %40 kuralından gelen bir tahmindir.
    {"isim": "Akbank_KK", "tutar": 123997.81, "min_kural": "ASGARI_44K", "oncelik": 3, "kalan_ay": 1},
    {"isim": "QNB_KK", "tutar": 155665.15, "min_kural": "ASGARI_FAIZ", "oncelik": 4, "kalan_ay": 1},
    {"isim": "Is_Bankasi_KK", "tutar": 56512.25, "min_kural": "ASGARI_FAIZ", "oncelik": 5, "kalan_ay": 1},
    
    # Sabit Taksitli Krediler (Borç bitirme planında öncelik düşüktür)
    {"isim": "Garanti_Krediler", "tutar": 30000.00, "min_kural": "SABIT_TAKSIT", "oncelik": 7, "kalan_ay": 12},
    {"isim": "Halkbank_Kredisi", "tutar": 1676.45, "min_kural": "SABIT_TAKSIT", "oncelik": 8, "kalan_ay": 1}, # Tek taksit kalmış kabul edildi
]

# ----------------------------------------------------------------------
# 2. YARDIMCI FONKSIYONLAR (Minimum Ödeme Hesaplama Mantığı)
# ----------------------------------------------------------------------

def hesapla_min_odeme(borc, faiz_orani):
    """Her bir borç için minimum ödeme tutarını kurala göre hesaplar."""
    tutar = borc['tutar']
    kural = borc['min_kural']
    
    # Yasal Faiz Kuralı (Ek Hesaplar)
    if kural == "FAIZ":
        return tutar * faiz_orani
    
    # Kredi Kartı Asgari Ödeme Kuralı (Basitleştirilmiş Tahmin)
    elif kural == "ASGARI_44K":
        # Akbank KK için verilen sabit minimum ödeme tahmini
        if tutar > 0:
            return 44686.89 
        return 0
        
    elif kural == "ASGARI_FAIZ":
        # QNB/Is Bankasi KK'lar için: Faiz + Küçük bir anapara (BDDK kuralını simüle eder)
        return (tutar * faiz_orani) + (tutar * 0.05)
        
    # Sabit Taksit Kuralı
    elif kural == "SABIT_TAKSIT":
        if borc['isim'] == "Garanti_Krediler" and borc['kalan_ay'] > 0:
            return GARANTI_KREDILER_TAKSIT
        elif borc['isim'] == "Halkbank_Kredisi" and borc['kalan_ay'] > 0:
             return tutar # Kalan tek taksiti kapatmak için
        return 0
        
    return 0

# ----------------------------------------------------------------------
# 3. SIMÜLASYON MOTORU
# ----------------------------------------------------------------------

def simule_borc_planı(borclar):
    
    aylik_sonuclar = []
    mevcut_borclar = borclar
    ay_sayisi = 0
    tarih = pd.to_datetime('2025-10-01')
    
    while tarih.year <= 2026 or any(b['tutar'] > 1 for b in mevcut_borclar): # 2026 sonuna kadar simülasyonu çalıştır
        
        ay_adi = tarih.strftime("%Y-%m")
        
        # 3.1. Gelir ve Sabit Gider Güncellemesi
        
        # Maaş Zammı Uygulaması (Ocak 2026)
        maas_1 = GELIR_MAAS_1 * (1.35 if tarih.year >= 2026 else 1.0)
        maas_2 = GELIR_MAAS_2 * (1.15 if tarih.year >= 2026 else 1.0)
        toplam_gelir = maas_1 + maas_2
        
        # Zorunlu Giderler
        zorunlu_gider_toplam = ZORUNLU_SABIT_GIDER + EV_KREDISI_TAKSIT
        if tarih.month <= 7 or tarih.year != 2026: # Okul taksidi Temmuz 2026'ya kadar devam eder
            zorunlu_gider_toplam += OKUL_TAKSIDI
        
        # Garanti Krediler (Eylül 2026'ya kadar devam eder)
        garanti_kredi_gider = 0
        if ay_sayisi < 12: 
             garanti_kredi_gider = GARANTI_KREDILER_TAKSIT
             
        # 3.2. Minimum Borç Ödemeleri ve Faiz Hesaplama
        
        min_odeme_toplam = 0
        borc_faiz_toplam = 0
        
        for borc in mevcut_borclar:
            if borc['tutar'] > 0:
                min_odeme = hesapla_min_odeme(borc, YASAL_FAIZ_AYLIK)
                faiz_olusan = borc['tutar'] * YASAL_FAIZ_AYLIK
                
                min_odeme_toplam += min_odeme
                borc_faiz_toplam += faiz_olusan
        
        # 3.3. Saldırı Gücü (Attack Power) Hesaplama
        
        # Maaş ve sabit giderler sonrası kalan para
        kalan_nakit = toplam_gelir - zorunlu_gider_toplam - garanti_kredi_gider - min_odeme_toplam
        
        saldırı_gucu = max(0, kalan_nakit) # Aylık Bütçe Fazlası
        tek_seferlik_kullanilan = 0
        
        # Ekim 2025: Tek Seferlik Gelir Kullanımı
        if tarih.month == 10 and tarih.year == 2025:
             saldırı_gucu += TEK_SEFERLIK_GELIR
             tek_seferlik_kullanilan = TEK_SEFERLIK_GELIR
             
        # Birikim Hesaplama (Tüm yüksek faizli borçlar bittikten sonra)
        borc_kapanis_tarihi = pd.to_datetime('2026-04-01') # Tahmini KK/Ek Hesap bitiş tarihi
        birikim = 0
        
        if tarih > borc_kapanis_tarihi and kalan_nakit > 0:
             # %90 kuralı uygulanır
             saldırı_gucu = kalan_nakit * 0.10
             birikim = kalan_nakit * 0.90
             
        # 3.4. Borçlara Ödeme Uygulama (Faiz Çığı)
        
        saldırı_kalan = saldırı_gucu
        kapanan_borclar_listesi = []
        
        # Önce tüm borçlara faiz eklenir ve min. ödeme yapılır
        for borc in mevcut_borclar:
            if borc['tutar'] > 0:
                min_odeme = hesapla_min_odeme(borc, YASAL_FAIZ_AYLIK)
                
                borc['tutar'] += borc['tutar'] * YASAL_FAIZ_AYLIK # Faiz ekle
                borc['tutar'] -= min_odeme # Minimum ödemeyi çıkar
                
                # Sabit taksitli kredilerin kalan ayını düşür
                if borc['min_kural'] == 'SABIT_TAKSIT':
                     borc['kalan_ay'] = max(0, borc['kalan_ay'] - 1)
                     
        # Borçları önceliğe göre sırala (Faiz Çığı Yöntemi)
        mevcut_borclar.sort(key=lambda x: x['oncelik'])
        
        # Saldırı Gücünü Uygula
        for borc in mevcut_borclar:
            if borc['tutar'] > 1 and saldırı_kalan > 0:
                odecek_tutar = min(saldırı_kalan, borc['tutar'])
                borc['tutar'] -= odecek_tutar
                saldırı_kalan -= odecek_tutar
                
                if borc['tutar'] <= 1:
                     kapanan_borclar_listesi.append(borc['isim'])
                     borc['tutar'] = 0

        # 3.5. Sonuçları Kaydetme
        
        kalan_borc_toplam = sum(b['tutar'] for b in mevcut_borclar)
        
        aylik_sonuclar.append({
            'Ay': ay_adi,
            'Gelir': round(toplam_gelir + (tek_seferlik_kullanilan if tek_seferlik_kullanilan else 0)),
            'Min_Odeme_Toplam': round(min_odeme_toplam),
            'Zorunlu_Giderler': round(zorunlu_gider_toplam + garanti_kredi_gider),
            'Saldırı_Gucu_Kullanilan': round(saldırı_gucu - saldırı_kalan),
            'Birikim': round(birikim),
            'Kapanan_Borclar': ', '.join(kapanan_borclar_listesi),
            'Kalan_Borc_Toplam': round(kalan_borc_toplam)
        })
        
        ay_sayisi += 1
        tarih += pd.DateOffset(months=1)
        if tarih > pd.to_datetime('2026-12-31'): # Simülasyonu Aralık 2026'da durdur
            break
            
    return pd.DataFrame(aylik_sonuclar)

# ----------------------------------------------------------------------
# 4. PROGRAMI ÇALIŞTIRMA
# ----------------------------------------------------------------------

borc_tablosu = simule_borc_planı(borclar)
print(borc_tablosu.to_markdown(index=False))