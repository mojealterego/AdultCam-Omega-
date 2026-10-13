"""Non-graphic, evidence-neutral programming templates; not revenue predictions."""

TEN_HOUR = (
    ('ACQUISITION', 'Otwarcie i test techniczny', 'Potwierdź transmisję, zasady czatu i uprawnienia uczestników.'),
    ('ENGAGEMENT', 'Przedstawienie formatu', 'Przejrzyste przedstawienie dostępnych form interakcji i ograniczeń.'),
    ('CONVERSION', 'Pierwszy cel społecznościowy', 'Cel widoczny, osiągalny i pozbawiony mylących obietnic.'),
    ('RECOVERY', 'Przerwa bezpieczeństwa', 'Sprawdź samopoczucie uczestników oraz sprzęt i prywatność.'),
    ('ENGAGEMENT', 'Segment tematyczny', 'Wariant dopuszczony przez regulamin i wybrane zgody.'),
    ('RETENTION', 'Wyróżnienie społeczności', 'Podziękuj uczestnikom bez ujawniania ich danych osobowych.'),
    ('CONVERSION', 'Oferty premium', 'Podaj jasne ceny, zakres i warunki produktów, o ile platforma dopuszcza.'),
    ('RECOVERY', 'Druga przerwa', 'Odśwież stan zgód, obciążenie i integralność ochrony obrazu.'),
    ('RETENTION', 'Zapowiedź kolejnego wydarzenia', 'Informuj o przyszłych planach tylko zgodnie z prawdą.'),
    ('CLOSING', 'Bezpieczne zakończenie', 'Zakończ stream, zweryfikuj OBS i zamknij sesję w audycie.'),
)


def build_ten_hour_plan() -> list[dict]:
    return [
        {'hour': i, 'category': category, 'goal': title,
         'operator_brief': brief, 'source': 'TEMPLATE_NOT_LIVE'}
        for i, (category,title,brief) in enumerate(TEN_HOUR, start=1)
    ]


def build_month_plan() -> list[dict]:
    plan=[]
    phases=[
        ('MARKET_ENTRY','Zbieraj rzeczywiste dane bez zakładania przychodów.'),
        ('OPTIMIZATION','Weryfikuj ograniczenia platform i dane z poprzedniego tygodnia.'),
        ('PREMIUM_POSITIONING','Testuj jasne i dozwolone warianty produktów premium.'),
        ('RETENTION','Weryfikuj zgodę na kontakt, lojalność i bezpieczeństwo kont.'),
    ]
    for day in range(1,31):
        phase,aim=phases[min((day-1)//7,3)]
        plan.append({'day':day,'phase':phase,'goal':aim,
                     'experiment': 'Pomiar wejść, konwersji i opinii wyłącznie z legalnie dostępnych źródeł.',
                     'estimated_revenue':None,'source':'TEMPLATE_NOT_LIVE'})
    return plan
