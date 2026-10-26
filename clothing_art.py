"""Clothing overlays and matching helpers for Milky.

Every overlay is a transparent 200x200 SVG that contains only the accessory.
The coordinates line up with Milky's face in the animated GIF:

* face bounds: x 18..182, y 53..146
* eyes: x 40..160, y 59..116
* smile: x 77..123, y 133..144
* hat/crown: x 40..160, y 6..66
* glasses/mask: x 35..165, y 70..118
* scarf/collar/bow: x 55..145, y 145..195
* earrings: x 14..36 and 164..186, y 95..130

The built-in items are used as prompt examples and as a safety net when the
model does not return a usable overlay.
"""

import re

HAT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <defs>
    <linearGradient id="hatCrown" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#ff9db2"/>
      <stop offset="100%" stop-color="#d94f70"/>
    </linearGradient>
    <linearGradient id="hatBrim" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#ffd0dc"/>
      <stop offset="100%" stop-color="#f07a96"/>
    </linearGradient>
    <radialGradient id="hatPom" cx="38%" cy="35%" r="70%">
      <stop offset="0%" stop-color="#fff8d6"/>
      <stop offset="100%" stop-color="#ffe58a"/>
    </radialGradient>
  </defs>
  <path d="M52 58 Q50 22 100 18 Q150 22 148 58 Z"
        fill="url(#hatCrown)" stroke="#a33855" stroke-width="3"/>
  <path d="M44 56 Q100 46 156 56 Q160 66 100 70 Q40 66 44 56 Z"
        fill="url(#hatBrim)" stroke="#a33855" stroke-width="3"/>
  <circle cx="100" cy="17" r="8" fill="url(#hatPom)"
          stroke="#c9a227" stroke-width="2"/>
  <g fill="none" stroke="#b33b5a" stroke-width="2" opacity="0.35"
     stroke-linecap="round">
    <path d="M72 31 Q70 45 70 57"/>
    <path d="M100 24 Q100 41 100 55"/>
    <path d="M128 31 Q130 45 130 57"/>
  </g>
  <path d="M56 61 Q100 69 144 61" fill="none" stroke="#8f2f49"
        stroke-width="2" opacity="0.25"/>
  <circle cx="120" cy="48" r="3" fill="#fff3b0" opacity="0.8"/>
  <circle cx="80" cy="50" r="2.4" fill="#fff3b0" opacity="0.7"/>
</svg>"""

CROWN = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <defs>
    <linearGradient id="crownGold" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#fff3a6"/>
      <stop offset="45%" stop-color="#ffd34d"/>
      <stop offset="100%" stop-color="#e0a51b"/>
    </linearGradient>
  </defs>
  <path d="M56 62 L60 20 L82 42 L100 12 L118 42 L140 20 L144 62 Z"
        fill="url(#crownGold)" stroke="#b8860b" stroke-width="3"
        stroke-linejoin="round"/>
  <path d="M58 58 Q100 68 142 58 L144 66 Q100 78 56 66 Z"
        fill="#ffe58a" stroke="#b8860b" stroke-width="2.5"/>
  <circle cx="100" cy="12" r="5" fill="#ff6b9d" stroke="#b8860b"
          stroke-width="1.5"/>
  <circle cx="72" cy="30" r="4" fill="#7ee0ff" stroke="#b8860b"
          stroke-width="1.4"/>
  <circle cx="128" cy="30" r="4" fill="#7ee0ff" stroke="#b8860b"
          stroke-width="1.4"/>
  <circle cx="100" cy="48" r="4.5" fill="#ff6b9d" stroke="#b8860b"
          stroke-width="1.4"/>
  <path d="M82 46 L86 34 M118 46 L114 34" fill="none" stroke="#fff8d6"
        stroke-width="2.2" opacity="0.75" stroke-linecap="round"/>
</svg>"""

