import streamlit as st
import pandas as pd
import os
import smtplib
import random
import string
import base64
import hashlib
import hmac
import time
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

# --- GÜVENLİK YARDIMCI FONKSİYONLARI ---
# Not: Eski düz metin şifreler, kullanıcı ilk başarılı giriş yaptığında otomatik hash formatına çevrilir.
HASH_ITERATIONS = 200_000
SESSION_MAX_AGE = 30 * 24 * 60 * 60  # 30 gün

def get_auth_secret():
    """Cookie oturum imzası için gizli anahtar.
    Streamlit Secrets içine şunu ekleyin:
    [auth]
    secret_key = "uzun-rastgele-bir-deger"
    """
    try:
        return st.secrets["auth"]["secret_key"]
    except Exception:
        # Uygulama hiç açılmasın diye sabit fallback veriyoruz; canlı kullanımda mutlaka değiştirin.
        return "CHANGE_ME__ED_AVM_AUTH_SECRET"

def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    pwd_hash = hashlib.pbkdf2_hmac(
        "sha256",
        str(password).encode("utf-8"),
        salt.encode("utf-8"),
        HASH_ITERATIONS
    ).hex()
    return f"pbkdf2_sha256${HASH_ITERATIONS}${salt}${pwd_hash}"

def verify_password(password: str, stored_password: str) -> bool:
    stored_password = str(stored_password or "")
    password = str(password or "")

    # Yeni güvenli format
    if stored_password.startswith("pbkdf2_sha256$"):
        try:
            _, iter_str, salt, expected_hash = stored_password.split("$", 3)
            test_hash = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt.encode("utf-8"),
                int(iter_str)
            ).hex()
            return hmac.compare_digest(test_hash, expected_hash)
        except Exception:
            return False

    # Geriye dönük uyumluluk: veritabanındaki eski düz metin şifreleri doğrular.
    return hmac.compare_digest(password, stored_password)

def make_session_token(email: str) -> str:
    exp = int(time.time()) + SESSION_MAX_AGE
    payload = f"{email}|{exp}"
    sig = hmac.new(
        get_auth_secret().encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}|{sig}".encode("utf-8")).decode("utf-8")

