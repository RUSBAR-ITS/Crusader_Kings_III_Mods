"""English reading aids for ambiguous medieval vocabulary in machine drafts only.

Never applied to the source catalog, scripts, or protected engine expressions.
The original and editorial translations remain available for comparison.
"""
import re

RULES=[
    (r'\bhosts\b','armies'),(r'\bhost\b','army'),
    (r'\btreat with\b','negotiate with'),(r'\btreat for me\b','negotiate on my behalf'),
    (r'\btreating with\b','negotiating with'),
    (r'\bgoodson\b','son-in-law'),
    (r'\bthe van\b','the vanguard'),
    (r'\bCall the banners\b','Summon the vassals to war'),
    (r'\bcall his banners\b','summon his vassals to war'),
    (r'\bcall my banners\b','summon my vassals to war'),
    (r'\bcalled the banners\b','summoned the vassals to war'),
    (r'\bbaggage train\b','supply caravan'),
    (r'\bhedge knight\b','wandering knight'),
    (r'\bhedge knights\b','wandering knights'),
]

def clarify(text):
    for pattern,replacement in RULES:
        text=re.sub(pattern,replacement,text,flags=re.I)
    return text
