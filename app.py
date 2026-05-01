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
KULLANICI_FILE = "kullanicilar.csv" # YENİ: Personel kayıt veritabanı
ADMIN_SIFRE = "ayhanlar2026"

gunler = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

# Dosya Kontrolleri ve Oluşturma
if not os.path.exists(TALEPLER_FILE):
    pd.DataFrame(columns=["Personel", "İzin Günü", "Haftalık Vardiya", "Neden", "Durum"]).to_csv(TALEPLER_FILE, index=False)
if not os.path.exists(VARDIYA_FILE):
    pd.DataFrame(columns=["Personel"] + gunler).to_csv(VARDIYA_FILE, index=False)
if not os.path.exists(KULLANICI_FILE):
    pd.DataFrame(columns=["Isim", "Email", "Sifre", "Durum"]).to_csv(KULLANICI_FILE, index=False)
if not os.path.exists(YAYIN_FILE):
    with open(YAYIN_FILE, "w") as f: f.write("GIZLI")

# --- MAİL GÖNDERME FONKSİYONU ---
def bildirim_maili_gonder(alici_mail, alici_isim):
    try:
        gonderen_mail = st.secrets["email"]["adres"]
        gonderen_sifre = st.secrets["email"]["sifre"]
        mesaj_metni = f"Merhaba {alici_isim},\n\nEkonomi Dünyası AVM bu haftanın vardiya listesi yayınlanmıştır. Sisteme giriş yaparak vardiyanızı kontrol edebilirsiniz.\n\nİyi çalışmalar."
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

# ==========================================
# GİRİŞ VE KAYIT EKRANI
# ==========================================
if not st.session_state.giris_yapildi:
    st.title("🏢 Ekonomi Dünyası AVM Giriş Portalı")
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        islem = st.radio("İşlem Seçiniz:", ["🔑 Personel Girişi", "📝 Yeni Kayıt Ol", "👑 Yönetici Girişi"])
        
        # 1. PERSONEL GİRİŞİ
        if islem == "🔑 Personel Girişi":
            email_input = st.text_input("E-posta Adresiniz:")
            sifre_input = st.text_input("Şifreniz:", type="password")
            
            if st.button("Giriş Yap"):
                df_k = pd.read_csv(KULLANICI_FILE)
                email_lower = email_input.strip().lower()
                kullanici = df_k[(df_k["Email"] == email_lower) & (df_k["Sifre"] == sifre_input)]
                
                if not kullanici.empty:
                    durum = kullanici.iloc[0]["Durum"]
                    if durum == "Beklemede":
                        st.warning("⏳ Hesabınız henüz yöneticiler tarafından onaylanmamıştır. Lütfen bekleyiniz.")
                    elif durum == "Reddedildi":
                        st.error("❌ Kayıt talebiniz reddedilmiştir.")
                    else:
                        st.session_state.giris_yapildi = True
                        st.session_state.kullanici_tipi = "Personel"
                        st.session_state.kullanici_adi = kullanici.iloc[0]["Isim"]
                        st.session_state.kullanici_mail = email_lower
                        st.rerun()
                else:
                    st.error("E-posta veya şifre hatalı!")
                    
        # 2. YENİ KAYIT OL
        elif islem == "📝 Yeni Kayıt Ol":
            st.info("Kayıt olduktan sonra sisteme giriş yapabilmek için yönetici onayını beklemeniz gerekmektedir.")
            with st.form("kayit_formu"):
                isim_yeni = st.text_input("Adınız Soyadınız:")
                email_yeni = st.text_input("E-posta Adresiniz:")
                sifre_yeni = st.text_input("Şifre Belirleyiniz:", type="password")
                
                if st.form_submit_button("Kayıt Talebini Gönder"):
                    df_k = pd.read_csv(KULLANICI_FILE)
                    email_lower = email_yeni.strip().lower()
                    
                    if email_lower in df_k["Email"].values:
                        st.error("Bu e-posta adresiyle zaten bir kayıt var!")
                    elif isim_yeni == "" or email_yeni == "" or sifre_yeni == "":
                        st.warning("Lütfen tüm alanları doldurunuz.")
                    else:
                        yeni_kullanici = {"Isim": isim_yeni.strip().title(), "Email": email_lower, "Sifre": sifre_yeni, "Durum": "Beklemede"}
                        pd.concat([df_k, pd.DataFrame([yeni_kullanici])]).to_csv(KULLANICI_FILE, index=False)
                        st.success("Kayıt talebiniz alındı! Yönetici onayından sonra giriş yapabilirsiniz.")

        # 3. YÖNETİCİ GİRİŞİ
        elif islem == "👑 Yönetici Girişi":
            admin_sifre = st.text_input("Yönetici Şifresi:", type="password")
            if st.button("Sistemi Aç"):
                if admin_sifre == ADMIN_SIFRE:
                    st.session_state.giris_yapildi = True
                    st.session_state.kullanici_tipi = "Yönetici"
                    st.session_state.kullanici_adi = "Yönetim"
                    st.rerun()
                else:
                    st.error("Hatalı Şifre!")

