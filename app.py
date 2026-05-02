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
vardiya_secenekleri = ["Sabahçı (09:00 - 18:00)", "Akşamcı (12:00 - 21:00)", "Tam Gün (09:00 - 21:00)"]
os.makedirs(PROFILE_DIR, exist_ok=True)

# --- VERİTABANI KENDİNİ TAMİR ETME ---
kullanici_sutunlari = ["Isim", "Email", "Sifre", "Telefon", "Durum", "Rol", "CalismaTipi"]

if not os.path.exists(KULLANICI_FILE):
    admin_data = {"Isim": "Yönetim", "Email": "admin@edavm.com", "Sifre": "ayhanlar2026", "Telefon": "05000000000", "Durum": "Onaylandı", "Rol": "Yonetici", "CalismaTipi": "Tam Zamanlı"}
    pd.DataFrame([admin_data], columns=kullanici_sutunlari).to_csv(KULLANICI_FILE, index=False)
else:
    df_k = pd.read_csv(KULLANICI_FILE, dtype=str)
    guncellendi_mi = False
    
    if "Telefon" not in df_k.columns: df_k["Telefon"] = ""; guncellendi_mi = True
    if "Rol" not in df_k.columns: df_k["Rol"] = "Personel"; guncellendi_mi = True
    if "CalismaTipi" not in df_k.columns: df_k["CalismaTipi"] = "Tam Zamanlı"; guncellendi_mi = True
        
    admin_mask = df_k["Email"] == "admin@edavm.com"
    if admin_mask.any():
        if df_k.loc[admin_mask, "Rol"].iloc[0] != "Yonetici": df_k.loc[admin_mask, "Rol"] = "Yonetici"; guncellendi_mi = True
        if df_k.loc[admin_mask, "Durum"].iloc[0] != "Onaylandı": df_k.loc[admin_mask, "Durum"] = "Onaylandı"; guncellendi_mi = True
    else:
        admin_data = {"Isim": "Yönetim", "Email": "admin@edavm.com", "Sifre": "ayhanlar2026", "Telefon": "05000000000", "Durum": "Onaylandı", "Rol": "Yonetici", "CalismaTipi": "Tam Zamanlı"}
        df_k = pd.concat([df_k, pd.DataFrame([admin_data])], ignore_index=True)
        guncellendi_mi = True
        
    if guncellendi_mi: df_k.to_csv(KULLANICI_FILE, index=False)

basvuru_sutunlari = ["Ad Soyad", "Telefon", "E-posta", "Pozisyon", "Çalışma Tipi", "Tecrübe", "Durum", "Tarih"]
if not os.path.exists(BASVURU_FILE): 
    pd.DataFrame(columns=basvuru_sutunlari).to_csv(BASVURU_FILE, index=False)
else:
    df_b_temp = pd.read_csv(BASVURU_FILE, dtype=str)
    if "Çalışma Tipi" not in df_b_temp.columns:
        df_b_temp["Çalışma Tipi"] = "Tam Zamanlı"
        df_b_temp.to_csv(BASVURU_FILE, index=False)

# --- OTOMATİK ÇÖP ÖĞÜTÜCÜ VE ÇİFT KAYIT SİLİCİ ---
if not os.path.exists(TALEPLER_FILE): 
    pd.DataFrame(columns=["Personel", "İzin Günü", "Haftalık Vardiya", "Neden", "Durum"]).to_csv(TALEPLER_FILE, index=False)
else:
    df_t_check = pd.read_csv(TALEPLER_FILE, dtype=str)
    ilk_uzunluk = len(df_t_check)
    df_t_check = df_t_check.dropna(subset=["İzin Günü", "Haftalık Vardiya", "Personel"])
    df_t_check = df_t_check[~df_t_check["İzin Günü"].astype(str).str.contains("nan", case=False, na=False)]
    df_t_check = df_t_check[~df_t_check["Haftalık Vardiya"].astype(str).str.contains("nan", case=False, na=False)]
    
    # YENİ KURAL: Aynı kişinin birden fazla talebi varsa sadece en sonuncuyu tut! (Eski denemeleri siler)
    df_t_check = df_t_check.drop_duplicates(subset=["Personel"], keep="last")
    
    if len(df_t_check) < ilk_uzunluk:
        df_t_check.to_csv(TALEPLER_FILE, index=False)

