"""Froditor – ein enkel tekstbehandlar for Linux."""

__version__ = "1.2.0"
APP_ID = "no.frodolini.Froditor"
REPO_URL = "https://github.com/Frodolini/Froditor"

BIRTH_DATE = "2026-10-25"  # då Froditor kom til verda
RELEASE_DATE = None  # blir sett til datoen for versjonen når .deb-pakka blir bygd

MONTHS = ["januar", "februar", "mars", "april", "mai", "juni", "juli",
          "august", "september", "oktober", "november", "desember"]


def format_date(iso_date: str | None) -> str:
    """'2026-10-25' → '25. oktober 2026'."""
    if not iso_date:
        return "under utvikling"
    year, month, day = (int(part) for part in iso_date.split("-"))
    return f"{day}. {MONTHS[month - 1]} {year}"
