import streamlit as st
import pandas as pd
import os
import smtplib
import random
import string
from email.mime.text import MIMEText

# 1. SİSTEM AYARLARI
st.set_page_config(page_title="ED-AVM Yönetim", layout="wide")

TALEPLER_FILE = "talepler.csv"
VARDIYA_FILE = "vardiya_duzeni.csv"
YAYIN_FILE = "yayin_durumu.txt"
KULLANICI_FILE = "kullanicilar.csv"
PROFILE_DIR = "profil_fotograflari" # YENİ: Fotoğrafların tutulacağı klasör

gunler = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

# Klasör ve Dosya Kontrolleri
os.makedirs(PROFILE_DIR, exist_ok=True)

if not os.path.exists(KULLANICI_FILE):
    admin_data = {"Isim": "Yönetim", "Email": "admin@edavm.com", "Sifre": "ayhanlar2026", "Telefon": "05000000000", "Durum": "Onaylandı", "Rol": "Yonetici"}
    pd.DataFrame([admin_data]).to_csv(KULLANICI_FILE, index=False)

if not os.path.exists(TALEPLER_FILE):
    pd.DataFrame(columns=["Personel", "İzin Günü", "Haftalık Vardiya", "Neden", "Durum"]).to_csv(TALEPLER_FILE, index=False)

if not os.path.exists(VARDIYA_FILE):
    pd.DataFrame(columns=["Personel"] + gunler).to_csv(VARDIYA_FILE, index=False)

if not os.path.exists(YAYIN_FILE):
    with open(YAYIN_FILE, "w") as f: f.write("GIZLI")

# --- MAİL VE KOD FONKSİYONLARI ---
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
    except:
        return False

def kod_uret():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

# --- SESSION STATE ---
if "giris_yapildi" not in st.session_state:
    st.session_state.update({"giris_yapildi": False, "kullanici_tipi": "", "kullanici_adi": "", "kullanici_mail": "", "reset_kod": "", "reset_mail": ""})

# ==========================================
# GİRİŞ / KAYIT / ŞİFRE SIFIRLAMA EKRANI
# ==========================================
if not st.session_state.giris_yapildi:
    col_logo, col_baslik = st.columns([1, 8])
    with col_baslik:
        st.title("🏢 Ekonomi Dünyası AVM Portalı")
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        sekme = st.radio("İşlem Seçiniz", ["🔑 Giriş Yap", "📝 Kayıt Ol", "❓ Şifremi Unuttum"], horizontal=True)

        if sekme == "🔑 Giriş Yap":
            email_in = st.text_input("E-posta").strip().lower()
            sifre_in = st.text_input("Şifre", type="password")
            if st.button("Sisteme Gir"):
                df_k = pd.read_csv(KULLANICI_FILE)
                user = df_k[(df_k["Email"] == email_in) & (df_k["Sifre"] == str(sifre_in))]
                if not user.empty:
                    if user.iloc[0]["Durum"] == "Onaylandı":
                        st.session_state.update({"giris_yapildi": True, "kullanici_tipi": user.iloc[0]["Rol"], "kullanici_adi": user.iloc[0]["Isim"], "kullanici_mail": email_in})
                        st.rerun()
                    else:
                        st.warning("⏳ Hesabınız onay bekliyor.")
                else:
                    st.error("❌ E-posta veya şifre hatalı.")

        elif sekme == "📝 Kayıt Ol":
            with st.form("kayit"):
                isim = st.text_input("Adınız Soyadınız")
                tel = st.text_input("Telefon Numaranız")
                mail = st.text_input("E-posta Adresiniz").strip().lower()
                sifre = st.text_input("Şifre Belirleyiniz", type="password")
                if st.form_submit_button("Kayıt Talebi Gönder"):
                    df_k = pd.read_csv(KULLANICI_FILE)
                    if mail in df_k["Email"].values:
                        st.error("Bu e-posta zaten sistemde kayıtlı.")
                    elif isim == "" or mail == "" or sifre == "":
                        st.warning("Lütfen zorunlu alanları doldurun.")
                    else:
                        yeni = {"Isim": isim.strip().title(), "Email": mail, "Sifre": sifre, "Telefon": tel, "Durum": "Beklemede", "Rol": "Personel"}
                        pd.concat([df_k, pd.DataFrame([yeni])]).to_csv(KULLANICI_FILE, index=False)
                        mail_gonder(mail, "ED-AVM | Kayıt Talebiniz Alındı", f"Merhaba {isim},\n\nKayıt talebiniz alındı. Yönetim onayından sonra giriş yapabilirsiniz.")
                        st.success("Kayıt başarılı! Bilgilendirme maili gönderildi.")

        elif sekme == "❓ Şifremi Unuttum":
            if st.session_state.reset_kod == "":
                mail_res = st.text_input("Sisteme Kayıtlı E-posta Adresiniz:")
                if st.button("Doğrulama Kodu Gönder"):
                    df_k = pd.read_csv(KULLANICI_FILE)
                    if mail_res.strip().lower() in df_k["Email"].values:
                        kod = kod_uret()
                        st.session_state.reset_kod = kod
                        st.session_state.reset_mail = mail_res.strip().lower()
                        mail_gonder(mail_res, "ED-AVM | Şifre Sıfırlama Kodu", f"Sisteme giriş için şifre sıfırlama kodunuz: {kod}")
                        st.info("6 haneli kod e-postanıza gönderildi.")
                    else:
                        st.error("Bu mail adresi sistemde bulunamadı.")
            else:
                st.success("Kod e-postanıza gönderildi!")
                kod_in = st.text_input("Mailinize gelen 6 haneli kodu girin:")
                yeni_sifre = st.text_input("Yeni Şifreniz:", type="password")
                if st.button("Şifreyi Güncelle"):
                    if kod_in == st.session_state.reset_kod:
                        df_k = pd.read_csv(KULLANICI_FILE)
                        df_k.loc[df_k["Email"] == st.session_state.reset_mail, "Sifre"] = yeni_sifre
                        df_k.to_csv(KULLANICI_FILE, index=False)
                        st.success("Şifreniz başarıyla güncellendi! Yeniden giriş yapabilirsiniz.")
                        st.session_state.reset_kod = ""
                    else:
                        st.error("Girdiğiniz kod hatalı.")

