"""SDK-free wire contract shared by the server and outbound companion."""

from .agent_contract import ModelRequest
from .protocol import ValidationError, require_keys
from .provider_base import AgentSettings


def restore_request(value):
    require_keys(value, ('model', 'instructions', 'history', 'context', 'allowed_types', 'schema', 'max_output_tokens'))
    if (not isinstance(value['instructions'], str) or not isinstance(value['history'], list)
            or not isinstance(value['context'], dict) or not isinstance(value['schema'], dict)
            or not isinstance(value['allowed_types'], list) or not all(isinstance(k, str) for k in value['allowed_types'])):
        raise ValidationError('Contratto connettore non valido.')
    AgentSettings(value['model'], max_output_tokens=value['max_output_tokens'])
    request = ModelRequest(**{**value, 'allowed_types': tuple(value['allowed_types'])})
    if request.size_bytes() > 200000:
        raise ValidationError('Input connettore oltre limite.')
    return request
