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
import json
from email.mime.text import MIMEText
from datetime import datetime
from supabase import create_client
from streamlit_cookies_controller import CookieController


# =========================================================
# 1. TEMEL AYARLAR
# =========================================================
st.set_page_config(page_title="ED-AVM Yönetim", layout="wide")

PROFILE_DIR = "profil_fotograflari"
THEME_DIR = "tema_dosyalari"
os.makedirs(PROFILE_DIR, exist_ok=True)
os.makedirs(THEME_DIR, exist_ok=True)

LOGO_PATH = os.path.join(THEME_DIR, "logo.png")
BG_PATH = os.path.join(THEME_DIR, "arkaplan.png")

STORAGE_BUCKET = "edavm-assets"
LOGO_STORAGE_PATH = "theme/logo.png"
BG_STORAGE_PATH = "theme/arkaplan.png"

gunler = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

vardiya_secenekleri = [
    "Sabahçı (09:00 - 18:00)",
    "Akşamcı (12:00 - 21:00)",
    "Tam Gün (09:00 - 21:00)"
]

OPERASYON_ROLLERI = [
    "Alt Kat",
    "Giriş Kat",
    "Üst Kat",
    "Dış Alan",
    "Dinamik Destek",
    "Destek"
]

ADMIN_GUN_DURUMLARI = ["İzinli", "Sabahçı", "Akşamcı", "Tam Gün"]

DEFAULT_PEAK_MINIMUMS = {
    "Alt Kat": 5,
    "Giriş Kat": 2,
    "Üst Kat": 1,
    "Dış Alan": 1,
    "Dinamik Destek": 1,
    "Destek": 0,
    "Toplam Aktif": 8
}

HASH_ITERATIONS = 200_000
SESSION_MAX_AGE = 30 * 24 * 60 * 60


# =========================================================
# 2. SUPABASE BAĞLANTISI
# =========================================================
@st.cache_resource
def init_connection():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

try:
    supabase = init_connection()
except Exception:
    st.error("⚠️ Veritabanı bağlantı hatası! Streamlit Secrets ayarlarınızı kontrol edin.")
    st.stop()


# =========================================================
# 3. GÜVENLİK / AUTH
# =========================================================
def get_auth_secret():
    try:
        return st.secrets["auth"]["secret_key"]
    except Exception:
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


# =========================================================
# 4. STORAGE / TEMA
# =========================================================
def storage_public_url(path: str):
    try:
        return supabase.storage.from_(STORAGE_BUCKET).get_public_url(path)
    except Exception:
        return None

def storage_file_exists(path: str) -> bool:
    try:
        folder, filename = os.path.split(path)
        items = supabase.storage.from_(STORAGE_BUCKET).list(folder)
        return any(item.get("name") == filename for item in items)
    except Exception:
        return False

def storage_image_url(path: str):
    if storage_file_exists(path):
        url = storage_public_url(path)
        if url:
            return f"{url}?v={int(time.time())}"
    return None

def upload_storage_file(uploaded_file, path: str):
    try:
        file_bytes = uploaded_file.getvalue()
        content_type = getattr(uploaded_file, "type", None) or "image/png"

        try:
            supabase.storage.from_(STORAGE_BUCKET).remove([path])
        except Exception:
            pass

        supabase.storage.from_(STORAGE_BUCKET).upload(
            path,
            file_bytes,
            file_options={"content-type": content_type}
        )
        return True, None
    except Exception as exc:
        return False, str(exc)

def remove_storage_file(path: str):
    try:
        supabase.storage.from_(STORAGE_BUCKET).remove([path])
        return True, None
    except Exception as exc:
        return False, str(exc)

def profile_storage_path(email: str) -> str:
    safe_email = str(email).lower().replace("@", "_at_").replace(".", "_")
    return f"profiles/{safe_email}.png"

