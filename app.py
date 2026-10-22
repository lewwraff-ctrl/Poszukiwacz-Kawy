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
    def is_valid_coffee_1kg(text: str) -> bool:
        """
        Wykazuje kawę ziarnistą o wadze 1 kg LUB zestawy 2x500g / 500g+500g.
        Odrzuca małe paczki 250g bez opcji zestawu.
        """
        t = text.lower()
        excluded = ["mielona", "rozpuszczalna", "kapsułki", "kapsulki", "zbożowa"]
        if any(bad in t for bad in excluded):
            return False

        has_beans = "ziarnista" in t or "ziarno" in t
        has_1kg = any(w in t for w in ["1 kg", "1kg", "1000 g", "1000g"])
        has_bundle = any(w in t for w in ["2x500", "2 x 500", "500g + 500g", "500 g + 500 g", "dwa opakowania", "drugi produkt"])

        return has_beans and (has_1kg or has_bundle)

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
            if 20.0 <= val <= 95.0:
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
            "https://ding.pl/szukaj/kawa-ziarnista-500g",
            "https://promoceny.pl/szukaj/kawa%20ziarnista%201kg",
        ]
        for url in aggregator_urls:
            try:
                res = requests.get(url, headers=self.headers, timeout=8)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, "html.parser")
                    for item in soup.find_all(["div", "article", "li", "a"]):
                        text = item.get_text(" ", strip=True)
                        if len(text) > 350 or not self.is_valid_coffee_1kg(text):
                            continue
                        if self.is_expired_text(text):
                            continue
                        matched_store = next((s for s in self.stores if s.lower() in text.lower()), None)
                        if matched_store:
                            price = self.extract_price(text)
                            if price:
                                # Jeśli wykryto zestaw 2x500g z ceną za pojedynczą paczkę, przeliczamy na 1kg
                                if "500g" in text.lower() or "500 g" in text.lower():
                                    if "drugi" in text.lower() or "50%" in text.lower() or "tańszy" in text.lower():
                                        price = price * 1.5  # Szacunkowy koszt zestawu 2x500g w promocji 50% na drugi
                                    else:
                                        price = price * 2.0  # Dwie sztuki po 500g

                                clean_name = re.sub(r"\s+", " ", text)[:80]
                                intens, kwas, prof = self.get_taste_profile(clean_name)
                                promo_offers.append(
                                    CoffeeOffer(
                                        sklep=matched_store,
                                        nazwa=f"[PROMOCJA] {clean_name}",
                                        cena=price,
                                        czy_promocja=True,
                                        status_na_dzis=f"🔥 Promocja / Zestaw 1kg ({self.today_str})",
                                        intensywnosc=intens,
                                        kwasowosc=kwas,
                                        profil=prof,
                                        link_sklep=self.get_store_promo_url(matched_store),
                                        link_mapa=self.get_map_url(matched_store),
                                    )
                                )
            except Exception:
                pass

        # Wyszukiwanie dodatkowe w sieci
        for store in self.stores:
            query = f"kawa ziarnista 1kg 2x500g promocja {store} {year_str} zł"
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}&df=w"
            try:
                res = requests.get(url, headers=self.headers, timeout=8)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, "html.parser")
                    for res_box in soup.select(".result__body"):
                        title_el = res_box.select_one(".result__title")
                        snippet_el = res_box.select_one(".result__snippet")
                        link_el = res_box.select_one("a.result__a")

                        full_text = (
                            (title_el.get_text(" ", strip=True) if title_el else "")
                            + " - "
                            + (snippet_el.get_text(" ", strip=True) if snippet_el else "")
                        )

                        if self.is_expired_text(full_text):
                            continue

                        if store.lower() in full_text.lower() and self.is_valid_coffee_1kg(full_text):
                            price = self.extract_price(full_text)
                            if price:
                                if "500g" in full_text.lower() and price < 30:
                                    price = price * 2.0  # Przeliczenie 2x500g na 1kg

                                clean_title = title_el.get_text(" ", strip=True)[:70] if title_el else f"Kawa ziarnista 1kg ({store})"
                                href = link_el.get("href") if link_el and link_el.get("href", "").startswith("http") else self.get_store_promo_url(store)
                                intens, kwas, prof = self.get_taste_profile(clean_title)
                                promo_offers.append(
                                    CoffeeOffer(
                                        sklep=store,
                                        nazwa=f"[GAZETKA] {clean_title}",
                                        cena=price,
                                        czy_promocja=True,
                                        status_na_dzis=f"🔥 Promocja / Gazetka ({self.today_str})",
                                        intensywnosc=intens,
                                        kwasowosc=kwas,
                                        profil=prof,
                                        link_sklep=href,
                                        link_mapa=self.get_map_url(store),
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

st.title("☕ Gdzie dzisiaj jechać po najtańszą kawę ZIARNISTĄ 1 kg (Promocje + Zestawy 2x500g)")
st.markdown(
    f"📅 **Stan na dzień:** `{day_name}, {today_formatted}` | "
    f"Sieci: **Kaufland, Auchan, Carrefour, Biedronka, Lidl, Dino**"
)

city_input = st.text_input(
    "📍 Wpisz swoje miasto lub dzielnicę (opcjonalnie do nawigacji):",
    placeholder="np. Poznań, Warszawa Mokotów, Wrocław...",
)

if st.button("🚗 Szukaj najtańszych promocji i zestawów", type="primary"):
    with st.spinner(f"Przeszukuję gazetki, promocje i zestawy 500g+500g na dzień {today_formatted}..."):
        nav = DailyCoffeeNavigator(city=city_input)
        offers = nav.get_all_today()

        df = pd.DataFrame([vars(o) for o in offers])
        df.sort_values(by="cena", ascending=True, inplace=True)
        df.drop_duplicates(subset=["sklep", "nazwa", "cena"], inplace=True)
        df.reset_index(drop=True, inplace=True)

        best = df.iloc[0]

        st.success(
            f"### 🎯 JEDŹ DZISIAJ DO: **{best['sklep'].upper()}**\n"
            f"**{best['cena']:.2f} zł** (za 1 kg) — *{best['nazwa']}* ({best['status_na_dzis']})\n\n"
            f"👅 **Profil smaku:** Intensywność: **{best['intensywnosc']}** | "
            f"Kwasowość: **{best['kwasowosc']}** | Nuty: *{best['profil']}*"
        )

        btn_col1, btn_col2, _ = st.columns([1, 1, 2])
        with btn_col1:
            st.link_button(f"🗺️ Nawiguj do {best['sklep']}", best["link_mapa"], use_container_width=True)
        with btn_col2:
            st.link_button(f"🔗 Zobacz gazetkę", best["link_sklep"], use_container_width=True)

        st.divider()

        # OSOBNA TABELA TYLKO NA PROMOCJE I ZESTAWY 1KG
        st.subheader(f"🔥 Aktualne PROMOCJE i zestawy 1 kg (w tym 2x500g) na dzień {today_formatted}:")
        promo_df = df[df["czy_promocja"] == True].copy()

        if promo_df.empty:
            st.info("Brak wykrytych specjalnych promocji gazetkowych w tej chwili. Sprawdź pełne zestawienie cen stałych poniżej.")
        else:
            promo_df.reset_index(drop=True, inplace=True)
            st.dataframe(
                promo_df[["sklep", "nazwa", "cena", "status_na_dzis", "link_sklep"]].rename(
                    columns={
                        "sklep": "Sklep",
                        "nazwa": "Oferta promocyjna",
                        "cena": "Szacunkowa cena za 1 kg (zł)",
                        "status_na_dzis": "Typ oferty",
                        "link_sklep": "Link do gazetki"
                    }
                ),
                column_config={"Link do gazetki": st.column_config.LinkColumn("Link")},
                use_container_width=True,
            )

        st.divider()

        # KĄCIK ŻONY
        st.subheader("⭐ Kącik Żony — Oceny i opinie żony")
        if "wife_reviews" not in st.session_state:
            st.session_state.wife_reviews = {}

        selected_coffee_to_review = st.selectbox("Wybierz kawę do oceny:", df["nazwa"].unique())
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            wife_rating = st.slider("Ocena żony (gwiazdki ⭐):", 1, 5, 4)
        with col_r2:
            wife_comment = st.text_input("Opinia / Notatka smakowa żony:", placeholder="np. super do mleka, za mocna...")

        if st.button("💾 Zapisz ocenę żony"):
            st.session_state.wife_reviews[selected_coffee_to_review] = {
                "rating": "⭐" * wife_rating,
                "comment": wife_comment
            }
            st.success("Zapisano ocenę żony!")

        if st.session_state.wife_reviews:
            st.markdown("#### 📝 Zapisane recenzje żony:")
            for cov, rev in st.session_state.wife_reviews.items():
                st.info(f"**{cov}** — Ocena: {rev['rating']} | Opinia: *{rev['comment']}*")

        st.divider()

        # KAFELKI SKLEPÓW
        st.subheader(f"🏪 Najtańsza opcja 1 kg w każdym z 6 sklepów ({today_formatted}):")
        cols = st.columns(3)
        for idx, store in enumerate(nav.stores):
            store_df = df[df["sklep"].str.lower() == store.lower()]
            with cols[idx % 3]:
                if not store_df.empty:
                    top_store = store_df.iloc[0]
                    with st.container(border=True):
                        st.markdown(f"#### 🛒 {store} — **{top_store['cena']:.2f} zł**")
                        st.caption(f"☕ **{top_store['nazwa']}**")
                        st.markdown(f"⚡ *Moc:* {top_store['intensywnosc']}")
                        st.markdown(f"🍋 *Kwasowość:* {top_store['kwasowosc']}")
                        st.markdown(f"🍫 *Nuty:* {top_store['profil']}")
                        c1, c2 = st.columns(2)
                        with c1:
                            st.link_button("🗺️ Jedź", top_store["link_mapa"], use_container_width=True)
                        with c2:
                            st.link_button("🔗 Oferta", top_store["link_sklep"], use_container_width=True)

        st.divider()

        # PEŁNA TABELA
        st.subheader("📋 Pełna tabela: Wszystkie opcje (Promocje, Zestawy 2x500g i Ceny Stałe)")
        st.dataframe(
            df[["sklep", "nazwa", "cena", "intensywnosc", "kwasowosc", "profil", "status_na_dzis"]].rename(
                columns={
                    "sklep": "Sklep",
                    "nazwa": "Kawa ziarnista 1 kg / Zestaw",
                    "cena": "Cena za 1 kg (zł)",
                    "intensywnosc": "Intensywność",
                    "kwasowosc": "Kwasowość",
                    "profil": "Nuty smakowe",
                    "status_na_dzis": "Rodzaj oferty",
                }
            ),
            use_container_width=True,
        )
