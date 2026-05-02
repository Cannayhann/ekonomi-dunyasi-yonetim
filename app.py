import streamlit as st
import pandas as pd
import os
import smtplib
import random
import string
from email.mime.text import MIMEText
from datetime import datetime
from supabase import create_client, Client

# 1. SİSTEM AYARLARI
st.set_page_config(page_title="ED-AVM Yönetim", layout="wide")

PROFILE_DIR = "profil_fotograflari"
os.makedirs(PROFILE_DIR, exist_ok=True)

gunler = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
vardiya_secenekleri = ["Sabahçı (09:00 - 18:00)", "Akşamcı (12:00 - 21:00)", "Tam Gün (09:00 - 21:00)"]

# --- 2. BULUT VERİTABANI (SUPABASE) BAĞLANTISI ---
@st.cache_resource
def init_connection():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

try:
    supabase = init_connection()
except Exception as e:
    st.error("⚠️ Veritabanı bağlantı hatası! Lütfen Streamlit Secrets ayarlarınızı kontrol edin.")
    st.stop()

# --- VERİ ÇEKME FONKSİYONLARI ---
def get_yayin_durumu():
    try:
        res = supabase.table('ayarlar').select('deger').eq('ayar_adi', 'yayin_durumu').execute()
        if res.data: return res.data[0]['deger']
    except: pass
    return "GIZLI"

yayin_durumu = get_yayin_durumu()

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

