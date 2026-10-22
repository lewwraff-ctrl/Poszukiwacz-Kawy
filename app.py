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
    def is_ strictly_whole_bean_1kg(text: str) -> bool:
        """
        Sprawdza, czy oferta dotyczy WYŁĄCZNIE kawy ziarnistej 1 kg (1000 g).
        Odrzuca kawy mielone, rozpuszczalne, zbożowe i kapsułki.
        """
        t = text.lower()
        excluded = ["mielona", "rozpuszczalna", "kapsułki", "kapsulki", "zbożowa", "inpost"]
        if any(bad in t for bad in excluded):
            return False

        has_beans = "ziarnista" in t or "ziarno" in t
        has_weight = any(w in t for w in ["1 kg", "1kg", "1000 g", "1000g"])
        return has_beans and has_weight

    def get_regular_baseline_prices(self) -> List[CoffeeOffer]:
        """Stały asortyment (tylko kawa ziarnista 1 kg) dostępny każdego dnia."""
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
        ]
        return [
            CoffeeOffer(
                sklep=store,
                nazwa=name,
                cena=price,
                czy_promocja=False,
                status_na_dzis=f"Stała cena półkowa ({self.today_str})",
                link_sklep=self.get_store_promo_url(store),
                link_mapa=self.get_map_url(store),
            )
            for store, name, price in base
        ]

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
        expired_keywords = [
            "archiwum",
            "archiwalna",
            "zakończona",
            "nieaktualna",
            "2022",
            "2023",
            "2024",
            "2025",
        ]
        return any(w in t for w in expired_keywords)

    def search_live_today_promotions(self) -> List[CoffeeOffer]:
        """Szuka aktualnych promocji wyłącznie na kawę ziarnistą 1 kg."""
        promo_offers = []
        year_str = self.now_pl.strftime("%Y")

        # 1. Sprawdzenie agregatorów gazetek (Ding / Promoceny) pod kątem kawy ziarnistej
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

                        matched_store = next(
                            (s for s in self.stores if s.lower() in text.lower()), None
                        )
                        if matched_store:
                            price = self.extract_price(text)
                            if price:
                                clean_name = re.sub(r"\s+", " ", text)[:75]
                                promo_offers.append(
                                    CoffeeOffer(
                                        sklep=matched_store,
                                        nazwa=clean_name,
                                        cena=price,
                                        czy_promocja=True,
                                        status_na_dzis=f"🔥 Promocja z gazetki ({self.today_str})",
                                        link_sklep=self.get_store_promo_url(matched_store),
                                        link_mapa=self.get_map_url(matched_store),
                                    )
                                )
