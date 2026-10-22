import asyncio
import re
import subprocess
from dataclasses import dataclass
from typing import List, Optional
import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page

# Automatyczna instalacja przeglądarki przy pierwszym starcie na serwerze
@st.cache_resource
def ensure_browser_installed():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception:
        pass

ensure_browser_installed()


@dataclass
class CoffeeOffer:
    sklep: str
    nazwa: str
    cena: float
    zrodlo: str


class MultiStoreCoffeeHunter:
    def __init__(self):
        self.stores = ["Kaufland", "Auchan", "Carrefour", "Biedronka", "Lidl", "Dino"]

    @staticmethod
    def extract_price(text: str) -> Optional[float]:
        if not text:
            return None
        match = re.search(r"(\d+[\.,]\d{2})", text.replace(" ", ""))
        if match:
            return float(match.group(1).replace(",", "."))
        return None

    @staticmethod
    def is_1kg_coffee(title: str) -> bool:
        t = title.lower()
        has_coffee = "kawa" in t
        has_weight = any(w in t for w in ["1 kg", "1kg", "1000 g", "1000g"])
        return has_coffee and has_weight

    async def scrape_auchan(self, page: Page) -> List[CoffeeOffer]:
        offers = []
        url = "https://zakupy.auchan.pl/shop/search?text=kawa%201kg"
        try:
            await page.goto(url, timeout=20000, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            soup = BeautifulSoup(await page.content(), "html.parser")
            for card in soup.select("article, div[data-testid*='product']"):
                text = card.get_text(" ", strip=True)
                if self.is_1kg_coffee(text):
                    price = self.extract_price(text)
                    title_el = card.find(["h2", "h3", "a", "span"])
                    title = title_el.get_text(strip=True) if title_el else text[:60]
                    if price and price > 15.0:
                        offers.append(CoffeeOffer("Auchan", title, price, "zakupy.auchan.pl"))
        except Exception:
            pass
        return offers

    async def scrape_carrefour(self, page: Page) -> List[CoffeeOffer]:
        offers = []
        url = "https://www.carrefour.pl/szukaj?q=kawa%201kg"
        try:
            await page.goto(url, timeout=20000, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            soup = BeautifulSoup(await page.content(), "html.parser")
            for card in soup.select("div[class*='product'], article"):
                text = card.get_text(" ", strip=True)
                if self.is_1kg_coffee(text):
                    price = self.extract_price(text)
                    title_el = card.find(["h2", "h3", "a"])
                    title = title_el.get_text(strip=True) if title_el else text[:60]
                    if price and price > 15.0:
                        offers.append(CoffeeOffer("Carrefour", title, price, "carrefour.pl"))
        except Exception:
            pass
        return offers

    async def scrape_promo_aggregators(self, page: Page) -> List[CoffeeOffer]:
        offers = []
        url = "https://ding.pl/szukaj/kawa-1kg"
        try:
            await page.goto(url, timeout=25000, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            soup = BeautifulSoup(await page.content(), "html.parser")
            for item in soup.select("div[class*='offer'], div[class*='product'], a[class*='card'], li"):
                text = item.get_text(" ", strip=True)
                if not self.is_1kg_coffee(text):
                    continue
                matched_store = next((s for s in self.stores if s.lower() in text.lower()), None)
                if matched_store:
                    price = self.extract_price(text)
                    if price and 15.0 < price < 150.0:
                        clean_name = re.sub(r"\s+", " ", text)[:80]
                        offers.append(CoffeeOffer(matched_store, clean_name, price, f"Gazetka ({matched_store})"))
        except Exception:
            pass
        return offers

    async def run(self) -> List[CoffeeOffer]:
        all_offers = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            context = await browser.new_context(locale="pl-PL")
            page = await context.new_page()

            all_offers.extend(await self.scrape_auchan(page))
            all_offers.extend(await self.scrape_carrefour(page))
            all_offers.extend(await self.scrape_promo_aggregators(page))

            await browser.close()
        return all_offers


# --- INTERFEJS STRONY INTERNETOWEJ (STREAMLIT) ---
st.set_page_config(page_title="Łowca Kawy 1kg", page_icon="☕", layout="wide")
st.title("☕ Porównywarka cen kawy 1 kg na żywo")
st.write("Obsługiwane sieci: **Kaufland, Auchan, Carrefour, Biedronka, Lidl, Dino**")

if st.button("🔍 Szukaj najtańszej kawy teraz", type="primary"):
    with st.spinner("Przeszukuję sklepy i gazetki promocyjne... (potrwa to ok. 15-20 sekund)"):
        hunter = MultiStoreCoffeeHunter()
        offers = asyncio.run(hunter.run())

        if not offers:
            st.warning("Nie udało się pobrać ofert lub brak aktualnych promocji na kawę 1 kg.")
        else:
            df = pd.DataFrame([vars(o) for o in offers])
            df.drop_duplicates(subset=["sklep", "cena"], inplace=True)
            df.sort_values(by="cena", ascending=True, inplace=True)
            df.reset_index(drop=True, inplace=True)

            st.subheader("🏆 Najtańsza kawa 1 kg w każdym ze sklepów")
            cols = st.columns(6)
            for idx, store in enumerate(hunter.stores):
                store_df = df[df["sklep"].str.lower() == store.lower()]
                with cols[idx]:
                    if not store_df.empty:
                        best = store_df.iloc[0]
                        st.metric(label=store, value=f"{best['cena']:.2f} zł", delta=best["nazwa"][:25] + "...")
                    else:
                        st.metric(label=store, value="Brak", delta="Brak w gazetce", delta_color="off")

            st.subheader("📋 Pełna tabela wszystkich znalezionych ofert")
            st.dataframe(df, use_container_width=True)

            csv = df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="📥 Pobierz tabelę do Excela (CSV)",
                data=csv,
                file_name="najtansza_kawa_1kg.csv",
                mime="text/csv",
            )
