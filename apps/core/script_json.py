"""JSON that is safe to drop inside a <script> block (W1.28).

``json.dumps`` leaves ``<``, ``>`` and ``&`` alone, so a string holding
``</script>`` — text the model read off a member's photo, say — closes the
script tag early when a template prints it with ``|safe``. These are escaped
the same way Django's ``json_script`` filter escapes them.
"""

import json

_SCRIPT_ESCAPES = {ord('<'): '\\u003C', ord('>'): '\\u003E', ord('&'): '\\u0026'}


def script_json(value) -> str:
    return json.dumps(value).translate(_SCRIPT_ESCAPES)
