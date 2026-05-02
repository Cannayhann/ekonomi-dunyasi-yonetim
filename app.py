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
    st.error("⚠️ Veritabanı bağlantı hatası! Secrets ayarlarınızı kontrol edin.")
    st.stop()

# --- YARDIMCI FONKSİYONLAR ---
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
    except: return False

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
    taslak = pd.DataFrame(index=aktifler, columns=gunler).fillna("⏳ Belirsiz")
    res_t = supabase.table('talepler').select('*').eq('durum', 'Onaylandı').execute()
    onayli = res_t.data if res_t.data else []
    for r in onayli:
        p = str(r["personel"])
        if p not in taslak.index: continue
        iz_str, v_str = str(r["izin_gunu"]), str(r["haftalik_vardiya"])
        for g in gunler:
            if g in iz_str: taslak.at[p, g] = "🔴 İZİNLİ"
            elif g == "Pazar": taslak.at[p, g] = "🟢 TAM GÜÇ"
            else:
                if "Karma" in v_str:
                    if f"{g}: Sabahçı" in v_str: shift = "S (09-18)"
                    elif f"{g}: Akşamcı" in v_str: shift = "A (12-21)"
                    elif f"{g}: Tam Gün" in v_str: shift = "T (09-21)"
                    else: shift = "S (09-18)"
                else:
                    shift = "A (12-21)" if "Akşamcı" in v_str else ("T (09-21)" if "Tam" in v_str else "S (09-18)")
                taslak.at[p, g] = shift
    return taslak.reset_index().rename(columns={'index': 'Personel'})

# ==========================================
# SİSTEM HAFIZASI (ÇEREZ) VE GİRİŞ KONTROLÜ
# ==========================================
cookies = CookieController()
if "giris_yapildi" not in st.session_state:
    st.session_state.update({
        "giris_yapildi": False, "kullanici_tipi": "", "kullanici_adi": "", 
        "kullanici_mail": "", "reset_kod": "", "reset_mail": "", 
        "calisma_tipi": "", "cikis_yapiliyor": False, "az_once_cikis_yapti": False
    })

if st.session_state.get("cikis_yapiliyor"):
    try: cookies.remove('edavm_user_mail')
    except: pass
    st.session_state.clear()
    st.session_state.update({"giris_yapildi": False, "az_once_cikis_yapti": True})
    st.rerun()

if not st.session_state.get("giris_yapildi") and not st.session_state.get("az_once_cikis_yapti"):
    kayitli_mail = cookies.get('edavm_user_mail')
    if kayitli_mail:
        try:
            res = supabase.table('kullanicilar').select('*').eq('email', kayitli_mail).execute()
            if res.data and res.data[0]["durum"] == "Onaylandı":
                u = res.data[0]
                st.session_state.update({
                    "giris_yapildi": True, "kullanici_tipi": u["rol"], 
                    "kullanici_adi": u["isim"], "kullanici_mail": u["email"],
                    "calisma_tipi": u.get("calisma_tipi", "Tam Zamanlı")
                })
        except: pass