GLASSES = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <defs>
    <linearGradient id="glassFrame" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#4a4a5e"/>
      <stop offset="100%" stop-color="#171722"/>
    </linearGradient>
    <linearGradient id="glassLens" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#d9f7ff"/>
      <stop offset="100%" stop-color="#8fd7ff"/>
    </linearGradient>
  </defs>
  <g fill="none" stroke="url(#glassFrame)" stroke-width="4.5"
     stroke-linecap="round">
    <rect x="34" y="72" width="60" height="44" rx="18"/>
    <rect x="106" y="72" width="60" height="44" rx="18"/>
    <path d="M94 90 Q100 85 106 90"/>
    <path d="M34 84 L18 78"/>
    <path d="M166 84 L182 78"/>
  </g>
  <rect x="39" y="77" width="50" height="34" rx="14"
        fill="url(#glassLens)" opacity="0.32"/>
  <rect x="111" y="77" width="50" height="34" rx="14"
        fill="url(#glassLens)" opacity="0.32"/>
  <path d="M45 83 Q56 77 68 80" fill="none" stroke="#ffffff"
        stroke-width="2.5" opacity="0.8" stroke-linecap="round"/>
  <path d="M117 83 Q128 77 140 80" fill="none" stroke="#ffffff"
        stroke-width="2.5" opacity="0.8" stroke-linecap="round"/>
  <circle cx="34" cy="84" r="3" fill="#6b6b7a"/>
  <circle cx="166" cy="84" r="3" fill="#6b6b7a"/>
</svg>"""

SCARF = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <defs>
    <linearGradient id="scarfMain" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#ff8a7a"/>
      <stop offset="100%" stop-color="#d63f5c"/>
    </linearGradient>
    <linearGradient id="scarfTail" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#e95770"/>
      <stop offset="100%" stop-color="#b92d49"/>
    </linearGradient>
  </defs>
  <path d="M52 144 Q100 163 148 144 L155 166 Q100 186 45 166 Z"
        fill="url(#scarfMain)" stroke="#9e2f47" stroke-width="3"
        stroke-linejoin="round"/>
  <path d="M115 166 Q132 174 136 194 L116 198 Q112 180 104 169 Z"
        fill="url(#scarfTail)" stroke="#9e2f47" stroke-width="3"
        stroke-linejoin="round"/>
  <path d="M60 150 Q100 166 140 150" fill="none" stroke="#ffd3cf"
        stroke-width="2" opacity="0.5" stroke-linecap="round"/>
  <g stroke="#ffe5d8" stroke-width="2" opacity="0.35"
     stroke-linecap="round">
    <path d="M70 170 L78 176"/>
    <path d="M86 176 L94 182"/>
    <path d="M128 178 L124 188"/>
  </g>
  <path d="M120 190 L132 191 M118 194 L131 195" stroke="#9e2f47"
        stroke-width="2" opacity="0.4" stroke-linecap="round"/>
</svg>"""

BOW = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <defs>
    <linearGradient id="bowFill" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#ff9db2"/>
      <stop offset="100%" stop-color="#c92f58"/>
    </linearGradient>
    <radialGradient id="bowKnot" cx="40%" cy="35%" r="70%">
      <stop offset="0%" stop-color="#ffd3dc"/>
      <stop offset="100%" stop-color="#ef7892"/>
    </radialGradient>
  </defs>
  <g transform="translate(0 13)">
    <path d="M100 152 L74 136 Q64 152 74 168 Z"
          fill="url(#bowFill)" stroke="#9e2f47" stroke-width="3"
          stroke-linejoin="round"/>
    <path d="M100 152 L126 136 Q136 152 126 168 Z"
          fill="url(#bowFill)" stroke="#9e2f47" stroke-width="3"
          stroke-linejoin="round"/>
    <path d="M94 150 Q100 144 106 150 L104 158 Q100 161 96 158 Z"
          fill="url(#bowKnot)" stroke="#9e2f47" stroke-width="2.5"
          stroke-linejoin="round"/>
    <path d="M76 143 Q82 152 76 161 M124 143 Q118 152 124 161"
          fill="none" stroke="#ffd9e2" stroke-width="2" opacity="0.6"
          stroke-linecap="round"/>
  </g>