if not os.path.exists(VARDIYA_FILE): pd.DataFrame(columns=["Personel"] + gunler).to_csv(VARDIYA_FILE, index=False)
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

def kod_uret(): return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def style_status(v):
    val_str = str(v)
    if "🔴" in val_str: c = "#ff4b4b"
    elif "A " in val_str: c = "#1c83e1"
    elif "S " in val_str: c = "#28a745"
    elif "T " in val_str: c = "#6f42c1"
    elif "🟢" in val_str: c = "#4CAF50"
    elif "⏳" in val_str: c = "#6c757d"
    else: c = ""
    return f'background-color: {c}; color: white' if c else ''

# --- CANLI TASLAK ---
def get_taslak_df():
    df_k = pd.read_csv(KULLANICI_FILE, dtype=str)
    aktifler = df_k[(df_k["Durum"] == "Onaylandı") & (df_k["Rol"] != "Yonetici")]["Isim"].tolist()
    if not aktifler: return pd.DataFrame()
    
    taslak = pd.DataFrame(index=aktifler, columns=gunler)
    taslak.fillna("⏳ Belirsiz", inplace=True)
    
    df_t = pd.read_csv(TALEPLER_FILE, dtype=str)
    onayli = df_t[df_t["Durum"] == "Onaylandı"]
    
    for _, r in onayli.iterrows():
        p = str(r["Personel"])
        if p not in taslak.index: continue
        iz_str = str(r["İzin Günü"])
        v_str = str(r["Haftalık Vardiya"])
        
        if "Akşamcı" in v_str: shift = "A (12-21)"
        elif "Tam" in v_str: shift = "T (09-21)"
        else: shift = "S (09-18)"
        
        for g in gunler:
            if g in iz_str: taslak.at[p, g] = "🔴 İZİNLİ"
            elif g == "Pazar": taslak.at[p, g] = "🟢 TAM GÜÇ"
            else: taslak.at[p, g] = shift
            
    taslak.reset_index(inplace=True)
    taslak.rename(columns={'index': 'Personel'}, inplace=True)
    return taslak

# --- SESSION STATE ---
if "giris_yapildi" not in st.session_state:
    st.session_state.update({"giris_yapildi": False, "kullanici_tipi": "", "kullanici_adi": "", "kullanici_mail": "", "reset_kod": "", "reset_mail": ""})

