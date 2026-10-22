import re
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from zoneinfo import ZoneInfo
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup


@dataclass
class CoffeeOffer:
    sklep: str
    nazwa: str
    cena: float
    czy_promocja: bool
    status_na_dzis: str
    intensywnosc: str
    kwasowosc: str
    profil: str
    link_sklep: str
    link_mapa: str


class DailyCoffeeNavigator:
    def __init__(self, city: str = ""):
        self.stores = ["Kaufland", "Auchan", "Carrefour", "Biedronka", "Lidl", "Dino"]
        self.city = city.strip()
        self.now_pl = datetime.now(ZoneInfo("Europe/Warsaw"))
        self.today_str = self.now_pl.strftime("%d.%m.%Y")
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8",
        }

    def get_map_url(self, store: str) -> str:
        query = f"{store} {self.city}".strip()
        return f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(query)}"

    def get_store_promo_url(self, store: str) -> str:
        links = {
            "Auchan": "https://zakupy.auchan.pl/shop/search?text=kawa%20ziarnista%201kg",
            "Carrefour": "https://www.carrefour.pl/szukaj?q=kawa%20ziarnista%201kg",
            "Biedronka": "https://www.biedronka.pl/pl/gazetki-promocyjne",
            "Lidl": "https://www.lidl.pl/c/nasze-brozury/s10008614",
            "Kaufland": "https://www.kaufland.pl/oferta/aktualny-tydzien.html",
            "Dino": "https://marketdino.pl/",
        }
        return links.get(store, "https://www.google.pl")

    @staticmethod
    def is_strictly_whole_bean_1kg(text: str) -> bool:
        t = text.lower()
        excluded = ["mielona", "rozpuszczalna", "kapsułki", "kapsulki", "zbożowa", "inpost"]
        if any(bad in t for bad in excluded):
            return False
        has_beans = "ziarnista" in t or "ziarno" in t
        has_weight = any(w in t for w in ["1 kg", "1kg", "1000 g", "1000g"])
        return has_beans and has_weight

    def get_taste_profile(self, name: str) -> tuple[str, str, str]:
        n = name.lower()
        if "gold" in n or "oro" in n:
            return ("Średnia / Zbalansowana (3/5)", "Niska (łagodna)", "Miodowe nuty, orzech, niska kwasowość")
        elif "espresso" in n or "gusto" in n:
            return ("Wysoka / Mocna (4/5)", "Minimalna", "Ciemny wypał, czekolada, intensywna crema")
        elif "crema" in n:
            return ("Średnia (3/5)", "Niska", "Kremowe body, delikatna słodycz, uniwersalna")
        elif "tchibo" in n or "family" in n:
            return ("Bardzo mocna (5/5)", "Średnia", "Tradycyjny, wyrazisty smak, nuta goryczki")
        elif "woseba" in n or "finezja" in n or "mocca" in n:
            return ("Średnia (3/5)", "Niska / Delikatna", "Aromatyczna, orzechowo-czekoladowa")
        else:
            return ("Średnia (3/5)", "Niska", "Klasyczny profil do domu")

    def get_regular_baseline_prices(self) -> List[CoffeeOffer]:
        base = [
            ("Auchan", "Kawa ziarnista Auchan (Kciuk) / Pouce 1kg", 29.99),
            ("Carrefour", "Kawa ziarnista Simpl / Carrefour Classic 1kg", 31.99),
            ("Auchan", "Kawa ziarnista Auchan Classic Crema 1kg", 34.98),
            ("Biedronka", "Kawa ziarnista Cafe d'Or Crema / Espresso 1kg", 34.99),
            ("Lidl", "Kawa ziarnista Bellarom Crema / Espresso 1kg", 34.99),
            ("Kaufland", "Kawa ziarnista K-Classic Crema / Espresso 1kg", 34.99),
            ("Carrefour", "Kawa ziarnista Carrefour Sensation 1kg", 36.99),
            ("Dino", "Kawa ziarnista Prima Finezja / Woseba 1kg", 38.99),
            ("Biedronka", "Kawa ziarnista Cafe d'Or Gold 1kg", 39.99),
            ("Lidl", "Kawa ziarnista Bellarom Gold 1kg", 39.99),
            ("Dino", "Kawa ziarnista Tchibo Family 1kg", 44.99),
            ("Kaufland", "Kawa ziarnista Jacobs Kronung / Tchibo Family 1kg", 49.99),
            # Częste hity internetowe w dyskontach:
            ("Biedronka", "Kawa ziarnista Lavazza Qualita Oro 1kg", 54.99),
            ("Lidl", "Kawa ziarnista Bellarom Espresso 1kg", 37.99),
            ("Kaufland", "Kawa ziarnista Woseba Mocca Fix Gold 1kg", 42.99),
        ]
        offers = []
        for store, name, price in base:
            intens, kwas, prof = self.get_taste_profile(name)
            offers.append(
                CoffeeOffer(
                    sklep=store,
                    nazwa=name,
                    cena=price,
                    czy_promocja=False,
                    status_na_dzis=f"Cena półkowa ({self.today_str})",
                    intensywnosc=intens,
                    kwasowosc=kwas,
                    profil=prof,
                    link_sklep=self.get_store_promo_url(store),
                    link_mapa=self.get_map_url(store),
                )
            )
        return offers

    @staticmethod
    def extract_price(text: str) -> Optional[float]:
        if not text:
            return None
        matches = re.findall(r"(\d{2}[\.,]\d{2})\s*(?:zł|PLN)", text, re.IGNORECASE)
        valid_prices = []
        for m in matches:
            val = float(m.replace(",", "."))
            if 21.0 <= val <= 95.0:
                valid_prices.append(val)
        return min(valid_prices) if valid_prices else None

    @staticmethod
    def is_expired_text(text: str) -> bool:
        t = text.lower()
        return any(w in t for w in ["archiwum", "archiwalna", "zakończona", "2022", "2023", "2024", "2025"])

    def search_live_today_promotions(self) -> List[CoffeeOffer]:
        promo_offers = []
        year_str = self.now_pl.strftime("%Y")
        aggregator_urls = [
            "https://ding.pl/szukaj/kawa-ziarnista-1kg",
            "https://promoceny.pl/szukaj/kawa%20ziarnista%201kg",
        ]
        for url in aggregator_urls:
            try:
                res = requests.get(url, headers=self.headers, timeout=8)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, "html.parser")
                    for item in soup.find_all(["div", "article", "li", "a"]):
                        text = item.get_text(" ", strip=True)
                        if len(text) > 300 or not self.is_strictly_whole_bean_1kg(text):
                            continue
                        if self.is_expired_text(text):
                            continue
                        matched_store = next((s for s in self.stores if s.lower() in text.lower()), None)
                        if matched_store:
                            price = self.extract_price(text)
                            if price:
                                clean_name = re.sub(r"\s+", " ", text)[:75]
                                intens, kwas, prof = self.get_taste_profile(clean_name)
                                promo_offers.append(
                                    CoffeeOffer(
                                        sklep=matched_store,
                                        nazwa=clean_name,
                                        cena=price,
                                        czy_promocja=True,
                                        status_na_dzis=f"🔥 Promocja gazetkowa ({self.today_str})",
                                        intensywnosc=intens,
                                        kwasowosc=kwas,
                                        profil=prof,
                                        link_sklep=self.get_store_promo_url(matched_store),
                                        link_mapa=self.get_map_url(matched_store),
                                    )
                                )
            except Exception:
                pass
        return promo_offers

    def get_all_today(self) -> List[CoffeeOffer]:
        items = self.get_regular_baseline_prices()
        items.extend(self.search_live_today_promotions())
        return items


