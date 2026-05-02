import streamlit as st
import pandas as pd
import os
import smtplib
import random
import string
import base64
from email.mime.text import MIMEText
from datetime import datetime
from supabase import create_client, Client
from streamlit_cookies_controller import CookieController

# 1. SİSTEM AYARLARI VE KLASÖRLER
st.set_page_config(page_title="ED-AVM Yönetim", layout="wide")

PROFILE_DIR = "profil_fotograflari"
THEME_DIR = "tema_dosyalari"
os.makedirs(PROFILE_DIR, exist_ok=True)
os.makedirs(THEME_DIR, exist_ok=True)

LOGO_PATH = os.path.join(THEME_DIR, "logo.png")
BG_PATH = os.path.join(THEME_DIR, "arkaplan.png")

gunler = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
vardiya_secenekleri = ["Sabahçı (09:00 - 18:00)", "Akşamcı (12:00 - 21:00)", "Tam Gün (09:00 - 21:00)"]

# --- TEMA UYGULAMA MOTORU ---
def tema_uygula():
    if os.path.exists(BG_PATH):
        try:
            with open(BG_PATH, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode()
            st.markdown(
            f"""
            <style>
            .stApp {{
                background-image: url(data:image/png;base64,{encoded_string});
                background-size: cover;
                background-position: center;
                background-attachment: fixed;
            }}
            .block-container {{
                background-color: rgba(255, 255, 255, 0.92);
                padding: 2rem;
                border-radius: 15px;
                box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
            }}
            </style>
            """, unsafe_allow_html=True)
        except: pass

tema_uygula()

# --- 2. BULUT VERİTABANI BAĞLANTISI ---
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

def tabloyu_ciz(df):
    df_gorsel = df.copy()
    if 'Personel' in df_gorsel.columns:
        df_gorsel['Personel'] = df_gorsel['Personel'].apply(lambda x: str(x).split(' (')[0] if ' (' in str(x) else x)
    st.table(df_gorsel.style.map(style_status, subset=gunler))

def get_taslak_df():
    res_k = supabase.table('kullanicilar').select('isim, email').eq('durum', 'Onaylandı').neq('rol', 'Yonetici').execute()
    aktifler = [f"{k['isim']} ({k['email']})" for k in res_k.data] if res_k.data else []
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
        
        for g in gunler:
            if g in iz_str: 
                taslak.at[p, g] = "🔴 İZİNLİ"
            elif g == "Pazar": 
                taslak.at[p, g] = "🟢 TAM GÜÇ"
            else:
                if "Karma" in v_str:
                    if f"{g}: Sabahçı" in v_str: shift = "S (09-18)"
                    elif f"{g}: Akşamcı" in v_str: shift = "A (12-21)"
                    elif f"{g}: Tam Gün" in v_str: shift = "T (09-21)"
                    else: shift = "S (09-18)"
                else:
                    if "Akşamcı" in v_str: shift = "A (12-21)"
                    elif "Tam" in v_str: shift = "T (09-21)"
                    else: shift = "S (09-18)"
                
                taslak.at[p, g] = shift
            
    taslak.reset_index(inplace=True)
    taslak.rename(columns={'index': 'Personel'}, inplace=True)
    return taslak

# ==========================================
# SİSTEM HAFIZASI (ÇEREZ) YÖNETİMİ
# ==========================================
cookies = CookieController()

if "giris_yapildi" not in st.session_state:
    st.session_state.update({
        "giris_yapildi": False, "kullanici_tipi": "", "kullanici_adi": "", 
        "kullanici_mail": "", "reset_kod": "", "reset_mail": "", 
        "calisma_tipi": "", "cikis_yapiliyor": False, 
        "yeni_cerez_yaz": None, "az_once_cikis_yapti": False
    })

if st.session_state.get("cikis_yapiliyor"):
    try: cookies.remove('edavm_user_mail')
    except Exception: pass
    st.query_params.clear()
    st.session_state.clear()
    st.session_state.update({"giris_yapildi": False, "cikis_yapiliyor": False, "az_once_cikis_yapti": True})

if st.session_state.get("yeni_cerez_yaz"):
    cookies.set('edavm_user_mail', st.session_state.get("yeni_cerez_yaz"), max_age=30*24*60*60)
    st.session_state.yeni_cerez_yaz = None

kayitli_mail = cookies.get('edavm_user_mail')
bilet_mail = None
if "session" in st.query_params:
    try: bilet_mail = base64.b64decode(st.query_params["session"]).decode('utf-8')
    except: pass
aktif_mail = kayitli_mail or bilet_mail

if not st.session_state.get("giris_yapildi") and aktif_mail and not st.session_state.get("az_once_cikis_yapti"):
    try:
        res = supabase.table('kullanicilar').select('*').eq('email', aktif_mail).execute()
        if res.data and res.data[0]["durum"] == "Onaylandı":
            user = res.data[0]
            st.session_state.update({
                "giris_yapildi": True, "kullanici_tipi": user["rol"], 
                "kullanici_adi": user["isim"], "kullanici_mail": user["email"],
                "calisma_tipi": user.get("calisma_tipi", "Tam Zamanlı")
            })
            if bilet_mail and not kayitli_mail:
                cookies.set('edavm_user_mail', user["email"], max_age=30*24*60*60)
        else:
            if kayitli_mail: 
                try: cookies.remove('edavm_user_mail')
                except: pass
            st.query_params.clear()
    except: pass

# ==========================================
# GİRİŞ / KAYIT EKRANI
# ==========================================
if not st.session_state.giris_yapildi:
    col_logo, col_baslik = st.columns([1, 8])
    with col_logo:
        if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, width=80)
    with col_baslik: st.title("🏢 Ekonomi Dünyası AVM Portalı")
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 4, 1])
    with col2:
        sekme = st.radio("İşlem Seçiniz", ["🔑 Giriş Yap", "📝 Kayıt Ol", "❓ Şifremi Unuttum", "👔 İş Başvurusu"], horizontal=True)

        if sekme == "🔑 Giriş Yap":
            email_in = st.text_input("E-posta").strip().lower()
            sifre_in = st.text_input("Şifre", type="password")
            beni_hatirla = st.checkbox("Beni Hatırla (Cihazda Oturumu Açık Tut)", value=False)
            
            if st.button("Sisteme Gir"):
                res = supabase.table('kullanicilar').select('*').eq('email', email_in).eq('sifre', sifre_in).execute()
                if res.data:
                    user = res.data[0]
                    if user["durum"] == "Onaylandı":
                        if beni_hatirla:
                            token = base64.b64encode(user["email"].encode('utf-8')).decode('utf-8')
                            st.query_params["session"] = token
                            st.session_state.yeni_cerez_yaz = user["email"]
                        else:
                            try:
                                if cookies.get('edavm_user_mail'): cookies.remove('edavm_user_mail')
                            except: pass
                            st.query_params.clear()
                                
                        st.session_state.update({
                            "giris_yapildi": True, "kullanici_tipi": user["rol"], 
                            "kullanici_adi": user["isim"], "kullanici_mail": user["email"],
                            "calisma_tipi": user.get("calisma_tipi", "Tam Zamanlı"), "az_once_cikis_yapti": False 
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
                        mesaj = f"Merhaba {isim.strip().title()},\n\nSisteme kayıt talebiniz başarıyla alınmıştır. Yönetim onayından sonra panelinize giriş yapabilirsiniz.\n\nİyi çalışmalar,\nED-AVM Yönetim"
                        mail_gonder(mail, "ED-AVM | Kayıt Talebiniz Alındı", mesaj)
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
# ANA SİSTEM PANELİ
# ==========================================
if st.session_state.giris_yapildi:
    pp_path = os.path.join(PROFILE_DIR, f"{st.session_state.kullanici_mail}.png")
    
    with st.sidebar:
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, use_container_width=True)
            st.divider()
            
        if os.path.exists(pp_path): st.image(pp_path, width=150)
        else: st.write("👤 *(Fotoğraf Yok)*")
            
        st.title(f"{st.session_state.kullanici_adi}")
        st.caption(f"{'👑 Yönetici' if st.session_state.kullanici_tipi == 'Yonetici' else 'Çalışan'}")
        st.divider()
        
        if st.session_state.kullanici_tipi == "Yonetici":
            menu_secenekleri = ["Yönetici Paneli", "Kesinleşen Liste", "Sistem Tasarımı", "Profilim"]
        else:
            menu_secenekleri = ["Vardiya İşlemleri", "Profilim"]
            
        sayfa = st.radio("Menü", menu_secenekleri)
        st.divider()
        
        def tam_cikis_yap():
            st.session_state.cikis_yapiliyor = True
            
        st.button("🚪 Çıkış Yap", on_click=tam_cikis_yap, use_container_width=True)

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
                st.success("Yüklendi! Yeni resminiz bir sonraki işlemde görünür olacaktır.")

        with col_bilgi:
            yeni_isim = st.text_input("Ad Soyad:", value=str(u_data["isim"]))
            yeni_tel = st.text_input("Telefon:", value=str(u_data["telefon"]))
            
            if st.session_state.kullanici_tipi != "Yonetici":
                idx_tip = 0 if u_data.get("calisma_tipi", "Tam Zamanlı") == "Tam Zamanlı" else 1
                yeni_tip = st.selectbox("Çalışma Tipi:", ["Tam Zamanlı", "Part-Time"], index=idx_tip)
            else:
                yeni_tip = u_data.get("calisma_tipi", "Tam Zamanlı")
                
            yeni_sifre = st.text_input("Şifre:", value=str(u_data["sifre"]), type="password")
            
            if st.button("Kaydet"):
                supabase.table('kullanicilar').update({
                    "isim": str(yeni_isim), "telefon": str(yeni_tel), "calisma_tipi": str(yeni_tip), "sifre": str(yeni_sifre)
                }).eq('email', st.session_state.kullanici_mail).execute()
                st.session_state.kullanici_adi = str(yeni_isim)
                st.session_state.calisma_tipi = str(yeni_tip)
                st.success("Profiliniz başarıyla güncellendi!"); st.rerun()

    elif sayfa == "Vardiya İşlemleri":
        st.header("📅 Haftalık Vardiya Planlaması")
        tab1, tab2, tab3 = st.tabs(["✍️ Planımı Gönder", "👀 Onaylananlar (Canlı Taslak)", "📊 Kesinleşen Liste"])
        
        with tab1:
            with st.form("personel_formu", clear_on_submit=True):
                # 1. GÜNLERİ BELİRLEME
                if st.session_state.calisma_tipi == "Part-Time":
                    st.info("ℹ️ Part-Time personel olarak sadece **ÇALIŞACAĞINIZ** günleri seçiniz.")
                    secilen_gunler = st.multiselect("✅ ÇALIŞACAĞINIZ Günleri Seçiniz:", gunler)
                    calisilan_gunler = secilen_gunler
                    izin_listesi = [g for g in gunler if g not in secilen_gunler]
                else:
                    st.info("ℹ️ Tam Zamanlı personelin haftada sadece 1 gün izin hakkı vardır.")
                    izin_secenekleri = ["❌ İzin İstemiyorum (Tam Hafta Çalışacağım)"] + gunler
                    secilen_gun = st.selectbox("🌴 İZİNLİ Olacağınız Günü Seçiniz:", izin_secenekleri)
                    if secilen_gun == "❌ İzin İstemiyorum (Tam Hafta Çalışacağım)":
                        calisilan_gunler = gunler
                        izin_listesi = []
                    else:
                        calisilan_gunler = [g for g in gunler if g != secilen_gun]
                        izin_listesi = [secilen_gun]

                # 2. VARDİYA BELİRLEME (YENİLENMİŞ MANTIK)
                karma_secimler = []
                
                if st.session_state.calisma_tipi == "Part-Time":
                    # PART-TIME: Karma vardiya zorunlu (En mantıklısı budur)
                    st.write("Seçtiğiniz günler için vardiyanızı ayarlayın:")
                    c1, c2 = st.columns(2)
                    for i, g in enumerate(calisilan_gunler):
                        with (c1 if i % 2 == 0 else c2):
                            sec = st.selectbox(f"{g}:", vardiya_secenekleri, key=f"karma_pt_{g}")
                            shift_kisa = "Sabahçı" if "Sabahçı" in sec else ("Akşamcı" if "Akşamcı" in sec else "Tam Gün")
                            karma_secimler.append(f"{g}: {shift_kisa}")
                    
                    if karma_secimler:
                        haftalik_shift = "Karma | " + ", ".join(karma_secimler)
                    else:
                        haftalik_shift = "Beklemede"
                else:
                    # TAM ZAMANLI: Sabit veya Karma seçebilir
                    vardiya_tipi = st.radio("Çalışma Düzeniniz:", ["Sabit Vardiya", "Karma Vardiya"])
                    if vardiya_tipi == "Sabit Vardiya":
                        sec_sabit = st.radio("Vardiyanız:", vardiya_secenekleri)
                        haftalik_shift = sec_sabit
                    else:
                        st.write("Günlük vardiya ayarınız:")
                        c1, c2 = st.columns(2)
                        for i, g in enumerate(calisilan_gunler):
                            with (c1 if i % 2 == 0 else c2):
                                sec = st.selectbox(f"{g}:", vardiya_secenekleri, key=f"karma_ft_{g}")
                                shift_kisa = "Sabahçı" if "Sabahçı" in sec else ("Akşamcı" if "Akşamcı" in sec else "Tam Gün")
                                karma_secimler.append(f"{g}: {shift_kisa}")
                        haftalik_shift = "Karma | " + ", ".join(karma_secimler)

                neden = st.text_area("Notunuz (İsteğe Bağlı):")
                
                if st.form_submit_button("Planımı Gönder"):
                    if st.session_state.calisma_tipi == "Part-Time" and len(secilen_gunler) == 0:
                        st.error("❌ Hata: En az bir çalışma günü seçmelisiniz.")
                    else:
                        izin_str = ", ".join(izin_listesi) if len(izin_listesi) > 0 else "İzin Yok"
                        benzersiz_kimlik = f"{st.session_state.kullanici_adi} ({st.session_state.kullanici_mail})"
                        yeni_talep = {"personel": benzersiz_kimlik, "izin_gunu": izin_str, "haftalik_vardiya": haftalik_shift, "neden": neden, "durum": "Beklemede"}
                        supabase.table('talepler').delete().eq('personel', benzersiz_kimlik).execute()
                        supabase.table('talepler').insert(yeni_talep).execute()
                        st.success("Talebiniz başarıyla iletildi.")
                    
        with tab2:
            c1, c2 = st.columns([4, 1])
            with c1: st.info("💡 Yönetimin şu ana kadar onayladığı güncel durumu gösterir.")
            with c2: 
                if st.button("🔄 Verileri Yenile", key="pers_yenile", use_container_width=True): st.rerun()
            taslak_df = get_taslak_df()
            if not taslak_df.empty: tabloyu_ciz(taslak_df)
            else: st.warning("Onaylı plan yok.")

        with tab3:
            if yayin_durumu == "YAYINLANDI":
                res_v = supabase.table('vardiyalar').select('*').execute()
                if res_v.data:
                    df_v = pd.DataFrame(res_v.data)
                    df_v.rename(columns={'personel': 'Personel'}, inplace=True)
                    tabloyu_ciz(df_v)
                else: st.warning("Liste boş.")
            else: st.warning("⚠️ Liste henüz yayınlanmadı.")

    elif sayfa == "Kesinleşen Liste":
        st.header("📊 Kesinleşen Vardiya Listesi")
        if yayin_durumu == "YAYINLANDI":
            res_v = supabase.table('vardiyalar').select('*').execute()
            if res_v.data:
                df_v = pd.DataFrame(res_v.data)
                df_v.rename(columns={'personel': 'Personel'}, inplace=True)
                tabloyu_ciz(df_v)
        else: st.warning("⚠️ Yayınlanmış liste yok.")

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
                    with st.expander(f"👤 {row['isim']} ({row['email']})"):
                        c1, c2 = st.columns(2)
                        if c1.button("Onayla", key=f"kon_{row['email']}"):
                            supabase.table('kullanicilar').update({'durum': 'Onaylandı'}).eq('email', row['email']).execute()
                            onay_mesaji = f"Merhaba {row['isim']},\n\nHesabınız onaylanmıştır. Linkten girebilirsiniz:\nhttps://ekonomi-dunyasi-yonetim-msu7zf86qlczbai2sb99am.streamlit.app"
                            mail_gonder(row['email'], "ED-AVM | Onay", onay_mesaji)
                            st.rerun()
                        if c2.button("Reddet", key=f"kred_{row['email']}"):
                            supabase.table('kullanicilar').delete().eq('email', row['email']).execute()
                            st.rerun()
                st.divider()
                st.subheader("Aktif Kullanıcılar")
                aktifler = df_k[df_k["durum"] == "Onaylandı"]
                for _, row in aktifler.iterrows():
                    exp_title = f"👑 {row['isim']}" if row['rol'] == 'Yonetici' else f"⚙️ {row['isim']} ({row['calisma_tipi']})"
                    with st.expander(exp_title):
                        st.write(f"Mail: {row['email']} | Tel: {row['telefon']}")
                        if row['rol'] != 'Yonetici':
                            idx_tip = 0 if row['calisma_tipi'] == "Tam Zamanlı" else 1
                            yeni_tip = st.selectbox("Tip:", ["Tam Zamanlı", "Part-Time"], index=idx_tip, key=f"tip_{row['email']}")
                            c1, c2 = st.columns(2)
                            if c1.button("💾 Güncelle", key=f"up_{row['email']}"):
                                supabase.table('kullanicilar').update({'calisma_tipi': yeni_tip}).eq('email', row['email']).execute(); st.rerun()
                            if row["email"] != st.session_state.kullanici_mail: 
                                if c2.button("🗑️ Sil", key=f"del_{row['email']}"):
                                    supabase.table('kullanicilar').delete().eq('email', row['email']).execute(); st.rerun()

        with tab_t:
            c1, c2 = st.columns([4, 1])
            with c1: st.subheader("1. Bekleyen Talepler")
            with c2: 
                if st.button("🔄 Yenile", key="yonetici_yenile", use_container_width=True): st.rerun()
            res_t = supabase.table('talepler').select('*').execute()
            df_t = pd.DataFrame(res_t.data) if res_t.data else pd.DataFrame()
            if not df_t.empty:
                bekleyen = df_t[df_t["durum"] == "Beklemede"]
                for _, row in bekleyen.iterrows():
                    p_name = str(row['personel']).split(' (')[0]
                    with st.expander(f"⏳ {p_name} | İzin: {row['izin_gunu']}"):
                        st.write(f"Talep Edilen: {row['haftalik_vardiya']}")
                        with st.form(key=f"onay_{row['id']}"):
                            is_karma = "Karma" in str(row['haftalik_vardiya'])
                            v_options = ["Kendi Karma Düzeni" if is_karma else "Kendi Seçimi"] + vardiya_secenekleri
                            yeni_v = st.radio("Kararınız:", v_options)
                            c1, c2 = st.columns(2)
                            if c1.form_submit_button("✅ Onayla"):
                                final_v = str(row['haftalik_vardiya']) if "Kendi" in yeni_v else yeni_v
                                supabase.table('talepler').update({'haftalik_vardiya': final_v, 'durum': 'Onaylandı'}).eq('id', row['id']).execute(); st.rerun()
                            if c2.form_submit_button("❌ Reddet"):
                                supabase.table('talepler').delete().eq('id', row['id']).execute(); st.rerun()

        with tab_m:
            st.subheader("🛠️ Manuel Atama")
            res_k = supabase.table('kullanicilar').select('isim, email').eq('durum', 'Onaylandı').neq('rol', 'Yonetici').execute()
            aktif_list = [f"{k['isim']} ({k['email']})" for k in res_k.data] if res_k.data else []
            if aktif_list:
                with st.form("manuel"):
                    p_sel = st.selectbox("Personel:", aktif_list)
                    i_sel = st.multiselect("İzinli:", gunler)
                    v_sel = st.radio("Vardiya:", vardiya_secenekleri)
                    if st.form_submit_button("Sisteme İşle"):
                        supabase.table('talepler').delete().eq('personel', p_sel).execute()
                        supabase.table('talepler').insert({"personel": p_sel, "izin_gunu": ", ".join(i_sel), "haftalik_vardiya": v_sel, "durum": "Onaylandı"}).execute(); st.success("Eklendi")

        with tab_y:
            st.subheader("Operasyon")
            if st.button("🔄 Sıfırla"):
                supabase.table('ayarlar').update({'deger': 'GIZLI'}).eq('ayar_adi', 'yayin_durumu').execute()
                supabase.table('talepler').delete().neq('id', 0).execute(); st.rerun()
            if st.button("🚀 Listeyi Yayınla"):
                taslak = get_taslak_df()
                if not taslak.empty:
                    supabase.table('vardiyalar').delete().neq('personel', 'x').execute()
                    for _, r in taslak.iterrows():
                        v_d = {"personel": r["Personel"]}
                        for g in gunler: v_d[g] = r[g]
                        supabase.table('vardiyalar').insert(v_d).execute()
                    supabase.table('ayarlar').update({'deger': 'YAYINLANDI'}).eq('ayar_adi', 'yayin_durumu').execute(); st.success("Yayınlandı")

        with tab_b:
            st.subheader("İK")
            res_b = supabase.table('basvurular').select('*').execute()
            if res_b.data:
                df_b = pd.DataFrame(res_b.data)
                for _, row in df_b[df_b["durum"] == "İnceleniyor"].iterrows():
                    with st.expander(f"👤 {row['ad_soyad']}"):
                        st.write(f"Tel: {row['telefon']} | Tecrübe: {row['tecrube']}")
                        if st.button("Kabul", key=f"bk_{row['id']}"): supabase.table('basvurular').update({'durum': 'Kabul'}).eq('id', row['id']).execute(); st.rerun()

    elif sayfa == "Sistem Tasarımı" and st.session_state.kullanici_tipi == "Yonetici":
        st.header("🎨 Tasarım")
        c1, c2 = st.columns(2)
        with c1:
            if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, width=150)
            l_up = st.file_uploader("Logo:")
            if l_up:
                with open(LOGO_PATH, "wb") as f: f.write(l_up.getbuffer())
                st.success("Kaydedildi. Yenileyin.")
        with c2:
            if os.path.exists(BG_PATH): st.image(BG_PATH, width=250)
            b_up = st.file_uploader("Arka Plan:")
            if b_up:
                with open(BG_PATH, "wb") as f: f.write(b_up.getbuffer())
                st.success("Kaydedildi. Yenileyin.")
