"""Synthetic Swiss documents with planted personal data, so the labels come for free."""

import json
import random
import string
from pathlib import Path

DOCS_PATH = Path("data/docs.jsonl")

FIRST_NAMES = {
    "Frau": ["Anna", "Laura", "Sarah", "Nicole", "Sandra", "Lea", "Chantal", "Ursula", "Mia"],
    "Herr": ["Daniel", "Thomas", "Marco", "Reto", "Lukas", "Beat", "Urs", "Jan", "Simon"],
}
# Several surnames are also German words (Koch = cook, Vogel = bird), which makes them harder.
SURNAMES = [
    "Meier", "Müller", "Keller", "Brunner", "Schmid", "Gerber", "Bühler", "Huber", "Steiner",
    "Koch", "Vogel", "Wolf", "Fuchs", "Graf", "Berger", "Zürcher", "Bernasconi", "Rossi",
]
# The last few streets lack a typical suffix (-strasse, -gasse, -weg, -platz).
STREETS = [
    "Bahnhofstrasse", "Seefeldstrasse", "Kirchgasse", "Rosenweg", "Dorfstrasse",
    "Marktplatz", "Obere Zäune", "Im Gässli", "Rütihof", "Auf der Mauer",
]
TOWNS = [
    ("8001", "Zürich"), ("3011", "Bern"), ("6003", "Luzern"), ("4051", "Basel"),
    ("9000", "St. Gallen"), ("8400", "Winterthur"), ("6300", "Zug"), ("5000", "Aarau"),
]
MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
          "September", "Oktober", "November", "Dezember"]

# Slots that hold personal data, with their entity type. {first}, {surname} and {title}
# reuse the main person's name and are covered by its PERSON entity.
PII_SLOTS = {"person": "PERSON", "person2": "PERSON", "ahv": "AHV", "iban": "IBAN",
             "phone": "PHONE", "email": "EMAIL", "address": "ADDRESS"}
# Facts that are not personal and that a cloud LLM needs to do its job: they must survive.
KEEP_SLOTS = ["amount", "date", "invoice_no", "order_no"]

TEMPLATES = {
    "bank_email": (
        "Betreff: Dauerauftrag ändern\n\nGuten Tag\n\nIch möchte den Dauerauftrag über "
        "{amount} ab dem {date} auf mein neues Konto {iban} umstellen. Bei Fragen erreichen "
        "Sie mich unter {phone}.\n\nFreundliche Grüsse\n{person}\n{address}"
    ),
    "invoice": (
        "Rechnung Nr. {invoice_no}\nDatum: {date}\n\nAn: {person}\n{address}\n\n"
        "Für die Reparatur der Heizung stellen wir Ihnen {amount} in Rechnung. Eine "
        "allfällige Gutschrift überweisen wir auf Ihr Konto {iban}.\n"
        "Bitte bestätigen Sie den Termin an {email}."
    ),
    "medical_note": (
        "Arztbericht vom {date}\n\nName: {person}\nAHV-Nr. {ahv}\nWohnhaft: {address}\n\n"
        "{title} {surname} stellte sich mit Rückenschmerzen seit drei Wochen vor. "
        "Physiotherapie verordnet, Kontrolle in sechs Wochen."
    ),
    "hr_note": (
        "Personalnotiz\n\n{person} (AHV {ahv}) beginnt am {date} im Projektteam. Der Lohn "
        "wird auf {iban} überwiesen. Als Referenz wurde {person2} angegeben, erreichbar "
        "unter {phone}."
    ),
    "support_ticket": (
        "Ticket {order_no}\n\nKunde: {person}, {email}\nRückruf an {phone}\n\n"
        "Der Router liefert seit dem {date} kein Internet mehr. {title} {surname} hat das "
        "Gerät bereits neu gestartet."
    ),
    "insurance_claim": (
        "Schadenmeldung\n\nVersicherte Person: {person}\nAHV-Nummer: {ahv}\n"
        "Adresse: {address}\n\nAm {date} wurde in der Wohnung eingebrochen. Gestohlen "
        "wurden ein Laptop und Schmuck im Wert von {amount}. Bitte überweisen Sie die "
        "Entschädigung auf {iban}."
    ),
    "club_chat": (
        "Hoi zäme, {person} hier, ich bin neu im Verein! Ihr erreicht mich unter "
        "{phone} oder {email}. Meine Adresse ist {address}, falls jemand zum Training am "
        "{date} mitfahren möchte."
    ),
    "callback_note": (
        "Hallo zusammen\n\nBitte {person} zurückrufen, es geht um die Bestellung {order_no}"
        " über {amount}. Rückruf an {phone}. Die Rückzahlung soll auf {iban} gehen."
    ),
}