# ==========================================
# GİRİŞ / KAYIT / ŞİFRE SIFIRLAMA / İŞ BAŞVURUSU
# ==========================================
if not st.session_state.giris_yapildi:
    col_logo, col_baslik = st.columns([1, 8])
    with col_baslik: st.title("🏢 Ekonomi Dünyası AVM Portalı")
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
                    else: st.warning("⏳ Hesabınız onay bekliyor.")
                else: st.error("❌ E-posta veya şifre hatalı.")

        elif sekme == "📝 Kayıt Ol":
            with st.form("kayit"):
                st.info("Bu alan halihazırda işe alınmış personeller içindir.")
                isim = st.text_input("Adınız Soyadınız")
                tel = st.text_input("Telefon Numaranız")
                mail = st.text_input("E-posta Adresiniz").strip().lower()
                calisma_tipi = st.selectbox("Çalışma Şekliniz", ["Tam Zamanlı", "Part-Time"])
                sifre = st.text_input("Şifre Belirleyiniz", type="password")
                
                if st.form_submit_button("Kayıt Talebi Gönder"):
                    df_k = pd.read_csv(KULLANICI_FILE, dtype=str)
                    if mail in df_k["Email"].values: st.error("Bu e-posta zaten sistemde kayıtlı.")
                    elif isim == "" or mail == "" or sifre == "": st.warning("Lütfen zorunlu alanları doldurun.")
                    else:
                        yeni = {"Isim": str(isim.strip().title()), "Email": str(mail), "Sifre": str(sifre), "Telefon": str(tel), "Durum": "Beklemede", "Rol": "Personel", "CalismaTipi": calisma_tipi}
                        pd.concat([df_k, pd.DataFrame([yeni])]).to_csv(KULLANICI_FILE, index=False)
                        st.success("Kayıt başarılı! Yönetim onayından sonra girebilirsiniz.")

        elif sekme == "❓ Şifremi Unuttum":
            if st.session_state.reset_kod == "":
                mail_res = st.text_input("Sisteme Kayıtlı E-posta Adresiniz:")
                if st.button("Doğrulama Kodu Gönder"):
                    df_k = pd.read_csv(KULLANICI_FILE, dtype=str)
                    if mail_res.strip().lower() in df_k["Email"].values:
                        kod = kod_uret()
                        st.session_state.reset_kod = kod
                        st.session_state.reset_mail = mail_res.strip().lower()
                        mail_gonder(mail_res, "ED-AVM | Şifre Sıfırlama", f"Sıfırlama kodunuz: {kod}")
                        st.info("Kod gönderildi.")
                    else: st.error("Mail bulunamadı.")
            else:
                kod_in = st.text_input("Mailinize gelen kodu girin:")
                yeni_sifre = st.text_input("Yeni Şifreniz:", type="password")
                if st.button("Şifreyi Güncelle"):
                    if kod_in == st.session_state.reset_kod:
                        df_k = pd.read_csv(KULLANICI_FILE, dtype=str)
                        df_k.loc[df_k["Email"] == st.session_state.reset_mail, "Sifre"] = str(yeni_sifre)
                        df_k.to_csv(KULLANICI_FILE, index=False)
                        st.success("Şifreniz güncellendi!"); st.session_state.reset_kod = ""
                    else: st.error("Kod hatalı.")

        elif sekme == "👔 İş Başvurusu":
            st.info("Ekonomi Dünyası AVM ekibine katılmak için formu doldurun.")
            with st.form("is_basvurusu"):
                b_isim = st.text_input("Adınız Soyadınız")
                b_tel = st.text_input("Telefon Numaranız")
                b_mail = st.text_input("E-posta Adresiniz")
                b_pozisyon = st.selectbox("Başvurulan Pozisyon", ["Satış Danışmanı", "Kasa Görevlisi", "Depo / Lojistik", "E-Ticaret Sorumlusu"])
                b_calisma_tipi = st.selectbox("Tercih Ettiğiniz Çalışma Şekli", ["Tam Zamanlı", "Part-Time"])
                b_tecrube = st.text_area("İş Tecrübeleriniz")
                
                if st.form_submit_button("Başvurumu İlet"):
                    if b_isim == "" or b_tel == "": st.warning("İsim ve telefon zorunludur.")
                    else:
                        yeni_basvuru = {"Ad Soyad": str(b_isim.strip().title()), "Telefon": str(b_tel), "E-posta": str(b_mail), "Pozisyon": str(b_pozisyon), "Çalışma Tipi": str(b_calisma_tipi), "Tecrübe": str(b_tecrube), "Durum": "İnceleniyor", "Tarih": datetime.now().strftime("%Y-%m-%d %H:%M")}
                        df_b = pd.read_csv(BASVURU_FILE, dtype=str)
                        pd.concat([df_b, pd.DataFrame([yeni_basvuru])]).to_csv(BASVURU_FILE, index=False)
                        st.success("Başvurunuz alındı!")

