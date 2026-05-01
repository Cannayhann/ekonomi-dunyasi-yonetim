import streamlit as st
import pandas as pd
import os
import smtplib
from email.mime.text import MIMEText

# 1. AYARLAR VE VERİTABANI
st.set_page_config(page_title="ED-AVM Sistem", layout="wide")

TALEPLER_FILE = "talepler.csv"
VARDIYA_FILE = "vardiya_duzeni.csv"
YAYIN_FILE = "yayin_durumu.txt"
ADMIN_SIFRE = "ayhanlar2026"

# Personel E-posta Veritabanı (Buraya personelin GERÇEK maillerini yazmalısın)
PERSONEL_DB = {
    "suleyman@edavm.com": "Süleyman",
    "firat@edavm.com": "Fırat",
    "fatih@edavm.com": "Fatih",
    "can@edavm.com": "Can",
    "esra@edavm.com": "Esra",
    "tugce@edavm.com": "Tuğçe",
    "nurdan@edavm.com": "Nurdan",
    "elif@edavm.com": "Elif",
    "ayse@edavm.com": "Ayşe",
    "fatma@edavm.com": "Fatma",
    "sude@edavm.com": "Sude"
}

gunler = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

# Dosya Kontrolleri
if not os.path.exists(TALEPLER_FILE):
    pd.DataFrame(columns=["Personel", "İzin Günü", "Haftalık Vardiya", "Neden", "Durum"]).to_csv(TALEPLER_FILE, index=False)
if not os.path.exists(YAYIN_FILE):
    with open(YAYIN_FILE, "w") as f: f.write("GIZLI")

# --- MAİL GÖNDERME FONKSİYONU ---
def bildirim_maili_gonder(alici_mail, alici_isim):
    try:
        # Streamlit Cloud ayarlarına gireceğimiz gizli şifreler
        gonderen_mail = st.secrets["email"]["adres"]
        gonderen_sifre = st.secrets["email"]["sifre"]
        
        mesaj_metni = f"Merhaba {alici_isim},\n\nEkonomi Dünyası AVM bu haftanın vardiya listesi yönetim tarafından yayınlanmıştır. Sisteme e-posta adresinizle giriş yaparak vardiyanızı kontrol edebilirsiniz.\n\nİyi çalışmalar."
        msg = MIMEText(mesaj_metni)
        msg['Subject'] = "ED-AVM Haftalık Vardiya Listesi Yayınlandı"
        msg['From'] = f"ED-AVM Yönetim <{gonderen_mail}>"
        msg['To'] = alici_mail
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(gonderen_mail, gonderen_sifre)
            server.send_message(msg)
        return True
    except Exception as e:
        return False

# --- GİRİŞ KONTROLÜ (SESSION STATE) ---
if "giris_yapildi" not in st.session_state:
    st.session_state.giris_yapildi = False
    st.session_state.kullanici_tipi = ""
    st.session_state.kullanici_adi = ""
    st.session_state.kullanici_mail = ""

# --- GİRİŞ EKRANI ---
if not st.session_state.giris_yapildi:
    st.title("🏢 Ekonomi Dünyası AVM Giriş Portalı")
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        giris_tipi = st.radio("Giriş Türü Seçiniz:", ["Personel Girişi", "Yönetici Girişi"])
        
        if giris_tipi == "Personel Girişi":
            email_input = st.text_input("Kayıtlı E-posta Adresiniz:")
            if st.button("Giriş Yap"):
                email_lower = email_input.strip().lower()
                if email_lower in PERSONEL_DB:
                    st.session_state.giris_yapildi = True
                    st.session_state.kullanici_tipi = "Personel"
                    st.session_state.kullanici_adi = PERSONEL_DB[email_lower]
                    st.session_state.kullanici_mail = email_lower
                    st.rerun()
                else:
                    st.error("Sistemde bu e-posta adresi bulunamadı! Yönetime danışınız.")
                    
        elif giris_tipi == "Yönetici Girişi":
            sifre = st.text_input("Yönetici Şifresi:", type="password")
            if st.button("Sistemi Aç"):
                if sifre == ADMIN_SIFRE:
                    st.session_state.giris_yapildi = True
                    st.session_state.kullanici_tipi = "Yönetici"
                    st.session_state.kullanici_adi = "Yönetim"
                    st.rerun()
                else:
                    st.error("Hatalı Şifre!")