def get_taslak_df():
    res_k = supabase.table('kullanicilar').select('isim').eq('durum', 'Onaylandı').neq('rol', 'Yonetici').execute()
    aktifler = [k['isim'] for k in res_k.data] if res_k.data else []
    if not aktifler: return pd.DataFrame()
    
    taslak = pd.DataFrame(index=aktifler, columns=gunler)
    taslak.fillna("⏳ Belirsiz", inplace=True)
    
    res_t = supabase.table('talepler').select('*').eq('durum', 'Onaylandı').execute()
    onayli = res_t.data if res_t.data else []
    
    for r in onayli:
        p = str(r["personel"])
        if p not in taslak.index: continue
        iz_str = str(r["izin_gunu"])
        v_str = str(r["haftalik_vardiya"])
        
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
    st.session_state.update({"giris_yapildi": False, "kullanici_tipi": "", "kullanici_adi": "", "kullanici_mail": "", "reset_kod": "", "reset_mail": "", "calisma_tipi": ""})

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
                res = supabase.table('kullanicilar').select('*').eq('email', email_in).eq('sifre', sifre_in).execute()
                if res.data:
                    user = res.data[0]
                    if user["durum"] == "Onaylandı":
                        st.session_state.update({
                            "giris_yapildi": True, 
                            "kullanici_tipi": user["rol"], 
                            "kullanici_adi": user["isim"], 
                            "kullanici_mail": user["email"],
                            "calisma_tipi": user.get("calisma_tipi", "Tam Zamanlı")
                        })
                        st.rerun()
                    else: st.warning("⏳ Hesabınız onay bekliyor.")
                else: st.error("❌ E-posta veya şifre hatalı.")

        elif sekme == "📝 Kayıt Ol":
            with st.form("kayit"):
                isim = st.text_input("Adınız Soyadınız")
                tel = st.text_input("Telefon Numaranız")
                mail = st.text_input("E-posta Adresiniz").strip().lower()
                calisma_tipi = st.selectbox("Çalışma Şekliniz", ["Tam Zamanlı", "Part-Time"])
                sifre = st.text_input("Şifre Belirleyiniz", type="password")
                
                if st.form_submit_button("Kayıt Talebi Gönder"):
                    res_kontrol = supabase.table('kullanicilar').select('email').eq('email', mail).execute()
                    if res_kontrol.data: st.error("Bu e-posta zaten sistemde kayıtlı.")
                    elif isim == "" or mail == "" or sifre == "": st.warning("Lütfen zorunlu alanları doldurun.")
                    else:
                        yeni_veri = {"isim": str(isim.strip().title()), "email": str(mail), "sifre": str(sifre), "telefon": str(tel), "durum": "Beklemede", "rol": "Personel", "calisma_tipi": calisma_tipi}
                        supabase.table('kullanicilar').insert(yeni_veri).execute()
                        st.success("Kayıt başarılı! Yönetim onayından sonra girebilirsiniz.")

        elif sekme == "❓ Şifremi Unuttum":
            if st.session_state.reset_kod == "":
                mail_res = st.text_input("Sisteme Kayıtlı E-posta Adresiniz:")
                if st.button("Doğrulama Kodu Gönder"):
                    res = supabase.table('kullanicilar').select('email').eq('email', mail_res.strip().lower()).execute()
                    if res.data:
                        kod = kod_uret()
                        st.session_state.reset_kod = kod
                        st.session_state.reset_mail = mail_res.strip().lower()
                        mail_gonder(mail_res, "ED-AVM | Şifre Sıfırlama", f"Sıfırlama kodunuz: {kod}")
                        st.info("Kod e-postanıza gönderildi.")
                    else: st.error("Mail sistemde bulunamadı.")
            else:
                kod_in = st.text_input("Mailinize gelen kodu girin:")
                yeni_sifre = st.text_input("Yeni Şifreniz:", type="password")
                if st.button("Şifreyi Güncelle"):
                    if kod_in == st.session_state.reset_kod:
                        supabase.table('kullanicilar').update({"sifre": str(yeni_sifre)}).eq('email', st.session_state.reset_mail).execute()
                        st.success("Şifreniz güncellendi!"); st.session_state.reset_kod = ""
                    else: st.error("Kod hatalı.")

        elif sekme == "👔 İş Başvurusu":
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
                        yeni_basvuru = {"ad_soyad": str(b_isim.strip().title()), "telefon": str(b_tel), "eposta": str(b_mail), "pozisyon": str(b_pozisyon), "calisma_tipi": str(b_calisma_tipi), "tecrube": str(b_tecrube), "durum": "İnceleniyor", "tarih": datetime.now().strftime("%Y-%m-%d %H:%M")}
                        supabase.table('basvurular').insert(yeni_basvuru).execute()
                        st.success("Başvurunuz İK sistemine başarıyla kaydedildi!")

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

    # --- PROFİLİM ---
    if sayfa == "Profilim":
        st.header("👤 Profilimi Düzenle")
        res_u = supabase.table('kullanicilar').select('*').eq('email', st.session_state.kullanici_mail).execute()
        u_data = res_u.data[0]
        
        col_foto, col_bilgi = st.columns([1, 2])
        with col_foto:
            st.subheader("Fotoğraf")
            if os.path.exists(pp_path): st.image(pp_path, width=200)
            yuklenen_foto = st.file_uploader("Yeni Fotoğraf Yükle (PNG/JPG)", type=["png", "jpg", "jpeg"])
            if yuklenen_foto is not None:
                with open(pp_path, "wb") as f: f.write(yuklenen_foto.getbuffer())
                st.success("Yüklendi!"); st.rerun()

        with col_bilgi:
            yeni_isim = st.text_input("Ad Soyad:", value=str(u_data["isim"]))
            yeni_tel = st.text_input("Telefon:", value=str(u_data["telefon"]))
            
            idx_tip = 0 if u_data.get("calisma_tipi", "Tam Zamanlı") == "Tam Zamanlı" else 1
            yeni_tip = st.selectbox("Çalışma Tipi:", ["Tam Zamanlı", "Part-Time"], index=idx_tip)
            yeni_sifre = st.text_input("Şifre:", value=str(u_data["sifre"]), type="password")
            
            if st.button("Kaydet"):
                supabase.table('kullanicilar').update({
                    "isim": str(yeni_isim), "telefon": str(yeni_tel), "calisma_tipi": str(yeni_tip), "sifre": str(yeni_sifre)
                }).eq('email', st.session_state.kullanici_mail).execute()
                st.session_state.kullanici_adi = str(yeni_isim)
                st.session_state.calisma_tipi = str(yeni_tip)
                st.success("Profiliniz başarıyla güncellendi!"); st.rerun()

    # --- VARDİYA İŞLEMLERİ (PERSONEL) ---
    elif sayfa == "Vardiya İşlemleri":
        st.header("📅 Haftalık Vardiya Planlaması")
        tab1, tab2, tab3 = st.tabs(["✍️ Planımı Gönder", "👀 Onaylananlar (Canlı Taslak)", "📊 Kesinleşen Liste"])
        
        with tab1:
            with st.form("personel_formu", clear_on_submit=True):
                if st.session_state.calisma_tipi == "Part-Time":
                    st.info("ℹ️ Part-Time personel olarak sadece **ÇALIŞACAĞINIZ** günleri seçiniz.")
                    secilen_gunler = st.multiselect("✅ ÇALIŞACAĞINIZ Günleri Seçiniz:", gunler)
                else:
                    st.info("ℹ️ Tam Zamanlı personel olarak **İZİNLİ** (boş) olacağınız günleri seçiniz.")
                    secilen_gunler = st.multiselect("🌴 İZİNLİ Olacağınız Günleri Seçiniz:", gunler)

                haftalik_shift = st.radio("Vardiyanız:", vardiya_secenekleri)
                neden = st.text_area("Notunuz (İsteğe Bağlı):")
                
                if st.form_submit_button("Planımı Gönder"):
                    if st.session_state.calisma_tipi == "Part-Time":
                        izin_listesi = [g for g in gunler if g not in secilen_gunler]
                    else:
                        izin_listesi = secilen_gunler
                        
                    izin_str = ", ".join(izin_listesi) if len(izin_listesi) > 0 else "İzin Yok"
                    
                    # Veritabanına Yazma (Aynı kişiden varsa eskiyi sil, yeniyi ekle mantığı - UPSERT)
                    yeni_talep = {"personel": st.session_state.kullanici_adi, "izin_gunu": izin_str, "haftalik_vardiya": haftalik_shift, "neden": neden, "durum": "Beklemede"}
                    
                    # Önce eskisini siliyoruz ki çöplük olmasın
                    supabase.table('talepler').delete().eq('personel', st.session_state.kullanici_adi).execute()
                    # Sonra yeni talebi ekliyoruz
                    supabase.table('talepler').insert(yeni_talep).execute()
                    
                    st.success("Talebiniz veritabanına işlendi ve yönetime iletildi.")
                    
        with tab2:
            st.info("💡 Yönetimin şu ana kadar onayladığı güncel durumu gösterir.")
            taslak_df = get_taslak_df()
            if not taslak_df.empty: st.table(taslak_df.style.map(style_status, subset=gunler))
            else: st.warning("Henüz onaylanmış bir plan yok.")

        with tab3:
            if yayin_durumu == "YAYINLANDI":
                res_v = supabase.table('vardiyalar').select('*').execute()
                if res_v.data:
                    df_v = pd.DataFrame(res_v.data)
                    df_v.rename(columns={'personel': 'Personel'}, inplace=True)
                    st.table(df_v.style.map(style_status, subset=gunler))
                else: st.warning("Liste veritabanında boş.")
            else: st.warning("⚠️ Kesinleşmiş liste henüz yayınlanmamıştır.")

    # --- KESİNLEŞEN LİSTE (YÖNETİCİ) ---
    elif sayfa == "Kesinleşen Liste":
        st.header("📊 Kesinleşen Vardiya Listesi")
        if yayin_durumu == "YAYINLANDI":
            res_v = supabase.table('vardiyalar').select('*').execute()
            if res_v.data:
                df_v = pd.DataFrame(res_v.data)
                df_v.rename(columns={'personel': 'Personel'}, inplace=True)
                st.table(df_v.style.map(style_status, subset=gunler))
        else: st.warning("⚠️ Yayınlanmış liste yok.")

    # --- YÖNETİCİ PANELİ ---
    elif sayfa == "Yönetici Paneli" and st.session_state.kullanici_tipi == "Yonetici":
        st.header("👑 Yönetim Kontrol Merkezi")
        tab_k, tab_t, tab_m, tab_y, tab_b = st.tabs(["👥 Kullanıcılar", "📥 Gelen Talepler", "🛠️ Manuel Plan", "🚀 Yayınlama", "👔 İK"])
        
        with tab_k:
            res_users = supabase.table('kullanicilar').select('*').execute()
            df_k = pd.DataFrame(res_users.data) if res_users.data else pd.DataFrame()
            
            if not df_k.empty:
                bekleyenler = df_k[df_k["durum"] == "Beklemede"]
                st.subheader("Yeni Kayıtlar")
                for _, row in bekleyenler.iterrows():
                    with st.expander(f"👤 {row['isim']} ({row['email']}) | {row.get('calisma_tipi', 'Tam Zamanlı')}"):
                        c1, c2 = st.columns(2)
                        if c1.button("Onayla", key=f"kon_{row['email']}"):
                            supabase.table('kullanicilar').update({'durum': 'Onaylandı'}).eq('email', row['email']).execute()
                            st.rerun()
                        if c2.button("Reddet", key=f"kred_{row['email']}"):
                            supabase.table('kullanicilar').delete().eq('email', row['email']).execute()
                            st.rerun()
                
                st.divider()
                st.subheader("Aktif Kullanıcılar")
                aktifler = df_k[df_k["durum"] == "Onaylandı"]
                for _, row in aktifler.iterrows():
                    mevcut_tip = row.get("calisma_tipi", "Tam Zamanlı")
                    with st.expander(f"⚙️ {row['isim']} ({row['rol']} - {mevcut_tip})"):
                        st.write(f"Mail: {row['email']} | Tel: {row['telefon']} | Şifre: {row['sifre']}")
                        idx_tip = 0 if mevcut_tip == "Tam Zamanlı" else 1
                        yeni_tip = st.selectbox("Çalışma Tipi:", ["Tam Zamanlı", "Part-Time"], index=idx_tip, key=f"tip_{row['email']}")
                        
                        c1, c2 = st.columns(2)
                        if c1.button("💾 Tipi Güncelle", key=f"kguncel_{row['email']}"):
                            supabase.table('kullanicilar').update({'calisma_tipi': yeni_tip}).eq('email', row['email']).execute()
                            st.rerun()
                        if row["email"] != st.session_state.kullanici_mail: 
                            if c2.button("🗑️ Kullanıcıyı Sil", key=f"kdel_{row['email']}"):
                                supabase.table('kullanicilar').delete().eq('email', row['email']).execute()
                                st.rerun()

        with tab_t:
            res_t = supabase.table('talepler').select('*').execute()
            df_t = pd.DataFrame(res_t.data) if res_t.data else pd.DataFrame()
            
            st.subheader("1. Bekleyen Talepler")
            if not df_t.empty:
                bekleyen_talepler = df_t[df_t["durum"] == "Beklemede"]
                if len(bekleyen_talepler) > 0:
                    for _, row in bekleyen_talepler.iterrows():
                        with st.expander(f"⏳ {row['personel']} | İzin: {row['izin_gunu']} | Vardiya: {row['haftalik_vardiya']}"):
                            if pd.notna(row['neden']) and str(row['neden']).strip() != "": st.write(f"**Not:** {row['neden']}")
                            with st.form(key=f"ilk_onay_{row['id']}"):
                                col_iz, col_var = st.columns(2)
                                with col_iz:
                                    mevcut_izin = [g for g in gunler if g in str(row['izin_gunu'])]
                                    yeni_izin = st.multiselect("İzinli/Boş Günler:", gunler, default=mevcut_izin)
                                with col_var:
                                    def_var_idx = 1 if "Akşamcı" in str(row['haftalik_vardiya']) else 2 if "Tam" in str(row['haftalik_vardiya']) else 0
                                    yeni_vardiya = st.radio("Vardiya:", vardiya_secenekleri, index=def_var_idx)
                                c1, c2 = st.columns(2)
                                if c1.form_submit_button("✅ Onayla"):
                                    yeni_izin_str = ", ".join(yeni_izin) if len(yeni_izin) > 0 else "İzin Yok"
                                    supabase.table('talepler').update({'izin_gunu': yeni_izin_str, 'haftalik_vardiya': str(yeni_vardiya), 'durum': 'Onaylandı'}).eq('id', row['id']).execute()
                                    st.rerun()
                                if c2.form_submit_button("❌ Reddet"):
                                    supabase.table('talepler').delete().eq('id', row['id']).execute()
                                    st.rerun()
                else: st.info("Bekleyen talep yok.")
            else: st.info("Sistemde hiç talep yok.")

            st.divider()
            
            st.subheader("2. Onaylanmış Talepleri Düzenle")
            if not df_t.empty:
                onayli_talepler = df_t[df_t["durum"] == "Onaylandı"]
                if len(onayli_talepler) > 0:
                    for _, row in onayli_talepler.iterrows():
                        with st.expander(f"✅ {row['personel']} | İzin: {row['izin_gunu']} | Vardiya: {row['haftalik_vardiya']}"):
                            if pd.notna(row['neden']) and str(row['neden']).strip() != "": st.write(f"**Not:** {row['neden']}")
                            with st.form(key=f"duzenle_onayli_{row['id']}"):
                                col_iz, col_var = st.columns(2)
                                with col_iz:
                                    mevcut_izin = [g for g in gunler if g in str(row['izin_gunu'])]
                                    guncel_izin = st.multiselect("İzin Değiştir:", gunler, default=mevcut_izin)
                                with col_var:
                                    def_var_idx = 1 if "Akşamcı" in str(row['haftalik_vardiya']) else 2 if "Tam" in str(row['haftalik_vardiya']) else 0
                                    guncel_vardiya = st.radio("Vardiya Değiştir:", vardiya_secenekleri, index=def_var_idx)
                                
                                c1, c2, c3 = st.columns(3)
                                if c1.form_submit_button("🔄 Güncelle"):
                                    yeni_izin_str = ", ".join(guncel_izin) if len(guncel_izin) > 0 else "İzin Yok"
                                    supabase.table('talepler').update({'izin_gunu': yeni_izin_str, 'haftalik_vardiya': str(guncel_vardiya)}).eq('id', row['id']).execute()
                                    st.rerun()
                                if c2.form_submit_button("⚠️ İptal Et"):
                                    supabase.table('talepler').update({'durum': 'Beklemede'}).eq('id', row['id']).execute()
                                    st.rerun()
                                if c3.form_submit_button("🗑️ Sil"):
                                    supabase.table('talepler').delete().eq('id', row['id']).execute()
                                    st.rerun()
                else: st.info("Onaylanmış talep yok.")
            
            st.divider()
            st.subheader("👀 Canlı Taslak Önizlemesi")
            taslak_df = get_taslak_df()
            if not taslak_df.empty: st.table(taslak_df.style.map(style_status, subset=gunler))

        with tab_m:
            st.subheader("🛠️ Manuel Vardiya Atama")
            res_k = supabase.table('kullanicilar').select('isim').eq('durum', 'Onaylandı').neq('rol', 'Yonetici').execute()
            aktif_personel_listesi = [k['isim'] for k in res_k.data] if res_k.data else []
            
            if len(aktif_personel_listesi) > 0:
                with st.form("manuel_atama"):
                    secilen_kisi = st.selectbox("Personel:", aktif_personel_listesi)
                    secilen_izin = st.multiselect("İzinli/Boş Günler:", gunler)
                    secilen_vardiya = st.radio("Vardiya:", vardiya_secenekleri)
                    if st.form_submit_button("Sisteme İşle (Onaylı)"):
                        izin_str = ", ".join(secilen_izin) if len(secilen_izin) > 0 else "İzin Yok"
                        supabase.table('talepler').delete().eq('personel', secilen_kisi).execute() # Eskisini sil
                        yeni_manuel = {"personel": secilen_kisi, "izin_gunu": izin_str, "haftalik_vardiya": secilen_vardiya, "neden": "Yönetici Manuel Atama", "durum": "Onaylandı"}
                        supabase.table('talepler').insert(yeni_manuel).execute()
                        st.success("Veritabanına eklendi!"); st.rerun()
            else:
                st.warning("Sistemde aktif personel bulunmuyor.")

        with tab_y:
            st.subheader("Haftalık Operasyon Kontrolü")
            if st.button("🔄 Yeni Haftaya Başla (Sıfırla)"):
                supabase.table('ayarlar').update({'deger': 'GIZLI'}).eq('ayar_adi', 'yayin_durumu').execute()
                # Tüm eski talepleri veritabanından kalıcı olarak siler
                supabase.table('talepler').delete().neq('id', 0).execute() 
                st.success("Veritabanı sıfırlandı. Tertemiz bir haftaya başlandı."); st.rerun()
            
            st.divider()
            col_yayin, col_mail = st.columns(2)
            with col_yayin:
                if st.button("🚀 Listeyi Kesinleştir ve Yayınla"):
                    taslak_df = get_taslak_df()
                    if not taslak_df.empty:
                        # Eski vardiya listesini temizle
                        supabase.table('vardiyalar').delete().neq('personel', 'x').execute()
                        
                        # Yeni vardiyaları ekle
                        for _, row in taslak_df.iterrows():
                            v_data = {"personel": row["Personel"]}
                            for g in gunler: v_data[g] = row[g]
                            supabase.table('vardiyalar').insert(v_data).execute()
                        
                        supabase.table('ayarlar').update({'deger': 'YAYINLANDI'}).eq('ayar_adi', 'yayin_durumu').execute()
                        supabase.table('talepler').delete().neq('id', 0).execute() # Çöpleri uçur
                        st.success("Liste Bulut'a kaydedildi ve yayınlandı!"); st.rerun()
                    else: st.warning("Onaylı plan yok.")
            with col_mail:
                if st.button("📧 Yayın Maili At"):
                    st.success("Mail sistemi hazır.")

        with tab_b:
            st.subheader("İş Başvuruları")
            res_b = supabase.table('basvurular').select('*').execute()
            if res_b.data:
                df_b = pd.DataFrame(res_b.data)
                bekleyen_b = df_b[df_b["durum"] == "İnceleniyor"]
                for _, row in bekleyen_b.iterrows():
                    with st.expander(f"👤 {row['ad_soyad']} - {row['pozisyon']} ({row.get('calisma_tipi', 'Tam Zamanlı')})"):
                        st.write(f"Tel: {row['telefon']} | Mail: {row['eposta']}\n\nTecrübe: {row['tecrube']}")
                        c1, c2, c3 = st.columns(3)
                        if c1.button("Kabul", key=f"bk_{row['id']}"): 
                            supabase.table('basvurular').update({'durum': 'Kabul'}).eq('id', row['id']).execute(); st.rerun()
                        if c2.button("Red", key=f"br_{row['id']}"): 
                            supabase.table('basvurular').update({'durum': 'Red'}).eq('id', row['id']).execute(); st.rerun()
                        if c3.button("Sil", key=f"bs_{row['id']}"): 
                            supabase.table('basvurular').delete().eq('id', row['id']).execute(); st.rerun()
            else: st.info("İncelenmeyi bekleyen başvuru yok.")
