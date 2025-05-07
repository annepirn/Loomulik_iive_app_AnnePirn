import streamlit as st
import requests
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from io import StringIO

STATISTIKAAMETI_API_URL = "https://andmed.stat.ee/api/v1/et/stat/RV032"
GEOJSON_PATH = "maakonnad.geojson"

AASTAD = [str(y) for y in range(2014, 2024)]
MAAKOND_KOODID = ["39", "44", "49", "51", "57", "59", "65", "67", "70", "74", "78", "82", "84", "86"]

def build_payload():
    return {
        "query": [
            {"code": "Aasta", "selection": {"filter": "item", "values": AASTAD}},
            {"code": "Maakond", "selection": {"filter": "item", "values": MAAKOND_KOODID}},
            {"code": "Sugu", "selection": {"filter": "item", "values": ["2", "3"]}}  # 2=Mees, 3=Naine
        ],
        "response": {"format": "csv"}
    }

@st.cache_data(show_spinner=False)
def import_data():
    response = requests.post(
        STATISTIKAAMETI_API_URL,
        json=build_payload(),
        headers={'Content-Type': 'application/json'}
    )
    if response.status_code == 200:
        return pd.read_csv(StringIO(response.content.decode('utf-8-sig')))
    else:
        st.error("API päring ebaõnnestus.")
        return pd.DataFrame()

@st.cache_data
def import_geojson():
    return gpd.read_file(GEOJSON_PATH)

# --- Streamlit UI ---
st.set_page_config(layout="wide")
st.title("Loomulik iive Eesti maakondades")

# Andmed
df = import_data()
gdf = import_geojson()
if df.empty:
    st.stop()

# Külgriba valikud
with st.sidebar:
    st.header("Seaded")
    valitud_aasta = st.selectbox("Vali aasta", sorted(df["Aasta"].unique()))
    sugu_valik = st.selectbox("Vali sugupool", ["Mehed", "Naised", "Kokku"])
    muutuja_valik = st.selectbox("Vali näitaja", ["Elussünnid", "Surmad", "Loomulik iive"])

# Andmetöötlus
df_aasta = df[df["Aasta"] == valitud_aasta]

if sugu_valik in ["Mehed", "Naised"]:
    veeru_nimi = f"{sugu_valik} {muutuja_valik}"
    if veeru_nimi not in df_aasta.columns:
        st.error(f"Veerg '{veeru_nimi}' puudub andmetes.")
        st.stop()
    df_summa = df_aasta[["Maakond", veeru_nimi]].copy()
    df_summa.rename(columns={veeru_nimi: "Valitud"}, inplace=True)
else:
    mehed_veerg = f"Mehed {muutuja_valik}"
    naised_veerg = f"Naised {muutuja_valik}"
    if mehed_veerg not in df_aasta.columns or naised_veerg not in df_aasta.columns:
        st.error("Üks vajalikest veergudest puudub.")
        st.stop()
    df_summa = df_aasta[["Maakond", mehed_veerg, naised_veerg]].copy()
    df_summa["Valitud"] = df_summa[mehed_veerg] + df_summa[naised_veerg]
    df_summa = df_summa[["Maakond", "Valitud"]]

# Geoandmete ühendamine
gdf_merged = gdf.merge(df_summa, how="left", left_on="MNIMI", right_on="Maakond")

# --- Kaart ---
st.subheader(f"{sugu_valik} {muutuja_valik} maakondade kaupa ({valitud_aasta})")
fig, ax = plt.subplots(figsize=(10, 8))
gdf_merged.plot(
    column="Valitud", cmap="viridis", linewidth=0.8, ax=ax, edgecolor='0.8', legend=True
)
ax.axis('off')
st.pyplot(fig)

# --- Tabel ---
st.subheader("Maakondlikud andmed (tabelina)")
df_summa_sorted = df_summa.sort_values("Valitud", ascending=False).reset_index(drop=True)
st.dataframe(df_summa_sorted, use_container_width=True)
