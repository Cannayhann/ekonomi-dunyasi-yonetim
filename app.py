import streamlit as st
import pandas as pd
import os
import smtplib
import random
import string
from email.mime.text import MIMEText
from datetime import datetime

# 1. SİSTEM AYARLARI
st.set_page_config(page_title="ED-AVM Yönetim", layout="wide")

TALEPLER_FILE = "talepler.csv"
VARDIYA_FILE = "vardiya_duzeni.csv"
YAYIN_FILE = "yayin_durumu.txt"
KULLANICI_FILE = "kullanicilar.csv"
BASVURU_FILE = "basvurular.csv" 
PROFILE_DIR = "profil_fotograflari"

gunler = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
vardiya_secenekleri = ["Sabahçı (09:00 - 18:00)", "Akşamcı (12:00 - 21:00)", "Tam Gün (09:00 - 21:00)"] # YENİ VARDİYA EKLENDİ
os.makedirs(PROFILE_DIR, exist_ok=True)

# --- VERİTABANI KENDİNİ TAMİR ETME ---
kullanici_sutunlari = ["Isim", "Email", "Sifre", "Telefon", "Durum", "Rol"]

if not os.path.exists(KULLANICI_FILE):
    admin_data = {"Isim": "Yönetim", "Email": "admin@edavm.com", "Sifre": "ayhanlar2026", "Telefon": "05000000000", "Durum": "Onaylandı", "Rol": "Yonetici"}
    pd.DataFrame([admin_data], columns=kullanici_sutunlari).to_csv(KULLANICI_FILE, index=False)
else:
    df_k = pd.read_csv(KULLANICI_FILE, dtype=str)
    guncellendi_mi = False
    
    if "Telefon" not in df_k.columns:
        df_k["Telefon"] = ""
        guncellendi_mi = True
    if "Rol" not in df_k.columns:
        df_k["Rol"] = "Personel"
        guncellendi_mi = True
        
    admin_mask = df_k["Email"] == "admin@edavm.com"
    if admin_mask.any():
        if df_k.loc[admin_mask, "Rol"].iloc[0] != "Yonetici":
            df_k.loc[admin_mask, "Rol"] = "Yonetici"
            guncellendi_mi = True
        if df_k.loc[admin_mask, "Durum"].iloc[0] != "Onaylandı":
            df_k.loc[admin_mask, "Durum"] = "Onaylandı"
            guncellendi_mi = True
    else:
        admin_data = {"Isim": "Yönetim", "Email": "admin@edavm.com", "Sifre": "ayhanlar2026", "Telefon": "05000000000", "Durum": "Onaylandı", "Rol": "Yonetici"}
        df_k = pd.concat([df_k, pd.DataFrame([admin_data])], ignore_index=True)
        guncellendi_mi = True
        
    if guncellendi_mi:
        df_k.to_csv(KULLANICI_FILE, index=False)

# Diğer Dosyalar
if not os.path.exists(TALEPLER_FILE):
    pd.DataFrame(columns=["Personel", "İzin Günü", "Haftalık Vardiya", "Neden", "Durum"]).to_csv(TALEPLER_FILE, index=False)
if not os.path.exists(VARDIYA_FILE):
    pd.DataFrame(columns=["Personel"] + gunler).to_csv(VARDIYA_FILE, index=False)
if not os.path.exists(YAYIN_FILE):
    with open(YAYIN_FILE, "w") as f: f.write("GIZLI")
if not os.path.exists(BASVURU_FILE):
    pd.DataFrame(columns=["Ad Soyad", "Telefon", "E-posta", "Pozisyon", "Tecrübe", "Durum", "Tarih"]).to_csv(BASVURU_FILE, index=False)

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

# --- TABLO RENKLENDİRME FONKSİYONU ---
def style_status(v):
    val_str = str(v)
    if "🔴" in val_str: c = "#ff4b4b" # İzinli
    elif "A " in val_str: c = "#1c83e1" # Akşamcı
    elif "S " in val_str: c = "#28a745" # Sabahçı
    elif "T " in val_str: c = "#6f42c1" # Tam Gün (Mor)
    else: c = "#4CAF50" # Tam Güç
    return f'background-color: {c}; color: white'

# --- SESSION STATE ---
if "giris_yapildi" not in st.session_state:
    st.session_state.update({"giris_yapildi": False, "kullanici_tipi": "", "kullanici_adi": "", "kullanici_mail": "", "reset_kod": "", "reset_mail": ""})