# ==========================================
# ANA SİSTEM (GİRİŞ YAPILDIKTAN SONRA)
# ==========================================
else:
    # YENİ EKLENEN: PROFİL FOTOĞRAFI GÖSTERİMİ
    pp_path = os.path.join(PROFILE_DIR, f"{st.session_state.kullanici_mail}.png")
    
    with st.sidebar:
        if os.path.exists(pp_path):
            st.image(pp_path, width=150)
        else:
            st.write("👤 *(Fotoğraf Yok)*")
            
        st.title(f"{st.session_state.kullanici_adi}")
        st.caption(f"{st.session_state.kullanici_tipi}")
        st.divider()
        
        menu_secenekleri = ["Vardiya İşlemleri", "Profilim"]
        if st.session_state.kullanici_tipi == "Yonetici":
            menu_secenekleri.append("Yönetici Paneli")
            
        sayfa = st.radio("Menü", menu_secenekleri)
        st.divider()
        if st.button("🚪 Çıkış Yap", use_container_width=True):
            st.session_state.giris_yapildi = False
            st.rerun()

    with open(YAYIN_FILE, "r") as f: yayin_durumu = f.read().strip()

    # --- 1. SAYFA: PROFİLİM (HERKES İÇİN) ---
    if sayfa == "Profilim":
        st.header("👤 Profilimi Düzenle")
        df_k = pd.read_csv(KULLANICI_FILE)
        u_data = df_k[df_k["Email"] == st.session_state.kullanici_mail].iloc[0]
        
        col_foto, col_bilgi = st.columns([1, 2])
        
        with col_foto:
            st.subheader("Fotoğraf")
            if os.path.exists(pp_path):
                st.image(pp_path, width=200)
            
            yuklenen_foto = st.file_uploader("Yeni Fotoğraf Yükle (PNG/JPG)", type=["png", "jpg", "jpeg"])
            if yuklenen_foto is not None:
                with open(pp_path, "wb") as f:
                    f.write(yuklenen_foto.getbuffer())
                st.success("Fotoğraf başarıyla yüklendi!")
                st.rerun()

        with col_bilgi:
            st.subheader("Kişisel Bilgiler")
            yeni_isim = st.text_input("Ad Soyad:", value=u_data["Isim"])
            yeni_tel = st.text_input("Telefon Numarası:", value=str(u_data["Telefon"]) if pd.notna(u_data["Telefon"]) else "")
            yeni_sifre = st.text_input("Şifre (Değiştirmek istemiyorsanız aynı bırakın):", value=u_data["Sifre"], type="password")
            
            if st.button("Bilgilerimi Kaydet"):
                df_k.loc[df_k["Email"] == st.session_state.kullanici_mail, ["Isim", "Telefon", "Sifre"]] = [yeni_isim, yeni_tel, yeni_sifre]
                df_k.to_csv(KULLANICI_FILE, index=False)
                st.session_state.kullanici_adi = yeni_isim
                st.success("Profil bilgileriniz başarıyla güncellendi.")
                st.rerun()

    # --- 2. SAYFA: VARDİYA İŞLEMLERİ (HERKES İÇİN) ---
    elif sayfa == "Vardiya İşlemleri":
        st.header("📅 Haftalık Vardiya Planlaması")
        tab1, tab2 = st.tabs(["✍️ Planımı Gönder", "📊 Kesinleşen Liste"])
        
        with tab1:
            st.info("Haftalık rotasyon kuralına göre seçim yapınız.")
            with st.form("personel_formu", clear_on_submit=True):
                izin_gunu = st.selectbox("Bu hafta hangi gün İZİNLİ olacaksınız?", gunler)
                haftalik_shift = st.radio("Hangi vardiyada olacaksınız?", ["Sabahçı (09:00 - 18:00)", "Akşamcı (12:00 - 21:00)"])
                neden = st.text_area("Yönetime Notunuz (İsteğe Bağlı):")
                
                if st.form_submit_button("Planımı Gönder"):
                    yeni = {"Personel": st.session_state.kullanici_adi, "İzin Günü": izin_gunu, "Haftalık Vardiya": haftalik_shift, "Neden": neden, "Durum": "Beklemede"}
                    df_t = pd.read_csv(TALEPLER_FILE)
                    pd.concat([df_t, pd.DataFrame([yeni])]).to_csv(TALEPLER_FILE, index=False)
                    st.success("Talebiniz yönetime iletildi.")
                    
        with tab2:
            if yayin_durumu == "YAYINLANDI":
                if os.path.exists(VARDIYA_FILE):
                    df_v = pd.read_csv(VARDIYA_FILE)
                    def style_status(v):
                        val_str = str(v)
                        c = "#ff4b4b" if "🔴" in val_str else "#1c83e1" if "A " in val_str else "#28a745" if "S " in val_str else "#4CAF50"
                        return f'background-color: {c}; color: white'
                    st.table(df_v.style.map(style_status, subset=gunler))
            else:
                st.warning("⚠️ Bu haftanın listesi henüz yönetim tarafından yayınlanmamıştır.")

    # --- 3. SAYFA: YÖNETİCİ PANELİ (SADECE ADMİN) ---
    elif sayfa == "Yönetici Paneli" and st.session_state.kullanici_tipi == "Yonetici":
        st.header("👑 Yönetim Kontrol Merkezi")
        tab_k, tab_v = st.tabs(["👥 Kullanıcı Yönetimi", "📋 Vardiya ve Yayın"])
        
        with tab_k:
            df_k = pd.read_csv(KULLANICI_FILE)
            bekleyenler = df_k[df_k["Durum"] == "Beklemede"]
            st.subheader("Yeni Kayıt Onayları")
            if len(bekleyenler) > 0:
                for idx, row in bekleyenler.iterrows():
                    with st.expander(f"👤 {row['Isim']} ({row['Email']}) | Tel: {row['Telefon']}"):
                        c1, c2 = st.columns(2)
                        if c1.button("Onayla", key=f"kon_{idx}"):
                            df_k.at[idx, "Durum"] = "Onaylandı"
                            df_k.to_csv(KULLANICI_FILE, index=False)
                            mail_gonder(row["Email"], "ED-AVM | Hesabınız Onaylandı", f"Merhaba {row['Isim']},\nSisteme giriş yapabilirsiniz.")
                            st.rerun()
                        if c2.button("Reddet", key=f"kred_{idx}"):
                            df_k.at[idx, "Durum"] = "Reddedildi"
                            df_k.to_csv(KULLANICI_FILE, index=False)
                            st.rerun()
            else:
                st.info("Bekleyen kayıt yok.")
                
            st.divider()
            st.subheader("Sistemdeki Aktif Kullanıcılar")
            aktifler = df_k[df_k["Durum"] == "Onaylandı"]
            for idx, row in aktifler.iterrows():
                with st.expander(f"⚙️ {row['Isim']} ({row['Rol']}) | Tel: {row['Telefon']}"):
                    st.write(f"**Email:** {row['Email']} | **Şifre:** {row['Sifre']}")
                    if row["Email"] != st.session_state.kullanici_mail: # Admin kendini silemesin
                        if st.button("Kullanıcıyı Sil", key=f"kdel_{idx}"):
                            df_k = df_k.drop(idx)
                            df_k.to_csv(KULLANICI_FILE, index=False)
                            st.rerun()

        with tab_v:
            if st.button("🔄 Yeni Haftaya Başla (Listeyi Sıfırla)"):
                with open(YAYIN_FILE, "w") as f: f.write("GIZLI")
                pd.DataFrame(columns=["Personel", "İzin Günü", "Haftalık Vardiya", "Neden", "Durum"]).to_csv(TALEPLER_FILE, index=False)
                st.success("Yeni haftaya geçildi.")
                st.rerun()

            st.divider()
            df_t = pd.read_csv(TALEPLER_FILE)
            bekleyen_talepler = df_t[df_t["Durum"] == "Beklemede"]
            
            st.subheader("Gelen Vardiya Talepleri")
            if len(bekleyen_talepler) > 0:
                for idx, row in bekleyen_talepler.iterrows():
                    with st.expander(f"📌 {row['Personel']} | İzin: {row['İzin Günü']} | Vardiya: {row['Haftalık Vardiya']}"):
                        if pd.notna(row['Neden']) and str(row['Neden']).strip() != "":
                            st.write(f"**Not:** {row['Neden']}")
                            
                        # Maili bul
                        user_email_list = df_k[df_k['Isim'] == row['Personel']]['Email'].values
                        user_email = user_email_list[0] if len(user_email_list) > 0 else None

                        c1, c2 = st.columns(2)
                        if c1.button("Onayla", key=f"von_{idx}"):
                            df_t.at[idx, "Durum"] = "Onaylandı"
                            df_t.to_csv(TALEPLER_FILE, index=False)
                            if user_email: mail_gonder(user_email, "Vardiyanız Onaylandı", "Talebini onaylanmıştır.")
                            st.rerun()
                        if c2.button("Reddet", key=f"vred_{idx}"):
                            df_t.at[idx, "Durum"] = "Reddedildi"
                            df_t.to_csv(TALEPLER_FILE, index=False)
                            if user_email: mail_gonder(user_email, "Vardiyanız Reddedildi", "Talebiniz reddedilmiştir. Yönetimle görüşün.")
                            st.rerun()
            else:
                st.info("Bekleyen talep yok.")

            st.divider()
            col_yayin, col_mail = st.columns(2)
            with col_yayin:
                if st.button("🚀 Listeyi Kesinleştir ve Yayınla"):
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
                        st.success("Liste yayınlandı!")
                        st.rerun()
                    else:
                        st.warning("Onaylı plan yok.")
                        
            with col_mail:
                if st.button("📧 Personele Yayın Maili At"):
                    with open(YAYIN_FILE, "r") as f:
                        if f.read().strip() == "YAYINLANDI":
                            onayli_k = df_k[df_k["Durum"] == "Onaylandı"]
                            with st.spinner("Mailler gönderiliyor..."):
                                basarili = sum(1 for _, u in onayli_k.iterrows() if mail_gonder(u["Email"], "Haftalık Liste Yayınlandı", "Liste yayınlandı, sisteme girip bakabilirsiniz."))
                            st.success(f"{basarili} kişiye mail gitti.")
                        else:
                            st.error("Önce listeyi yayınlayın!")