# ==========================================
# GİRİŞ / KAYIT / SIFIRLAMA EKRANLARI
# ==========================================
if not st.session_state.giris_yapildi:
    col_logo, col_baslik = st.columns([1, 8])
    with col_logo:
        if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, width=80)
    with col_baslik: st.title("🏢 Ekonomi Dünyası AVM Portalı")
    st.markdown("---")
    
    col_form, _ = st.columns([2, 1])
    with col_form:
        sekme = st.radio("İşlem Seçiniz", ["🔑 Giriş Yap", "📝 Kayıt Ol", "❓ Şifremi Unuttum", "👔 İş Başvurusu"], horizontal=True)

        if sekme == "🔑 Giriş Yap":
            email_in = st.text_input("E-posta").strip().lower()
            sifre_in = st.text_input("Şifre", type="password")
            beni_hatirla = st.checkbox("Beni Hatırla", value=False)
            if st.button("Sisteme Gir", use_container_width=True):
                res = supabase.table('kullanicilar').select('*').eq('email', email_in).eq('sifre', sifre_in).execute()
                if res.data:
                    u = res.data[0]
                    if u["durum"] == "Onaylandı":
                        if beni_hatirla: cookies.set('edavm_user_mail', u["email"], max_age=30*24*60*60)
                        st.session_state.update({
                            "giris_yapildi": True, "kullanici_tipi": u["rol"], 
                            "kullanici_adi": u["isim"], "kullanici_mail": u["email"],
                            "calisma_tipi": u.get("calisma_tipi", "Tam Zamanlı")
                        })
                        st.rerun()
                    else: st.warning("⏳ Hesabınız yönetim onayı bekliyor.")
                else: st.error("❌ Hatalı e-posta veya şifre.")

        elif sekme == "📝 Kayıt Ol":
            with st.form("kayit_formu"):
                isim = st.text_input("Ad Soyad")
                mail = st.text_input("E-posta").strip().lower()
                tel = st.text_input("Telefon")
                tip = st.selectbox("Çalışma Şekli", ["Tam Zamanlı", "Part-Time"])
                sifre = st.text_input("Şifre", type="password")
                if st.form_submit_button("Kayıt Talebi Gönder"):
                    if isim and mail and sifre:
                        check = supabase.table('kullanicilar').select('email').eq('email', mail).execute()
                        if check.data: st.error("Bu mail zaten kayıtlı.")
                        else:
                            supabase.table('kullanicilar').insert({"isim": isim.title(), "email": mail, "telefon": tel, "sifre": sifre, "durum": "Beklemede", "rol": "Personel", "calisma_tipi": tip}).execute()
                            mail_gonder(mail, "Kayıt Alındı", f"Merhaba {isim}, talebiniz iletildi. Onaylanınca haber vereceğiz.")
                            st.success("Kayıt iletildi, onay bekleyin.")
                    else: st.warning("Lütfen boş alan bırakmayın.")

        elif sekme == "❓ Şifremi Unuttum":
            if not st.session_state.get("reset_kod"):
                m_res = st.text_input("Mail Adresiniz:")
                if st.button("Kod Gönder"):
                    res = supabase.table('kullanicilar').select('email').eq('email', m_res.strip().lower()).execute()
                    if res.data:
                        kod = kod_uret()
                        st.session_state.update({"reset_kod": kod, "reset_mail": m_res.strip().lower()})
                        mail_gonder(m_res, "Şifre Sıfırlama", f"Kodunuz: {kod}")
                        st.info("Kod mailinize gönderildi.")
                    else: st.error("Mail bulunamadı.")
            else:
                k_in = st.text_input("Kodu Girin:")
                s_yeni = st.text_input("Yeni Şifre:", type="password")
                if st.button("Güncelle"):
                    if k_in == st.session_state.reset_kod:
                        supabase.table('kullanicilar').update({"sifre": s_yeni}).eq('email', st.session_state.reset_mail).execute()
                        st.success("Şifre değişti!"); st.session_state.reset_kod = ""
                    else: st.error("Kod yanlış.")

        elif sekme == "👔 İş Başvurusu":
            with st.form("ik_form"):
                b_ad = st.text_input("Ad Soyad")
                b_tel = st.text_input("Tel")
                b_poz = st.selectbox("Pozisyon", ["Satış", "Kasa", "Depo"])
                b_tec = st.text_area("Tecrübe")
                if st.form_submit_button("Başvur"):
                    supabase.table('basvurular').insert({"ad_soyad": b_ad, "telefon": b_tel, "pozisyon": b_poz, "tecrube": b_tec, "durum": "İnceleniyor", "tarih": datetime.now().strftime("%Y-%m-%d")}).execute()
                    st.success("Başvuru alındı.")