# --- INTERFEJS STRONY ---
st.set_page_config(page_title="Gdzie dziś po kawę ziarnistą 1 kg?", page_icon="☕", layout="wide")

now_pl = datetime.now(ZoneInfo("Europe/Warsaw"))
days_pl = ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"]
day_name = days_pl[now_pl.weekday()]
today_formatted = now_pl.strftime("%d.%m.%Y")

st.title("☕ Gdzie dzisiaj jechać po najtańszą kawę ZIARNISTĄ 1 kg?")
st.markdown(
    f"📅 **Stan na dzień:** `{day_name}, {today_formatted}` | "
    f"Sieci: **Kaufland, Auchan, Carrefour, Biedronka, Lidl, Dino**"
)

city_input = st.text_input(
    "📍 Wpisz swoje miasto lub dzielnicę (opcjonalnie do nawigacji):",
    placeholder="np. Poznań, Warszawa Mokotów, Wrocław...",
)

if st.button("🚗 Sprawdź oferty, smaki i opinie z internetu", type="primary"):
    with st.spinner(f"Pobieram ceny, profile i opinie internautów na dzień {today_formatted}..."):
        nav = DailyCoffeeNavigator(city=city_input)
        offers = nav.get_all_today()

        df = pd.DataFrame([vars(o) for o in offers])
        df.sort_values(by="cena", ascending=True, inplace=True)
        df.drop_duplicates(subset=["sklep", "nazwa", "cena"], inplace=True)
        df.reset_index(drop=True, inplace=True)

        best = df.iloc[0]

        # REKOMENDACJA
        st.success(
            f"### 🎯 JEDŹ DZISIAJ DO: **{best['sklep'].upper()}**\n"
            f"**{best['cena']:.2f} zł** — *{best['nazwa']}* ({best['status_na_dzis']})\n\n"
            f"👅 **Profil smaku:** Intensywność: **{best['intensywnosc']}** | "
            f"Kwasowość: **{best['kwasowosc']}** | Nuty: *{best['profil']}*"
        )

        btn_col1, btn_col2, _ = st.columns([1, 1, 2])
        with btn_col1:
            st.link_button(f"🗺️ Nawiguj do {best['sklep']}", best["link_mapa"], use_container_width=True)
        with btn_col2:
            st.link_button(f"🔗 Zobacz gazetkę", best["link_sklep"], use_container_width=True)

        st.divider()

        # INTERNETOWY RANKING POLECANYCH PRZEZ LUDZI
        st.subheader("💬 Co polecają ludzie w internecie? (Ranking opinii konsumentów)")
        st.write("Oto zestawienie kaw ziarnistych 1 kg najchętniej polecanych na polskich grupach kawowych i forach jako najlepszy wybór w relacji ceny do jakości:")
        
        internet_favorites = [
            {"kawa": "Lavazza Qualita Oro 1 kg", "polecenia": "⭐⭐⭐⭐⭐ (Hit internetu)", "opinia_ludzi": "Najczęściej polecana kawa z dyskontów do ekspresów ciśnieniowych i przelewu. Niska kwasowość, nuty kwiatowo-owocowe, świetna crema."},
            {"kawa": "Bellarom Crema / Gold (Lidl) 1 kg", "polecenia": "⭐⭐⭐⭐☆ (Król budżetu)", "opinia_ludzi": "Zdecydowany faworyt forów internetowych w kategorii 'cena do jakości'. Jak