</svg>"""

EARRINGS = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <defs>
    <linearGradient id="earringGold" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#fff3a6"/>
      <stop offset="100%" stop-color="#d9a51f"/>
    </linearGradient>
  </defs>
  <g fill="none" stroke="url(#earringGold)" stroke-width="3">
    <circle cx="26" cy="120" r="7"/>
    <circle cx="174" cy="120" r="7"/>
  </g>
  <path d="M26 127 L26 136 M174 127 L174 136" stroke="#d4a017"
        stroke-width="3" stroke-linecap="round"/>
  <circle cx="26" cy="141" r="5" fill="#ff7aa8" stroke="#b8860b"
          stroke-width="1.5"/>
  <circle cx="174" cy="141" r="5" fill="#ff7aa8" stroke="#b8860b"
          stroke-width="1.5"/>
  <circle cx="23" cy="117" r="2" fill="#fff7d6"/>
  <circle cx="171" cy="117" r="2" fill="#fff7d6"/>
</svg>"""

MASK = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <defs>
    <linearGradient id="maskFill" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#e8f7ff"/>
      <stop offset="100%" stop-color="#9fd0ea"/>
    </linearGradient>
  </defs>
  <path d="M52 100 Q100 92 148 100 L144 132 Q100 154 56 132 Z"
        fill="url(#maskFill)" stroke="#7aa7c7" stroke-width="2.5"
        stroke-linejoin="round"/>
  <g fill="none" stroke="#a9cfe6" stroke-width="2" opacity="0.8">
    <path d="M60 108 Q100 116 140 108"/>
    <path d="M58 118 Q100 128 142 118"/>
    <path d="M56 128 Q100 139 144 128"/>
  </g>
  <path d="M52 100 L26 92 M148 100 L174 92" fill="none"
        stroke="#8cb7d4" stroke-width="2.5" stroke-linecap="round"/>
  <path d="M70 101 Q100 96 130 101" fill="none" stroke="#ffffff"
        stroke-width="2" opacity="0.6"/>
</svg>"""

NECKLACE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <defs>
    <linearGradient id="necklaceGold" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#fff3a6"/>
      <stop offset="100%" stop-color="#d9a51f"/>
    </linearGradient>
  </defs>
  <path d="M68 145 Q100 180 132 145" fill="none"
        stroke="url(#necklaceGold)" stroke-width="3"
        stroke-linecap="round"/>
  <circle cx="100" cy="177" r="6" fill="#ff7aa8" stroke="#b8860b"
          stroke-width="1.6"/>
  <circle cx="82" cy="161" r="2.2" fill="#fff7d6"/>
  <circle cx="118" cy="161" r="2.2" fill="#fff7d6"/>
  <path d="M100 177 L100 184" stroke="#d4a017" stroke-width="2"
        stroke-linecap="round"/>
</svg>"""

CLOTHING_REFERENCE = (
    "\nClothing overlay reference:\n"
    "- Milky's visible face is a floating white line-art cat face in a "
    "transparent 200x200 frame. The app layers body, neck and head items "
    "behind her face line art, and only face items in front; her face must "
    "stay visible.\n"
    "- Face bounds: x 18..182, y 53..146. Eyes: x 40..160, y 59..116. "
    "Smile: x 77..123, y 133..144.\n"
    "- Hat or crown: x 40..160, y 6..66. Glasses or mask: x 35..165, "
    "y 70..118. Scarf, collar, bow or necklace: x 55..145, y 145..195. "
    "Never put a neck item above y 145; it would sit on her smile. "
    "Earrings: x 14..36 and 164..186, y 95..130.\n"
    "- Draw only the requested item: no face, body, background, border, "
    "text or watermark. Use a transparent background and exactly "
    "viewBox=\"0 0 200 200\".\n"
    "- Make it look worn and fitted: brims sit on the head, frames surround "
    "the eyes, a scarf wraps under the smile. Use gradients, shading, "
    "highlights and a few small details. Never fill the whole canvas. "
    "Do not cover both eyes; a mask may cover the lower face, but her eyes "
    "must remain visible.\n"
    "- The examples below are style and coordinate guides. Draw the item the "
    "user asked for; do not copy a hat when they asked for a scarf or "
    "glasses.\n"
    "Example hat overlay:\n"
    + HAT
    + "\nExample glasses overlay:\n"
    + GLASSES
    + "\n"
)

