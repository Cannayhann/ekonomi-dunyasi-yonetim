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
KULLANICI_FILE = "kullanicilar.csv"
ADMIN_SIFRE = "ayhanlar2026"

gunler = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

# Dosya Kontrolleri
if not os.path.exists(TALEPLER_FILE):
    pd.DataFrame(columns=["Personel", "İzin Günü", "Haftalık Vardiya", "Neden", "Durum"]).to_csv(TALEPLER_FILE, index=False)
if not os.path.exists(VARDIYA_FILE):
    pd.DataFrame(columns=["Personel"] + gunler).to_csv(VARDIYA_FILE, index=False)
if not os.path.exists(KULLANICI_FILE):
    pd.DataFrame(columns=["Isim", "Email", "Sifre", "Durum"]).to_csv(KULLANICI_FILE, index=False)
if not os.path.exists(YAYIN_FILE):
    with open(YAYIN_FILE, "w") as f: f.write("GIZLI")

# --- DİNAMİK MAİL GÖNDERME FONKSİYONU ---
def mail_gonder(alici_mail, konu, mesaj_metni):
    try:
        gonderen_mail = st.secrets["email"]["adres"]
        gonderen_sifre = st.secrets["email"]["sifre"]
        
        msg = MIMEText(mesaj_metni)
        msg['Subject'] = konu
        msg['From'] = f"ED-AVM Yönetim <{gonderen_mail}>"
        msg['To'] = alici_mail
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(gonderen_mail, gonderen_sifre)
            server.send_message(msg)
        return True
    except Exception as e:
        return False

