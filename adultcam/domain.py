"""Pure policy and lifecycle rules. No external I/O."""
from dataclasses import dataclass

ALLOWED_STATES = {
    'PREPARE': {'READY', 'CLOSED'},
    'READY': {'PREPARE', 'CLOSED'},
    'LIVE_PUBLIC': {'RECOVERY', 'ENDING'},
    'RECOVERY': {'LIVE_PUBLIC', 'ENDING'},
    'ENDING': {'CLOSED'},
    'CLOSED': set(),
}

OBS_OPERATIONS = frozenset({'start_stream', 'stop_stream'})


@dataclass(frozen=True)
class Decision:
    verdict: str
    reason: str
    risk_class: str


def session_transition_allowed(current: str, target: str, attested: bool) -> Decision:
    if target not in ALLOWED_STATES.get(current, set()):
        return Decision('BLOCK', f'Niedozwolone przejście {current} → {target}', 'R4')
    if target == 'READY' and not attested:
        return Decision('NEEDS_VERIFICATION', 'Wymagane aktualne oświadczenie o weryfikacji wieku, zgodzie i uprawnieniach.', 'R4')
    return Decision('ALLOW', 'Dopuszczalne przejście wewnętrzne.', 'R2')


def action_policy(operation: str, state: str, attested: bool) -> Decision:
    if operation not in OBS_OPERATIONS:
        return Decision('BLOCK', 'Operacja bez zweryfikowanego adaptera.', 'R6')
    if operation == 'start_stream':
        if state != 'READY':
            return Decision('BLOCK', 'Sesja musi być w stanie READY.', 'R4')
        if not attested:
            return Decision('NEEDS_VERIFICATION', 'Brak aktualnego oświadczenia operatora.', 'R4')
    if operation == 'stop_stream' and state == 'CLOSED':
        return Decision('BLOCK', 'Sesja jest zamknięta.', 'R4')
    # Emergency stop stays possible when a lost OBS receipt leaves the session in READY.
    # Stopping a broadcast does not require renewing an expired self-attestation.
    return Decision('ALLOW_WITH_CONDITIONS', 'Wymagane osobne zatwierdzenie operatora i potwierdzona odpowiedź OBS.', 'R4')