# ==========================================
# GİRİŞ / KAYIT / ŞİFRE SIFIRLAMA / İŞ BAŞVURUSU
# ==========================================
if not st.session_state.giris_yapildi:
    col_logo, col_baslik = st.columns([1, 8])
    with col_baslik:
        st.title("🏢 Ekonomi Dünyası AVM Portalı")
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 4, 1])
    with col2:
        sekme = st.radio("İşlem Seçiniz", ["🔑 Giriş Yap", "📝 Kayıt Ol", "❓ Şifremi Unuttum", "👔 İş Başvurusu"], horizontal=True)

        if sekme == "🔑 Giriş Yap":
            email_in = st.text_input("E-posta").strip().lower()
            sifre_in = st.text_input("Şifre", type="password")
            if st.button("Sisteme Gir"):
                df_k = pd.read_csv(KULLANICI_FILE, dtype=str)
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
                st.info("Bu alan halihazırda işe alınmış personeller içindir.")
                isim = st.text_input("Adınız Soyadınız")
                tel = st.text_input("Telefon Numaranız")
                mail = st.text_input("E-posta Adresiniz").strip().lower()
                sifre = st.text_input("Şifre Belirleyiniz", type="password")
                if st.form_submit_button("Kayıt Talebi Gönder"):
                    df_k = pd.read_csv(KULLANICI_FILE, dtype=str)
                    if mail in df_k["Email"].values:
                        st.error("Bu e-posta zaten sistemde kayıtlı.")
                    elif isim == "" or mail == "" or sifre == "":
                        st.warning("Lütfen zorunlu alanları doldurun.")
                    else:
                        yeni = {"Isim": str(isim.strip().title()), "Email": str(mail), "Sifre": str(sifre), "Telefon": str(tel), "Durum": "Beklemede", "Rol": "Personel"}
                        pd.concat([df_k, pd.DataFrame([yeni])]).to_csv(KULLANICI_FILE, index=False)
                        mail_gonder(mail, "ED-AVM | Kayıt Talebiniz Alındı", f"Merhaba {isim},\n\nKayıt talebiniz alındı. Yönetim onayından sonra giriş yapabilirsiniz.")
                        st.success("Kayıt başarılı! Bilgilendirme maili gönderildi.")

        elif sekme == "❓ Şifremi Unuttum":
            if st.session_state.reset_kod == "":
                mail_res = st.text_input("Sisteme Kayıtlı E-posta Adresiniz:")
                if st.button("Doğrulama Kodu Gönder"):
                    df_k = pd.read_csv(KULLANICI_FILE, dtype=str)
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
                        df_k = pd.read_csv(KULLANICI_FILE, dtype=str)
                        df_k.loc[df_k["Email"] == st.session_state.reset_mail, "Sifre"] = str(yeni_sifre)
                        df_k.to_csv(KULLANICI_FILE, index=False)
                        st.success("Şifreniz başarıyla güncellendi! Yeniden giriş yapabilirsiniz.")
                        st.session_state.reset_kod = ""
                    else:
                        st.error("Girdiğiniz kod hatalı.")

        elif sekme == "👔 İş Başvurusu":
            st.info("Ekonomi Dünyası AVM ekibine katılmak için aşağıdaki formu doldurabilirsiniz. Özgeçmişiniz yönetimimiz tarafından incelenecektir.")
            with st.form("is_basvurusu"):
                b_isim = st.text_input("Adınız Soyadınız")
                b_tel = st.text_input("Telefon Numaranız")
                b_mail = st.text_input("E-posta Adresiniz")
                b_pozisyon = st.selectbox("Başvurulan Pozisyon", ["Satış Danışmanı", "Kasa Görevlisi", "Depo / Lojistik", "E-Ticaret Sorumlusu"])
                b_tecrube = st.text_area("İş Tecrübeleriniz ve Eklemek İstedikleriniz", placeholder="Daha önceki iş deneyimlerinizi kısaca yazınız...")
                
                if st.form_submit_button("Başvurumu İlet"):
                    if b_isim == "" or b_tel == "":
                        st.warning("Lütfen isim ve telefon numarası alanlarını doldurunuz.")
                    else:
                        tarih = datetime.now().strftime("%Y-%m-%d %H:%M")
                        yeni_basvuru = {"Ad Soyad": str(b_isim.strip().title()), "Telefon": str(b_tel), "E-posta": str(b_mail), "Pozisyon": str(b_pozisyon), "Tecrübe": str(b_tecrube), "Durum": "İnceleniyor", "Tarih": tarih}
                        df_b = pd.read_csv(BASVURU_FILE, dtype=str)
                        pd.concat([df_b, pd.DataFrame([yeni_basvuru])]).to_csv(BASVURU_FILE, index=False)
                        st.success("Başvurunuz başarıyla alındı! İnsan Kaynakları departmanımız sizinle iletişime geçecektir.")

