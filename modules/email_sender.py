"""Email invitations. Delivery is simulated by default for demonstrations."""


def send_invitation(candidate: dict, vacancy: dict) -> dict:
    if not candidate.get("email"):
        return {"status": "Error", "detail": "El candidato no tiene correo."}
    return {"status": "Simulado", "detail": f"Invitación preparada para {candidate['email']} por {vacancy['title']}."}
