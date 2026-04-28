from ..models import ClinicalProtocol

def get_protocol_for_category(category):
    """
    Fetches the clinical protocol (CBT/DBT) for a given category.
    """
    if not category:
        return "Provide general empathetic support and active listening."
        
    protocol = ClinicalProtocol.objects.filter(category=category).first()
    if protocol:
        return f"Follow the {protocol.technique_type} protocol for {category.name}: {protocol.content}"
        
    return f"Provide general supportive listening focused on {category.name}."