# ==========================================
# ANA SİSTEM (GİRİŞ YAPILDIKTAN SONRA)
# ==========================================
else:
    colA, colB = st.columns([8, 1])
    with colA: st.title(f"🏢 ED-AVM | Hoş Geldin, {st.session_state.kullanici_adi}")
    with colB:
        if st.button("🚪 Çıkış Yap"):
            st.session_state.giris_yapildi = False
            st.rerun()
            
    st.markdown("---")
    
    with open(YAYIN_FILE, "r") as f: yayin_durumu = f.read().strip()

    # --- PERSONEL EKRANI ---
    if st.session_state.kullanici_tipi == "Personel":
        tab1, tab2 = st.tabs(["✍️ Haftalık Planım", "📅 Kesinleşen Liste"])
        
        with tab1:
            st.info("💡 Rotasyon kuralına göre seçim yapınız (1 hafta sabah, 1 hafta akşam). Neden belirtmek zorunlu değildir.")
            with st.form("personel_formu", clear_on_submit=True):
                izin_gunu = st.selectbox("Bu hafta hangi gün İZİNLİ olacaksınız?", gunler)
                haftalik_shift = st.radio("Hangi vardiyada olacaksınız?", ["Sabahçı (09:00 - 18:00)", "Akşamcı (12:00 - 21:00)"])
                neden = st.text_area("Notunuz (İsteğe Bağlı):")
                
                if st.form_submit_button("Planımı Gönder"):
                    yeni = {"Personel": st.session_state.kullanici_adi, "İzin Günü": izin_gunu, "Haftalık Vardiya": haftalik_shift, "Neden": neden, "Durum": "Beklemede"}
                    df_t = pd.read_csv(TALEPLER_FILE)
                    pd.concat([df_t, pd.DataFrame([yeni])]).to_csv(TALEPLER_FILE, index=False)
                    st.success("Talebiniz yönetime iletildi.")
                    
        with tab2:
            if yayin_durumu == "YAYINLANDI":
                df_v = pd.read_csv(VARDIYA_FILE)
                def style_status(v):
                    val_str = str(v)
                    c = "#ff4b4b" if "🔴" in val_str else "#1c83e1" if "A " in val_str else "#28a745" if "S " in val_str else "#4CAF50"
                    return f'background-color: {c}; color: white'
                st.table(df_v.style.map(style_status, subset=gunler))
            else:
                st.warning("⚠️ Bu haftanın listesi henüz yönetim tarafından yayınlanmamıştır.")

    # --- YÖNETİCİ EKRANI ---
    elif st.session_state.kullanici_tipi == "Yönetici":
        tab1, tab2, tab3 = st.tabs(["👥 Kullanıcı Onayları", "👑 Vardiya Planlama", "📅 Kesinleşen Liste"])
        
        # YENİ EKLENEN: KULLANICI ONAY PANELİ
        with tab1:
            st.header("Sisteme Kayıt Olmak İsteyen Personeller")
            df_k = pd.read_csv(KULLANICI_FILE)
            bekleyen_kullanicilar = df_k[df_k["Durum"] == "Beklemede"]
            
            if len(bekleyen_kullanicilar) > 0:
                for idx, row in bekleyen_kullanicilar.iterrows():
                    with st.expander(f"👤 {row['Isim']} ({row['Email']})"):
                        c1, c2 = st.columns(2)
                        if c1.button("Kullanıcıyı Onayla", key=f"k_on_{idx}"):
                            df_k.at[idx, "Durum"] = "Onaylandı"
                            df_k.to_csv(KULLANICI_FILE, index=False)
                            st.rerun()
                        if c2.button("Reddet", key=f"k_red_{idx}"):
                            df_k.at[idx, "Durum"] = "Reddedildi"
                            df_k.to_csv(KULLANICI_FILE, index=False)
                            st.rerun()
            else:
                st.info("Onay bekleyen yeni kayıt bulunmuyor.")
                
            st.divider()
            st.write("**Aktif (Onaylanmış) Personel Listesi:**")
            st.dataframe(df_k[df_k["Durum"] == "Onaylandı"][["Isim", "Email"]], use_container_width=True)

        with tab2:
            if st.button("🔄 Yeni Haftaya Başla (Mevcut Listeyi Personelden Gizle)"):
                with open(YAYIN_FILE, "w") as f: f.write("GIZLI")
                pd.DataFrame(columns=["Personel", "İzin Günü", "Haftalık Vardiya", "Neden", "Durum"]).to_csv(TALEPLER_FILE, index=False)
                st.success("Sistem sıfırlandı. Yeni talepler bekleniyor.")
                st.rerun()

            st.divider()
            df_t = pd.read_csv(TALEPLER_FILE)
            bekleyen_talepler = df_t[df_t["Durum"] == "Beklemede"]
            
            if len(bekleyen_talepler) > 0:
                st.write("### Onay Bekleyen Vardiya Talepleri")
                for idx, row in bekleyen_talepler.iterrows():
                    with st.expander(f"📌 {row['Personel']} | İzin: {row['İzin Günü']} | Vardiya: {row['Haftalık Vardiya']}"):
                        if pd.notna(row['Neden']) and str(row['Neden']).strip() != "":
                            st.write(f"**Not:** {row['Neden']}")
                        
                        c1, c2 = st.columns(2)
                        if c1.button("Onayla", key=f"v_on_{idx}"):
                            df_t.at[idx, "Durum"] = "Onaylandı"
                            df_t.to_csv(TALEPLER_FILE, index=False)
                            st.rerun()
                        if c2.button("Reddet", key=f"v_red_{idx}"):
                            df_t.at[idx, "Durum"] = "Reddedildi"
                            df_t.to_csv(TALEPLER_FILE, index=False)
                            st.rerun()
            else:
                st.info("Onay bekleyen plan bulunmuyor.")

            st.divider()
            st.write("### Yayın ve Bildirim İşlemleri")
            if st.button("🚀 Planı Kesinleştir, Yayınla ve Personele Mail Gönder"):
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
                    with open(YAYIN_FILE, "w") as f: f.write("YAYINLANDI")
                    st.success("Haftalık çizelge oluşturuldu ve yayınlandı!")
                    
                    # SADECE ONAYLI KULLANICILARA MAİL GÖNDER
                    df_k_mail = pd.read_csv(KULLANICI_FILE)
                    onayli_kullanicilar = df_k_mail[df_k_mail["Durum"] == "Onaylandı"]
                    
                    with st.spinner("Personele bildirim mailleri gönderiliyor..."):
                        basarili_mail = 0
                        for _, user in onayli_kullanicilar.iterrows():
                            if bildirim_maili_gonder(user["Email"], user["Isim"]):
                                basarili_mail += 1
                        
                        if basarili_mail > 0:
                            st.info(f"{basarili_mail} aktif personele başarıyla mail gönderildi.")
                        else:
                            st.error("Mailler gönderilemedi. (Streamlit Secrets ayarlarınızı kontrol edin).")
                    st.rerun()
                else:
                    st.warning("Henüz onaylanmış vardiya planı yok.")
                    
        with tab3:
            if os.path.exists(VARDIYA_FILE):
                df_v = pd.read_csv(VARDIYA_FILE)
                def style_status(v):
                    val_str = str(v)
                    c = "#ff4b4b" if "🔴" in val_str else "#1c83e1" if "A " in val_str else "#28a745" if "S " in val_str else "#4CAF50"
                    return f'background-color: {c}; color: white'
                st.table(df_v.style.map(style_status, subset=gunler))
