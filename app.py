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

# --- Streamlit ---
st.set_page_config(page_title="Loomulik iive", layout="wide")
st.title("Loomulik iive Eesti maakondades")
st.markdown("### Tere tulemast Anne Pirni Eesti iibe dashboardile!")

# --- Andmete laadimine ---
df = import_data()
gdf = import_geojson()

if df.empty:
    st.stop()

# --- Vasak menüü ---
with st.sidebar:
    valitud_aasta = st.selectbox("Vali aasta", sorted(df["Aasta"].unique()))
    sugu_valik = st.selectbox("Vali sugupool", ["Mehed", "Naised", "Kokku"])
    muutuja_valik = st.selectbox("Vali kaardimuutuja", ["Elussünnid", "Surmad", "Loomulik iive"])

# --- Andmete töötlemine kaardi jaoks ---
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

# --- Kaart ---
gdf_merged = gdf.merge(df_summa, how="left", left_on="MNIMI", right_on="Maakond")

fig, ax = plt.subplots(figsize=(10, 8))
gdf_merged.plot(
    column="Valitud", cmap="viridis", linewidth=0.8, ax=ax, edgecolor='0.8', legend=True
)
ax.set_title(f"{sugu_valik} {muutuja_valik} maakondade kaupa ({valitud_aasta})")
ax.axis('off')
st.pyplot(fig)

# --- Tabel kõigi näitajatega ---
df_aasta = df[df["Aasta"] == valitud_aasta].copy()

# Lisame maakonna koodid geoandmetest
maakonna_koodid = gdf[["MNIMI", "MKOOD"]].rename(columns={"MNIMI": "Maakond", "MKOOD": "Maakonna kood"})
df_aasta = df_aasta.merge(maakonna_koodid, on="Maakond", how="left")

# Loome uue DataFrame'i tabeli jaoks
tabeli_df = pd.DataFrame()

if sugu_valik in ["Mehed", "Naised"]:
    # Kontrollime, et vajalikud veerud olemas
    vajalikud = [f"{sugu_valik} Elussünnid", f"{sugu_valik} Surmad", f"{sugu_valik} Loomulik iive"]
    for v in vajalikud:
        if v not in df_aasta.columns:
            st.error(f"Veerg '{v}' puudub andmetes.")
            st.stop()

    tabeli_df["Elussünnid"] = df_aasta[f"{sugu_valik} Elussünnid"]
    tabeli_df["Surmad"] = df_aasta[f"{sugu_valik} Surmad"]
    tabeli_df["Loomulik iive"] = df_aasta[f"{sugu_valik} Loomulik iive"]

else:  # Kokku
    # Summeerime meeste ja naiste väärtused
    for v in ["Elussünnid", "Surmad", "Loomulik iive"]:
        mehed_col = f"Mehed {v}"
        naised_col = f"Naised {v}"
        if mehed_col not in df_aasta.columns or naised_col not in df_aasta.columns:
            st.error(f"Puuduvad veerud '{mehed_col}' ja/või '{naised_col}'.")
            st.stop()
        tabeli_df[v] = df_aasta[mehed_col] + df_aasta[naised_col]

# Lisame Maakonna, Maakonna koodi ja järjekorranumbri
tabeli_df.insert(0, "Maakond", df_aasta["Maakond"])
tabeli_df.insert(0, "Maakonna kood", df_aasta["Maakonna kood"])
tabeli_df.insert(0, "Jrk nr", range(1, len(tabeli_df) + 1))

# --- Tabeli kuvamine ---
st.subheader(f"Eesti rahvastiku näitajad ({sugu_valik}, {valitud_aasta})")
st.dataframe(tabeli_df)

# --- Allalaadimine ---
csv = tabeli_df.to_csv(index=False).encode("utf-8")
st.download_button(
    label="Laadi tabel alla CSV-na",
    data=csv,
    file_name=f"rahvastik_{sugu_valik.lower()}_{valitud_aasta}.csv",
    mime="text/csv"
)
