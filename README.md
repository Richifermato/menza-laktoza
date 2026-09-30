# Menza U4 bez laktózy

Každou neděli ve 13:00 stáhne jídelníček menzy UTB (výdejna U4) na nadcházející týden,
nechá AI (Google Gemini) ohodnotit každé jídlo semaforem pro člověka, který musí úplně
vyloučit laktózu, a výsledek zveřejní jako webovou stránku na GitHub Pages.

- 🟢 bez mléčných výrobků
- 🟡 může obsahovat skryté mléko – ověřit v kuchyni
- 🔴 obsahuje mléčné výrobky

## Jak to funguje

1. `.github/workflows/tydenni-jidelnicek.yml` spouští úlohu v neděli ve 13:00 (Europe/Prague).
2. `menza.py` stáhne veřejný RSS feed menzy, vybere polévky, obědy, minutky a pizzy,
   pošle je jedním dotazem do Gemini API a vygeneruje `docs/index.html`.
3. Úloha stránku commitne do repozitáře a GitHub Pages ji zveřejní.

Menza alergeny ve feedu nezveřejňuje, hodnocení je proto odhad podle názvu jídla.

## Spuštění lokálně

```
GEMINI_API_KEY=... python3 menza.py
```

Klíč zdarma: https://aistudio.google.com/apikey. V repozitáři je uložen jako secret `GEMINI_API_KEY`.