# ==========================================
# ANA SİSTEM PANELİ
# ==========================================
else:
    with st.sidebar:
        if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, use_container_width=True); st.divider()
        st.title(f"{st.session_state.kullanici_adi}")
        st.caption(f"🛡️ {st.session_state.kullanici_tipi} | {st.session_state.calisma_tipi}")
        m_list = ["Yönetici Paneli", "Kesinleşen Liste", "Sistem Tasarımı", "Profilim"] if st.session_state.kullanici_tipi == "Yonetici" else ["Vardiya İşlemleri", "Profilim"]
        sayfa = st.radio("Menü", m_list)
        if st.button("🚪 Çıkış Yap", use_container_width=True):
            st.session_state.cikis_yapiliyor = True; st.rerun()

    # --- PERSONEL SAYFASI ---
    if sayfa == "Vardiya İşlemleri":
        st.header("📅 Haftalık Vardiya Planlaması")
        tab1, tab2, tab3 = st.tabs(["✍️ Planımı Gönder", "👀 Canlı Taslak", "📊 Kesin Liste"])
        
        with tab1:
            if st.session_state.calisma_tipi == "Part-Time":
                st.info("ℹ️ Sadece **ÇALIŞACAĞINIZ** günleri seçiniz.")
                sec_gunler = st.multiselect("✅ Günleri Seçiniz:", gunler)
                calis_gun = sec_gunler
                iz_list = [g for g in gunler if g not in sec_gunler]
            else:
                st.info("ℹ️ Haftalık 1 gün izin hakkınız vardır.")
                iz_sec = ["❌ İzin İstemiyorum"] + gunler
                s_gun = st.selectbox("🌴 İzinli Günü Seçiniz:", iz_sec)
                calis_gun = gunler if s_gun == "❌ İzin İstemiyorum" else [g for g in gunler if g != s_gun]
                iz_list = [] if s_gun == "❌ İzin İstemiyorum" else [s_gun]

            if (st.session_state.calisma_tipi == "Part-Time" and len(sec_gunler) > 0) or st.session_state.calisma_tipi == "Tam Zamanlı":
                with st.form("v_onay"):
                    k_secim = []
                    if st.session_state.calisma_tipi == "Part-Time":
                        c1, c2 = st.columns(2)
                        for i, g in enumerate(calis_gun):
                            with (c1 if i % 2 == 0 else c2):
                                s = st.selectbox(f"{g}:", vardiya_secenekleri, key=f"p_{g}")
                                k_secim.append(f"{g}: {'Sabahçı' if 'Sabah' in s else ('Akşamcı' if 'Akşam' in s else 'Tam Gün')}")
                        h_sh = "Karma | " + ", ".join(k_secim)
                    else:
                        v_t = st.radio("Düzen:", ["Sabit", "Karma"], horizontal=True)
                        if v_t == "Sabit": h_sh = st.radio("Vardiya:", vardiya_secenekleri)
                        else:
                            c1, c2 = st.columns(2)
                            for i, g in enumerate(calis_gun):
                                with (c1 if i % 2 == 0 else c2):
                                    s = st.selectbox(f"{g}:", vardiya_secenekleri, key=f"t_{g}")
                                    k_secim.append(f"{g}: {'Sabahçı' if 'Sabah' in s else ('Akşamcı' if 'Akşam' in s else 'Tam Gün')}")
                            h_sh = "Karma | " + ", ".join(k_secim)
                    
                    not_v = st.text_area("Not (Opsiyonel):")
                    if st.form_submit_button("Planı Gönder"):
                        b_id = f"{st.session_state.kullanici_adi} ({st.session_state.kullanici_mail})"
                        supabase.table('talepler').delete().eq('personel', b_id).execute()
                        supabase.table('talepler').insert({"personel": b_id, "izin_gunu": ", ".join(iz_list), "haftalik_vardiya": h_sh, "neden": not_v, "durum": "Beklemede"}).execute()
                        st.success("İletildi!"); st.balloons()

        with tab2:
            st.button("🔄 Verileri Yenile", on_click=lambda: st.rerun())
            tabloyu_ciz(get_taslak_df())

    # --- YÖNETİCİ SAYFASI ---
    elif sayfa == "Yönetici Paneli":
        st.header("👑 Yönetim Paneli")
        t1, t2, t3, t4, t5 = st.tabs(["👥 Kullanıcılar", "📥 Talepler", "🛠️ Manuel", "🚀 Yayınla", "👔 İK"])
        
        with t2:
            st.button("🔄 Talepleri Yenile", key="y_ref")
            res_t = supabase.table('talepler').select('*').eq('durum', 'Beklemede').execute()
            if res_t.data:
                for r in res_t.data:
                    p_ad = r['personel'].split(' (')[0]
                    with st.expander(f"⏳ {p_ad} | İzin: {r['izin_gunu']}"):
                        st.write(f"Talep: {r['haftalik_vardiya']}")
                        with st.form(f"f_{r['id']}"):
                            karar = st.radio("Karar:", ["Kendi Düzeni"] + vardiya_secenekleri)
                            if st.form_submit_button("Onayla"):
                                final = r['haftalik_vardiya'] if "Kendi" in karar else karar
                                supabase.table('talepler').update({'haftalik_vardiya': final, 'durum': 'Onaylandı'}).eq('id', r['id']).execute(); st.rerun()

        with t1:
            res_u = supabase.table('kullanicilar').select('*').execute()
            for u in res_u.data:
                label = f"👤 {u['isim']} (ONAY BEKLİYOR)" if u['durum'] == "Beklemede" else (f"👑 {u['isim']}" if u['rol'] == 'Yonetici' else f"⚙️ {u['isim']} ({u['calisma_tipi']})")
                with st.expander(label):
                    if u['durum'] == "Beklemede":
                        if st.button("Onayla", key=f"o_{u['email']}"):
                            supabase.table('kullanicilar').update({'durum': 'Onaylandı'}).eq('email', u['email']).execute()
                            mail_gonder(u['email'], "Onay", "Hesabınız açıldı: https://ekonomi-dunyasi-yonetim-msu7zf86qlczbai2sb99am.streamlit.app")
                            st.rerun()
                    elif u['rol'] != 'Yonetici':
                        n_t = st.selectbox("Tip:", ["Tam Zamanlı", "Part-Time"], index=0 if u['calisma_tipi']=="Tam Zamanlı" else 1, key=f"tip_{u['email']}")
                        if st.button("Güncelle", key=f"gu_{u['email']}"):
                            supabase.table('kullanicilar').update({'calisma_tipi': n_t}).eq('email', u['email']).execute(); st.rerun()
                        if st.button("🗑️ Sil", key=f"si_{u['email']}"):
                            b_name = f"{u['isim']} ({u['email']})"
                            supabase.table('talepler').delete().eq('personel', b_name).execute()
                            supabase.table('kullanicilar').delete().eq('email', u['email']).execute(); st.rerun()

        with t4:
            if st.button("🔄 Haftayı Sıfırla"):
                supabase.table('ayarlar').update({'deger': 'GIZLI'}).eq('ayar_adi', 'yayin_durumu').execute()
                supabase.table('talepler').delete().neq('id', 0).execute(); st.rerun()
            if st.button("🚀 Listeyi Yayınla"):
                df = get_taslak_df()
                if not df.empty:
                    supabase.table('vardiyalar').delete().neq('personel', 'x').execute()
                    for _, r in df.iterrows():
                        v_d = {"personel": r["Personel"]}
                        for g in gunler: v_d[g] = r[g]
                        supabase.table('vardiyalar').insert(v_d).execute()
                    supabase.table('ayarlar').update({'deger': 'YAYINLANDI'}).eq('ayar_adi', 'yayin_durumu').execute()
                    st.success("Yayınlandı!")

    elif sayfa == "Sistem Tasarımı":
        st.header("🎨 Tasarım Paneli")
        c1, c2 = st.columns(2)
        with c1:
            if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, width=150)
            l_up = st.file_uploader("Logo:")
            if l_up:
                with open(LOGO_PATH, "wb") as f: f.write(l_up.getbuffer())
                st.success("Kaydedildi. Sayfayı yenileyin (F5).")
        with c2:
            if os.path.exists(BG_PATH): st.image(BG_PATH, width=250)
            b_up = st.file_uploader("Arka Plan:")
            if b_up:
                with open(BG_PATH, "wb") as f: f.write(b_up.getbuffer())
                st.success("Kaydedildi. Sayfayı yenileyin (F5).")

    elif sayfa == "Profilim":
        res_p = supabase.table('kullanicilar').select('*').eq('email', st.session_state.kullanici_mail).execute()
        p_data = res_p.data[0]
        st.header("👤 Profil Düzenle")
        c_f, c_b = st.columns([1, 2])
        pp_f = os.path.join(PROFILE_DIR, f"{st.session_state.kullanici_mail}.png")
        with c_f:
            if os.path.exists(pp_f): st.image(pp_f, width=200)
            f_u = st.file_uploader("Fotoğraf:")
            if f_u:
                with open(pp_f, "wb") as f: f.write(f_u.getbuffer())
                st.rerun()
        with c_b:
            n_i = st.text_input("Ad Soyad:", value=p_data["isim"])
            n_t = st.text_input("Telefon:", value=p_data["telefon"])
            n_s = st.text_input("Şifre:", value=p_data["sifre"], type="password")
            if st.button("Kaydet"):
                supabase.table('kullanicilar').update({"isim": n_i, "telefon": n_t, "sifre": n_s}).eq('email', st.session_state.kullanici_mail).execute()
                st.success("Güncellendi!")

    elif sayfa == "Kesinleşen Liste":
        st.header("📊 Yayınlanmış Vardiya Listesi")
        if yayin_durumu == "YAYINLANDI":
            res_v = supabase.table('vardiyalar').select('*').execute()
            if res_v.data:
                df_v = pd.DataFrame(res_v.data).rename(columns={'personel': 'Personel'})
                tabloyu_ciz(df_v)
        else: st.warning("⚠️ Henüz yayınlanmış bir liste bulunmamaktadır.")
