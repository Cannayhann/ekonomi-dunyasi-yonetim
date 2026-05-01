import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="ED-AVM Sistem", layout="wide")

TALEPLER_FILE = "talepler.csv"
VARDIYA_FILE = "vardiya_duzeni.csv"
ADMIN_SIFRE = "ayhanlar2026"  # Bu şifreyi istediğin gibi değiştirebilirsin

gunler = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

if not os.path.exists(TALEPLER_FILE):
    pd.DataFrame(columns=["Personel", "İzin Günü", "Haftalık Vardiya", "Durum"]).to_csv(TALEPLER_FILE, index=False)

# --- SESSİON STATE (GİRİŞ KONTROLÜ) ---
if "giris_yapildi" not in st.session_state:
    st.session_state.giris_yapildi = False
    st.session_state.kullanici_tipi = ""
    st.session_state.kullanici_adi = ""

# --- GİRİŞ EKRANI ---
if not st.session_state.giris_yapildi:
    st.title("🏢 Ekonomi Dünyası AVM Giriş Portalı")
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        giris_tipi = st.radio("Giriş Türü Seçiniz:", ["Personel Girişi", "Yönetici Girişi"])
        
        if giris_tipi == "Personel Girişi":
            isim = st.text_input("Adınız Soyadınız:")
            if st.button("Giriş Yap"):
                if isim.strip() != "":
                    st.session_state.giris_yapildi = True
                    st.session_state.kullanici_tipi = "Personel"
                    st.session_state.kullanici_adi = isim.strip().title()
                    st.rerun()
                else:
                    st.error("Lütfen isminizi giriniz!")
                    
        elif giris_tipi == "Yönetici Girişi":
            sifre = st.text_input("Yönetici Şifresi:", type="password")
            if st.button("Sistemi Aç"):
                if sifre == ADMIN_SIFRE:
                    st.session_state.giris_yapildi = True
                    st.session_state.kullanici_tipi = "Yönetici"
                    st.session_state.kullanici_adi = "Admin"
                    st.rerun()
                else:
                    st.error("Hatalı Şifre!")

# --- ANA SİSTEM (GİRİŞ YAPILDIKTAN SONRA) ---
else:
    # Çıkış Yap Butonu (Sağ üstte)
    colA, colB = st.columns([8, 1])
    with colA:
        st.title(f"🏢 ED-AVM | Hoş Geldin, {st.session_state.kullanici_adi}")
    with colB:
        if st.button("🚪 Çıkış Yap"):
            st.session_state.giris_yapildi = False
            st.rerun()
            
    st.markdown("---")

    # PERSONEL EKRANI SADECE TAB 1 VE TAB 3 GÖRÜR
    if st.session_state.kullanici_tipi == "Personel":
        tab1, tab3 = st.tabs(["✍️ Haftalık Planım", "📅 Kesinleşen Liste"])
        
        with tab1:
            st.info("💡 Not: Haftalık rotasyon kuralına göre seçim yapınız (1 hafta sabah, 1 hafta akşam).")
            with st.form("personel_formu", clear_on_submit=True):
                st.write(f"**Talep Oluşturan:** {st.session_state.kullanici_adi}")
                izin_gunu = st.selectbox("Bu hafta hangi gün İZİNLİ olacaksınız?", gunler)
                haftalik_shift = st.radio("Haftanın geri kalanında hangi vardiyada olacaksınız?", 
                                          ["Sabahçı (09:00 - 18:00)", "Akşamcı (12:00 - 21:00)"])
                
                if st.form_submit_button("Planımı Gönder"):
                    yeni = {"Personel": st.session_state.kullanici_adi, "İzin Günü": izin_gunu, "Haftalık Vardiya": haftalik_shift, "Durum": "Beklemede"}
                    df_t = pd.read_csv(TALEPLER_FILE)
                    pd.concat([df_t, pd.DataFrame([yeni])]).to_csv(TALEPLER_FILE, index=False)
                    st.success("Haftalık planın yönetime iletildi.")
                    
        with tab3:
            if os.path.exists(VARDIYA_FILE):
                df_v = pd.read_csv(VARDIYA_FILE)
                def style_status(v):
                    val_str = str(v)
                    c = "#ff4b4b" if "🔴" in val_str else "#1c83e1" if "A " in val_str else "#28a745" if "S " in val_str else "#4CAF50"
                    return f'background-color: {c}; color: white'
                st.table(df_v.style.map(style_status, subset=gunler))
            else:
                st.info("Henüz liste yayınlanmadı.")

    # YÖNETİCİ EKRANI HER ŞEYİ GÖRÜR
    elif st.session_state.kullanici_tipi == "Yönetici":
        tab2, tab3 = st.tabs(["👑 Yönetici Onay Paneli", "📅 Kesinleşen Liste"])
        
        with tab2:
            df_t = pd.read_csv(TALEPLER_FILE)
            bekleyenler = df_t[df_t["Durum"] == "Beklemede"]
            
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

            st.divider()
            if st.button("🚀 Planı Kesinleştir ve Listeyi Oluştur"):
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
                    st.success("Haftalık çizelge başarıyla yayınlandı!")
                else:
                    st.warning("Onaylanmış plan yok.")
                    
        with tab3:
            if os.path.exists(VARDIYA_FILE):
                df_v = pd.read_csv(VARDIYA_FILE)
                def style_status(v):
                    val_str = str(v)
                    c = "#ff4b4b" if "🔴" in val_str else "#1c83e1" if "A " in val_str else "#28a745" if "S " in val_str else "#4CAF50"
                    return f'background-color: {c}; color: white'
                st.table(df_v.style.map(style_status, subset=gunler))
