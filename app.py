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
            ("Biedronka", "Kawa ziarnista Lavazza Qualita Oro 1kg", 54.99),
            ("Lidl", "Kawa ziarnista Bellarom Espresso 1kg", 37.99),
            ("Kaufland", "Kawa ziarnista Woseba Mocca Fix Gold 1kg", 42.99),
        ]
        offers = []
        for store, name, price in base:
            intens, kwas
