import re
from dataclasses import dataclass
from typing import List, Optional
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup


@dataclass
class CoffeeOffer:
    sklep: str
    nazwa: str
    cena: float
    zrodlo: str


class FastCoffeeHunter:
    def __init__(self):
        self.stores = ["Kaufland", "Auchan", "Carrefour", "Biedronka", "Lidl", "Dino"]
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "pl-PL,pl;q=0.9",
        }

    @staticmethod
    def extract_price(text: str) -> Optional[float]:
        if not text:
            return None
        # Szuka ceny w formacie np. 39,99 zł lub 45.00
        matches = re.findall(r"(\d{2,3}[\.,]\d{2})", text)
        for m in matches:
            val = float(m.replace(",", "."))
            if 18.0 <= val <= 140.0:  # Realistyczny przedział cenowy dla 1 kg kawy
                return val
        return None

    @staticmethod
    def is_1kg_coffee(title: str) -> bool:
        t = title.lower()
        has_coffee = "kawa" in t
        has_weight = any(w in t for w in ["1 kg", "1kg", "1000 g", "1000g"])
        return has_coffee and has_weight

    def scrape_ding(self) -> List[CoffeeOffer]:
        """Pobiera oferty ze wszystkich 6 sieci z agregatora gazetek Ding.pl."""
        offers = []
        urls = [
            "https://ding.pl/szukaj/kawa-1kg",
            "https://ding.pl/szukaj/kawa-ziarnista-1kg",
            "https://ding.pl/szukaj/kawa-1000g",
        ]
        for url in urls:
            try:
                res = requests.get(url, headers=self.headers, timeout=10)
                if res.status_code != 200:
                    continue
                soup = BeautifulSoup(res.text, "html.parser")
                for item in soup.find_all(["div", "article", "li", "a"]):
                    text = item.get_text(" ", strip=True)
                    if len(text) > 300 or not self.is_1kg_coffee(text):
                        continue

                    matched_store = next(
                        (s for s in self.stores if s.lower() in text.lower()), None
                    )
                    if matched_store:
                        price = self.extract_price(text)
                        if price:
                            clean_name = re.sub(r"\s+", " ", text)[:85]
                            offers.append(
                                CoffeeOffer(
                                    sklep=matched_store,
                                    nazwa=clean_name,
                                    cena=price,
                                    zrodlo="Gazetka / Promocja",
                                )
                            )
            except Exception:
                pass
        return offers

    def scrape_promoceny(self) -> List[CoffeeOffer]:
        """Dodatkowe źródło dla wszystkich 6 sieci (Promoceny.pl)."""
        offers = []
        url = "https://promoceny.pl/szukaj/kawa%201kg"
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                for item in soup.find_all(["div", "article", "tr"]):
                    text = item.get_text(" ", strip=True)
                    if len(text) > 300 or not self.is_1kg_coffee(text):
                        continue

                    matched_store = next(
                        (s for s in self.stores if s.lower() in text.lower()), None
                    )
                    if matched_store:
                        price = self.extract_price(text)
                        if price:
                            clean_name = re.sub(r"\s+", " ", text)[:85]
                            offers.append(
                                CoffeeOffer(
                                    sklep=matched_store,
                                    nazwa=clean_name,
                                    cena=price,
                                    zrodlo="Promoceny",
                                )
                            )
        except Exception:
            pass
        return offers

    def run(self) -> List[CoffeeOffer]:
        all_offers = []
        all_offers.extend(self.scrape_ding())
        all_offers.extend(self.scrape_promoceny())
        return all_offers


# --- INTERFEJS STRONY ---
st.set_page_config(page_title="Łowca Kawy 1kg", page_icon="☕", layout="wide")
st.title("☕ Porównywarka cen kawy 1 kg")
st.write("Obsługiwane sklepy: **Kaufland, Auchan, Carrefour, Biedronka, Lidl, Dino**")

if st.button("🔍 Szukaj najtańszej kawy", type="primary"):
    with st.spinner("Przeszukuję aktualne oferty ze wszystkich 6 sklepów..."):
        hunter = FastCoffeeHunter()
        offers = hunter.run()

        if not offers:
            st.warning(
                "W tym momencie nie znaleziono aktywnych ofert na kawę 1 kg w publicznych gazetkach lub serwer został tymczasowo przyblokowany."
            )
        else:
            df = pd.DataFrame([vars(o) for o in offers])
            df.drop_duplicates(subset=["sklep", "cena"], inplace=True)
            df.sort_values(by="cena", ascending=True, inplace=True)
            df.reset_index(drop=True, inplace=True)

            st.subheader("🏆 Najtańsza znaleziona kawa w każdej sieci:")
            cols = st.columns(3)
            for idx, store in enumerate(hunter.stores):
                store_df = df[df["sklep"].str.lower() == store.lower()]
                with cols[idx % 3]:
                    if not store_df.empty:
                        best = store_df.iloc[0]
                        st.success(f"**{store}**: {best['cena']:.2f} zł\n\n{best['nazwa'][:55]}...")
                    else:
                        st.info(f"**{store}**: Brak aktualnej promocji 1 kg")

            st.subheader("📋 Wszystkie znalezione oferty (od najtańszej):")
            st.dataframe(df, use_container_width=True)