def parse_session_token(token: str):
    try:
        decoded = base64.urlsafe_b64decode(str(token).encode("utf-8")).decode("utf-8")
        email, exp_str, sig = decoded.rsplit("|", 2)
        payload = f"{email}|{exp_str}"
        expected_sig = hmac.new(
            get_auth_secret().encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        if int(exp_str) < int(time.time()):
            return None
        return email
    except Exception:
        return None

def safe_db_execute(query, fallback=None, show_error=False, error_message="Veritabanı işlemi başarısız."):
    try:
        return query.execute()
    except Exception as exc:
        if show_error:
            st.error(f"{error_message} Detay: {exc}")
        return fallback



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



# --- YÖNETİCİ GÜN BAZLI VARDİYA EDİTÖRÜ YARDIMCILARI ---
ADMIN_GUN_DURUMLARI = ["İzinli", "Sabahçı", "Akşamcı", "Tam Gün"]

def kisa_vardiya_etiketi(vardiya_metni: str) -> str:
    """Seçilen uzun vardiya metnini kısa, veritabanı uyumlu etikete çevirir."""
    vardiya_metni = str(vardiya_metni or "")
    if "Akşamcı" in vardiya_metni:
        return "Akşamcı"
    if "Tam" in vardiya_metni:
        return "Tam Gün"
    return "Sabahçı"

def izin_listesi_oku(izin_gunu: str):
    izin_gunu = str(izin_gunu or "")
    if izin_gunu.strip() in ["", "İzin Yok", "nan", "None"]:
        return []
    return [g for g in gunler if g in izin_gunu]

def vardiya_plani_oku(izin_gunu: str, haftalik_vardiya: str):
    """DB'deki izin_gunu + haftalik_vardiya alanlarından gün bazlı plan sözlüğü üretir."""
    izinler = izin_listesi_oku(izin_gunu)
    v_str = str(haftalik_vardiya or "")

    # Önce sabit vardiyaya göre tüm günlere varsayılan ata.
    if "Akşamcı" in v_str and "Karma" not in v_str:
        varsayilan = "Akşamcı"
    elif "Tam" in v_str and "Karma" not in v_str:
        varsayilan = "Tam Gün"
    else:
        varsayilan = "Sabahçı"

    plan = {g: varsayilan for g in gunler}

    # Karma metindeki gün özel seçimlerini oku.
    if "Karma" in v_str:
        for g in gunler:
            if f"{g}: Akşamcı" in v_str:
                plan[g] = "Akşamcı"
            elif f"{g}: Tam Gün" in v_str:
                plan[g] = "Tam Gün"
            elif f"{g}: Sabahçı" in v_str:
                plan[g] = "Sabahçı"

    # İzinli günler vardiyadan bağımsız olarak izinli kabul edilir.
    for g in izinler:
        plan[g] = "İzinli"

    return plan

def vardiya_plani_db_formatina_cevir(plan: dict):
    """Gün bazlı planı mevcut Supabase şemasına uyumlu iki string alana çevirir."""
    izinler = [g for g in gunler if plan.get(g) == "İzinli"]
    calisma_secimleri = [f"{g}: {plan.get(g, 'Sabahçı')}" for g in gunler if plan.get(g) != "İzinli"]

    izin_str = ", ".join(izinler) if izinler else "İzin Yok"
    vardiya_str = "Karma | " + ", ".join(calisma_secimleri) if calisma_secimleri else "Karma | Seçim Yok"
    return izin_str, vardiya_str

def gun_bazli_vardiya_editoru(prefix: str, izin_gunu: str = "İzin Yok", haftalik_vardiya: str = "Sabahçı"):
    """Yönetici ekranları için her günü ayrı düzenleten küçük editör."""
    mevcut_plan = vardiya_plani_oku(izin_gunu, haftalik_vardiya)
    yeni_plan = {}

    st.markdown("**Gün bazlı vardiya düzenleme:**")
    st.caption("Her gün için İzinli / Sabahçı / Akşamcı / Tam Gün seçebilirsiniz. Pazar listede mağaza kuralı gereği Tam Güç görünebilir; izin seçilirse izinli kalır.")

    c1, c2 = st.columns(2)
    for i, g in enumerate(gunler):
        with (c1 if i % 2 == 0 else c2):
            mevcut_deger = mevcut_plan.get(g, "Sabahçı")
            if mevcut_deger not in ADMIN_GUN_DURUMLARI:
                mevcut_deger = "Sabahçı"
            yeni_plan[g] = st.selectbox(
                f"{g}:",
                ADMIN_GUN_DURUMLARI,
                index=ADMIN_GUN_DURUMLARI.index(mevcut_deger),
                key=f"{prefix}_{g}"
            )

    return vardiya_plani_db_formatina_cevir(yeni_plan)

# --- MÜHENDİSLİK: Karma Vardiyayı Tabloda Çözümleyen Fonksiyon ---
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
                # Karma vardiya okuyucusu
                if "Karma" in v_str:
                    if f"{g}: Sabahçı" in v_str: shift = "S (09-18)"
                    elif f"{g}: Akşamcı" in v_str: shift = "A (12-21)"
                    elif f"{g}: Tam Gün" in v_str: shift = "T (09-21)"
                    else: shift = "S (09-18)" # Eğer karma listede yoksa varsayılan
                # Sabit vardiya okuyucusu
                else:
                    if "Akşamcı" in v_str: shift = "A (12-21)"
                    elif "Tam" in v_str: shift = "T (09-21)"
                    else: shift = "S (09-18)"
                
                taslak.at[p, g] = shift
            
    taslak.reset_index(inplace=True)
    taslak.rename(columns={'index': 'Personel'}, inplace=True)
    return taslak



def vardiya_sayaclarini_hesapla(df: pd.DataFrame):
    """Canlı taslak tablosundan gün gün vardiya/izin sayılarını çıkarır."""
    if df is None or df.empty:
        return pd.DataFrame(), []

    toplam_personel = len(df)
    ozet_satirlari = []
    uyarilar = []

    for g in gunler:
        sabahci = aksamci = tam_gun = tam_guc = izinli = belirsiz = 0

        for deger in df[g].astype(str).tolist():
            if "🔴" in deger:
                izinli += 1
            elif "🟢" in deger:
                tam_guc += 1
            elif "⏳" in deger:
                belirsiz += 1
            elif deger.startswith("S"):
                sabahci += 1
            elif deger.startswith("A"):
                aksamci += 1
            elif deger.startswith("T"):
                tam_gun += 1

        calisan = sabahci + aksamci + tam_gun + tam_guc
        ozet_satirlari.append({
            "Gün": g,
            "Sabahçı": sabahci,
            "Akşamcı": aksamci,
            "Tam Gün": tam_gun,
            "Tam Güç": tam_guc,
            "İzinli": izinli,
            "Belirsiz": belirsiz,
            "Toplam Çalışan": calisan,
        })

        if belirsiz > 0:
            uyarilar.append(f"{g}: {belirsiz} personelin planı belirsiz.")
        if g != "Pazar":
            if calisan == 0:
                uyarilar.append(f"{g}: Hiç çalışan görünmüyor. Yayınlamadan önce kontrol edin.")
            if sabahci == 0:
                uyarilar.append(f"{g}: Sabahçı personel yok.")
            if aksamci == 0:
                uyarilar.append(f"{g}: Akşamcı personel yok.")
        if toplam_personel > 0 and izinli >= max(2, round(toplam_personel * 0.5)):
            uyarilar.append(f"{g}: İzinli kişi sayısı yüksek ({izinli}/{toplam_personel}).")

    return pd.DataFrame(ozet_satirlari), uyarilar


def operasyon_ozetini_goster(df: pd.DataFrame, baslik="📌 Günlük Personel Sayacı ve Uyarılar"):
    """Yönetici için gün bazlı vardiya dağılımını ve risk uyarılarını gösterir."""
    if df is None or df.empty:
        st.info("Sayaç oluşturmak için onaylanmış plan bulunmuyor.")
        return

    st.subheader(baslik)
    ozet_df, uyarilar = vardiya_sayaclarini_hesapla(df)

    st.caption("Bu tablo sadece onaylanmış taleplerden oluşan canlı taslağa göre hesaplanır.")
    st.dataframe(ozet_df, use_container_width=True, hide_index=True)

    if uyarilar:
        with st.expander(f"⚠️ Operasyon uyarıları ({len(uyarilar)})", expanded=True):
            for u in uyarilar:
                st.warning(u)
    else:
        st.success("Şu an belirgin bir vardiya çakışması veya eksikliği görünmüyor.")

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
    try:
        cookies.remove('edavm_user_session')
        cookies.remove('edavm_user_mail')  # eski sürümden kalmış olabilir
    except Exception:
        pass
    st.query_params.clear()
    st.session_state.clear()
    st.session_state.update({"giris_yapildi": False, "cikis_yapiliyor": False, "az_once_cikis_yapti": True})

if st.session_state.get("yeni_cerez_yaz"):
    cookies.set('edavm_user_session', st.session_state.get("yeni_cerez_yaz"), max_age=SESSION_MAX_AGE)
    st.session_state.yeni_cerez_yaz = None

kayitli_token = cookies.get('edavm_user_session')
aktif_mail = parse_session_token(kayitli_token) if kayitli_token else None

# Eski sürümden kalan güvensiz mail cookie'si varsa temizle.
try:
    if cookies.get('edavm_user_mail'):
        cookies.remove('edavm_user_mail')
except Exception:
    pass

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
        else:
            try:
                cookies.remove('edavm_user_session')
            except Exception:
                pass
            st.query_params.clear()
    except Exception:
        pass

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
                res = supabase.table('kullanicilar').select('*').eq('email', email_in).execute()
                if res.data:
                    user = res.data[0]
                    if verify_password(sifre_in, user.get("sifre", "")):
                        if user["durum"] == "Onaylandı":
                            # Eski düz metin şifre varsa, ilk başarılı girişte otomatik güvenli hash'e çevir.
                            if not str(user.get("sifre", "")).startswith("pbkdf2_sha256$"):
                                supabase.table('kullanicilar').update({"sifre": hash_password(sifre_in)}).eq('email', user["email"]).execute()

                            if beni_hatirla:
                                st.session_state.yeni_cerez_yaz = make_session_token(user["email"])
                            else:
                                try:
                                    if cookies.get('edavm_user_session'): cookies.remove('edavm_user_session')
                                    if cookies.get('edavm_user_mail'): cookies.remove('edavm_user_mail')  # eski cookie temizliği
                                except Exception:
                                    pass
                            st.query_params.clear()

                            st.session_state.update({
                                "giris_yapildi": True, "kullanici_tipi": user["rol"], 
                                "kullanici_adi": user["isim"], "kullanici_mail": user["email"],
                                "calisma_tipi": user.get("calisma_tipi", "Tam Zamanlı"), "az_once_cikis_yapti": False 
                            })
                            st.rerun() 
                        else:
                            st.warning("⏳ Hesabınız onay bekliyor.")
                    else:
                        st.error("❌ E-posta veya şifre hatalı.")
                else:
                    st.error("❌ E-posta veya şifre hatalı.")

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
                        yeni_veri = {"isim": str(isim.strip().title()), "email": str(mail), "sifre": hash_password(sifre), "telefon": str(tel), "durum": "Beklemede", "rol": "Personel", "calisma_tipi": calisma_tipi}
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
                        supabase.table('kullanicilar').update({"sifre": hash_password(yeni_sifre)}).eq('email', st.session_state.reset_mail).execute()
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
                
            yeni_sifre = st.text_input("Yeni Şifre (değiştirmek istemiyorsanız boş bırakın):", type="password")
            
            if st.button("Kaydet"):
                guncel_veri = {
                    "isim": str(yeni_isim),
                    "telefon": str(yeni_tel),
                    "calisma_tipi": str(yeni_tip)
                }
                if yeni_sifre.strip():
                    guncel_veri["sifre"] = hash_password(yeni_sifre)

                supabase.table('kullanicilar').update(guncel_veri).eq('email', st.session_state.kullanici_mail).execute()
                st.session_state.kullanici_adi = str(yeni_isim)
                st.session_state.calisma_tipi = str(yeni_tip)
                st.success("Profiliniz başarıyla güncellendi!"); st.rerun()

    elif sayfa == "Vardiya İşlemleri":
        st.header("📅 Haftalık Vardiya Planlaması")
        tab1, tab2, tab3 = st.tabs(["✍️ Planımı Gönder", "👀 Onaylananlar (Canlı Taslak)", "📊 Kesinleşen Liste"])

        with tab1:
            secilen_gunler = []
            if st.session_state.calisma_tipi == "Part-Time":
                st.info("ℹ️ Part-Time personel olarak önce **çalışacağınız günleri**, sonra her gün için **vardiya saatinizi** seçiniz.")
                secilen_gunler = st.multiselect(
                    "✅ ÇALIŞACAĞINIZ Günleri Seçiniz:",
                    gunler,
                    key="pt_calisma_gunleri"
                )

            with st.form("personel_formu", clear_on_submit=True):
                # İZİN / ÇALIŞMA GÜNÜ TESPİTİ + VARDİYA SEÇİMİ
                karma_secimler = []

                if st.session_state.calisma_tipi == "Part-Time":
                    calisilan_gunler = secilen_gunler
                    izin_listesi = [g for g in gunler if g not in secilen_gunler]

                    if calisilan_gunler:
                        st.markdown("**Seçtiğiniz günler için vardiya tercihiniz:**")
                        st.caption("Part-Time personelde her seçilen gün ayrı ayrı Sabahçı / Akşamcı / Tam Gün olarak belirlenir.")
                        c1, c2 = st.columns(2)
                        for i, g in enumerate(calisilan_gunler):
                            with (c1 if i % 2 == 0 else c2):
                                sec = st.selectbox(
                                    f"{g} vardiyası:",
                                    vardiya_secenekleri,
                                    key=f"pt_vardiya_{g}"
                                )
                                shift_kisa = "Sabahçı" if "Sabahçı" in sec else ("Akşamcı" if "Akşamcı" in sec else "Tam Gün")
                                karma_secimler.append(f"{g}: {shift_kisa}")
                        haftalik_shift = "Karma | " + ", ".join(karma_secimler)
                    else:
                        haftalik_shift = "Karma | Seçim Yok"

                else:
                    st.info("ℹ️ İzin kullanmak istemiyorsanız ilgili seçeneği seçebilirsiniz.")
                    izin_secenekleri = ["❌ İzin İstemiyorum (Tam Hafta Çalışacağım)"] + gunler
                    secilen_gun = st.selectbox("🌴 İZİNLİ Olacağınız Günü Seçiniz:", izin_secenekleri)
                    if secilen_gun == "❌ İzin İstemiyorum (Tam Hafta Çalışacağım)":
                        calisilan_gunler = gunler
                        izin_listesi = []
                    else:
                        calisilan_gunler = [g for g in gunler if g != secilen_gun]
                        izin_listesi = [secilen_gun]

                    vardiya_tipi = st.radio("Çalışma Düzeniniz:", ["Sabit Vardiya (Tüm Hafta Aynı)", "Karma Vardiya (Günlere Göre Değişken)"])

                    if vardiya_tipi == "Sabit Vardiya (Tüm Hafta Aynı)":
                        haftalik_shift = st.radio("Vardiyanız:", vardiya_secenekleri)
                    else:
                        st.write("Aşağıdan her çalışma günü için vardiyanızı ayarlayabilirsiniz:")
                        st.caption("Not: Pazar günleri mağaza kuralı gereği tablolara her zaman 'Tam Güç' olarak yansıtılmaktadır.")
                        c1, c2 = st.columns(2)
                        for i, g in enumerate(calisilan_gunler):
                            with (c1 if i % 2 == 0 else c2):
                                sec = st.selectbox(f"{g} vardiyası:", vardiya_secenekleri, key=f"karma_{g}")
                                shift_kisa = "Sabahçı" if "Sabahçı" in sec else ("Akşamcı" if "Akşamcı" in sec else "Tam Gün")
                                karma_secimler.append(f"{g}: {shift_kisa}")

                        if karma_secimler:
                            haftalik_shift = "Karma | " + ", ".join(karma_secimler)
                        else:
                            haftalik_shift = "Karma | Seçim Yok"

                neden = st.text_area("Notunuz (İsteğe Bağlı):")

                if st.form_submit_button("Planımı Gönder"):
                    if st.session_state.calisma_tipi == "Part-Time" and len(secilen_gunler) == 0:
                        st.error("❌ Hata: Lütfen çalışacağınız günleri seçiniz.")
                    else:
                        izin_str = ", ".join(izin_listesi) if len(izin_listesi) > 0 else "İzin Yok"
                        benzersiz_kimlik = f"{st.session_state.kullanici_adi} ({st.session_state.kullanici_mail})"

                        yeni_talep = {
                            "personel": benzersiz_kimlik,
                            "izin_gunu": izin_str,
                            "haftalik_vardiya": haftalik_shift,
                            "neden": neden,
                            "durum": "Beklemede"
                        }

                        supabase.table('talepler').delete().eq('personel', benzersiz_kimlik).execute()
                        supabase.table('talepler').insert(yeni_talep).execute()
                        st.success("Talebiniz veritabanına işlendi ve yönetime iletildi.")

        with tab2:
            c1, c2 = st.columns([4, 1])
            with c1: st.info("💡 Yönetimin şu ana kadar onayladığı güncel durumu gösterir.")
            with c2: 
                if st.button("🔄 Verileri Yenile", key="pers_yenile", use_container_width=True): st.rerun()
                
            taslak_df = get_taslak_df()
            if not taslak_df.empty: 
                tabloyu_ciz(taslak_df)
            else: st.warning("Henüz onaylanmış bir plan yok.")

        with tab3:
            if yayin_durumu == "YAYINLANDI":
                res_v = supabase.table('vardiyalar').select('*').execute()
                if res_v.data:
                    df_v = pd.DataFrame(res_v.data)
                    df_v.rename(columns={'personel': 'Personel'}, inplace=True)
                    tabloyu_ciz(df_v)
                else: st.warning("Liste veritabanında boş.")
            else: st.warning("⚠️ Kesinleşmiş liste henüz yayınlanmamıştır.")

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
                    with st.expander(f"👤 {row['isim']} ({row['email']}) | {row.get('calisma_tipi', 'Tam Zamanlı')}"):
                        c1, c2 = st.columns(2)
                        if c1.button("Onayla", key=f"kon_{row['email']}"):
                            supabase.table('kullanicilar').update({'durum': 'Onaylandı'}).eq('email', row['email']).execute()
                            onay_mesaji = f"Merhaba {row['isim']},\n\nED-AVM portal hesabınız yönetim tarafından onaylanmıştır. Aşağıdaki linkten giriş yapabilirsiniz:\nhttps://ekonomi-dunyasi-yonetim-msu7zf86qlczbai2sb99am.streamlit.app\n\nİyi çalışmalar."
                            mail_gonder(row['email'], "ED-AVM | Hesabınız Onaylandı", onay_mesaji)
                            st.rerun()
                        if c2.button("Reddet", key=f"kred_{row['email']}"):
                            supabase.table('kullanicilar').delete().eq('email', row['email']).execute()
                            st.rerun()
                
                st.divider()
                st.subheader("Aktif Kullanıcılar")
                aktifler = df_k[df_k["durum"] == "Onaylandı"]
                for _, row in aktifler.iterrows():
                    mevcut_tip = row.get("calisma_tipi", "Tam Zamanlı")
                    
                    if row['rol'] == 'Yonetici':
                        expander_title = f"👑 {row['isim']} (Yönetici)"
                    else:
                        expander_title = f"⚙️ {row['isim']} ({row['rol']} - {mevcut_tip})"
                        
                    with st.expander(expander_title):
                        st.write(f"Mail: {row['email']} | Tel: {row['telefon']}")
                        
                        if row['rol'] != 'Yonetici':
                            idx_tip = 0 if mevcut_tip == "Tam Zamanlı" else 1
                            yeni_tip = st.selectbox("Çalışma Tipi:", ["Tam Zamanlı", "Part-Time"], index=idx_tip, key=f"tip_{row['email']}")
                            
                            c1, c2 = st.columns(2)
                            if c1.button("💾 Tipi Güncelle", key=f"kguncel_{row['email']}"):
                                supabase.table('kullanicilar').update({'calisma_tipi': yeni_tip}).eq('email', row['email']).execute()
                                st.rerun()
                            if row["email"] != st.session_state.kullanici_mail: 
                                if c2.button("🗑️ Kullanıcıyı Sil", key=f"kdel_{row['email']}"):
                                    benzersiz_isim = f"{row['isim']} ({row['email']})"
                                    supabase.table('talepler').delete().eq('personel', benzersiz_isim).execute()
                                    supabase.table('vardiyalar').delete().eq('personel', benzersiz_isim).execute()
                                    supabase.table('kullanicilar').delete().eq('email', row['email']).execute()
                                    st.rerun()
                        else:
                            st.info("💡 Yönetici hesaplarında çalışma veya vardiya tipi aranmaz.")

        with tab_t:
            taslak_df_sayac = get_taslak_df()
            operasyon_ozetini_goster(taslak_df_sayac)
            st.divider()

            c1, c2 = st.columns([4, 1])
            with c1: st.subheader("1. Bekleyen Talepler")
            with c2: 
                if st.button("🔄 Talepleri Yenile", key="yonetici_yenile", use_container_width=True): st.rerun()
            
            res_t = supabase.table('talepler').select('*').execute()
            df_t = pd.DataFrame(res_t.data) if res_t.data else pd.DataFrame()
            
            if not df_t.empty:
                bekleyen_talepler = df_t[df_t["durum"] == "Beklemede"]
                if len(bekleyen_talepler) > 0:
                    for _, row in bekleyen_talepler.iterrows():
                        personel_adi = str(row['personel']).split(' (')[0] if ' (' in str(row['personel']) else str(row['personel'])
                        with st.expander(f"⏳ {personel_adi} | İzin: {row['izin_gunu']} | Vardiya: {row['haftalik_vardiya']}"):
                            if pd.notna(row['neden']) and str(row['neden']).strip() != "": st.write(f"**Not:** {row['neden']}")
                            with st.form(key=f"ilk_onay_{row['id']}"):
                                yeni_izin_str, final_vardiya = gun_bazli_vardiya_editoru(
                                    prefix=f"bekleyen_{row['id']}",
                                    izin_gunu=row['izin_gunu'],
                                    haftalik_vardiya=row['haftalik_vardiya']
                                )

                                c1, c2 = st.columns(2)
                                if c1.form_submit_button("✅ Onayla"):
                                    supabase.table('talepler').update({
                                        'izin_gunu': yeni_izin_str,
                                        'haftalik_vardiya': final_vardiya,
                                        'durum': 'Onaylandı'
                                    }).eq('id', row['id']).execute()
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
                        personel_adi = str(row['personel']).split(' (')[0] if ' (' in str(row['personel']) else str(row['personel'])
                        with st.expander(f"✅ {personel_adi} | İzin: {row['izin_gunu']} | Vardiya: {row['haftalik_vardiya']}"):
                            if pd.notna(row['neden']) and str(row['neden']).strip() != "": st.write(f"**Not:** {row['neden']}")
                            with st.form(key=f"duzenle_onayli_{row['id']}"):
                                guncel_izin_str, final_vardiya = gun_bazli_vardiya_editoru(
                                    prefix=f"onayli_{row['id']}",
                                    izin_gunu=row['izin_gunu'],
                                    haftalik_vardiya=row['haftalik_vardiya']
                                )

                                c1, c2, c3 = st.columns(3)
                                if c1.form_submit_button("🔄 Güncelle"):
                                    supabase.table('talepler').update({
                                        'izin_gunu': guncel_izin_str,
                                        'haftalik_vardiya': final_vardiya
                                    }).eq('id', row['id']).execute()
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
            if not taslak_df.empty: 
                tabloyu_ciz(taslak_df)

        with tab_m:
            st.subheader("🛠️ Manuel Vardiya Atama")
            res_k = supabase.table('kullanicilar').select('isim, email').eq('durum', 'Onaylandı').neq('rol', 'Yonetici').execute()
            aktif_personel_listesi = [f"{k['isim']} ({k['email']})" for k in res_k.data] if res_k.data else []
            
            if len(aktif_personel_listesi) > 0:
                with st.form("manuel_atama"):
                    secilen_kisi = st.selectbox("Personel:", aktif_personel_listesi)
                    izin_str, secilen_vardiya = gun_bazli_vardiya_editoru(
                        prefix="manuel_atama",
                        izin_gunu="İzin Yok",
                        haftalik_vardiya="Sabahçı"
                    )
                    if st.form_submit_button("Sisteme İşle (Onaylı)"):
                        supabase.table('talepler').delete().eq('personel', secilen_kisi).execute()
                        yeni_manuel = {
                            "personel": secilen_kisi,
                            "izin_gunu": izin_str,
                            "haftalik_vardiya": secilen_vardiya,
                            "neden": "Yönetici Manuel Atama",
                            "durum": "Onaylandı"
                        }
                        supabase.table('talepler').insert(yeni_manuel).execute()
                        st.success("Veritabanına eklendi!"); st.rerun()
            else:
                st.warning("Sistemde aktif personel bulunmuyor.")

        with tab_y:
            st.subheader("Haftalık Operasyon Kontrolü")
            taslak_df_yayin_kontrol = get_taslak_df()
            operasyon_ozetini_goster(taslak_df_yayin_kontrol, baslik="📌 Yayın Öncesi Günlük Kontrol")
            st.divider()

            if st.button("🔄 Yeni Haftaya Başla (Sıfırla)"):
                supabase.table('ayarlar').update({'deger': 'GIZLI'}).eq('ayar_adi', 'yayin_durumu').execute()
                supabase.table('talepler').delete().neq('id', 0).execute() 
                st.success("Veritabanı sıfırlandı. Tertemiz bir haftaya başlandı."); st.rerun()
            
            st.divider()
            col_yayin, col_mail = st.columns(2)
            with col_yayin:
                if st.button("🚀 Listeyi Kesinleştir ve Yayınla"):
                    taslak_df = get_taslak_df()
                    if not taslak_df.empty:
                        supabase.table('vardiyalar').delete().neq('personel', 'x').execute()
                        for _, row in taslak_df.iterrows():
                            v_data = {"personel": row["Personel"]}
                            for g in gunler: v_data[g] = row[g]
                            supabase.table('vardiyalar').insert(v_data).execute()
                        supabase.table('ayarlar').update({'deger': 'YAYINLANDI'}).eq('ayar_adi', 'yayin_durumu').execute()
                        supabase.table('talepler').delete().neq('id', 0).execute()
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
            
    elif sayfa == "Sistem Tasarımı" and st.session_state.kullanici_tipi == "Yonetici":
        st.header("🎨 Sistemi Özelleştir")
        st.write("Sitenizin arayüzünü bir WordPress paneli gibi kolayca özelleştirin.")
        st.divider()
        
        c1, c2 = st.columns(2)
        with c1:
            st.write("**1. Firma Logosu**")
            st.caption("Sol menüde ve giriş ekranında en üstte görünür.")
            if os.path.exists(LOGO_PATH): 
                st.image(LOGO_PATH, width=150)
            yeni_logo = st.file_uploader("Yeni Logo Yükle (PNG/JPG)", type=['png','jpg','jpeg'], key="logo_up")
            if yeni_logo is not None:
                with open(LOGO_PATH, "wb") as f: f.write(yeni_logo.getbuffer())
                st.success("Logo başarıyla kaydedildi! Sayfayı yenilediğinizde (F5) aktif olacak.")
                
            if st.button("🗑️ Logoyu Kaldır") and os.path.exists(LOGO_PATH):
                os.remove(LOGO_PATH); st.rerun()
                
        with c2:
            st.write("**2. Arka Plan Görseli**")
            st.caption("Sitenin tüm arka planını kaplar (Açık renkli fotolar önerilir).")
            if os.path.exists(BG_PATH): 
                st.image(BG_PATH, width=250)
            yeni_bg = st.file_uploader("Yeni Arka Plan Yükle (PNG/JPG)", type=['png','jpg','jpeg'], key="bg_up")
            if yeni_bg is not None:
                with open(BG_PATH, "wb") as f: f.write(yeni_bg.getbuffer())
                st.success("Arka plan başarıyla kaydedildi! Sayfayı yenilediğinizde (F5) aktif olacak.")
                
            if st.button("🗑️ Arka Planı Kaldır") and os.path.exists(BG_PATH):
                os.remove(BG_PATH); st.rerun()
