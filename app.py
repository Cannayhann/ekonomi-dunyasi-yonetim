import streamlit as st
import pandas as pd
import os

# 1. SİSTEM AYARLARI
st.set_page_config(page_title="ED-AVM Yönetim", layout="wide")

TALEPLER_FILE = "talepler.csv"
VARDIYA_FILE = "vardiya_duzeni.csv"
AKSAMCI_SINIRI = 6 

gunler = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

if not os.path.exists(TALEPLER_FILE):
    pd.DataFrame(columns=["Personel", "İzin Günü", "Haftalık Vardiya", "Durum"]).to_csv(TALEPLER_FILE, index=False)

# 2. ARAYÜZ BAŞLIĞI
st.title("🏢 EKONOMİ DÜNYASI AVM | Haftalık Planlama")

tab1, tab2, tab3 = st.tabs(["✍️ Personel Giriş Ekranı", "👑 Yönetici Onay & Denetim", "📅 Kesinleşen Liste"])

# --- TAB 1: PERSONEL GİRİŞİ ---
with tab1:
    st.header("Haftalık Tercihinizi Giriniz")
    with st.form("personel_formu", clear_on_submit=True):
        isim = st.text_input("Adınız Soyadınız:").strip().title()
        izin_gunu = st.selectbox("Bu hafta hangi gün İZİNLİ olacaksınız?", gunler)
        haftalik_shift = st.radio("Haftanın geri kalanında hangi vardiyada olacaksınız?", 
                                  ["Sabahçı (09:00 - 18:00)", "Akşamcı (12:00 - 21:00)"])
        
        submit = st.form_submit_button("Planımı Gönder")
        
        if submit:
            if isim == "":
                st.error("Lütfen isminizi giriniz!")
            else:
                yeni = {"Personel": isim, "İzin Günü": izin_gunu, "Haftalık Vardiya": haftalik_shift, "Durum": "Beklemede"}
                df_t = pd.read_csv(TALEPLER_FILE)
                pd.concat([df_t, pd.DataFrame([yeni])]).to_csv(TALEPLER_FILE, index=False)
                st.success(f"Teşekkürler {isim}. Haftalık planın iletildi.")

# --- TAB 2: YÖNETİCİ ONAY VE KONTENJAN DENETİMİ ---
with tab2:
    st.header("Gelen Planları Onayla")
    df_t = pd.read_csv(TALEPLER_FILE)
    bekleyenler = df_t[df_t["Durum"] == "Beklemede"]
    
    # Kapasite Analizi - NaN (float) hatalarını engellemek için str() ekledik
    aksamci_counts = {g: 0 for g in gunler}
    for _, r in df_t[df_t["Durum"] != "Reddedildi"].iterrows():
        if "Akşamcı" in str(r["Haftalık Vardiya"]):
            for g in gunler:
                if g != str(r["İzin Günü"]):
                    aksamci_counts[g] += 1
    
    st.subheader("📊 Mevcut Doluluk Analizi (Akşamcı Sayıları)")
    cols = st.columns(7)
    for i, g in enumerate(gunler):
        count = aksamci_counts[g]
        if count > AKSAMCI_SINIRI:
            cols[i].error(f"{g}: {count}")
        else:
            cols[i].metric(g, f"{count} Kişi")

    st.divider()

    if len(bekleyenler) > 0:
        for idx, row in bekleyenler.iterrows():
            with st.expander(f"📌 {row['Personel']} | İzin: {row['İzin Günü']} | Vardiya: {row['Haftalık Vardiya']}"):
                c1, c2 = st.columns(2)
                if c1.button("Onayla", key=f"on_{idx}"):
                    df_t.at[idx, "Durum"] = "Onaylandı"
                    df_t.to_csv(TALEPLER_FILE, index=False)
                    st.rerun()
                if c2.button("Reddet", key=f"red_{idx}"):
                    df_t.at[idx, "Durum"] = "Reddedildi"
                    df_t.to_csv(TALEPLER_FILE, index=False)
                    st.rerun()
    else:
        st.info("Onay bekleyen plan bulunmuyor.")

    if st.button("🚀 Planı Kesinleştir ve Listeyi Oluştur"):
        onayli = df_t[df_t["Durum"] == "Onaylandı"]
        if len(onayli) == 0:
            st.warning("Henüz onaylanmış bir plan yok.")
        else:
            unique_staff = onayli["Personel"].unique()
            final_df = pd.DataFrame(index=unique_staff, columns=gunler)
            
            for _, r in onayli.iterrows():
                p = str(r["Personel"])
                iz = str(r["İzin Günü"])
                # Hata Buradaydı: str() ekleyerek float hatasını çözdük
                shift = "A (12-21)" if "Akşamcı" in str(r["Haftalık Vardiya"]) else "S (09-18)"
                
                for g in gunler:
                    if g == iz: 
                        final_df.at[p, g] = "🔴 İZİNLİ"
                    elif g == "Pazar": 
                        final_df.at[p, g] = "🟢 TAM GÜÇ"
                    else: 
                        final_df.at[p, g] = shift
            
            final_df.reset_index(inplace=True)
            final_df.rename(columns={'index': 'Personel'}, inplace=True)
            final_df.to_csv(VARDIYA_FILE, index=False)
            st.success("Haftalık çizelge başarıyla yayınlandı!")

# --- TAB 3: KESİNLEŞEN LİSTE ---
with tab3:
    if os.path.exists(VARDIYA_FILE):
        df_v = pd.read_csv(VARDIYA_FILE)
        
        def style_status(v):
            val_str = str(v)
            c = "#ff4b4b" if "🔴" in val_str else "#1c83e1" if "A " in val_str else "#28a745" if "S " in val_str else "#4CAF50"
            return f'background-color: {c}; color: white'
            
        st.table(df_v.style.applymap(style_status, subset=gunler))
    else:
        st.info("Henüz kesinleşmiş bir liste yok. 'Listeyi Oluştur' butonuna basınız.")