# --- GİRİŞ KONTROLÜ ---
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
                        st.warning("⏳ Hesabınız henüz onaylanmamıştır.")
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
                    
        elif islem == "📝 Yeni Kayıt Ol":
            st.info("Kayıt olduktan sonra yönetici onayını beklemeniz gerekmektedir.")
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
                        
                        # --- YENİ EKLENEN: KARŞILAMA MAİLİ ---
                        mail_gonder(
                            email_lower, 
                            "ED-AVM | Kayıt Talebiniz Alındı", 
                            f"Merhaba {isim_yeni.strip().title()},\n\nEkonomi Dünyası AVM personel sistemine kayıt talebiniz başarıyla alınmıştır. Yönetim tarafından hesabınız onaylandığında sisteme giriş yapabileceksiniz.\n\nİyi çalışmalar dileriz."
                        )
                        
                        st.success("Kayıt talebiniz alındı ve size bir bilgilendirme maili gönderildi! Yönetici onayını bekleyiniz.")

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
            st.info("💡 Rotasyon kuralına göre seçim yapınız. Neden belirtmek zorunlu değildir.")
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
                st.warning("⚠️ Bu haftanın listesi henüz yayınlanmamıştır.")

    # --- YÖNETİCİ EKRANI ---
    elif st.session_state.kullanici_tipi == "Yönetici":
        tab1, tab2, tab3 = st.tabs(["👥 Kullanıcı Yönetimi", "👑 Vardiya Planlama", "📅 Kesinleşen Liste"])
        
        # 1. SEKME: KULLANICI YÖNETİMİ
        with tab1:
            st.header("Sisteme Kayıt Olmak İsteyenler")
            df_k = pd.read_csv(KULLANICI_FILE)
            bekleyen_kullanicilar = df_k[df_k["Durum"] == "Beklemede"]
            
            if len(bekleyen_kullanicilar) > 0:
                for idx, row in bekleyen_kullanicilar.iterrows():
                    with st.expander(f"👤 {row['Isim']} ({row['Email']})"):
                        c1, c2 = st.columns(2)
                        if c1.button("Onayla", key=f"k_on_{idx}"):
                            df_k.at[idx, "Durum"] = "Onaylandı"
                            df_k.to_csv(KULLANICI_FILE, index=False)
                            mail_gonder(row["Email"], "ED-AVM Hesabınız Onaylandı", f"Merhaba {row['Isim']},\n\nSisteme kaydınız onaylanmıştır. Kendi belirlediğiniz şifrenizle giriş yapabilirsiniz.")
                            st.rerun()
                        if c2.button("Reddet", key=f"k_red_{idx}"):
                            df_k.at[idx, "Durum"] = "Reddedildi"
                            df_k.to_csv(KULLANICI_FILE, index=False)
                            st.rerun()
            else:
                st.info("Onay bekleyen yeni kayıt bulunmuyor.")
                
            st.divider()
            st.header("Aktif Personeller ve Şifre Yönetimi")
            aktifler = df_k[df_k["Durum"] == "Onaylandı"]
            if len(aktifler) > 0:
                for idx, row in aktifler.iterrows():
                    with st.expander(f"⚙️ {row['Isim']} | Email: {row['Email']} | Şifre: {row['Sifre']}"):
                        st.warning(f"Dikkat: {row['Isim']} isimli kullanıcıyı sistemden silmek üzeresiniz.")
                        if st.button("🗑️ Kullanıcıyı Sil", key=f"del_{idx}"):
                            df_k = df_k.drop(idx)
                            df_k.to_csv(KULLANICI_FILE, index=False)
                            st.rerun()
            else:
                st.info("Sistemde henüz onaylı personel bulunmuyor.")

        # 2. SEKME: VARDİYA PLANLAMA
        with tab2:
            if st.button("🔄 Yeni Haftaya Başla (Mevcut Listeyi Gizle)"):
                with open(YAYIN_FILE, "w") as f: f.write("GIZLI")
                pd.DataFrame(columns=["Personel", "İzin Günü", "Haftalık Vardiya", "Neden", "Durum"]).to_csv(TALEPLER_FILE, index=False)
                st.success("Sistem sıfırlandı. Yeni talepler bekleniyor.")
                st.rerun()

            st.divider()
            df_t = pd.read_csv(TALEPLER_FILE)
            bekleyen_talepler = df_t[df_t["Durum"] == "Beklemede"]
            df_k_guncel = pd.read_csv(KULLANICI_FILE)
            
            if len(bekleyen_talepler) > 0:
                st.write("### Onay Bekleyen Vardiya Talepleri")
                for idx, row in bekleyen_talepler.iterrows():
                    with st.expander(f"📌 {row['Personel']} | İzin: {row['İzin Günü']} | Vardiya: {row['Haftalık Vardiya']}"):
                        if pd.notna(row['Neden']) and str(row['Neden']).strip() != "":
                            st.write(f"**Not:** {row['Neden']}")
                        
                        user_email_list = df_k_guncel[df_k_guncel['Isim'] == row['Personel']]['Email'].values
                        user_email = user_email_list[0] if len(user_email_list) > 0 else None

                        c1, c2 = st.columns(2)
                        if c1.button("Onayla", key=f"v_on_{idx}"):
                            df_t.at[idx, "Durum"] = "Onaylandı"
                            df_t.to_csv(TALEPLER_FILE, index=False)
                            if user_email:
                                mail_gonder(user_email, "ED-AVM | Vardiya Talebiniz Onaylandı", f"Merhaba {row['Personel']},\n\nBu haftaki vardiya ve izin talebiniz yönetim tarafından ONAYLANMIŞTIR.")
                            st.rerun()
                        if c2.button("Reddet", key=f"v_red_{idx}"):
                            df_t.at[idx, "Durum"] = "Reddedildi"
                            df_t.to_csv(TALEPLER_FILE, index=False)
                            if user_email:
                                mail_gonder(user_email, "ED-AVM | Vardiya Talebiniz Reddedildi", f"Merhaba {row['Personel']},\n\nBu haftaki vardiya ve izin talebiniz yönetim tarafından REDDEDİLMİŞTİR. Lütfen sisteme girip yeni bir talep oluşturunuz veya yönetimle görüşünüz.")
                            st.rerun()
            else:
                st.info("Onay bekleyen plan bulunmuyor.")

            st.divider()
            st.write("### Yayın ve Bildirim İşlemleri")
            
            col_yayin, col_mail = st.columns(2)
            
            with col_yayin:
                if st.button("🚀 Planı Kesinleştir ve Yayınla"):
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
                        st.success("Haftalık çizelge oluşturuldu ve yayınlandı! Liste artık görünebilir.")
                        st.rerun()
                    else:
                        st.warning("Henüz onaylanmış vardiya planı yok.")
                        
            with col_mail:
                if st.button("📧 Tüm Personele Yayın Maili Gönder"):
                    with open(YAYIN_FILE, "r") as f: guncel_yayin = f.read().strip()
                    
                    if guncel_yayin == "YAYINLANDI":
                        onayli_kullanicilar = df_k_guncel[df_k_guncel["Durum"] == "Onaylandı"]
                        if len(onayli_kullanicilar) > 0:
                            with st.spinner("Personele bildirim mailleri gönderiliyor..."):
                                basarili_mail = 0
                                for _, user in onayli_kullanicilar.iterrows():
                                    if mail_gonder(user["Email"], "ED-AVM | Haftalık Liste Yayınlandı", f"Merhaba {user['Isim']},\n\nBu haftanın kesinleşmiş vardiya listesi yayınlanmıştır. Sisteme girip kontrol edebilirsiniz."):
                                        basarili_mail += 1
                                st.success(f"{basarili_mail} personele yayın maili başarıyla gönderildi!")
                        else:
                            st.warning("Sistemde aktif/onaylı personel bulunmuyor.")
                    else:
                        st.error("⚠️ HATA: Mail göndermeden önce planı kesinleştirip yayınlamalısınız!")
                    
        # 3. SEKME: KESİNLEŞEN LİSTE
        with tab3:
            if os.path.exists(VARDIYA_FILE):
                df_v = pd.read_csv(VARDIYA_FILE)
                def style_status(v):
                    val_str = str(v)
                    c = "#ff4b4b" if "🔴" in val_str else "#1c83e1" if "A " in val_str else "#28a745" if "S " in val_str else "#4CAF50"
                    return f'background-color: {c}; color: white'
                st.table(df_v.style.map(style_status, subset=gunler))
