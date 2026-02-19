"""lt_common - Shepard's XML parsing (simplified)."""
import re
from typing import List


def parse_shepard_letters(xml_or_text: str) -> List[str]:
    """Extract Shepard's treatment letters (O, W, X, A, etc.) from XML or text."""
    letters = []
    for m in re.finditer(r"[OWXA]+", xml_or_text.upper()):
        letters.extend(list(m.group()))
    return list(set(letters))