# ==========================================
# ANA SİSTEM (GİRİŞ YAPILDIKTAN SONRA)
# ==========================================
else:
    pp_path = os.path.join(PROFILE_DIR, f"{st.session_state.kullanici_mail}.png")
    
    with st.sidebar:
        if os.path.exists(pp_path):
            st.image(pp_path, width=150)
        else:
            st.write("👤 *(Fotoğraf Yok)*")
            
        st.title(f"{st.session_state.kullanici_adi}")
        st.caption(f"{'👑 Yönetici' if st.session_state.kullanici_tipi == 'Yonetici' else 'Çalışan'}")
        st.divider()
        
        if st.session_state.kullanici_tipi == "Yonetici":
            menu_secenekleri = ["Yönetici Paneli", "Kesinleşen Liste", "Profilim"]
        else:
            menu_secenekleri = ["Vardiya İşlemleri", "Profilim"]
            
        sayfa = st.radio("Menü", menu_secenekleri)
        st.divider()
        if st.button("🚪 Çıkış Yap", use_container_width=True):
            st.session_state.giris_yapildi = False
            st.rerun()

    with open(YAYIN_FILE, "r") as f: yayin_durumu = f.read().strip()

    # --- 1. SAYFA: PROFİLİM ---
    if sayfa == "Profilim":
        st.header("👤 Profilimi Düzenle")
        df_k = pd.read_csv(KULLANICI_FILE, dtype=str)
        u_data = df_k[df_k["Email"] == st.session_state.kullanici_mail].iloc[0]
        col_foto, col_bilgi = st.columns([1, 2])
        
        with col_foto:
            st.subheader("Fotoğraf")
            if os.path.exists(pp_path):
                st.image(pp_path, width=200)
            yuklenen_foto = st.file_uploader("Yeni Fotoğraf Yükle (PNG/JPG)", type=["png", "jpg", "jpeg"])
            if yuklenen_foto is not None:
                with open(pp_path, "wb") as f: f.write(yuklenen_foto.getbuffer())
                st.success("Fotoğraf başarıyla yüklendi!")
                st.rerun()

        with col_bilgi:
            st.subheader("Kişisel Bilgiler")
            yeni_isim = st.text_input("Ad Soyad:", value=str(u_data["Isim"]))
            yeni_tel = st.text_input("Telefon Numarası:", value=str(u_data["Telefon"]) if pd.notna(u_data["Telefon"]) else "")
            yeni_sifre = st.text_input("Şifre (Değiştirmek istemiyorsanız aynı bırakın):", value=str(u_data["Sifre"]), type="password")
            
            if st.button("Bilgilerimi Kaydet"):
                mask = df_k["Email"] == st.session_state.kullanici_mail
                df_k.loc[mask, "Isim"] = str(yeni_isim)
                df_k.loc[mask, "Telefon"] = str(yeni_tel)
                df_k.loc[mask, "Sifre"] = str(yeni_sifre)
                df_k.to_csv(KULLANICI_FILE, index=False)
                st.session_state.kullanici_adi = str(yeni_isim)
                st.success("Profil bilgileriniz başarıyla güncellendi!")
                st.rerun()

    # --- 2. SAYFA: VARDİYA İŞLEMLERİ (SADECE PERSONEL İÇİN) ---
    elif sayfa == "Vardiya İşlemleri":
        st.header("📅 Haftalık Vardiya Planlaması")
        tab1, tab2 = st.tabs(["✍️ Planımı Gönder", "📊 Kesinleşen Liste"])
        
        with tab1:
            st.info("Haftalık rotasyon kuralına göre seçim yapınız.")
            with st.form("personel_formu", clear_on_submit=True):
                izin_gunu = st.selectbox("Bu hafta hangi gün İZİNLİ olacaksınız?", gunler)
                haftalik_shift = st.radio("Hangi vardiyada olacaksınız?", vardiya_secenekleri)
                neden = st.text_area("Yönetime Notunuz (İsteğe Bağlı):")
                
                if st.form_submit_button("Planımı Gönder"):
                    yeni = {"Personel": st.session_state.kullanici_adi, "İzin Günü": izin_gunu, "Haftalık Vardiya": haftalik_shift, "Neden": neden, "Durum": "Beklemede"}
                    df_t = pd.read_csv(TALEPLER_FILE, dtype=str)
                    pd.concat([df_t, pd.DataFrame([yeni])]).to_csv(TALEPLER_FILE, index=False)
                    st.success("Talebiniz yönetime iletildi.")
                    
        with tab2:
            if yayin_durumu == "YAYINLANDI":
                if os.path.exists(VARDIYA_FILE):
                    df_v = pd.read_csv(VARDIYA_FILE, dtype=str)
                    st.table(df_v.style.map(style_status, subset=gunler))
            else:
                st.warning("⚠️ Bu haftanın listesi henüz yönetim tarafından yayınlanmamıştır.")

    # --- 3. SAYFA: KESİNLEŞEN LİSTE (SADECE YÖNETİCİ İÇİN) ---
    elif sayfa == "Kesinleşen Liste":
        st.header("📊 Kesinleşen Vardiya Listesi")
        if yayin_durumu == "YAYINLANDI":
            if os.path.exists(VARDIYA_FILE):
                df_v = pd.read_csv(VARDIYA_FILE, dtype=str)
                st.table(df_v.style.map(style_status, subset=gunler))
        else:
            st.warning("⚠️ Bu haftanın listesi henüz yayınlanmadığı için görüntülenemiyor.")

    # --- 4. SAYFA: YÖNETİCİ PANELİ ---
    elif sayfa == "Yönetici Paneli" and st.session_state.kullanici_tipi == "Yonetici":
        st.header("👑 Yönetim Kontrol Merkezi")
        
        tab_k, tab_t, tab_m, tab_y, tab_b = st.tabs(["👥 Kullanıcılar", "📥 Gelen Talepler", "🛠️ Manuel Planlama", "🚀 Yayınlama", "👔 İK Başvuruları"])
        
        with tab_k:
            df_k = pd.read_csv(KULLANICI_FILE, dtype=str)
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
            st.subheader("Aktif Kullanıcılar")
            aktifler = df_k[df_k["Durum"] == "Onaylandı"]
            for idx, row in aktifler.iterrows():
                with st.expander(f"⚙️ {row['Isim']} ({row['Rol']}) | Tel: {row['Telefon']}"):
                    st.write(f"**Email:** {row['Email']} | **Şifre:** {row['Sifre']}")
                    if row["Email"] != st.session_state.kullanici_mail: 
                        if st.button("Kullanıcıyı Sil", key=f"kdel_{idx}"):
                            df_k = df_k.drop(idx)
                            df_k.to_csv(KULLANICI_FILE, index=False)
                            st.rerun()

        with tab_t:
            df_t = pd.read_csv(TALEPLER_FILE, dtype=str)
            bekleyen_talepler = df_t[df_t["Durum"] == "Beklemede"]
            st.subheader("Personelden Gelen Vardiya ve İzin Talepleri")
            
            if len(bekleyen_talepler) > 0:
                for idx, row in bekleyen_talepler.iterrows():
                    with st.expander(f"📌 {row['Personel']} | İzin: {row['İzin Günü']} | Vardiya: {row['Haftalık Vardiya']}"):
                        if pd.notna(row['Neden']) and str(row['Neden']).strip() != "":
                            st.write(f"**Personelin Notu:** {row['Neden']}")
                        
                        user_email_list = df_k[df_k['Isim'] == row['Personel']]['Email'].values
                        user_email = user_email_list[0] if len(user_email_list) > 0 else None

                        with st.form(key=f"duzenle_form_{idx}"):
                            st.write("🔧 **Yönetici Müdahalesi**")
                            col_iz, col_var = st.columns(2)
                            
                            with col_iz:
                                try: def_iz_idx = gunler.index(str(row['İzin Günü']))
                                except: def_iz_idx = 0
                                yeni_izin = st.selectbox("İzin Gününü Ata:", gunler, index=def_iz_idx)
                                
                            with col_var:
                                if "Akşamcı" in str(row['Haftalık Vardiya']): def_var_idx = 1
                                elif "Tam" in str(row['Haftalık Vardiya']): def_var_idx = 2
                                else: def_var_idx = 0
                                
                                yeni_vardiya = st.radio("Vardiyayı Ata:", vardiya_secenekleri, index=def_var_idx)
                                
                            c1, c2 = st.columns(2)
                            btn_onay = c1.form_submit_button("✅ Değişikliklerle Onayla")
                            btn_red = c2.form_submit_button("❌ Reddet")

                            if btn_onay:
                                df_t_guncel = pd.read_csv(TALEPLER_FILE, dtype=str)
                                df_t_guncel.at[idx, "İzin Günü"] = str(yeni_izin)
                                df_t_guncel.at[idx, "Haftalık Vardiya"] = str(yeni_vardiya)
                                df_t_guncel.at[idx, "Durum"] = "Onaylandı"
                                df_t_guncel.to_csv(TALEPLER_FILE, index=False)
                                
                                if user_email: 
                                    if yeni_izin == row['İzin Günü'] and yeni_vardiya == row['Haftalık Vardiya']:
                                        mail_gonder(user_email, "ED-AVM | Vardiyanız Onaylandı", f"Merhaba {row['Personel']},\nTalebiniz aynen onaylanmıştır.")
                                    else:
                                        mail_gonder(user_email, "ED-AVM | Vardiyanız Düzenlenerek Onaylandı", f"Merhaba {row['Personel']},\nYönetim operasyonel nedenlerle talebinizi güncelledi. Yeni durumunuz:\nİzin: {yeni_izin}\nVardiya: {yeni_vardiya}")
                                st.rerun()

                            if btn_red:
                                df_t_guncel = pd.read_csv(TALEPLER_FILE, dtype=str)
                                df_t_guncel.at[idx, "Durum"] = "Reddedildi"
                                df_t_guncel.to_csv(TALEPLER_FILE, index=False)
                                if user_email: mail_gonder(user_email, "ED-AVM | Vardiyanız Reddedildi", "Talebiniz reddedilmiştir. Yönetimle görüşünüz.")
                                st.rerun()
            else:
                st.info("Bekleyen talep yok.")

        with tab_m:
            st.subheader("🛠️ Personele Manuel Vardiya Atama")
            st.info("Form doldurmayı unutan veya yeni gelen personele doğrudan vardiya atayabilirsiniz.")
            
            aktif_personel_listesi = df_k[df_k["Durum"] == "Onaylandı"]["Isim"].tolist()
            
            if len(aktif_personel_listesi) > 0:
                with st.form("manuel_atama"):
                    secilen_kisi = st.selectbox("Personel Seçiniz:", aktif_personel_listesi)
                    secilen_izin = st.selectbox("İzin Gününü Belirleyin:", gunler)
                    secilen_vardiya = st.radio("Vardiyasını Belirleyin:", vardiya_secenekleri)
                    
                    if st.form_submit_button("Sisteme İşle (Otomatik Onaylı)"):
                        df_t = pd.read_csv(TALEPLER_FILE, dtype=str)
                        df_t = df_t[df_t["Personel"] != secilen_kisi] 
                        yeni_manuel = {"Personel": secilen_kisi, "İzin Günü": secilen_izin, "Haftalık Vardiya": secilen_vardiya, "Neden": "Yönetici tarafından manuel atandı.", "Durum": "Onaylandı"}
                        df_t = pd.concat([df_t, pd.DataFrame([yeni_manuel])], ignore_index=True)
                        df_t.to_csv(TALEPLER_FILE, index=False)
                        st.success(f"{secilen_kisi} için vardiya başarıyla oluşturuldu ve onaylandı!")
                        st.rerun()
            else:
                st.warning("Sistemde aktif personel bulunmuyor.")

        with tab_y:
            st.subheader("Haftalık Operasyon Kontrolü")
            if st.button("🔄 Yeni Haftaya Başla (Mevcut Listeyi Gizle)"):
                with open(YAYIN_FILE, "w") as f: f.write("GIZLI")
                pd.DataFrame(columns=["Personel", "İzin Günü", "Haftalık Vardiya", "Neden", "Durum"]).to_csv(TALEPLER_FILE, index=False)
                st.success("Sistem sıfırlandı. Yeni haftanın talepleri bekleniyor.")
                st.rerun()

            st.divider()
            col_yayin, col_mail = st.columns(2)
            with col_yayin:
                if st.button("🚀 Listeyi Kesinleştir ve Yayınla"):
                    df_t = pd.read_csv(TALEPLER_FILE, dtype=str)
                    onayli = df_t[df_t["Durum"] == "Onaylandı"]
                    if len(onayli) > 0:
                        unique_staff = onayli["Personel"].unique()
                        final_df = pd.DataFrame(index=unique_staff, columns=gunler)
                        for _, r in onayli.iterrows():
                            p = str(r["Personel"])
                            iz = str(r["İzin Günü"])
                            
                            vardiya_str = str(r["Haftalık Vardiya"])
                            if "Akşamcı" in vardiya_str: shift = "A (12-21)"
                            elif "Tam" in vardiya_str: shift = "T (09-21)"
                            else: shift = "S (09-18)"
                            
                            for g in gunler:
                                if g == iz: final_df.at[p, g] = "🔴 İZİNLİ"
                                elif g == "Pazar": final_df.at[p, g] = "🟢 TAM GÜÇ"
                                else: final_df.at[p, g] = shift
                        final_df.reset_index(inplace=True)
                        final_df.rename(columns={'index': 'Personel'}, inplace=True)
                        final_df.to_csv(VARDIYA_FILE, index=False)
                        with open(YAYIN_FILE, "w") as f: f.write("YAYINLANDI")
                        st.success("Liste başarıyla yayınlandı!")
                        st.rerun()
                    else:
                        st.warning("Henüz onaylanmış plan yok.")
                        
            with col_mail:
                if st.button("📧 Personele Yayın Maili At"):
                    with open(YAYIN_FILE, "r") as f:
                        if f.read().strip() == "YAYINLANDI":
                            onayli_k = df_k[df_k["Durum"] == "Onaylandı"]
                            with st.spinner("Mailler gönderiliyor..."):
                                basarili = sum(1 for _, u in onayli_k.iterrows() if mail_gonder(u["Email"], "Haftalık Liste Yayınlandı", "Liste yayınlandı, sisteme girip bakabilirsiniz."))
                            st.success(f"{basarili} kişiye mail gitti.")
                        else:
                            st.error("Önce listeyi yayınlamalısınız!")

        with tab_b:
            st.subheader("Gelen İş Başvuruları")
            df_b = pd.read_csv(BASVURU_FILE, dtype=str)
            bekleyen_basvurular = df_b[df_b["Durum"] == "İnceleniyor"]
            
            if len(bekleyen_basvurular) > 0:
                for idx, row in bekleyen_basvurular.iterrows():
                    with st.expander(f"👤 {row['Ad Soyad']} - {row['Pozisyon']} | Tarih: {row['Tarih']}"):
                        st.write(f"**Telefon:** {row['Telefon']} | **E-posta:** {row['E-posta']}")
                        st.write(f"**Tecrübeleri:**\n{row['Tecrübe']}")
                        
                        c1, c2, c3 = st.columns(3)
                        if c1.button("✅ Olumlu (Arşive Ekle)", key=f"bok_{idx}"):
                            df_b.at[idx, "Durum"] = "Kabul Edildi"
                            df_b.to_csv(BASVURU_FILE, index=False)
                            st.rerun()
                        if c2.button("❌ Reddet", key=f"bred_{idx}"):
                            df_b.at[idx, "Durum"] = "Reddedildi"
                            df_b.to_csv(BASVURU_FILE, index=False)
                            st.rerun()
                        if c3.button("🗑️ Sil", key=f"bsil_{idx}"):
                            df_b = df_b.drop(idx)
                            df_b.to_csv(BASVURU_FILE, index=False)
                            st.rerun()
            else:
                st.info("İncelenmeyi bekleyen yeni başvuru bulunmuyor.")
                
            st.divider()
            st.write("**Arşiv (Geçmiş Başvurular)**")
            arsiv_b = df_b[df_b["Durum"] != "İnceleniyor"]
            if len(arsiv_b) > 0:
                st.dataframe(arsiv_b, use_container_width=True)
            else:
                st.write("Henüz arşive alınmış başvuru yok.")
