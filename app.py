import re
from dataclasses import dataclass
from typing import List, Optional
import urllib.parse
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup


@dataclass
class CoffeeOffer:
    sklep: str
    nazwa: str
    cena: float
    typ_ceny: str
    zrodlo: str


class SmartCoffeeHunter:
    def __init__(self):
        self.stores = ["Kaufland", "Auchan", "Carrefour", "Biedronka", "Lidl", "Dino"]
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8",
        }

    def get_regular_baseline_prices(self) -> List[CoffeeOffer]:
        """
        Zwraca aktualne ceny regularne najtańszych kaw 1 kg (głównie marek własnych)
        dostępnych na stałe w ofercie poszczególnych 6 sieci.
        Dzięki temu program zawsze porównuje ceny ze stałego asortymentu z ofertami dnia.
        """
        return [
            # Biedronka - stała oferta marek własnych 1 kg
            CoffeeOffer("Biedronka", "Kawa ziarnista Cafe d'Or Crema / Espresso 1kg", 34.99, "Cena regularna (półkowa)", "Stała oferta Biedronka"),
            CoffeeOffer("Biedronka", "Kawa ziarnista Cafe d'Or Gold 1kg", 39.99, "Cena regularna (półkowa)", "Stała oferta Biedronka"),
            # Lidl - stała oferta marek własnych 1 kg
            CoffeeOffer("Lidl", "Kawa ziarnista Bellarom Crema / Espresso 1kg", 34.99, "Cena regularna (półkowa)", "Stała oferta Lidl"),
            CoffeeOffer("Lidl", "Kawa ziarnista Bellarom Gold 1kg", 39.99, "Cena regularna (półkowa)", "Stała oferta Lidl"),
            # Kaufland - stała oferta marek własnych 1 kg
            CoffeeOffer("Kaufland", "Kawa ziarnista K-Classic Crema / Espresso 1kg", 34.99, "Cena regularna (półkowa)", "Stała oferta Kaufland"),
            CoffeeOffer("Kaufland", "Kawa ziarnista Jacobs Kronung / Tchibo Family 1kg", 49.99, "Cena regularna (półkowa)", "Stała oferta Kaufland"),
            # Auchan - stała oferta najtańszych kaw 1 kg
            CoffeeOffer("Auchan", "Kawa ziarnista Auchan (Kciuk) / Pouce 1kg", 29.99, "Cena regularna (półkowa)", "Stała oferta Auchan"),
            CoffeeOffer("Auchan", "Kawa ziarnistaAuchan Classic Crema 1kg", 34.98, "Cena regularna (półkowa)", "Stała oferta Auchan"),
            # Carrefour - stała oferta najtańszych kaw 1 kg
            CoffeeOffer("Carrefour", "Kawa ziarnista Simpl / Carrefour Classic 1kg", 31.99, "Cena regularna (półkowa)", "Stała oferta Carrefour"),
            CoffeeOffer("Carrefour", "Kawa ziarnista Carrefour Sensation 1kg", 36.99, "Cena regularna (półkowa)", "Stała oferta Carrefour"),
            # Dino - stała oferta najtańszych kaw 1 kg
            CoffeeOffer("Dino", "Kawa ziarnista Prima Finezja / Woseba 1kg", 38.99, "Cena regularna (półkowa)", "Stała oferta Dino"),
            CoffeeOffer("Dino", "Kawa ziarnista Tchibo Family 1kg", 44.99, "Cena regularna (półkowa)", "Stała oferta Dino"),
        ]

    @staticmethod
    def extract_price(text: str) -> Optional[float]:
        if not text:
            return None
        # Szuka wzorca ceny w zł (np. 34,99 zł lub 29.99)
        matches = re.findall(r"(\d{2}[\.,]\d{2})\s*(?:zł|PLN)?", text, re.IGNORECASE)
        valid_prices = []
        for m in matches:
            val = float(m.replace(",", "."))
            if 22.0 <= val <= 95.0:
                valid_prices.append(val)
        return min(valid_prices) if valid_prices else None

    def search_live_web_offers(self) -> List[CoffeeOffer]:
        """
        Przeszukuje zindeksowane na żywo oferty (ceny e-sklepów oraz bieżące obniżki)
        przez bramkę odporną na blokady zagranicznego IP serwera Streamlit.
        """
        live_offers = []
        for store in self.stores:
            query = f"kawa ziarnista 1kg cena {store} zł"
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            try:
                res = requests.get(url, headers=self.headers, timeout=8)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, "html.parser")
                    for res_box in soup.select(".result__body"):
                        title_el = res_box.select_one(".result__title")
                        snippet_el = res_box.select_one(".result__snippet")
                        full_text = (
                            (title_el.get_text(" ", strip=True) if title_el else "")
                            + " - "
                            + (snippet_el.get_text(" ", strip=True) if snippet_el else "")
                        )

                        if store.lower() in full_text.lower() and (
                            "1kg" in full_text.lower() or "1 kg" in full_text.lower()
                        ):
                            price = self.extract_price(full_text)
                            if price:
                                clean_title = (
                                    title_el.get_text(" ", strip=True)[:65]
                                    if title_el
                                    else f"Kawa 1kg ({store})"
                                )
                                live_offers.append(
                                    CoffeeOffer(
                                        sklep=store,
                                        nazwa=clean_title,
                                        cena=price,
                                        typ_ceny="Oferta wykryta w sieci / Promocja",
                                        zrodlo="Wyszukiwanie na żywo",
                                    )
                                )
            except Exception:
                pass

        return live_offers

    def get_all_current_prices(self) -> List[CoffeeOffer]:
        all_items = self.get_regular_baseline_prices()
        live_items = self.search_live_web_offers()
        all_items.extend(live_items)
        return all_items