# ==========================================
# ANA SİSTEM (GİRİŞ YAPILDIKTAN SONRA)
# ==========================================
else:
    pp_path = os.path.join(PROFILE_DIR, f"{st.session_state.kullanici_mail}.png")
    
    with st.sidebar:
        if os.path.exists(pp_path): st.image(pp_path, width=150)
        else: st.write("👤 *(Fotoğraf Yok)*")
            
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

    # --- PROFİLİM ---
    if sayfa == "Profilim":
        st.header("👤 Profilimi Düzenle")
        df_k = pd.read_csv(KULLANICI_FILE, dtype=str)
        u_data = df_k[df_k["Email"] == st.session_state.kullanici_mail].iloc[0]
        col_foto, col_bilgi = st.columns([1, 2])
        
        with col_foto:
            st.subheader("Fotoğraf")
            if os.path.exists(pp_path): st.image(pp_path, width=200)
            yuklenen_foto = st.file_uploader("Yeni Fotoğraf Yükle (PNG/JPG)", type=["png", "jpg", "jpeg"])
            if yuklenen_foto is not None:
                with open(pp_path, "wb") as f: f.write(yuklenen_foto.getbuffer())
                st.success("Yüklendi!"); st.rerun()

        with col_bilgi:
            yeni_isim = st.text_input("Ad Soyad:", value=str(u_data["Isim"]))
            yeni_tel = st.text_input("Telefon:", value=str(u_data["Telefon"]) if pd.notna(u_data["Telefon"]) else "")
            
            idx_tip = 0 if u_data.get("CalismaTipi", "Tam Zamanlı") == "Tam Zamanlı" else 1
            yeni_tip = st.selectbox("Çalışma Tipi:", ["Tam Zamanlı", "Part-Time"], index=idx_tip)
            
            yeni_sifre = st.text_input("Şifre:", value=str(u_data["Sifre"]), type="password")
            
            if st.button("Kaydet"):
                mask = df_k["Email"] == st.session_state.kullanici_mail
                df_k.loc[mask, "Isim"] = str(yeni_isim)
                df_k.loc[mask, "Telefon"] = str(yeni_tel)
                df_k.loc[mask, "CalismaTipi"] = str(yeni_tip)
                df_k.loc[mask, "Sifre"] = str(yeni_sifre)
                df_k.to_csv(KULLANICI_FILE, index=False)
                st.session_state.kullanici_adi = str(yeni_isim)
                st.success("Güncellendi!"); st.rerun()

    # --- VARDİYA İŞLEMLERİ (PERSONEL) ---
    elif sayfa == "Vardiya İşlemleri":
        st.header("📅 Haftalık Vardiya Planlaması")
        tab1, tab2, tab3 = st.tabs(["✍️ Planımı Gönder", "👀 Onaylananlar (Canlı Taslak)", "📊 Kesinleşen Liste"])
        
        with tab1:
            with st.form("personel_formu", clear_on_submit=True):
                izin_gunleri = st.multiselect("İzinli / Çalışmadığınız Günler (Part-time iseniz tüm boş günlerinizi seçin):", gunler)
                haftalik_shift = st.radio("Vardiyanız:", vardiya_secenekleri)
                neden = st.text_area("Notunuz (İsteğe Bağlı):")
                if st.form_submit_button("Planımı Gönder"):
                    izin_str = ", ".join(izin_gunleri) if len(izin_gunleri) > 0 else "İzin Yok"
                    yeni = {"Personel": st.session_state.kullanici_adi, "İzin Günü": izin_str, "Haftalık Vardiya": haftalik_shift, "Neden": neden, "Durum": "Beklemede"}
                    df_t = pd.read_csv(TALEPLER_FILE, dtype=str)
                    pd.concat([df_t, pd.DataFrame([yeni])]).to_csv(TALEPLER_FILE, index=False)
                    st.success("Talebiniz yönetime iletildi.")
                    
        with tab2:
            st.info("💡 Yönetimin şu ana kadar onayladığı güncel durumu gösterir.")
            taslak_df = get_taslak_df()
            if not taslak_df.empty: st.table(taslak_df.style.map(style_status, subset=gunler))
            else: st.warning("Henüz onaylanmış bir plan yok.")

        with tab3:
            if yayin_durumu == "YAYINLANDI":
                if os.path.exists(VARDIYA_FILE):
                    df_v = pd.read_csv(VARDIYA_FILE, dtype=str)
                    st.table(df_v.style.map(style_status, subset=gunler))
            else: st.warning("⚠️ Kesinleşmiş liste henüz yayınlanmamıştır.")

    # --- KESİNLEŞEN LİSTE (YÖNETİCİ) ---
    elif sayfa == "Kesinleşen Liste":
        st.header("📊 Kesinleşen Vardiya Listesi")
        if yayin_durumu == "YAYINLANDI":
            if os.path.exists(VARDIYA_FILE):
                df_v = pd.read_csv(VARDIYA_FILE, dtype=str)
                st.table(df_v.style.map(style_status, subset=gunler))
        else: st.warning("⚠️ Yayınlanmış liste yok.")

    # --- YÖNETİCİ PANELİ ---
    elif sayfa == "Yönetici Paneli" and st.session_state.kullanici_tipi == "Yonetici":
        st.header("👑 Yönetim Kontrol Merkezi")
        tab_k, tab_t, tab_m, tab_y, tab_b = st.tabs(["👥 Kullanıcılar", "📥 Gelen Talepler (Düzenle & Sil)", "🛠️ Manuel Plan", "🚀 Yayınlama", "👔 İK"])
        
        with tab_k:
            df_k = pd.read_csv(KULLANICI_FILE, dtype=str)
            bekleyenler = df_k[df_k["Durum"] == "Beklemede"]
            st.subheader("Yeni Kayıtlar")
            for idx, row in bekleyenler.iterrows():
                with st.expander(f"👤 {row['Isim']} ({row['Email']}) | Tel: {row['Telefon']} | {row.get('CalismaTipi', 'Tam Zamanlı')}"):
                    c1, c2 = st.columns(2)
                    if c1.button("Onayla", key=f"kon_{idx}"):
                        df_k.at[idx, "Durum"] = "Onaylandı"; df_k.to_csv(KULLANICI_FILE, index=False); st.rerun()
                    if c2.button("Reddet", key=f"kred_{idx}"):
                        df_k.at[idx, "Durum"] = "Reddedildi"; df_k.to_csv(KULLANICI_FILE, index=False); st.rerun()
            
            st.divider()
            st.subheader("Aktif Kullanıcılar")
            aktifler = df_k[df_k["Durum"] == "Onaylandı"]
            for idx, row in aktifler.iterrows():
                mevcut_tip = row.get("CalismaTipi", "Tam Zamanlı")
                with st.expander(f"⚙️ {row['Isim']} ({row['Rol']} - {mevcut_tip})"):
                    st.write(f"Mail: {row['Email']} | Tel: {row['Telefon']} | Şifre: {row['Sifre']}")
                    
                    idx_tip = 0 if mevcut_tip == "Tam Zamanlı" else 1
                    yeni_tip = st.selectbox("Çalışma Tipi:", ["Tam Zamanlı", "Part-Time"], index=idx_tip, key=f"tip_{idx}")
                    
                    c1, c2 = st.columns(2)
                    if c1.button("💾 Tipi Güncelle", key=f"kguncel_{idx}"):
                        df_k.at[idx, "CalismaTipi"] = yeni_tip
                        df_k.to_csv(KULLANICI_FILE, index=False)
                        st.rerun()
                        
                    if row["Email"] != st.session_state.kullanici_mail: 
                        if c2.button("🗑️ Kullanıcıyı Sil", key=f"kdel_{idx}"):
                            df_k = df_k.drop(idx); df_k.to_csv(KULLANICI_FILE, index=False); st.rerun()

        with tab_t:
            df_t = pd.read_csv(TALEPLER_FILE, dtype=str)
            
            # --- 1. BEKLEYEN TALEPLER ---
            st.subheader("1. Bekleyen Talepler")
            bekleyen_talepler = df_t[df_t["Durum"] == "Beklemede"]
            if len(bekleyen_talepler) > 0:
                for idx, row in bekleyen_talepler.iterrows():
                    with st.expander(f"⏳ {row['Personel']} | İzin: {row['İzin Günü']} | Vardiya: {row['Haftalık Vardiya']}"):
                        # NOT/NEDEN GÖSTERİMİ
                        if pd.notna(row['Neden']) and str(row['Neden']).strip() != "" and str(row['Neden']).lower() != "nan": 
                            st.write(f"**Personelin Notu:** {row['Neden']}")
                            
                        with st.form(key=f"ilk_onay_{idx}"):
                            col_iz, col_var = st.columns(2)
                            with col_iz:
                                mevcut_izin = [g for g in gunler if g in str(row['İzin Günü'])]
                                yeni_izin = st.multiselect("İzin:", gunler, default=mevcut_izin)
                            with col_var:
                                if "Akşamcı" in str(row['Haftalık Vardiya']): def_var_idx = 1
                                elif "Tam" in str(row['Haftalık Vardiya']): def_var_idx = 2
                                else: def_var_idx = 0
                                yeni_vardiya = st.radio("Vardiya:", vardiya_secenekleri, index=def_var_idx)
                            c1, c2 = st.columns(2)
                            if c1.form_submit_button("✅ Onayla"):
                                yeni_izin_str = ", ".join(yeni_izin) if len(yeni_izin) > 0 else "İzin Yok"
                                df_t_guncel = pd.read_csv(TALEPLER_FILE, dtype=str)
                                df_t_guncel.at[idx, "İzin Günü"] = yeni_izin_str
                                df_t_guncel.at[idx, "Haftalık Vardiya"] = str(yeni_vardiya)
                                df_t_guncel.at[idx, "Durum"] = "Onaylandı"
                                df_t_guncel.to_csv(TALEPLER_FILE, index=False)
                                st.rerun()
                            if c2.form_submit_button("❌ Reddet"):
                                df_t_guncel = pd.read_csv(TALEPLER_FILE, dtype=str)
                                df_t_guncel.at[idx, "Durum"] = "Reddedildi"
                                df_t_guncel.to_csv(TALEPLER_FILE, index=False)
                                st.rerun()
            else: st.info("Bekleyen talep yok.")

            st.divider()
            
            # --- 2. ONAYLANANLARI DÜZENLEME & TOPLU SİLME ---
            st.subheader("2. Onaylanmış Talepleri Düzenle / Toplu Temizle")
            onayli_talepler = df_t[df_t["Durum"] == "Onaylandı"]
            
            if len(onayli_talepler) > 0:
                t1, t2, t3, t4 = st.columns(4)
                with t1:
                    if st.button("☑️ Tümünü Seç"):
                        for i in onayli_talepler.index: st.session_state[f"toplu_{i}"] = True
                        st.rerun()
                with t2:
                    if st.button("🔳 Seçimi Kaldır"):
                        for i in onayli_talepler.index: st.session_state[f"toplu_{i}"] = False
                        st.rerun()
                        
                secilen_idxler = [i for i in onayli_talepler.index if st.session_state.get(f"toplu_{i}", False)]
                
                with t3:
                    if len(secilen_idxler) > 0:
                        if st.button(f"🗑️ Seçilenleri Sil ({len(secilen_idxler)})", type="primary"):
                            df_t_guncel = pd.read_csv(TALEPLER_FILE, dtype=str)
                            df_t_guncel = df_t_guncel.drop(secilen_idxler)
                            df_t_guncel.to_csv(TALEPLER_FILE, index=False)
                            for i in secilen_idxler: del st.session_state[f"toplu_{i}"]
                            st.rerun()
                st.write("") 
                
                for idx, row in onayli_talepler.iterrows():
                    c_chk, c_exp = st.columns([1, 20])
                    with c_chk:
                        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
                        st.checkbox("", key=f"toplu_{idx}")
                    with c_exp:
                        with st.expander(f"✅ {row['Personel']} | İzin: {row['İzin Günü']} | Vardiya: {row['Haftalık Vardiya']}"):
                            # YENİ: NOT/NEDEN BURAYA DA EKLENDİ
                            if pd.notna(row['Neden']) and str(row['Neden']).strip() != "" and str(row['Neden']).lower() != "nan": 
                                st.write(f"**Personelin Notu:** {row['Neden']}")
                                
                            with st.form(key=f"duzenle_onayli_{idx}"):
                                col_iz, col_var = st.columns(2)
                                with col_iz:
                                    mevcut_izin = [g for g in gunler if g in str(row['İzin Günü'])]
                                    guncel_izin = st.multiselect("İzin Değiştir:", gunler, default=mevcut_izin)
                                with col_var:
                                    if "Akşamcı" in str(row['Haftalık Vardiya']): def_var_idx = 1
                                    elif "Tam" in str(row['Haftalık Vardiya']): def_var_idx = 2
                                    else: def_var_idx = 0
                                    guncel_vardiya = st.radio("Vardiya Değiştir:", vardiya_secenekleri, index=def_var_idx)
                                
                                c1, c2 = st.columns(2)
                                if c1.form_submit_button("🔄 Güncelle"):
                                    yeni_izin_str = ", ".join(guncel_izin) if len(guncel_izin) > 0 else "İzin Yok"
                                    df_t_guncel = pd.read_csv(TALEPLER_FILE, dtype=str)
                                    df_t_guncel.at[idx, "İzin Günü"] = yeni_izin_str
                                    df_t_guncel.at[idx, "Haftalık Vardiya"] = str(guncel_vardiya)
                                    df_t_guncel.to_csv(TALEPLER_FILE, index=False)
                                    st.rerun()
                                if c2.form_submit_button("⚠️ İptal Et (Beklemeye Al)"):
                                    df_t_guncel = pd.read_csv(TALEPLER_FILE, dtype=str)
                                    df_t_guncel.at[idx, "Durum"] = "Beklemede"
                                    df_t_guncel.to_csv(TALEPLER_FILE, index=False)
                                    st.rerun()
            else: st.info("Henüz onaylanmış talep yok.")
            
            st.divider()
            
            st.subheader("👀 Canlı Taslak Önizlemesi")
            taslak_df = get_taslak_df()
            if not taslak_df.empty: st.table(taslak_df.style.map(style_status, subset=gunler))

        with tab_m:
            st.subheader("🛠️ Manuel Vardiya Atama")
            aktif_personel_listesi = df_k[(df_k["Durum"] == "Onaylandı") & (df_k["Rol"] != "Yonetici")]["Isim"].tolist()
            
            if len(aktif_personel_listesi) > 0:
                with st.form("manuel_atama"):
                    secilen_kisi = st.selectbox("Personel:", aktif_personel_listesi)
                    secilen_izin = st.multiselect("İzin Günleri:", gunler)
                    secilen_vardiya = st.radio("Vardiya:", vardiya_secenekleri)
                    if st.form_submit_button("Sisteme İşle (Onaylı)"):
                        izin_str = ", ".join(secilen_izin) if len(secilen_izin) > 0 else "İzin Yok"
                        df_t = pd.read_csv(TALEPLER_FILE, dtype=str)
                        df_t = df_t[df_t["Personel"] != secilen_kisi] 
                        yeni_manuel = {"Personel": secilen_kisi, "İzin Günü": izin_str, "Haftalık Vardiya": secilen_vardiya, "Neden": "Manuel atandı.", "Durum": "Onaylandı"}
                        df_t = pd.concat([df_t, pd.DataFrame([yeni_manuel])], ignore_index=True)
                        df_t.to_csv(TALEPLER_FILE, index=False)
                        st.success("Atandı!"); st.rerun()
            else:
                st.warning("Sistemde aktif personel bulunmuyor.")

        with tab_y:
            st.subheader("Haftalık Operasyon Kontrolü")
            if st.button("🔄 Yeni Haftaya Başla (Sıfırla)"):
                with open(YAYIN_FILE, "w") as f: f.write("GIZLI")
                pd.DataFrame(columns=["Personel", "İzin Günü", "Haftalık Vardiya", "Neden", "Durum"]).to_csv(TALEPLER_FILE, index=False)
                st.success("Sıfırlandı."); st.rerun()
            st.divider()
            col_yayin, col_mail = st.columns(2)
            with col_yayin:
                if st.button("🚀 Listeyi Kesinleştir ve Yayınla"):
                    taslak_df = get_taslak_df()
                    if not taslak_df.empty:
                        taslak_df.to_csv(VARDIYA_FILE, index=False)
                        with open(YAYIN_FILE, "w") as f: f.write("YAYINLANDI")
                        
                        pd.DataFrame(columns=["Personel", "İzin Günü", "Haftalık Vardiya", "Neden", "Durum"]).to_csv(TALEPLER_FILE, index=False)
                        
                        st.success("Liste yayınlandı ve talep listesi yeni hafta için temizlendi!"); st.rerun()
                    else: st.warning("Onaylı plan yok.")
            with col_mail:
                if st.button("📧 Yayın Maili At"):
                    with open(YAYIN_FILE, "r") as f:
                        if f.read().strip() == "YAYINLANDI":
                            onayli_k = df_k[df_k["Durum"] == "Onaylandı"]
                            with st.spinner("Mailler gönderiliyor..."):
                                basarili = sum(1 for _, u in onayli_k.iterrows() if mail_gonder(u["Email"], "Haftalık Liste Yayınlandı", "Liste yayınlandı, sisteme girip bakabilirsiniz."))
                            st.success(f"{basarili} kişiye mail gitti.")
                        else:
                            st.error("Önce listeyi yayınlamalısınız!")

        with tab_b:
            st.subheader("İş Başvuruları")
            df_b = pd.read_csv(BASVURU_FILE, dtype=str)
            bekleyen_b = df_b[df_b["Durum"] == "İnceleniyor"]
            for idx, row in bekleyen_b.iterrows():
                with st.expander(f"👤 {row['Ad Soyad']} - {row['Pozisyon']} ({row.get('Çalışma Tipi', 'Tam Zamanlı')})"):
                    st.write(f"Tel: {row['Telefon']} | Mail: {row['E-posta']}\n\nTecrübe: {row['Tecrübe']}")
                    c1, c2, c3 = st.columns(3)
                    if c1.button("Kabul", key=f"bk_{idx}"): df_b.at[idx, "Durum"]="Kabul"; df_b.to_csv(BASVURU_FILE, index=False); st.rerun()
                    if c2.button("Red", key=f"br_{idx}"): df_b.at[idx, "Durum"]="Red"; df_b.to_csv(BASVURU_FILE, index=False); st.rerun()
                    if c3.button("Sil", key=f"bs_{idx}"): df_b=df_b.drop(idx); df_b.to_csv(BASVURU_FILE, index=False); st.rerun()