def ahv_check_digit(digits12: str) -> int:
    """EAN-13 check digit, which Swiss AHV numbers use."""
    total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(digits12))
    return (10 - total % 10) % 10


def iban_check_digits(bban: str) -> int:
    """ISO 13616 check digits for a Swiss IBAN ("CH" becomes 1217)."""
    return 98 - int(bban + "121700") % 97


def ahv(rng: random.Random) -> str:
    d = "756" + "".join(rng.choices(string.digits, k=9))
    d += str(ahv_check_digit(d))
    return f"{d[:3]}.{d[3:7]}.{d[7:11]}.{d[11:]}"


def iban(rng: random.Random) -> str:
    bban = "".join(rng.choices(string.digits, k=17))
    compact = f"CH{iban_check_digits(bban):02d}{bban}"
    if rng.random() < 0.5:
        return compact
    return " ".join(compact[i : i + 4] for i in range(0, len(compact), 4))


def phone(rng: random.Random) -> str:
    prefix = rng.choice(["76", "78", "79", "44", "31", "41"])  # mobile and landline
    d = prefix + "".join(rng.choices(string.digits, k=7))
    return rng.choice([
        f"0{d[:2]} {d[2:5]} {d[5:7]} {d[7:]}",
        f"+41 {d[:2]} {d[2:5]} {d[5:7]} {d[7:]}",
        f"0{d}",
    ])


def email(first: str, surname: str, rng: random.Random) -> str:
    local = f"{first}.{surname}".lower().translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue"}))
    return f"{local}@{rng.choice(['bluewin.ch', 'gmx.ch', 'sunrise.ch', 'outlook.com'])}"


def make_doc(rng: random.Random, kind: str) -> dict:
    title = rng.choice(["Frau", "Herr"])
    first, surname = rng.choice(FIRST_NAMES[title]), rng.choice(SURNAMES)
    plz, town = rng.choice(TOWNS)
    values = {
        "title": title, "first": first, "surname": surname,
        "person": f"{first} {surname}",
        "person2": f"{rng.choice(FIRST_NAMES[rng.choice(['Frau', 'Herr'])])} "
                   f"{rng.choice([s for s in SURNAMES if s != surname])}",
        "ahv": ahv(rng), "iban": iban(rng), "phone": phone(rng),
        "email": email(first, surname, rng),
        "address": f"{rng.choice(STREETS)} {rng.randint(1, 80)}, {plz} {town}",
        "amount": f"CHF {rng.randint(80, 9000):,}.{rng.choice(['00', '50'])}".replace(",", "'"),
        "date": f"{rng.randint(1, 28)}. {rng.choice(MONTHS)} 2026",
        "invoice_no": f"2026-{rng.randint(1000, 9999)}",
        "order_no": str(rng.randint(10**9, 10**10 - 1)),
    }
    template = TEMPLATES[kind]
    used = {slot for _, slot, _, _ in string.Formatter().parse(template) if slot}
    return {
        "kind": kind,
        "text": template.format(**values),
        "pii": [{"type": t, "value": values[s]} for s, t in PII_SLOTS.items() if s in used],
        "keep": [values[s] for s in KEEP_SLOTS if s in used],
    }


def generate(per_kind: int = 30, seed: int = 0) -> list[dict]:
    rng = random.Random(seed)
    docs = [make_doc(rng, kind) for kind in TEMPLATES for _ in range(per_kind)]
    return [{"id": i, **doc} for i, doc in enumerate(docs)]


def load_docs() -> list[dict]:
    with DOCS_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


if __name__ == "__main__":
    docs = generate()
    DOCS_PATH.parent.mkdir(exist_ok=True)
    with DOCS_PATH.open("w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    print(f"wrote {len(docs)} documents to {DOCS_PATH}")
