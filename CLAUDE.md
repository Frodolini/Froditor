# Froditor – rettleiing for Claude

Froditor er ein enkel tekstbehandlar i stil med Notisblokk for Linux, skriven i
Python 3 med GTK 4 (PyGObject). Han blir levert som `.deb`-pakke og oppdatert
via ei signert APT-kjelde på GitHub Pages. Eigar: Frode (GitHub: Frodolini).

## Språk

- All tekst brukaren ser i appen, i README og i commit-meldingar skal vere på **nynorsk**.
- Svar Frode på nynorsk.

## Struktur

| Sti | Innhald |
| --- | --- |
| `froditor/__init__.py` | `__version__`, `BIRTH_DATE`, `RELEASE_DATE`, `format_date()` |
| `froditor/app.py` | `Gtk.Application`, snarvegar (`ACCELS`), «Om»-dialogen |
| `froditor/window.py` | Hovudvindauget: meny, filer, søk/erstatt, skrift, statuslinje |
| `froditor/fileio.py` | Lesing/skriving av filer (teiknkoding, linjeskift, trygg lagring) |
| `froditor/settings.py` | Innstillingar i `~/.config/froditor/settings.json` |
| `data/` | Ikon, `.desktop`-fil, APT-kjelda som pakka installerer |
| `packaging/` | `build-deb.sh`, `build-apt-repo.sh`, nettsida på Pages |
| `.github/workflows/release.yml` | Test → bygg → release → Pages |
| `tests/` | `test_fileio.py` (utan skjerm), `test_window.py` (treng skjerm) |

## Slik blir ein ny versjon publisert

- **Auk `__version__` i `froditor/__init__.py` og push til `main`.** Arbeidsflyten
  ser at det ikkje finst ein release for versjonen, byggjer `.deb`, lagar taggen
  `vX.Y.Z` og releasen, og oppdaterer APT-kjelda. Brukarane får versjonen med
  `sudo apt update && sudo apt upgrade`.
- Endringar i appen (alt brukaren merkar) → auk versjonen:
  - `X.Y.Z+1` for småretting og tekstendringar
  - `X.Y+1.0` for nye funksjonar
- Endringar berre i dokumentasjon, testar eller denne fila → **ikkje** auk versjonen.
- **Ikkje push taggar sjølv** og ikkje lag releasar for hand – arbeidsflyten gjer det.
  (Tag-push er òg blokkert frå Claude sitt skymiljø.)
- `RELEASE_DATE` skal stå som `None` i kjeldekoden; `build-deb.sh` set datoen.

## Før du pushar

1. Køyr testane. Dei må gå gjennom:
   ```bash
   sudo apt-get install -y python3-gi gir1.2-gtk-4.0 xvfb   # om dei manglar
   GSK_RENDERER=cairo xvfb-run -a python3 -m unittest discover -s tests -t . -v
   ```
   Bruk ein `python3` som har `gi` installert. I Claude sitt skymiljø kan
   `python3` vere ein annan versjon enn systemet sin – bruk då t.d. `python3.12`.
2. Skriv testar for ny funksjonalitet i `tests/`.
3. Om det endrar noko brukaren ser: oppdater README (funksjonsliste og snarvegtabell).
4. Sjekk gjerne at pakka byggjer: `packaging/build-deb.sh` (skal skrive ut stien til `.deb`-fila).

## Reglar for koden

- **Må fungere på GTK 4.6 og nyare** (Ubuntu 22.04, Debian 12 og nyare).
  API frå GTK 4.10+ (t.d. `Gtk.FileDialog`, `Gtk.FontDialog`, `Gtk.AlertDialog`)
  skal ha ein fallback, slik det alt er gjort i `window.py` med `hasattr(Gtk, ...)`.
- **Ingen nye avhengigheiter.** Pakka krev berre `python3`, `python3-gi` og
  `gir1.2-gtk-4.0`. Ikkje bruk libadwaita eller pip-pakkar.
- Dialogar: bruk `self.ask(...)` og `self.show_error(...)` i `window.py`.
- Ulagra endringar må aldri gå tapt: alt som lukkar eller byter dokument skal gå
  gjennom `confirm_discard()`.
- Fillagring går alltid gjennom `fileio.write_text()` (trygg lagring via mellombels fil).
  Linjeskift (LF/CRLF) blir teke vare på. Nye `.ps1`-filer får UTF-8 med BOM.
- Lagre-dialogen brukar `Gtk.FileChooserNative` med vilje, fordi berre den fortel
  kva filtype brukaren valde. Ikkje byt han ut med `Gtk.FileDialog`.
- Nye snarvegar: legg dei i `ACCELS` i `app.py` og i snarvegtabellen i README.
- Nye filtypar: legg dei i `FILE_TYPES` i `window.py`.
- Hald det enkelt. Froditor skal vere ein Notisblokk, ikkje ein kodeeditor.

## Ikkje rør utan at Frode ber om det

- Signeringsnøkkelen (hemmelegheita `GPG_PRIVATE_KEY`) og `scripts/oppsett-signering.sh`.
  Ein ny nøkkel gjer at alle maskiner må installere `.deb`-fila på nytt for hand.
- Adressa i `data/froditor.sources` og namnet på keyring-fila.
- Pakkenamnet `froditor` og app-ID-en `no.frodolini.Froditor`.

## Kjende ting

- GitHub Pages-miljøet (`github-pages`) tillèt publisering frå `main` og frå taggar `v*`.
- Dei grøne stega i Actions er `test`, `release` og `deploy`. Når versjonen ikkje er
  ny, blir bygginga hoppa over og `deploy` køyrer ikkje – det er rett.