# --- ANA SİSTEM ---
else:
    colA, colB = st.columns([8, 1])
    with colA: st.title(f"🏢 ED-AVM | Hoş Geldin, {st.session_state.kullanici_adi}")
    with colB:
        if st.button("🚪 Çıkış Yap"):
            st.session_state.giris_yapildi = False
            st.rerun()
            
    st.markdown("---")

    # YAYIN DURUMUNU KONTROL ET
    with open(YAYIN_FILE, "r") as f:
        yayin_durumu = f.read().strip()

    # --- PERSONEL EKRANI ---
    if st.session_state.kullanici_tipi == "Personel":
        tab1, tab2 = st.tabs(["✍️ Haftalık Planım", "📅 Kesinleşen Liste"])
        
        with tab1:
            st.info("💡 Haftalık rotasyon kuralına göre seçim yapınız (1 hafta sabah, 1 hafta akşam).")
            with st.form("personel_formu", clear_on_submit=True):
                izin_gunu = st.selectbox("Bu hafta hangi gün İZİNLİ olacaksınız?", gunler)
                haftalik_shift = st.radio("Haftanın geri kalanında hangi vardiyada olacaksınız?", 
                                          ["Sabahçı (09:00 - 18:00)", "Akşamcı (12:00 - 21:00)"])
                # NEDEN KISMI İSTEĞE BAĞLI EKLENDİ
                neden = st.text_area("İzin veya Vardiya Talebi İçin Notunuz (İsteğe Bağlı):", placeholder="Örn: Salı günü hastane randevum var...")
                
                if st.form_submit_button("Planımı Gönder"):
                    yeni = {"Personel": st.session_state.kullanici_adi, "İzin Günü": izin_gunu, "Haftalık Vardiya": haftalik_shift, "Neden": neden, "Durum": "Beklemede"}
                    df_t = pd.read_csv(TALEPLER_FILE)
                    pd.concat([df_t, pd.DataFrame([yeni])]).to_csv(TALEPLER_FILE, index=False)
                    st.success("Haftalık planın yönetime iletildi.")
                    
        with tab2:
            # GİZLİLİK KURALI: Yalnızca yayınlandıysa görsünler
            if yayin_durumu == "YAYINLANDI":
                if os.path.exists(VARDIYA_FILE):
                    df_v = pd.read_csv(VARDIYA_FILE)
                    def style_status(v):
                        val_str = str(v)
                        c = "#ff4b4b" if "🔴" in val_str else "#1c83e1" if "A " in val_str else "#28a745" if "S " in val_str else "#4CAF50"
                        return f'background-color: {c}; color: white'
                    st.table(df_v.style.map(style_status, subset=gunler))
            else:
                st.warning("⚠️ Bu haftanın vardiya listesi henüz yönetim tarafından yayınlanmamıştır. Lütfen daha sonra tekrar kontrol ediniz.")

    # --- YÖNETİCİ EKRANI ---
    elif st.session_state.kullanici_tipi == "Yönetici":
        tab1, tab2 = st.tabs(["👑 Yönetici Onay Paneli", "📅 Kesinleşen Liste"])
        
        with tab1:
            # YENİ HAFTAYA HAZIRLIK BUTONU (Listeyi Gizler)
            if st.button("🔄 Yeni Haftaya Başla (Mevcut Listeyi Personelden Gizle)"):
                with open(YAYIN_FILE, "w") as f: f.write("GIZLI")
                pd.DataFrame(columns=["Personel", "İzin Günü", "Haftalık Vardiya", "Neden", "Durum"]).to_csv(TALEPLER_FILE, index=False)
                st.success("Sistem sıfırlandı. Liste personelden gizlendi, yeni talepler bekleniyor.")
                st.rerun()

            st.divider()
            df_t = pd.read_csv(TALEPLER_FILE)
            bekleyenler = df_t[df_t["Durum"] == "Beklemede"]
            
            if len(bekleyenler) > 0:
                st.write("### Onay Bekleyen Talepler")
                for idx, row in bekleyenler.iterrows():
                    with st.expander(f"📌 {row['Personel']} | İzin: {row['İzin Günü']} | Vardiya: {row['Haftalık Vardiya']}"):
                        if pd.notna(row['Neden']) and str(row['Neden']).strip() != "":
                            st.write(f"**Not:** {row['Neden']}")
                        
                        c1, c2 = st.columns(2)
                        if c1.button("Onayla", key=f"on_{idx}"):
                            df_t.at[idx, "Durum"] = "Onaylandı"
                            df_t.to_csv(TALEPLER_FILE, index=False)
                            st.rerun()
                        if c2.button("Reddet", key=f"red_{idx}"):
                            df_t.at[idx, "Durum"] = "Reddedildi"
                            df_t.to_csv(TALEPLER_FILE, index=False)
                            st.rerun()
            else:
                st.info("Onay bekleyen plan bulunmuyor.")

            st.divider()
            st.write("### Yayın ve Bildirim")
            if st.button("🚀 Planı Kesinleştir, Yayınla ve Mail Gönder"):
                onayli = df_t[df_t["Durum"] == "Onaylandı"]
                if len(onayli) > 0:
                    unique_staff = onayli["Personel"].unique()
                    final_df = pd.DataFrame(index=unique_staff, columns=gunler)
                    
                    for _, r in onayli.iterrows():
                        p = str(r["Personel"])
                        iz = str(r["İzin Günü"])
                        shift = "A (12-21)" if "Akşamcı" in str(r["Haftalık Vardiya"]) else "S (09-18)"
                        for g in gunler:
                            if g == iz: final_df.at[p, g] = "🔴 İZİNLİ"
                            elif g == "Pazar": final_df.at[p, g] = "🟢 TAM GÜÇ"
                            else: final_df.at[p, g] = shift
                    
                    final_df.reset_index(inplace=True)
                    final_df.rename(columns={'index': 'Personel'}, inplace=True)
                    final_df.to_csv(VARDIYA_FILE, index=False)
                    
                    # Durumu Yayınlandı Yap
                    with open(YAYIN_FILE, "w") as f: f.write("YAYINLANDI")
                    st.success("Haftalık çizelge başarıyla yayınlandı! Liste artık personel tarafından görülebilir.")
                    
                    # MAİL GÖNDERİM TETİKLEMESİ
                    with st.spinner("Personele bildirim mailleri gönderiliyor..."):
                        basarili_mail = 0
                        for mail, isim in PERSONEL_DB.items():
                            if bildirim_maili_gonder(mail, isim):
                                basarili_mail += 1
                        
                        if basarili_mail > 0:
                            st.info(f"{basarili_mail} personele başarıyla mail gönderildi.")
                        else:
                            st.error("Mailler gönderilemedi. Lütfen Streamlit Secrets ayarlarınızı kontrol edin.")
                    st.rerun()
                else:
                    st.warning("Onaylanmış plan yok.")
                    
        with tab2:
            if os.path.exists(VARDIYA_FILE):
                df_v = pd.read_csv(VARDIYA_FILE)
                def style_status(v):
                    val_str = str(v)
                    c = "#ff4b4b" if "🔴" in val_str else "#1c83e1" if "A " in val_str else "#28a745" if "S " in val_str else "#4CAF50"
                    return f'background-color: {c}; color: white'
                st.table(df_v.style.map(style_status, subset=gunler))