def tema_uygula():
    bg_url = storage_image_url(BG_STORAGE_PATH)

    if bg_url:
        st.markdown(
            f"""
            <style>
            .stApp {{
                background-image: url('{bg_url}');
                background-size: cover;
                background-position: center;
                background-attachment: fixed;
            }}
            .block-container {{
                background-color: rgba(255, 255, 255, 0.92);
                padding: 2rem;
                border-radius: 15px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            }}
            </style>
            """,
            unsafe_allow_html=True
        )
        return

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
                    box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                }}
                </style>
                """,
                unsafe_allow_html=True
            )
        except Exception:
            pass

tema_uygula()


# =========================================================
# 5. GENEL YARDIMCILAR
# =========================================================
def get_yayin_durumu():
    try:
        res = supabase.table("ayarlar").select("deger").eq("ayar_adi", "yayin_durumu").execute()
        if res.data:
            return res.data[0]["deger"]
    except Exception:
        pass
    return "GIZLI"

yayin_durumu = get_yayin_durumu()

def mail_gonder(alici_mail, konu, mesaj_metni):
    try:
        gonderen_mail = st.secrets["email"]["adres"]
        gonderen_sifre = st.secrets["email"]["sifre"]

        msg = MIMEText(mesaj_metni)
        msg["Subject"] = konu
        msg["From"] = f"ED-AVM Yönetim <{gonderen_mail}>"
        msg["To"] = alici_mail

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gonderen_mail, gonderen_sifre)
            server.send_message(msg)

        return True
    except Exception:
        return False

def kod_uret():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

def style_status(v):
    val_str = str(v)

    if "🔴" in val_str:
        c = "#ff4b4b"
    elif "A " in val_str:
        c = "#1c83e1"
    elif "S " in val_str:
        c = "#28a745"
    elif "T " in val_str:
        c = "#6f42c1"
    elif "🟢" in val_str:
        c = "#4CAF50"
    elif "⏳" in val_str:
        c = "#6c757d"
    else:
        c = ""

    return f"background-color: {c}; color: white" if c else ""

def tabloyu_ciz(df):
    df_gorsel = df.copy()

    if "Personel" in df_gorsel.columns:
        df_gorsel["Personel"] = df_gorsel["Personel"].apply(
            lambda x: str(x).split(" (")[0] if " (" in str(x) else x
        )

    st.table(df_gorsel.style.map(style_status, subset=gunler))


# =========================================================
# 6. YOĞUN SAAT AYARLARI
# =========================================================
def get_peak_minimums():
    try:
        res = supabase.table("ayarlar").select("deger").eq("ayar_adi", "peak_minimums").execute()
        if res.data:
            data = json.loads(res.data[0]["deger"])
            return {**DEFAULT_PEAK_MINIMUMS, **data}
    except Exception:
        pass

    return DEFAULT_PEAK_MINIMUMS.copy()

def save_peak_minimums(values: dict):
    payload = json.dumps(values, ensure_ascii=False)

    try:
        existing = supabase.table("ayarlar").select("ayar_adi").eq("ayar_adi", "peak_minimums").execute()

        if existing.data:
            supabase.table("ayarlar").update({"deger": payload}).eq("ayar_adi", "peak_minimums").execute()
        else:
            supabase.table("ayarlar").insert({
                "ayar_adi": "peak_minimums",
                "deger": payload
            }).execute()

        return True, None
    except Exception as exc:
        return False, str(exc)


# =========================================================
# 7. VARDİYA PARSE / FORMAT
# =========================================================
def izin_listesi_oku(izin_gunu: str):
    izin_gunu = str(izin_gunu or "")

    if izin_gunu.strip() in ["", "İzin Yok", "nan", "None"]:
        return []

    return [g for g in gunler if g in izin_gunu]

def vardiya_plani_oku(izin_gunu: str, haftalik_vardiya: str):
    izinler = izin_listesi_oku(izin_gunu)
    v_str = str(haftalik_vardiya or "")

    if "Akşamcı" in v_str and "Karma" not in v_str:
        varsayilan = "Akşamcı"
    elif "Tam" in v_str and "Karma" not in v_str:
        varsayilan = "Tam Gün"
    else:
        varsayilan = "Sabahçı"

    plan = {g: varsayilan for g in gunler}

    if "Karma" in v_str:
        for g in gunler:
            if f"{g}: Akşamcı" in v_str:
                plan[g] = "Akşamcı"
            elif f"{g}: Tam Gün" in v_str:
                plan[g] = "Tam Gün"
            elif f"{g}: Sabahçı" in v_str:
                plan[g] = "Sabahçı"

    for g in izinler:
        plan[g] = "İzinli"

    return plan

def vardiya_plani_db_formatina_cevir(plan: dict):
    izinler = [g for g in gunler if plan.get(g) == "İzinli"]
    calisma_secimleri = [
        f"{g}: {plan.get(g, 'Sabahçı')}"
        for g in gunler
        if plan.get(g) != "İzinli"
    ]

    izin_str = ", ".join(izinler) if izinler else "İzin Yok"
    vardiya_str = "Karma | " + ", ".join(calisma_secimleri) if calisma_secimleri else "Karma | Seçim Yok"

    return izin_str, vardiya_str

def gun_bazli_vardiya_editoru(prefix: str, izin_gunu: str = "İzin Yok", haftalik_vardiya: str = "Sabahçı"):
    mevcut_plan = vardiya_plani_oku(izin_gunu, haftalik_vardiya)
    yeni_plan = {}

    st.markdown("**Gün bazlı vardiya düzenleme:**")
    st.caption("Her gün için İzinli / Sabahçı / Akşamcı / Tam Gün seçebilirsiniz.")

    for g in gunler:
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
# =========================================================
# 8. TASLAK TABLO VE OPERASYON KONTROL
# =========================================================
def get_taslak_df():
    res_k = supabase.table("kullanicilar").select("isim, email").eq("durum", "Onaylandı").neq("rol", "Yonetici").execute()
    aktifler = [f"{k['isim']} ({k['email']})" for k in res_k.data] if res_k.data else []

    if not aktifler:
        return pd.DataFrame()

    taslak = pd.DataFrame(index=aktifler, columns=gunler)
    taslak.fillna("⏳ Belirsiz", inplace=True)

    res_t = supabase.table("talepler").select("*").eq("durum", "Onaylandı").execute()
    onayli = res_t.data if res_t.data else []

    for r in onayli:
        p = str(r["personel"])

        if p not in taslak.index:
            continue

        iz_str = str(r["izin_gunu"])
        v_str = str(r["haftalik_vardiya"])

        for g in gunler:
            if g in iz_str:
                taslak.at[p, g] = "🔴 İZİNLİ"
            else:
                if "Karma" in v_str:
                    if f"{g}: Sabahçı" in v_str:
                        shift = "S (09-18)"
                    elif f"{g}: Akşamcı" in v_str:
                        shift = "A (12-21)"
                    elif f"{g}: Tam Gün" in v_str:
                        shift = "T (09-21)"
                    else:
                        shift = "S (09-18)"
                else:
                    if "Akşamcı" in v_str:
                        shift = "A (12-21)"
                    elif "Tam" in v_str:
                        shift = "T (09-21)"
                    else:
                        shift = "S (09-18)"

                taslak.at[p, g] = shift

    taslak.reset_index(inplace=True)
    taslak.rename(columns={"index": "Personel"}, inplace=True)

    return taslak

def vardiya_aktif_mi_12_18(v):
    val = str(v)

    if "🔴" in val or "İZİNLİ" in val or "⏳" in val or "Belirsiz" in val:
        return False

    return ("S " in val) or ("A " in val) or ("T " in val) or ("🟢" in val)

def personel_email_ayikla(personel_str: str):
    try:
        metin = str(personel_str)
        if "(" in metin and ")" in metin:
            return metin.split("(")[-1].replace(")", "").strip()
    except Exception:
        pass

    return None

def kullanici_rol_map_getir():
    try:
        res = supabase.table("kullanicilar").select("isim, email, operasyon_rolu").eq("durum", "Onaylandı").neq("rol", "Yonetici").execute()
        data = res.data if res.data else []

        return {
            str(k.get("email", "")).strip().lower(): k.get("operasyon_rolu", "Alt Kat")
            for k in data
        }
    except Exception:
        return {}

def peak_coverage_hesapla(taslak_df: pd.DataFrame):
    if taslak_df is None or taslak_df.empty:
        return {}, []

    minimums = get_peak_minimums()
    role_minimums = {
        k: v for k, v in minimums.items()
        if k != "Toplam Aktif"
    }

    rol_map = kullanici_rol_map_getir()
    coverage = {}

    for g in gunler:
        coverage[g] = {rol: 0 for rol in role_minimums.keys()}
        coverage[g]["Tanımsız"] = 0
        coverage[g]["Toplam Aktif"] = 0

    for _, row in taslak_df.iterrows():
        personel = str(row.get("Personel", ""))
        email = personel_email_ayikla(personel)
        rol = rol_map.get(str(email).lower(), "Tanımsız") if email else "Tanımsız"

        for g in gunler:
            if vardiya_aktif_mi_12_18(row.get(g, "")):
                if rol in coverage[g]:
                    coverage[g][rol] += 1
                else:
                    coverage[g]["Tanımsız"] += 1

                coverage[g]["Toplam Aktif"] += 1

    uyarilar = []

    for g in gunler:
        for rol, minimum in role_minimums.items():
            mevcut = coverage[g].get(rol, 0)

            if mevcut < minimum:
                uyarilar.append(f"{g}: {rol} eksik ({mevcut}/{minimum})")

        toplam_min = minimums.get("Toplam Aktif", 8)
        toplam = coverage[g].get("Toplam Aktif", 0)

        if toplam < toplam_min:
            uyarilar.append(f"{g}: Toplam aktif personel eksik ({toplam}/{toplam_min})")

    return coverage, uyarilar

def operasyon_kontrol_paneli(taslak_df: pd.DataFrame, baslik="12:00–18:00 Yoğun Saat Operasyon Kontrolü"):
    st.subheader(baslik)

    if taslak_df is None or taslak_df.empty:
        st.info("Kontrol edilecek onaylı plan bulunmuyor.")
        return [], pd.DataFrame()

    minimums = get_peak_minimums()
    role_minimums = {
        k: v for k, v in minimums.items()
        if k != "Toplam Aktif"
    }

    coverage, uyarilar = peak_coverage_hesapla(taslak_df)

    rows = []

    for g in gunler:
        row = {"Gün": g}

        for rol, minimum in role_minimums.items():
            mevcut = coverage[g].get(rol, 0)
            durum = "✅" if mevcut >= minimum else "❌"
            row[rol] = f"{durum} {mevcut}/{minimum}"

        toplam_min = minimums.get("Toplam Aktif", 8)
        toplam_mevcut = coverage[g].get("Toplam Aktif", 0)
        toplam_durum = "✅" if toplam_mevcut >= toplam_min else "❌"

        row["Toplam Aktif"] = f"{toplam_durum} {toplam_mevcut}/{toplam_min}"
        row["Tanımsız"] = coverage[g].get("Tanımsız", 0)

        rows.append(row)

    kontrol_df = pd.DataFrame(rows)
    st.dataframe(kontrol_df, use_container_width=True)

    if uyarilar:
        st.warning("⚠️ Yoğun saat kapasitesinde eksikler var.")
        with st.expander("Eksik / riskli noktaları göster"):
            for u in uyarilar:
                st.write(f"- {u}")
    else:
        st.success("✅ 12:00–18:00 yoğun saat operasyon kapasitesi karşılanıyor.")

    return uyarilar, kontrol_df

def gunluk_vardiya_sayaci(taslak_df: pd.DataFrame, baslik="Günlük Vardiya Sayacı"):
    st.subheader(baslik)

    if taslak_df is None or taslak_df.empty:
        st.info("Sayım yapılacak onaylı plan bulunmuyor.")
        return pd.DataFrame()

    rows = []

    for g in gunler:
        sabah = 0
        aksam = 0
        tam = 0
        izinli = 0
        belirsiz = 0

        for _, row in taslak_df.iterrows():
            val = str(row.get(g, ""))

            if "S " in val:
                sabah += 1
            elif "A " in val:
                aksam += 1
            elif "T " in val or "🟢" in val:
                tam += 1
            elif "🔴" in val:
                izinli += 1
            elif "⏳" in val:
                belirsiz += 1

        rows.append({
            "Gün": g,
            "Sabahçı": sabah,
            "Akşamcı": aksam,
            "Tam Gün / Tam Güç": tam,
            "İzinli": izinli,
            "Belirsiz": belirsiz,
            "12–18 Aktif Toplam": sabah + aksam + tam
        })

    sayac_df = pd.DataFrame(rows)
    st.dataframe(sayac_df, use_container_width=True)

    return sayac_df

def hafta_id_uret():
    today = datetime.now()
    iso = today.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"

def vardiya_arsiv_kaydet(taslak_df: pd.DataFrame):
    if taslak_df is None or taslak_df.empty:
        return False, "Arşivlenecek plan yok."

    hafta_id = hafta_id_uret()
    rows = []

    for _, row in taslak_df.iterrows():
        v_data = {
            "hafta_id": hafta_id,
            "personel": row["Personel"],
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        for g in gunler:
            v_data[g] = row[g]

        rows.append(v_data)

    try:
        supabase.table("vardiya_arsiv").delete().eq("hafta_id", hafta_id).execute()
        supabase.table("vardiya_arsiv").insert(rows).execute()
        return True, f"{hafta_id} haftası arşivlendi."
    except Exception as exc:
        return False, f"Arşiv kaydı yapılamadı. Detay: {exc}"

def otomatik_haftalik_vardiya_ata(tam_gun_kullan=True):
    """
    Onaylı taleplerin izin günlerini korur.
    Karma vardiya yerine haftalık sabit vardiya atar.
    """
    try:
        res_t = supabase.table("talepler").select("*").eq("durum", "Onaylandı").execute()
        talepler = res_t.data if res_t.data else []

        if not talepler:
            return False, "Onaylı talep bulunamadı."

        vardiya_havuzu = [
            "Sabahçı (09:00 - 18:00)",
            "Akşamcı (12:00 - 21:00)"
        ]

        if tam_gun_kullan:
            vardiya_havuzu.append("Tam Gün (09:00 - 21:00)")

        random.shuffle(talepler)

        for i, talep in enumerate(talepler):
            atanacak_vardiya = vardiya_havuzu[i % len(vardiya_havuzu)]
            mevcut_not = str(talep.get("neden", "") or "").strip()
            sistem_notu = "Sistem otomatik haftalık vardiya ataması yaptı."

            yeni_not = sistem_notu if mevcut_not == "" else f"{mevcut_not} | {sistem_notu}"

            supabase.table("talepler").update({
                "haftalik_vardiya": atanacak_vardiya,
                "neden": yeni_not
            }).eq("id", talep["id"]).execute()

        return True, f"{len(talepler)} personel için haftalık vardiya otomatik atandı."

    except Exception as exc:
        return False, f"Otomatik vardiya atama sırasında hata oluştu: {exc}"


# =========================================================
# 9. SESSION / COOKIE
# =========================================================
cookies = CookieController()

if "giris_yapildi" not in st.session_state:
    st.session_state.update({
        "giris_yapildi": False,
        "kullanici_tipi": "",
        "kullanici_adi": "",
        "kullanici_mail": "",
        "reset_kod": "",
        "reset_mail": "",
        "calisma_tipi": "",
        "cikis_yapiliyor": False,
        "yeni_cerez_yaz": None,
        "az_once_cikis_yapti": False
    })

if st.session_state.get("cikis_yapiliyor"):
    try:
        cookies.remove("edavm_user_session")
        cookies.remove("edavm_user_mail")
    except Exception:
        pass

    st.query_params.clear()
    st.session_state.clear()
    st.session_state.update({
        "giris_yapildi": False,
        "cikis_yapiliyor": False,
        "az_once_cikis_yapti": True
    })

if st.session_state.get("yeni_cerez_yaz"):
    cookies.set("edavm_user_session", st.session_state.get("yeni_cerez_yaz"), max_age=SESSION_MAX_AGE)
    st.session_state.yeni_cerez_yaz = None

kayitli_token = cookies.get("edavm_user_session")
aktif_mail = parse_session_token(kayitli_token) if kayitli_token else None

try:
    if cookies.get("edavm_user_mail"):
        cookies.remove("edavm_user_mail")
except Exception:
    pass

if not st.session_state.get("giris_yapildi") and aktif_mail and not st.session_state.get("az_once_cikis_yapti"):
    try:
        res = supabase.table("kullanicilar").select("*").eq("email", aktif_mail).execute()

        if res.data and res.data[0]["durum"] == "Onaylandı":
            user = res.data[0]
            st.session_state.update({
                "giris_yapildi": True,
                "kullanici_tipi": user["rol"],
                "kullanici_adi": user["isim"],
                "kullanici_mail": user["email"],
                "calisma_tipi": user.get("calisma_tipi", "Tam Zamanlı")
            })
        else:
            try:
                cookies.remove("edavm_user_session")
            except Exception:
                pass
            st.query_params.clear()
    except Exception:
        pass


# =========================================================
# 10. GİRİŞ / KAYIT EKRANI
# =========================================================
if not st.session_state.giris_yapildi:
    col_logo, col_baslik = st.columns([1, 8])

    with col_logo:
        logo_url = storage_image_url(LOGO_STORAGE_PATH)

        if logo_url:
            st.image(logo_url, width=80)
        elif os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, width=80)

    with col_baslik:
        st.title("🏢 Ekonomi Dünyası AVM Portalı")

    st.markdown("---")

    col1, col2, col3 = st.columns([1, 4, 1])

    with col2:
        sekme = st.radio(
            "İşlem Seçiniz",
            ["🔑 Giriş Yap", "📝 Kayıt Ol", "❓ Şifremi Unuttum", "👔 İş Başvurusu"],
            horizontal=True
        )

        if sekme == "🔑 Giriş Yap":
            email_in = st.text_input("E-posta").strip().lower()
            sifre_in = st.text_input("Şifre", type="password")
            beni_hatirla = st.checkbox("Beni Hatırla (Cihazda Oturumu Açık Tut)", value=False)

            if st.button("Sisteme Gir"):
                res = supabase.table("kullanicilar").select("*").eq("email", email_in).execute()

                if res.data:
                    user = res.data[0]

                    if verify_password(sifre_in, user.get("sifre", "")):
                        if user["durum"] == "Onaylandı":
                            if not str(user.get("sifre", "")).startswith("pbkdf2_sha256$"):
                                supabase.table("kullanicilar").update({
                                    "sifre": hash_password(sifre_in)
                                }).eq("email", user["email"]).execute()

                            if beni_hatirla:
                                st.session_state.yeni_cerez_yaz = make_session_token(user["email"])
                            else:
                                try:
                                    if cookies.get("edavm_user_session"):
                                        cookies.remove("edavm_user_session")
                                    if cookies.get("edavm_user_mail"):
                                        cookies.remove("edavm_user_mail")
                                except Exception:
                                    pass

                            st.query_params.clear()

                            st.session_state.update({
                                "giris_yapildi": True,
                                "kullanici_tipi": user["rol"],
                                "kullanici_adi": user["isim"],
                                "kullanici_mail": user["email"],
                                "calisma_tipi": user.get("calisma_tipi", "Tam Zamanlı"),
                                "az_once_cikis_yapti": False
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
                    res_kontrol = supabase.table("kullanicilar").select("email").eq("email", mail).execute()

                    if res_kontrol.data:
                        st.error("Bu e-posta zaten sistemde kayıtlı.")
                    elif isim == "" or mail == "" or sifre == "":
                        st.warning("Lütfen zorunlu alanları doldurun.")
                    else:
                        yeni_veri = {
                            "isim": str(isim.strip().title()),
                            "email": str(mail),
                            "sifre": hash_password(sifre),
                            "telefon": str(tel),
                            "durum": "Beklemede",
                            "rol": "Personel",
                            "calisma_tipi": calisma_tipi,
                            "operasyon_rolu": "Alt Kat"
                        }

                        supabase.table("kullanicilar").insert(yeni_veri).execute()
                        mail_gonder(
                            mail,
                            "ED-AVM | Kayıt Talebiniz Alındı",
                            f"Merhaba {isim.strip().title()},\n\nSisteme kayıt talebiniz alınmıştır. Yönetim onayından sonra giriş yapabilirsiniz.\n\nED-AVM Yönetim"
                        )
                        st.success("Kayıt başarılı! Yönetim onayından sonra girebilirsiniz.")

        elif sekme == "❓ Şifremi Unuttum":
            if st.session_state.reset_kod == "":
                mail_res = st.text_input("Sisteme Kayıtlı E-posta Adresiniz:")

                if st.button("Doğrulama Kodu Gönder"):
                    res = supabase.table("kullanicilar").select("email").eq("email", mail_res.strip().lower()).execute()

                    if res.data:
                        kod = kod_uret()
                        st.session_state.reset_kod = kod
                        st.session_state.reset_mail = mail_res.strip().lower()
                        mail_gonder(mail_res, "ED-AVM | Şifre Sıfırlama", f"Sıfırlama kodunuz: {kod}")
                        st.info("Kod e-postanıza gönderildi.")
                    else:
                        st.error("Mail sistemde bulunamadı.")
            else:
                kod_in = st.text_input("Mailinize gelen kodu girin:")
                yeni_sifre = st.text_input("Yeni Şifreniz:", type="password")

                if st.button("Şifreyi Güncelle"):
                    if kod_in == st.session_state.reset_kod:
                        supabase.table("kullanicilar").update({
                            "sifre": hash_password(yeni_sifre)
                        }).eq("email", st.session_state.reset_mail).execute()

                        st.success("Şifreniz güncellendi!")
                        st.session_state.reset_kod = ""
                    else:
                        st.error("Kod hatalı.")

        elif sekme == "👔 İş Başvurusu":
            with st.form("is_basvurusu"):
                b_isim = st.text_input("Adınız Soyadınız")
                b_tel = st.text_input("Telefon Numaranız")
                b_mail = st.text_input("E-posta Adresiniz")
                b_pozisyon = st.selectbox(
                    "Başvurulan Pozisyon",
                    ["Satış Danışmanı", "Kasa Görevlisi", "Depo / Lojistik", "E-Ticaret Sorumlusu"]
                )
                b_calisma_tipi = st.selectbox("Tercih Ettiğiniz Çalışma Şekli", ["Tam Zamanlı", "Part-Time"])
                b_tecrube = st.text_area("İş Tecrübeleriniz")

                if st.form_submit_button("Başvurumu İlet"):
                    if b_isim == "" or b_tel == "":
                        st.warning("İsim ve telefon zorunludur.")
                    else:
                        yeni_basvuru = {
                            "ad_soyad": str(b_isim.strip().title()),
                            "telefon": str(b_tel),
                            "eposta": str(b_mail),
                            "pozisyon": str(b_pozisyon),
                            "calisma_tipi": str(b_calisma_tipi),
                            "tecrube": str(b_tecrube),
                            "durum": "İnceleniyor",
                            "tarih": datetime.now().strftime("%Y-%m-%d %H:%M")
                        }

                        supabase.table("basvurular").insert(yeni_basvuru).execute()
                        st.success("Başvurunuz İK sistemine başarıyla kaydedildi!")
# =========================================================
# 11. ANA PANEL
# =========================================================
if st.session_state.giris_yapildi:
    profile_url = storage_image_url(profile_storage_path(st.session_state.kullanici_mail))
    pp_path = os.path.join(PROFILE_DIR, f"{st.session_state.kullanici_mail}.png")

    with st.sidebar:
        logo_url = storage_image_url(LOGO_STORAGE_PATH)

        if logo_url:
            st.image(logo_url, use_container_width=True)
            st.divider()
        elif os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, use_container_width=True)
            st.divider()

        if profile_url:
            st.image(profile_url, width=150)
        elif os.path.exists(pp_path):
            st.image(pp_path, width=150)
        else:
            st.write("👤 *(Fotoğraf Yok)*")

        st.title(f"{st.session_state.kullanici_adi}")
        st.caption("👑 Yönetici" if st.session_state.kullanici_tipi == "Yonetici" else "Çalışan")
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


    # =====================================================
    # PROFİL
    # =====================================================
    if sayfa == "Profilim":
        st.header("👤 Profilimi Düzenle")

        res_u = supabase.table("kullanicilar").select("*").eq("email", st.session_state.kullanici_mail).execute()
        u_data = res_u.data[0]

        col_foto, col_bilgi = st.columns([1, 2])

        with col_foto:
            st.subheader("Fotoğraf")

            if profile_url:
                st.image(profile_url, width=200)
            elif os.path.exists(pp_path):
                st.image(pp_path, width=200)

            yuklenen_foto = st.file_uploader("Yeni Fotoğraf Yükle (PNG/JPG)", type=["png", "jpg", "jpeg"])

            if yuklenen_foto is not None:
                ok, err = upload_storage_file(yuklenen_foto, profile_storage_path(st.session_state.kullanici_mail))

                if ok:
                    st.success("Fotoğraf yüklendi. Sayfayı yenileyince görünecektir.")
                else:
                    st.error(f"Fotoğraf yüklenemedi: {err}")

        with col_bilgi:
            yeni_isim = st.text_input("Ad Soyad:", value=str(u_data["isim"]))
            yeni_tel = st.text_input("Telefon:", value=str(u_data["telefon"]))
            st.caption(f"Operasyon Rolü: {u_data.get('operasyon_rolu', 'Tanımsız')}")

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

                supabase.table("kullanicilar").update(guncel_veri).eq("email", st.session_state.kullanici_mail).execute()

                st.session_state.kullanici_adi = str(yeni_isim)
                st.session_state.calisma_tipi = str(yeni_tip)

                st.success("Profiliniz başarıyla güncellendi!")
                st.rerun()


    # =====================================================
    # PERSONEL VARDİYA
    # =====================================================
    elif sayfa == "Vardiya İşlemleri":
        st.header("📅 Haftalık Vardiya Planlaması")
        tab1, tab2, tab3 = st.tabs(["✍️ Planımı Gönder", "👀 Onaylananlar (Canlı Taslak)", "📊 Kesinleşen Liste"])

        with tab1:
            secilen_gunler = []

            if st.session_state.calisma_tipi == "Part-Time":
                st.info("ℹ️ Part-Time personel olarak önce çalışacağınız günleri, sonra her gün için vardiya saatinizi seçiniz.")
                secilen_gunler = st.multiselect("✅ ÇALIŞACAĞINIZ Günleri Seçiniz:", gunler, key="pt_calisma_gunleri")

            with st.form("personel_formu", clear_on_submit=True):
                karma_secimler = []

                if st.session_state.calisma_tipi == "Part-Time":
                    calisilan_gunler = secilen_gunler
                    izin_listesi = [g for g in gunler if g not in secilen_gunler]

                    if calisilan_gunler:
                        st.markdown("**Seçtiğiniz günler için vardiya tercihiniz:**")

                        for g in calisilan_gunler:
                            sec = st.selectbox(f"{g} vardiyası:", vardiya_secenekleri, key=f"pt_vardiya_{g}")
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

                    st.caption("Not: Yönetim haftalık vardiya dağıtımını otomatik veya manuel olarak düzenleyebilir.")
                    haftalik_shift = st.radio("Tercih ettiğiniz haftalık vardiya:", vardiya_secenekleri)

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

                        supabase.table("talepler").delete().eq("personel", benzersiz_kimlik).execute()
                        supabase.table("talepler").insert(yeni_talep).execute()

                        st.success("Talebiniz veritabanına işlendi ve yönetime iletildi.")

        with tab2:
            st.info("💡 Yönetimin şu ana kadar onayladığı güncel durumu gösterir.")
            if st.button("🔄 Verileri Yenile", key="pers_yenile"):
                st.rerun()

            taslak_df = get_taslak_df()

            if not taslak_df.empty:
                tabloyu_ciz(taslak_df)
            else:
                st.warning("Henüz onaylanmış bir plan yok.")

        with tab3:
            if yayin_durumu == "YAYINLANDI":
                res_v = supabase.table("vardiyalar").select("*").execute()

                if res_v.data:
                    df_v = pd.DataFrame(res_v.data)
                    df_v.rename(columns={"personel": "Personel"}, inplace=True)
                    tabloyu_ciz(df_v)
                else:
                    st.warning("Liste veritabanında boş.")
            else:
                st.warning("⚠️ Kesinleşmiş liste henüz yayınlanmamıştır.")


    # =====================================================
    # KESİNLEŞEN LİSTE
    # =====================================================
    elif sayfa == "Kesinleşen Liste":
        st.header("📊 Kesinleşen Vardiya Listesi")

        if yayin_durumu == "YAYINLANDI":
            res_v = supabase.table("vardiyalar").select("*").execute()

            if res_v.data:
                df_v = pd.DataFrame(res_v.data)
                df_v.rename(columns={"personel": "Personel"}, inplace=True)
                tabloyu_ciz(df_v)
            else:
                st.warning("Liste boş.")
        else:
            st.warning("⚠️ Yayınlanmış liste yok.")


    # =====================================================
    # YÖNETİCİ PANELİ
    # =====================================================
    elif sayfa == "Yönetici Paneli" and st.session_state.kullanici_tipi == "Yonetici":
        st.header("👑 Yönetim Kontrol Merkezi")

        tab_k, tab_t, tab_m, tab_y, tab_b = st.tabs([
            "👥 Kullanıcılar",
            "📥 Gelen Talepler",
            "🛠️ Manuel / Otomatik Plan",
            "🚀 Yayınlama",
            "👔 İK"
        ])

        with tab_k:
            res_users = supabase.table("kullanicilar").select("*").execute()
            df_k = pd.DataFrame(res_users.data) if res_users.data else pd.DataFrame()

            if not df_k.empty:
                bekleyenler = df_k[df_k["durum"] == "Beklemede"]
                st.subheader("Yeni Kayıtlar")

                for _, row in bekleyenler.iterrows():
                    with st.expander(f"👤 {row['isim']} ({row['email']}) | {row.get('calisma_tipi', 'Tam Zamanlı')}"):
                        yeni_op_rol = st.selectbox("Operasyon Rolü:", OPERASYON_ROLLERI, key=f"oprol_new_{row['email']}")
                        c1, c2 = st.columns(2)

                        if c1.button("Onayla", key=f"kon_{row['email']}"):
                            supabase.table("kullanicilar").update({
                                "durum": "Onaylandı",
                                "operasyon_rolu": yeni_op_rol
                            }).eq("email", row["email"]).execute()

                            mail_gonder(
                                row["email"],
                                "ED-AVM | Hesabınız Onaylandı",
                                f"Merhaba {row['isim']},\n\nED-AVM portal hesabınız onaylanmıştır.\n\nİyi çalışmalar."
                            )
                            st.rerun()

                        if c2.button("Reddet", key=f"kred_{row['email']}"):
                            supabase.table("kullanicilar").delete().eq("email", row["email"]).execute()
                            st.rerun()

                st.divider()
                st.subheader("Aktif Kullanıcılar")

                aktifler = df_k[df_k["durum"] == "Onaylandı"]

                for _, row in aktifler.iterrows():
                    mevcut_tip = row.get("calisma_tipi", "Tam Zamanlı")
                    mevcut_op_rol = row.get("operasyon_rolu", "Alt Kat")

                    if row["rol"] == "Yonetici":
                        expander_title = f"👑 {row['isim']} (Yönetici)"
                    else:
                        expander_title = f"⚙️ {row['isim']} ({row['rol']} - {mevcut_tip} - {mevcut_op_rol})"

                    with st.expander(expander_title):
                        st.write(f"Mail: {row['email']} | Tel: {row['telefon']}")

                        if row["rol"] != "Yonetici":
                            idx_tip = 0 if mevcut_tip == "Tam Zamanlı" else 1
                            yeni_tip = st.selectbox(
                                "Çalışma Tipi:",
                                ["Tam Zamanlı", "Part-Time"],
                                index=idx_tip,
                                key=f"tip_{row['email']}"
                            )

                            yeni_op_rol = st.selectbox(
                                "Operasyon Rolü:",
                                OPERASYON_ROLLERI,
                                index=OPERASYON_ROLLERI.index(mevcut_op_rol) if mevcut_op_rol in OPERASYON_ROLLERI else 0,
                                key=f"oprol_edit_{row['email']}"
                            )

                            c1, c2 = st.columns(2)

                            if c1.button("💾 Bilgileri Güncelle", key=f"kguncel_{row['email']}"):
                                supabase.table("kullanicilar").update({
                                    "calisma_tipi": yeni_tip,
                                    "operasyon_rolu": yeni_op_rol
                                }).eq("email", row["email"]).execute()
                                st.rerun()

                            if row["email"] != st.session_state.kullanici_mail:
                                if c2.button("🗑️ Kullanıcıyı Sil", key=f"kdel_{row['email']}"):
                                    benzersiz_isim = f"{row['isim']} ({row['email']})"
                                    supabase.table("talepler").delete().eq("personel", benzersiz_isim).execute()
                                    supabase.table("vardiyalar").delete().eq("personel", benzersiz_isim).execute()
                                    supabase.table("kullanicilar").delete().eq("email", row["email"]).execute()
                                    st.rerun()
                        else:
                            st.info("Yönetici hesabı.")

        with tab_t:
            c1, c2 = st.columns([4, 1])

            with c1:
                st.subheader("1. Bekleyen Talepler")

            with c2:
                if st.button("🔄 Talepleri Yenile", key="yonetici_yenile"):
                    st.rerun()

            res_t = supabase.table("talepler").select("*").execute()
            df_t = pd.DataFrame(res_t.data) if res_t.data else pd.DataFrame()

            if not df_t.empty:
                bekleyen_talepler = df_t[df_t["durum"] == "Beklemede"]

                if len(bekleyen_talepler) > 0:
                    for _, row in bekleyen_talepler.iterrows():
                        personel_adi = str(row["personel"]).split(" (")[0] if " (" in str(row["personel"]) else str(row["personel"])

                        with st.expander(f"⏳ {personel_adi} | İzin: {row['izin_gunu']} | Vardiya: {row['haftalik_vardiya']}"):
                            if pd.notna(row["neden"]) and str(row["neden"]).strip() != "":
                                st.write(f"**Not:** {row['neden']}")

                            with st.form(key=f"ilk_onay_{row['id']}"):
                                yeni_izin_str, final_vardiya = gun_bazli_vardiya_editoru(
                                    prefix=f"ilk_{row['id']}",
                                    izin_gunu=row["izin_gunu"],
                                    haftalik_vardiya=row["haftalik_vardiya"]
                                )

                                c1, c2 = st.columns(2)

                                if c1.form_submit_button("✅ Onayla"):
                                    supabase.table("talepler").update({
                                        "izin_gunu": yeni_izin_str,
                                        "haftalik_vardiya": final_vardiya,
                                        "durum": "Onaylandı"
                                    }).eq("id", row["id"]).execute()
                                    st.rerun()

                                if c2.form_submit_button("❌ Reddet"):
                                    supabase.table("talepler").delete().eq("id", row["id"]).execute()
                                    st.rerun()
                else:
                    st.info("Bekleyen talep yok.")
            else:
                st.info("Sistemde hiç talep yok.")

            st.divider()
            st.subheader("2. Onaylanmış Talepleri Düzenle")

            if not df_t.empty:
                onayli_talepler = df_t[df_t["durum"] == "Onaylandı"]

                if len(onayli_talepler) > 0:
                    for _, row in onayli_talepler.iterrows():
                        personel_adi = str(row["personel"]).split(" (")[0] if " (" in str(row["personel"]) else str(row["personel"])

                        with st.expander(f"✅ {personel_adi} | İzin: {row['izin_gunu']} | Vardiya: {row['haftalik_vardiya']}"):
                            if pd.notna(row["neden"]) and str(row["neden"]).strip() != "":
                                st.write(f"**Not:** {row['neden']}")

                            with st.form(key=f"duzenle_onayli_{row['id']}"):
                                yeni_izin_str, final_vardiya = gun_bazli_vardiya_editoru(
                                    prefix=f"duzenle_{row['id']}",
                                    izin_gunu=row["izin_gunu"],
                                    haftalik_vardiya=row["haftalik_vardiya"]
                                )

                                c1, c2, c3 = st.columns(3)

                                if c1.form_submit_button("🔄 Güncelle"):
                                    supabase.table("talepler").update({
                                        "izin_gunu": yeni_izin_str,
                                        "haftalik_vardiya": final_vardiya
                                    }).eq("id", row["id"]).execute()
                                    st.rerun()

                                if c2.form_submit_button("⚠️ İptal Et"):
                                    supabase.table("talepler").update({"durum": "Beklemede"}).eq("id", row["id"]).execute()
                                    st.rerun()

                                if c3.form_submit_button("🗑️ Sil"):
                                    supabase.table("talepler").delete().eq("id", row["id"]).execute()
                                    st.rerun()
                else:
                    st.info("Onaylanmış talep yok.")

            st.divider()
            st.subheader("👀 Canlı Taslak Önizlemesi")

            taslak_df = get_taslak_df()

            if not taslak_df.empty:
                tabloyu_ciz(taslak_df)
                st.divider()
                gunluk_vardiya_sayaci(taslak_df)
                st.divider()
                operasyon_kontrol_paneli(taslak_df)
            else:
                st.info("Önizlenecek onaylı plan yok.")

        with tab_m:
            st.subheader("🎲 Otomatik Haftalık Vardiya Atama")
            st.caption(
                "Bu işlem onaylı taleplerdeki izin günlerini korur, "
                "karma vardiya düzenini kaldırır ve personellere haftalık sabit vardiya atar."
            )

            tam_gun_kullan = st.checkbox(
                "Tam Gün vardiyası da otomatik dağıtıma dahil edilsin",
                value=True,
                key="otomatik_tam_gun_kullan"
            )

            otomatik_onay = st.checkbox(
                "Otomatik atama yapılacağını onaylıyorum.",
                key="otomatik_vardiya_onay"
            )

            if st.button("🎲 Onaylı Personele Haftalık Vardiya Ata", disabled=not otomatik_onay):
                ok, msg = otomatik_haftalik_vardiya_ata(tam_gun_kullan=tam_gun_kullan)

                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

            st.divider()

            st.subheader("🛠️ Manuel Vardiya Atama")

            res_k = supabase.table("kullanicilar").select("isim, email").eq("durum", "Onaylandı").neq("rol", "Yonetici").execute()
            aktif_personel_listesi = [f"{k['isim']} ({k['email']})" for k in res_k.data] if res_k.data else []

            if len(aktif_personel_listesi) > 0:
                with st.form("manuel_atama"):
                    secilen_kisi = st.selectbox("Personel:", aktif_personel_listesi)
                    st.markdown("**Manuel gün bazlı plan:**")

                    manuel_plan = {}

                    for g in gunler:
                        manuel_plan[g] = st.selectbox(
                            f"{g}:",
                            ADMIN_GUN_DURUMLARI,
                            index=1,
                            key=f"manuel_{g}"
                        )

                    izin_str, vardiya_str = vardiya_plani_db_formatina_cevir(manuel_plan)

                    if st.form_submit_button("Sisteme İşle (Onaylı)"):
                        supabase.table("talepler").delete().eq("personel", secilen_kisi).execute()

                        yeni_manuel = {
                            "personel": secilen_kisi,
                            "izin_gunu": izin_str,
                            "haftalik_vardiya": vardiya_str,
                            "neden": "Yönetici Manuel Atama",
                            "durum": "Onaylandı"
                        }

                        supabase.table("talepler").insert(yeni_manuel).execute()
                        st.success("Veritabanına eklendi!")
                        st.rerun()
            else:
                st.warning("Sistemde aktif personel bulunmuyor.")

        with tab_y:
            st.subheader("Haftalık Operasyon Kontrolü")
            st.caption("Yayınlamadan önce 12:00–18:00 yoğun saat kapasitesi ve genel vardiya dengesi kontrol edilir.")

            taslak_df = get_taslak_df()

            if not taslak_df.empty:
                tabloyu_ciz(taslak_df)
                st.divider()
                gunluk_vardiya_sayaci(taslak_df, baslik="Yayın Öncesi Günlük Vardiya Sayacı")
                st.divider()
                uyarilar, kontrol_df = operasyon_kontrol_paneli(
                    taslak_df,
                    baslik="Yayın Öncesi 12:00–18:00 Operasyon Kontrolü"
                )
            else:
                uyarilar = []
                st.warning("Yayınlanacak onaylı plan bulunmuyor.")

            st.divider()

            st.markdown("### Yeni Haftaya Başlama")
            reset_onay = st.checkbox("Yeni haftaya başlarken mevcut taleplerin silineceğini onaylıyorum.", key="reset_onay")

            if st.button("🔄 Yeni Haftaya Başla (Sıfırla)", disabled=not reset_onay):
                supabase.table("ayarlar").update({"deger": "GIZLI"}).eq("ayar_adi", "yayin_durumu").execute()
                supabase.table("talepler").delete().neq("id", 0).execute()
                st.success("Veritabanı sıfırlandı. Yeni haftaya başlandı.")
                st.rerun()

            st.divider()
            st.markdown("### Listeyi Yayınla")

            if uyarilar:
                uyarilari_gordum = st.checkbox("Yoğun saat uyarılarını gördüm ve buna rağmen yayınlamayı onaylıyorum.", key="uyari_onay")
            else:
                uyarilari_gordum = True

            listeyi_kontrol_ettim = st.checkbox("Kesinleşen listeyi kontrol ettim.", key="liste_kontrol_onay")
            yayin_hazir = (not taslak_df.empty) and uyarilari_gordum and listeyi_kontrol_ettim

            col_yayin, col_mail = st.columns(2)

            with col_yayin:
                if st.button("🚀 Listeyi Kesinleştir ve Yayınla", disabled=not yayin_hazir):
                    if not taslak_df.empty:
                        arsiv_ok, arsiv_msg = vardiya_arsiv_kaydet(taslak_df)

                        if arsiv_ok:
                            st.success(f"Arşiv: {arsiv_msg}")
                        else:
                            st.warning(arsiv_msg)

                        supabase.table("vardiyalar").delete().neq("personel", "x").execute()

                        for _, row in taslak_df.iterrows():
                            v_data = {"personel": row["Personel"]}

                            for g in gunler:
                                v_data[g] = row[g]

                            supabase.table("vardiyalar").insert(v_data).execute()

                        supabase.table("ayarlar").update({"deger": "YAYINLANDI"}).eq("ayar_adi", "yayin_durumu").execute()
                        supabase.table("talepler").delete().neq("id", 0).execute()

                        st.success("Liste kaydedildi ve yayınlandı!")
                        st.rerun()
                    else:
                        st.warning("Onaylı plan yok.")

            with col_mail:
                if st.button("📧 Yayın Maili At"):
                    st.success("Mail sistemi hazır.")

        with tab_b:
            st.subheader("İş Başvuruları")

            res_b = supabase.table("basvurular").select("*").execute()

            if res_b.data:
                df_b = pd.DataFrame(res_b.data)
                bekleyen_b = df_b[df_b["durum"] == "İnceleniyor"]

                for _, row in bekleyen_b.iterrows():
                    with st.expander(f"👤 {row['ad_soyad']} - {row['pozisyon']} ({row.get('calisma_tipi', 'Tam Zamanlı')})"):
                        st.write(f"Tel: {row['telefon']} | Mail: {row['eposta']}\n\nTecrübe: {row['tecrube']}")

                        c1, c2, c3 = st.columns(3)

                        if c1.button("Kabul", key=f"bk_{row['id']}"):
                            supabase.table("basvurular").update({"durum": "Kabul"}).eq("id", row["id"]).execute()
                            st.rerun()

                        if c2.button("Red", key=f"br_{row['id']}"):
                            supabase.table("basvurular").update({"durum": "Red"}).eq("id", row["id"]).execute()
                            st.rerun()

                        if c3.button("Sil", key=f"bs_{row['id']}"):
                            supabase.table("basvurular").delete().eq("id", row["id"]).execute()
                            st.rerun()
            else:
                st.info("İncelenmeyi bekleyen başvuru yok.")


    # =====================================================
    # SİSTEM TASARIMI
    # =====================================================
    elif sayfa == "Sistem Tasarımı" and st.session_state.kullanici_tipi == "Yonetici":
        st.header("🎨 Sistemi Özelleştir")
        st.write("Sitenizin arayüzünü ve operasyon kurallarını buradan yönetebilirsiniz.")
        st.caption("Görseller Supabase Storage içindeki `edavm-assets` bucket'ına kaydedilir.")
        st.divider()

        c1, c2 = st.columns(2)

        with c1:
            st.write("**1. Firma Logosu**")
            logo_url = storage_image_url(LOGO_STORAGE_PATH)

            if logo_url:
                st.image(logo_url, width=150)
            elif os.path.exists(LOGO_PATH):
                st.image(LOGO_PATH, width=150)

            yeni_logo = st.file_uploader("Yeni Logo Yükle (PNG/JPG)", type=["png", "jpg", "jpeg"], key="logo_up")

            if yeni_logo is not None:
                ok, err = upload_storage_file(yeni_logo, LOGO_STORAGE_PATH)

                if ok:
                    st.success("Logo Supabase Storage'a kaydedildi.")
                else:
                    st.error(f"Logo yüklenemedi: {err}")

            if st.button("🗑️ Logoyu Kaldır"):
                ok, err = remove_storage_file(LOGO_STORAGE_PATH)

                if ok:
                    st.success("Logo kaldırıldı.")
                    st.rerun()
                else:
                    st.error(f"Logo kaldırılamadı: {err}")

        with c2:
            st.write("**2. Arka Plan Görseli**")
            bg_url = storage_image_url(BG_STORAGE_PATH)

            if bg_url:
                st.image(bg_url, width=250)
            elif os.path.exists(BG_PATH):
                st.image(BG_PATH, width=250)

            yeni_bg = st.file_uploader("Yeni Arka Plan Yükle (PNG/JPG)", type=["png", "jpg", "jpeg"], key="bg_up")

            if yeni_bg is not None:
                ok, err = upload_storage_file(yeni_bg, BG_STORAGE_PATH)

                if ok:
                    st.success("Arka plan Supabase Storage'a kaydedildi.")
                else:
                    st.error(f"Arka plan yüklenemedi: {err}")

            if st.button("🗑️ Arka Planı Kaldır"):
                ok, err = remove_storage_file(BG_STORAGE_PATH)

                if ok:
                    st.success("Arka plan kaldırıldı.")
                    st.rerun()
                else:
                    st.error(f"Arka plan kaldırılamadı: {err}")

        st.divider()
        st.subheader("⚙️ Yoğun Saat Operasyon Kuralları")
        st.caption("12:00–18:00 arası minimum personel gereksinimlerini buradan değiştirebilirsiniz.")

        mevcut_minimumlar = get_peak_minimums()

        with st.form("peak_minimums_form"):
            c1, c2, c3 = st.columns(3)

            with c1:
                alt_kat_min = st.number_input(
                    "Alt Kat Minimum",
                    min_value=0,
                    max_value=50,
                    value=int(mevcut_minimumlar.get("Alt Kat", 5))
                )
                giris_kat_min = st.number_input(
                    "Giriş Kat Minimum",
                    min_value=0,
                    max_value=50,
                    value=int(mevcut_minimumlar.get("Giriş Kat", 2))
                )

            with c2:
                ust_kat_min = st.number_input(
                    "Üst Kat Minimum",
                    min_value=0,
                    max_value=50,
                    value=int(mevcut_minimumlar.get("Üst Kat", 1))
                )
                dis_alan_min = st.number_input(
                    "Dış Alan Minimum",
                    min_value=0,
                    max_value=50,
                    value=int(mevcut_minimumlar.get("Dış Alan", 1))
                )

            with c3:
                dinamik_min = st.number_input(
                    "Dinamik Destek Minimum",
                    min_value=0,
                    max_value=50,
                    value=int(mevcut_minimumlar.get("Dinamik Destek", 1))
                )
                destek_min = st.number_input(
                    "Destek Minimum",
                    min_value=0,
                    max_value=50,
                    value=int(mevcut_minimumlar.get("Destek", 0))
                )
                toplam_min = st.number_input(
                    "Toplam Aktif Minimum",
                    min_value=0,
                    max_value=100,
                    value=int(mevcut_minimumlar.get("Toplam Aktif", 8))
                )

            if st.form_submit_button("💾 Operasyon Kurallarını Kaydet"):
                yeni_minimumlar = {
                    "Alt Kat": alt_kat_min,
                    "Giriş Kat": giris_kat_min,
                    "Üst Kat": ust_kat_min,
                    "Dış Alan": dis_alan_min,
                    "Dinamik Destek": dinamik_min,
                    "Destek": destek_min,
                    "Toplam Aktif": toplam_min
                }

                ok, err = save_peak_minimums(yeni_minimumlar)

                if ok:
                    st.success("Operasyon kuralları kaydedildi.")
                    st.rerun()
                else:
                    st.error(f"Kurallar kaydedilemedi: {err}")