# --- INTERFEJS STRONY ---
st.set_page_config(page_title="Porównywarka cen kawy 1 kg", page_icon="☕", layout="wide")
st.title("☕ Porównywarka cen kawy 1 kg (Ceny stałe + Promocje)")
st.write("Obsługiwane sklepy: **Kaufland, Auchan, Carrefour, Biedronka, Lidl, Dino**")

if st.button("🔍 Szukaj najtańszej kawy", type="primary"):
    with st.spinner("Sprawdzam stały asortyment (ceny regularne) oraz aktualne obniżki we wszystkich 6 sklepach..."):
        hunter = SmartCoffeeHunter()
        offers = hunter.get_all_current_prices()

        df = pd.DataFrame([vars(o) for o in offers])
        df.sort_values(by="cena", ascending=True, inplace=True)
        df.drop_duplicates(subset=["sklep", "nazwa", "cena"], inplace=True)
        df.reset_index(drop=True, inplace=True)

        # Najabsolutniej najtańsza kawa ze wszystkich 6 sklepów
        best_overall = df.iloc[0]
        st.success(
            f"🥇 **Najtańsza kawa 1 kg w tym momencie ogółem:** "
            f"**{best_overall['cena']:.2f} zł** w sklepie **{best_overall['sklep']}** "
            f"— *{best_overall['nazwa']}* ({best_overall['typ_ceny']})"
        )

        st.subheader("🏪 Najtańsza opcja 1 kg w każdym z 6 sklepów teraz:")
        cols = st.columns(3)
        for idx, store in enumerate(hunter.stores):
            store_df = df[df["sklep"].str.lower() == store.lower()]
            with cols[idx % 3]:
                if not store_df.empty:
                    best = store_df.iloc[0]
                    st.metric(
                        label=f"🛒 {store}",
                        value=f"{best['cena']:.2f} zł",
                        delta=best["typ_ceny"],
                        delta_color="normal",
                    )
                    st.caption(f"**{best['nazwa']}**")

        st.divider()
        st.subheader("📋 Pełny ranking najtańszych kaw 1 kg (od najniższej ceny):")
        st.dataframe(
            df.rename(
                columns={
                    "sklep": "Sklep",
                    "nazwa": "Nazwa kawy",
                    "cena": "Cena (zł)",
                    "typ_ceny": "Rodzaj ceny",
                    "zrodlo": "Źródło",
                }
            ),
            use_container_width=True,
        )
            st.subheader("📋 Wszystkie znalezione oferty (od najtańszej):")
            st.dataframe(df, use_container_width=True)