_WEAR_RE = re.compile(
    r"\bоден\w*|\bодет\w*|\bодева\w*|\bнаден\w*|\bнадет\w*|\bнадел\w*|"
    r"\bнадева\w*|\bнаки\w*|\bпример\w*|\bнаряд\w*|"
    r"\bнос(?:и|ить|ит|ишь|им|ят|ите)\b|\bнош\w*|"
    r"\b(?:put\s+(?:it\s+)?on|wear(?:s|ing)?|wore|try\s+on|"
    r"dress(?:es|ed|ing)?(?:\s+up)?)\b",
    re.IGNORECASE,
)

# In a drawing request, "a cat wearing a hat" describes the picture, not a
# request for Milky to put the hat on.  Only a direct imperative counts as a
# request for an actual overlay.
_EXPLICIT_WEAR_RE = re.compile(
    r"\b(?:надень|надевай|одень|оденься|накинь|накидывай|примерь|примеряй|"
    r"надеть|надевать|одевать|"
    r"put\s+(?:it\s+)?on|try\s+on|"
    r"wear\s+(?:it|this|that|these|those|a|an|the)\b)\b",
    re.IGNORECASE,
)

_ITEM_PATTERNS = (
    ("golden crown", "head", CROWN, re.compile(
        r"\bкорон\w*|\bдиадем\w*|\bтиар\w*|\bвенец\b|\bвенок\w*|"
        r"\b(?:crown|crowns|tiara|tiaras|diadem)\w*\b",
        re.IGNORECASE,
    )),
    ("round glasses", "face", GLASSES, re.compile(
        r"\bочк\w*|\bочкар\w*|\bпенсне\b|\bмонокл\w*|\b(?:glasses|"
        r"sunglasses|shades|spectacles|monocle|eyeglasses)\b",
        re.IGNORECASE,
    )),
    ("face mask", "face", MASK, re.compile(
        r"\bмаск\w*|\b(?:mask|masks|face\s+mask|surgical\s+mask)\b",
        re.IGNORECASE,
    )),
    ("soft scarf", "neck", SCARF, re.compile(
        r"\bшарф\w*|\bснуд\w*|\bворотник\w*|\b(?:scarf|scarves|muffler|"
        r"snood|collar|collars)\b",
        re.IGNORECASE,
    )),
    ("delicate necklace", "neck", NECKLACE, re.compile(
        r"\bожерель\w*|\bколье\b|\bбусы\b|\bцепочк\w*|\bкулон\w*|"
        r"\bмедальон\w*|\b(?:necklace|necklaces|choker|pendant|locket)\b",
        re.IGNORECASE,
    )),
    ("bow tie", "neck", BOW, re.compile(
        r"\bбант\w*|\bбабочк\w*|\b(?:bow|bows|bowtie|bow-tie|necktie|"
        r"neck-tie)\b",
        re.IGNORECASE,
    )),
    ("gold earrings", "other", EARRINGS, re.compile(
        r"\bсерьг\w*|\bсерёж\w*|\b(?:earring|earrings)\b",
        re.IGNORECASE,
    )),
    ("warm hat", "head", HAT, re.compile(
        r"\bшапк\w*|\bшапочк\w*|\bкепк\w*|\bшляп\w*|\bберет\w*|"
        r"\bушанк\w*|\bпанам\w*|\bкапюшон\w*|\b(?:hat|hats|cap|caps|"
        r"beanie|beanies|beret|bonnet|hood|fedora)\b",
        re.IGNORECASE,
    )),
)


def wants_clothing(text):
    """Return True when the user asks Milky to put something on."""
    return bool(text) and _WEAR_RE.search(text) is not None


def wants_wear_overlay(text):
    """Return True for a direct request to wear an overlay, not a drawing."""
    return bool(text) and _EXPLICIT_WEAR_RE.search(text) is not None


def fallback_clothing(text):
    """Return ``(name, slot, svg)`` for a common clothing request."""
    if not wants_clothing(text):
        return None
    for name, slot, svg, pattern in _ITEM_PATTERNS:
        if pattern.search(text):
            return name, slot, svg
    return None
