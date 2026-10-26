"""Hand-drawn SVG artwork used when the model does not supply its own.

Every drawing is a self-contained SVG with a 200x200 viewBox, soft gradients,
shading and small details so it looks good inside Milky's window.
"""

import re

# ---------------------------------------------------------------------------
# Artwork
# ---------------------------------------------------------------------------

CAT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <defs>
    <radialGradient id="catBg" cx="50%" cy="35%" r="75%">
      <stop offset="0%" stop-color="#fffaf0"/>
      <stop offset="100%" stop-color="#ffe1b0"/>
    </radialGradient>
    <linearGradient id="catFur" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#ffbd63"/>
      <stop offset="100%" stop-color="#e8873a"/>
    </linearGradient>
    <linearGradient id="catBelly" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#fff7e8"/>
      <stop offset="100%" stop-color="#ffdfb8"/>
    </linearGradient>
  </defs>
  <rect width="200" height="200" fill="url(#catBg)"/>
  <ellipse cx="100" cy="186" rx="60" ry="10" fill="#8a4b1f" opacity="0.15"/>
  <path d="M148 166 q36 -4 28 -34 q-4 -14 -18 -11 q11 11 3 23 q-9 13 -31 15 z"
        fill="url(#catFur)" stroke="#b96a28" stroke-width="2.4"/>
  <path d="M62 170 q-10 -52 38 -56 q48 4 38 56 z"
        fill="url(#catFur)" stroke="#b96a28" stroke-width="2.6"/>
  <ellipse cx="100" cy="160" rx="24" ry="19" fill="url(#catBelly)"/>
  <ellipse cx="79" cy="173" rx="12" ry="7" fill="#fff7e8" stroke="#b96a28" stroke-width="2"/>
  <ellipse cx="121" cy="173" rx="12" ry="7" fill="#fff7e8" stroke="#b96a28" stroke-width="2"/>
  <path d="M60 76 L56 36 L90 58 Z" fill="url(#catFur)" stroke="#b96a28"
        stroke-width="2.6" stroke-linejoin="round"/>
  <path d="M140 76 L144 36 L110 58 Z" fill="url(#catFur)" stroke="#b96a28"
        stroke-width="2.6" stroke-linejoin="round"/>
  <path d="M66 68 L64 47 L82 60 Z" fill="#ffb6c1"/>
  <path d="M134 68 L136 47 L118 60 Z" fill="#ffb6c1"/>
  <ellipse cx="100" cy="92" rx="45" ry="41" fill="url(#catFur)"
           stroke="#b96a28" stroke-width="2.6"/>
  <path d="M91 57 q0 13 1 17 M100 55 q0 15 0 19 M109 57 q0 13 -1 17"
        stroke="#c2702c" stroke-width="3" fill="none" stroke-linecap="round"/>
  <ellipse cx="82" cy="90" rx="10.5" ry="12.5" fill="#2c2c2c"/>
  <ellipse cx="118" cy="90" rx="10.5" ry="12.5" fill="#2c2c2c"/>
  <circle cx="85.5" cy="86" r="3.8" fill="#ffffff"/>
  <circle cx="121.5" cy="86" r="3.8" fill="#ffffff"/>
  <circle cx="79" cy="94.5" r="1.7" fill="#ffffff" opacity="0.85"/>
  <circle cx="115" cy="94.5" r="1.7" fill="#ffffff" opacity="0.85"/>
  <ellipse cx="100" cy="111" rx="21" ry="14" fill="#fff7e8"/>
  <path d="M96 106 h8 l-4 5.5 z" fill="#ff8fa3" stroke="#e06b80"
        stroke-width="1.4" stroke-linejoin="round"/>
  <path d="M100 112 q0 6 -7 6 q-5 0 -6 -4" fill="none" stroke="#8a4b1f"
        stroke-width="1.8" stroke-linecap="round"/>
  <path d="M100 112 q0 6 7 6 q5 0 6 -4" fill="none" stroke="#8a4b1f"
        stroke-width="1.8" stroke-linecap="round"/>
  <path d="M75 106 h-18 M75 112 l-19 4 M125 106 h18 M125 112 l19 4"
        stroke="#a05a24" stroke-width="1.5" stroke-linecap="round"/>
  <ellipse cx="69" cy="105" rx="7" ry="4.5" fill="#ff8fa3" opacity="0.45"/>
  <ellipse cx="131" cy="105" rx="7" ry="4.5" fill="#ff8fa3" opacity="0.45"/>
  <path d="M74 126 q26 14 52 0" fill="none" stroke="#c2702c" stroke-width="2"
        opacity="0.35" stroke-linecap="round"/>
</svg>"""

DOG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <defs>
    <radialGradient id="dogBg" cx="50%" cy="35%" r="75%">
      <stop offset="0%" stop-color="#eaf6ff"/>
      <stop offset="100%" stop-color="#b9dcff"/>
    </radialGradient>
    <linearGradient id="dogFur" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#c98a52"/>
      <stop offset="100%" stop-color="#a5652f"/>
    </linearGradient>
  </defs>
  <rect width="200" height="200" fill="url(#dogBg)"/>
  <ellipse cx="100" cy="187" rx="58" ry="9" fill="#3b5a7a" opacity="0.16"/>
  <path d="M146 160 q30 2 26 -20 q-2 -10 -12 -8 q8 8 1 17 q-6 8 -20 8 z"
        fill="url(#dogFur)" stroke="#7d4a20" stroke-width="2.2"/>
  <ellipse cx="100" cy="150" rx="44" ry="36" fill="url(#dogFur)"
           stroke="#7d4a20" stroke-width="2.6"/>
  <ellipse cx="100" cy="156" rx="25" ry="24" fill="#f3d9b8"/>
  <ellipse cx="76" cy="174" rx="13" ry="8" fill="#f3d9b8" stroke="#7d4a20" stroke-width="2"/>
  <ellipse cx="124" cy="174" rx="13" ry="8" fill="#f3d9b8" stroke="#7d4a20" stroke-width="2"/>
  <ellipse cx="62" cy="88" rx="15" ry="26" fill="#8f5526" stroke="#7d4a20"
           stroke-width="2.4" transform="rotate(12 62 88)"/>
  <ellipse cx="138" cy="88" rx="15" ry="26" fill="#8f5526" stroke="#7d4a20"
           stroke-width="2.4" transform="rotate(-12 138 88)"/>
  <ellipse cx="100" cy="88" rx="42" ry="39" fill="url(#dogFur)"
           stroke="#7d4a20" stroke-width="2.6"/>
  <path d="M62 74 q8 -18 22 -8 q-12 4 -14 18 z" fill="#f3d9b8" opacity="0.55"/>
  <ellipse cx="85" cy="82" rx="7" ry="8" fill="#2b2b2b"/>
  <ellipse cx="115" cy="82" rx="7" ry="8" fill="#2b2b2b"/>
  <circle cx="87" cy="79" r="2.6" fill="#ffffff"/>
  <circle cx="117" cy="79" r="2.6" fill="#ffffff"/>
  <ellipse cx="100" cy="106" rx="25" ry="19" fill="#f7e3c9"/>
  <ellipse cx="100" cy="98" rx="9" ry="7" fill="#33221a"/>
  <path d="M100 105 q0 5 -8 5 q-5 0 -6 -4 M100 105 q0 5 8 5 q5 0 6 -4"
        fill="none" stroke="#7d4a20" stroke-width="1.8" stroke-linecap="round"/>
  <path d="M94 113 q6 10 12 0 z" fill="#ff7f8f"/>
  <ellipse cx="70" cy="100" rx="6.5" ry="4" fill="#ff8fa3" opacity="0.4"/>
  <ellipse cx="130" cy="100" rx="6.5" ry="4" fill="#ff8fa3" opacity="0.4"/>
  <path d="M84 122 q16 8 32 0" fill="none" stroke="#ff5f6d"
        stroke-width="4" stroke-linecap="round"/>
  <circle cx="100" cy="126" r="6" fill="#ffd34d" stroke="#d9a400" stroke-width="1.5"/>
</svg>"""

BUNNY = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <defs>
    <radialGradient id="bunBg" cx="50%" cy="35%" r="75%">
      <stop offset="0%" stop-color="#fff6fa"/>
      <stop offset="100%" stop-color="#ffd7e6"/>
    </radialGradient>
    <linearGradient id="bunFur" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="100%" stop-color="#e9e2ee"/>
    </linearGradient>
  </defs>
  <rect width="200" height="200" fill="url(#bunBg)"/>
  <ellipse cx="100" cy="186" rx="52" ry="9" fill="#b5658a" opacity="0.18"/>
  <ellipse cx="82" cy="50" rx="13" ry="40" fill="url(#bunFur)" stroke="#c9bdd2"
           stroke-width="2.2" transform="rotate(-8 82 50)"/>
  <ellipse cx="118" cy="50" rx="13" ry="40" fill="url(#bunFur)" stroke="#c9bdd2"
           stroke-width="2.2" transform="rotate(8 118 50)"/>
  <ellipse cx="82" cy="52" rx="6" ry="28" fill="#ffc2d6" transform="rotate(-8 82 52)"/>
  <ellipse cx="118" cy="52" rx="6" ry="28" fill="#ffc2d6" transform="rotate(8 118 52)"/>
  <ellipse cx="100" cy="152" rx="43" ry="34" fill="url(#bunFur)"
           stroke="#c9bdd2" stroke-width="2.4"/>
  <ellipse cx="100" cy="160" rx="24" ry="20" fill="#ffffff" opacity="0.7"/>
  <ellipse cx="100" cy="104" rx="45" ry="40" fill="url(#bunFur)"
           stroke="#c9bdd2" stroke-width="2.4"/>
  <ellipse cx="82" cy="100" rx="8" ry="10" fill="#332b3c"/>
  <ellipse cx="118" cy="100" rx="8" ry="10" fill="#332b3c"/>
  <circle cx="84.5" cy="96" r="3" fill="#ffffff"/>
  <circle cx="120.5" cy="96" r="3" fill="#ffffff"/>
  <path d="M96 114 h8 l-4 5 z" fill="#ff8fb1" stroke="#e06b90" stroke-width="1.3"/>
  <path d="M100 119 q0 5 -7 5 q-4 0 -5 -3 M100 119 q0 5 7 5 q4 0 5 -3"
        fill="none" stroke="#a98bb8" stroke-width="1.7" stroke-linecap="round"/>
  <rect x="96" y="128" width="3.4" height="6" rx="1.2" fill="#ffffff"
        stroke="#d9cfe0" stroke-width="0.8"/>
  <rect x="100.6" y="128" width="3.4" height="6" rx="1.2" fill="#ffffff"
        stroke="#d9cfe0" stroke-width="0.8"/>
  <path d="M74 118 h-16 M74 123 l-17 4 M126 118 h16 M126 123 l17 4"
        stroke="#b9a6c6" stroke-width="1.4" stroke-linecap="round"/>
  <ellipse cx="70" cy="112" rx="7" ry="4.5" fill="#ff9dbb" opacity="0.5"/>
  <ellipse cx="130" cy="112" rx="7" ry="4.5" fill="#ff9dbb" opacity="0.5"/>
  <ellipse cx="78" cy="174" rx="13" ry="8" fill="#ffffff" stroke="#c9bdd2" stroke-width="2"/>
  <ellipse cx="122" cy="174" rx="13" ry="8" fill="#ffffff" stroke="#c9bdd2" stroke-width="2"/>
  <g transform="rotate(24 158 150)">
    <path d="M150 138 l16 4 l-12 14 z" fill="#ff9a3c" stroke="#e07b1f"
          stroke-width="1.5" stroke-linejoin="round"/>
    <path d="M149 137 l-2 -7 M153 138 l3 -7" stroke="#6ab04c"
          stroke-width="2" stroke-linecap="round"/>
  </g>
</svg>"""

SUN = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <defs>
    <linearGradient id="sunSky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#8ed3ff"/>
      <stop offset="100%" stop-color="#d8f0ff"/>
    </linearGradient>
    <radialGradient id="sunCore" cx="45%" cy="40%" r="65%">
      <stop offset="0%" stop-color="#fff6b0"/>
      <stop offset="55%" stop-color="#ffd23f"/>
      <stop offset="100%" stop-color="#ff9e1b"/>
    </radialGradient>
  </defs>
  <rect width="200" height="200" fill="url(#sunSky)"/>
  <g fill="#ffcf4d" opacity="0.85">
    <path d="M100 12 l9 26 h-18 z"/>
    <path d="M100 162 l9 26 h-18 z"/>
    <path d="M12 100 l26 -9 v18 z"/>
    <path d="M162 100 l26 -9 v18 z"/>
    <path d="M38 38 l24 12 -13 13 z"/>
    <path d="M162 38 l-24 12 13 13 z"/>
    <path d="M38 162 l24 -12 -13 -13 z"/>
    <path d="M162 162 l-24 -12 13 -13 z"/>
  </g>
  <circle cx="100" cy="100" r="50" fill="url(#sunCore)" stroke="#f2a52a" stroke-width="3"/>
  <ellipse cx="83" cy="93" rx="5" ry="6" fill="#7a4a00"/>
  <ellipse cx="117" cy="93" rx="5" ry="6" fill="#7a4a00"/>
  <circle cx="84.5" cy="90.5" r="1.6" fill="#ffffff"/>
  <circle cx="118.5" cy="90.5" r="1.6" fill="#ffffff"/>
  <path d="M84 111 q16 14 32 0" fill="none" stroke="#7a4a00"
        stroke-width="3.5" stroke-linecap="round"/>
  <ellipse cx="72" cy="108" rx="7" ry="4.5" fill="#ff7b6b" opacity="0.55"/>
  <ellipse cx="128" cy="108" rx="7" ry="4.5" fill="#ff7b6b" opacity="0.55"/>
  <g fill="#ffffff" opacity="0.9">
    <ellipse cx="40" cy="162" rx="22" ry="11"/>
    <ellipse cx="58" cy="158" rx="16" ry="9"/>
    <ellipse cx="24" cy="158" rx="14" ry="8"/>
    <ellipse cx="160" cy="48" rx="20" ry="10"/>
    <ellipse cx="176" cy="44" rx="13" ry="7"/>
    <ellipse cx="146" cy="44" rx="12" ry="7"/>
  </g>
</svg>"""

MOON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <defs>
    <linearGradient id="moonSky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#0f1230"/>
      <stop offset="55%" stop-color="#292659"/>
      <stop offset="100%" stop-color="#5a3f82"/>
    </linearGradient>
    <radialGradient id="moonGlow">
      <stop offset="0%" stop-color="#fff4c2" stop-opacity="0.5"/>
      <stop offset="100%" stop-color="#fff4c2" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="moonBody" cx="40%" cy="35%" r="70%">
      <stop offset="0%" stop-color="#fffbe0"/>
      <stop offset="60%" stop-color="#ffecae"/>
      <stop offset="100%" stop-color="#f0c96c"/>
    </radialGradient>
  </defs>
  <rect width="200" height="200" fill="url(#moonSky)"/>
  <circle cx="128" cy="74" r="62" fill="url(#moonGlow)"/>
  <path d="M138 26 a46 46 0 1 0 0 92 a37 37 0 1 1 0 -92 z"
        fill="url(#moonBody)" stroke="#e0b85a" stroke-width="1.5"/>
  <ellipse cx="128" cy="50" rx="7" ry="6" fill="#e6c268" opacity="0.55"/>
  <ellipse cx="116" cy="76" rx="9" ry="7" fill="#e6c268" opacity="0.5"/>
  <ellipse cx="132" cy="98" rx="5" ry="4" fill="#e6c268" opacity="0.5"/>
  <ellipse cx="143" cy="66" rx="3" ry="2.5" fill="#e6c268" opacity="0.45"/>
  <g fill="#fff6cc">
    <path d="M40 30 l2.2 5.6 5.6 2.2 -5.6 2.2 -2.2 5.6 -2.2 -5.6 -5.6 -2.2 5.6 -2.2 z"/>
    <path d="M68 66 l1.7 4.3 4.3 1.7 -4.3 1.7 -1.7 4.3 -1.7 -4.3 -4.3 -1.7 4.3 -1.7 z" opacity="0.85"/>
    <path d="M45 100 l1.3 3.4 3.4 1.3 -3.4 1.3 -1.3 3.4 -1.3 -3.4 -3.4 -1.3 3.4 -1.3 z" opacity="0.7"/>
    <path d="M166 122 l1.5 4 4 1.5 -4 1.5 -1.5 4 -1.5 -4 -4 -1.5 4 -1.5 z" opacity="0.75"/>
  </g>
  <g fill="#ffffff" opacity="0.8">
    <circle cx="24" cy="58" r="1.6"/>
    <circle cx="78" cy="22" r="1.3"/>
    <circle cx="176" cy="40" r="1.5"/>
    <circle cx="152" cy="132" r="1.4"/>
    <circle cx="34" cy="128" r="1.2"/>
    <circle cx="96" cy="112" r="1.2"/>
    <circle cx="62" cy="140" r="1.5"/>
  </g>
  <path d="M18 22 q14 4 22 16" fill="none" stroke="#fff6cc"
        stroke-width="1.6" stroke-linecap="round" opacity="0.8"/>
  <path d="M0 168 q42 -24 82 -4 q36 20 70 -2 q28 -18 48 0 v38 H0 z"
        fill="#201a44"/>
  <path d="M0 180 q54 -14 108 2 q46 14 92 -2 v20 H0 z" fill="#141031"/>
  <path d="M118 168 l6 -14 l6 14 z M132 170 l5 -11 l5 11 z" fill="#0e0b26"/>
</svg>"""

HEART = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <defs>
    <radialGradient id="heartBg" cx="50%" cy="40%" r="75%">
      <stop offset="0%" stop-color="#fff2f6"/>
      <stop offset="100%" stop-color="#ffd0e0"/>
    </radialGradient>
    <linearGradient id="heartFill" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#ff8fb0"/>
      <stop offset="100%" stop-color="#e5396b"/>
    </linearGradient>
  </defs>
  <rect width="200" height="200" fill="url(#heartBg)"/>
  <ellipse cx="100" cy="184" rx="54" ry="9" fill="#b02a55" opacity="0.16"/>
  <path d="M100 172 C38 130 20 96 31 69 C42 42 79 43 100 72 C121 43 158 42 169 69 C180 96 162 130 100 172 Z"
        fill="url(#heartFill)" stroke="#c2285a" stroke-width="2.5"/>
  <path d="M62 74 C50 82 48 98 54 110 C58 118 64 124 70 128 C62 112 60 94 68 82 C73 75 78 71 84 69 C78 66 68 67 62 74 Z"
        fill="#ffffff" opacity="0.4"/>
  <ellipse cx="76" cy="86" rx="13" ry="8" fill="#ffffff" opacity="0.28"
           transform="rotate(-28 76 86)"/>
  <g fill="#ff6f9a">
    <path d="M142 54 l2 5 5 2 -5 2 -2 5 -2 -5 -5 -2 5 -2 z" opacity="0.9"/>
    <path d="M52 142 l1.6 4 4 1.6 -4 1.6 -1.6 4 -1.6 -4 -4 -1.6 4 -1.6 z" opacity="0.8"/>
    <path d="M160 108 l1.4 3.6 3.6 1.4 -3.6 1.4 -1.4 3.6 -1.4 -3.6 -3.6 -1.4 3.6 -1.4 z" opacity="0.7"/>
  </g>
  <g fill="#ff8fb0" opacity="0.75">
    <path d="M40 62 c-8 -6 -16 4 -8 11 l8 7 8 -7 c8 -7 0 -17 -8 -11 z"/>
    <path d="M158 158 c-6 -5 -13 3 -6 9 l6 5 6 -5 c7 -6 0 -14 -6 -9 z"/>
  </g>
</svg>"""

FLOWER = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <defs>
    <linearGradient id="flSky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#d8f2ff"/>
      <stop offset="100%" stop-color="#f4fff4"/>
    </linearGradient>
    <radialGradient id="flCenter" cx="40%" cy="35%" r="65%">
      <stop offset="0%" stop-color="#ffe9a3"/>
      <stop offset="100%" stop-color="#f2a52a"/>
    </radialGradient>
    <linearGradient id="flPetal" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#ffd1e0"/>
      <stop offset="100%" stop-color="#ff6fa5"/>
    </linearGradient>
  </defs>
  <rect width="200" height="200" fill="url(#flSky)"/>
  <path d="M0 168 q40 -14 80 0 q44 16 120 -2 v34 H0 z" fill="#a8e063"/>
  <path d="M0 180 q54 -10 108 2 q48 10 92 -2 v20 H0 z" fill="#7ec850"/>
  <path d="M100 162 q-6 -44 2 -78" fill="none" stroke="#4f9e3a"
        stroke-width="5" stroke-linecap="round"/>
  <path d="M102 138 q-26 -4 -34 -24 q26 0 34 24 z" fill="#6dbb4c"
        stroke="#4f9e3a" stroke-width="2" stroke-linejoin="round"/>
  <path d="M101 124 q26 -2 32 -24 q-26 2 -32 24 z" fill="#8bd267"
        stroke="#4f9e3a" stroke-width="2" stroke-linejoin="round"/>
  <g stroke="#e5396b" stroke-width="1.6">
    <ellipse cx="100" cy="54" rx="14" ry="25" fill="url(#flPetal)" transform="rotate(0 100 78)"/>
    <ellipse cx="100" cy="54" rx="14" ry="25" fill="url(#flPetal)" transform="rotate(45 100 78)"/>
    <ellipse cx="100" cy="54" rx="14" ry="25" fill="url(#flPetal)" transform="rotate(90 100 78)"/>
    <ellipse cx="100" cy="54" rx="14" ry="25" fill="url(#flPetal)" transform="rotate(135 100 78)"/>
    <ellipse cx="100" cy="54" rx="14" ry="25" fill="url(#flPetal)" transform="rotate(180 100 78)"/>
    <ellipse cx="100" cy="54" rx="14" ry="25" fill="url(#flPetal)" transform="rotate(225 100 78)"/>
    <ellipse cx="100" cy="54" rx="14" ry="25" fill="url(#flPetal)" transform="rotate(270 100 78)"/>
    <ellipse cx="100" cy="54" rx="14" ry="25" fill="url(#flPetal)" transform="rotate(315 100 78)"/>
  </g>
  <circle cx="100" cy="78" r="18" fill="url(#flCenter)" stroke="#d98d14" stroke-width="2"/>
  <g fill="#c47a10" opacity="0.7">
    <circle cx="93" cy="72" r="1.7"/>
    <circle cx="107" cy="72" r="1.7"/>
    <circle cx="100" cy="82" r="1.7"/>
    <circle cx="91" cy="82" r="1.4"/>
    <circle cx="109" cy="82" r="1.4"/>
    <circle cx="100" cy="70" r="1.4"/>
  </g>
  <g fill="#ffffff" opacity="0.85">
    <circle cx="36" cy="48" r="8"/>
    <circle cx="170" cy="36" r="6"/>
    <circle cx="156" cy="66" r="4"/>
  </g>
</svg>"""

STAR = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <defs>
    <linearGradient id="stSky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#161436"/>
      <stop offset="100%" stop-color="#3f2c66"/>
    </linearGradient>
    <linearGradient id="stFill" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#fff6b0"/>
      <stop offset="100%" stop-color="#ffb52e"/>
    </linearGradient>
    <radialGradient id="stGlow">
      <stop offset="0%" stop-color="#ffe680" stop-opacity="0.5"/>
      <stop offset="100%" stop-color="#ffe680" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="200" height="200" fill="url(#stSky)"/>
  <circle cx="100" cy="100" r="82" fill="url(#stGlow)"/>
  <path d="M100 42 L115 79 L155 82 L125 108 L134 147 L100 126 L66 147 L75 108 L45 82 L85 79 Z"
        fill="url(#stFill)" stroke="#e8991a" stroke-width="2.5" stroke-linejoin="round"/>
  <ellipse cx="84" cy="95" rx="4.5" ry="5.5" fill="#7a4a00"/>
  <ellipse cx="116" cy="95" rx="4.5" ry="5.5" fill="#7a4a00"/>
  <circle cx="85.5" cy="93" r="1.4" fill="#ffffff"/>
  <circle cx="117.5" cy="93" r="1.4" fill="#ffffff"/>
  <path d="M89 108 q11 9 22 0" fill="none" stroke="#7a4a00"
        stroke-width="2.6" stroke-linecap="round"/>
  <ellipse cx="74" cy="104" rx="5" ry="3.2" fill="#ff8f6b" opacity="0.55"/>
  <ellipse cx="126" cy="104" rx="5" ry="3.2" fill="#ff8f6b" opacity="0.55"/>
  <g fill="#fff6cc">
    <path d="M32 38 l1.8 4.6 4.6 1.8 -4.6 1.8 -1.8 4.6 -1.8 -4.6 -4.6 -1.8 4.6 -1.8 z"/>
    <path d="M168 52 l1.4 3.6 3.6 1.4 -3.6 1.4 -1.4 3.6 -1.4 -3.6 -3.6 -1.4 3.6 -1.4 z" opacity="0.85"/>
    <path d="M158 158 l1.6 4 4 1.6 -4 1.6 -1.6 4 -1.6 -4 -4 -1.6 4 -1.6 z" opacity="0.75"/>
  </g>
  <g fill="#ffffff" opacity="0.8">
    <circle cx="26" cy="70" r="1.5"/>
    <circle cx="58" cy="30" r="1.2"/>
    <circle cx="150" cy="28" r="1.4"/>
    <circle cx="178" cy="112" r="1.5"/>
    <circle cx="40" cy="130" r="1.3"/>
    <circle cx="170" cy="176" r="1.2"/>
  </g>
</svg>"""

FISH = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <defs>
    <linearGradient id="fiWater" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#7fd8ff"/>
      <stop offset="100%" stop-color="#1b5f9e"/>
    </linearGradient>
    <linearGradient id="fiBody" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#ffb45c"/>
      <stop offset="100%" stop-color="#f0701f"/>
    </linearGradient>
  </defs>
  <rect width="200" height="200" fill="url(#fiWater)"/>
  <ellipse cx="100" cy="190" rx="110" ry="26" fill="#f4d9a0" opacity="0.75"/>
  <path d="M0 176 q30 -12 60 0 q30 12 60 0 q30 -12 60 0 q10 4 20 0 v30 H0 z"
        fill="#e6c07a" opacity="0.7"/>
  <g fill="none" stroke="#3f9c4a" stroke-width="4" stroke-linecap="round">
    <path d="M24 188 q-6 -30 4 -54 q8 -20 2 -38"/>
    <path d="M40 190 q10 -24 2 -44"/>
    <path d="M176 190 q-8 -26 2 -46"/>
  </g>
  <g fill="#ffffff" opacity="0.35">
    <circle cx="150" cy="52" r="7"/>
    <circle cx="163" cy="34" r="4.5"/>
    <circle cx="140" cy="30" r="3"/>
    <circle cx="170" cy="70" r="5"/>
  </g>
  <path d="M116 102 l32 -22 v44 z" fill="#ff8f3f" stroke="#c9560f"
        stroke-width="2" stroke-linejoin="round"/>
  <ellipse cx="88" cy="102" rx="46" ry="30" fill="url(#fiBody)"
           stroke="#c9560f" stroke-width="2.4"/>
  <path d="M78 76 q10 -14 22 -8" fill="#ff8f3f" stroke="#c9560f" stroke-width="2"/>
  <path d="M82 128 q10 10 22 6" fill="#ff8f3f" stroke="#c9560f" stroke-width="2"/>
  <g fill="none" stroke="#d97323" stroke-width="1.6" opacity="0.8">
    <path d="M74 88 q10 8 0 16"/>
    <path d="M88 84 q10 10 0 20"/>
    <path d="M102 84 q10 10 0 20"/>
    <path d="M114 88 q8 8 0 16"/>
  </g>
  <circle cx="62" cy="96" r="7" fill="#ffffff" stroke="#c9560f" stroke-width="1.5"/>
  <circle cx="60" cy="96" r="3.4" fill="#222222"/>
  <circle cx="58.6" cy="94.6" r="1.2" fill="#ffffff"/>
  <path d="M48 108 q6 4 12 1" fill="none" stroke="#b34a0c"
        stroke-width="2" stroke-linecap="round"/>
  <ellipse cx="56" cy="110" rx="5" ry="3" fill="#ff8fa3" opacity="0.4"/>
  <g fill="#ffffff" opacity="0.45">
    <circle cx="120" cy="140" r="4"/>
    <circle cx="132" cy="154" r="3"/>
    <circle cx="126" cy="124" r="2.5"/>
  </g>
</svg>"""

BUTTERFLY = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <defs>
    <linearGradient id="bfBg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#e8f7ff"/>
      <stop offset="100%" stop-color="#fff4d6"/>
    </linearGradient>
    <linearGradient id="bfWing" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#8ecbff"/>
      <stop offset="55%" stop-color="#7a8cff"/>
      <stop offset="100%" stop-color="#b46bff"/>
    </linearGradient>
    <linearGradient id="bfWing2" x1="1" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#8ecbff"/>
      <stop offset="55%" stop-color="#7a8cff"/>
      <stop offset="100%" stop-color="#b46bff"/>
    </linearGradient>
  </defs>
  <rect width="200" height="200" fill="url(#bfBg)"/>
  <g fill="#ffffff" opacity="0.8">
    <circle cx="32" cy="42" r="6"/>
    <circle cx="170" cy="150" r="5"/>
    <circle cx="156" cy="36" r="3.5"/>
  </g>
  <path d="M100 94 C70 46 30 50 34 84 C37 108 72 108 100 94 Z"
        fill="url(#bfWing)" stroke="#5a4bb5" stroke-width="2"/>
  <path d="M100 94 C130 46 170 50 166 84 C163 108 128 108 100 94 Z"
        fill="url(#bfWing2)" stroke="#5a4bb5" stroke-width="2"/>
  <path d="M100 100 C74 128 46 138 48 156 C50 172 82 158 100 120 Z"
        fill="url(#bfWing)" stroke="#5a4bb5" stroke-width="2"/>
  <path d="M100 100 C126 128 154 138 152 156 C150 172 118 158 100 120 Z"
        fill="url(#bfWing2)" stroke="#5a4bb5" stroke-width="2"/>
  <g fill="#ffffff" opacity="0.75">
    <circle cx="64" cy="78" r="8"/>
    <circle cx="136" cy="78" r="8"/>
    <circle cx="60" cy="134" r="5"/>
    <circle cx="140" cy="134" r="5"/>
    <circle cx="72" cy="94" r="3"/>
    <circle cx="128" cy="94" r="3"/>
  </g>
  <g fill="#ffd34d" opacity="0.9">
    <circle cx="86" cy="64" r="3"/>
    <circle cx="114" cy="64" r="3"/>
  </g>
  <ellipse cx="100" cy="108" rx="6" ry="26" fill="#4a3b6b"/>
  <circle cx="100" cy="80" r="7" fill="#4a3b6b"/>
  <circle cx="97.5" cy="78" r="1.4" fill="#ffffff"/>
  <circle cx="102.5" cy="78" r="1.4" fill="#ffffff"/>
  <path d="M97 75 q-12 -14 -20 -10 M103 75 q12 -14 20 -10" fill="none"
        stroke="#4a3b6b" stroke-width="2" stroke-linecap="round"/>
  <circle cx="76" cy="64" r="2.2" fill="#4a3b6b"/>
  <circle cx="124" cy="64" r="2.2" fill="#4a3b6b"/>
</svg>"""

RAINBOW = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <defs>
    <linearGradient id="rbSky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#a5e2ff"/>
      <stop offset="100%" stop-color="#eafaff"/>
    </linearGradient>
  </defs>
  <rect width="200" height="200" fill="url(#rbSky)"/>
  <circle cx="164" cy="42" r="20" fill="#ffd94d"/>
  <circle cx="164" cy="42" r="26" fill="#ffd94d" opacity="0.25"/>
  <g fill="none" stroke-linecap="round">
    <path d="M24 158 A76 76 0 0 1 176 158" stroke="#ff5d5d" stroke-width="13"/>
    <path d="M37 158 A63 63 0 0 1 163 158" stroke="#ff9f43" stroke-width="13"/>
    <path d="M50 158 A50 50 0 0 1 150 158" stroke="#ffd93d" stroke-width="13"/>
    <path d="M63 158 A37 37 0 0 1 137 158" stroke="#6bd968" stroke-width="13"/>
    <path d="M76 158 A24 24 0 0 1 124 158" stroke="#5aa9ff" stroke-width="13"/>
    <path d="M89 158 A11 11 0 0 1 111 158" stroke="#a77bff" stroke-width="13"/>
  </g>
  <g fill="#ffffff">
    <ellipse cx="52" cy="164" rx="30" ry="15"/>
    <ellipse cx="36" cy="158" rx="18" ry="11"/>
    <ellipse cx="70" cy="158" rx="18" ry="11"/>
    <ellipse cx="148" cy="164" rx="30" ry="15"/>
    <ellipse cx="132" cy="158" rx="18" ry="11"/>
    <ellipse cx="166" cy="158" rx="18" ry="11"/>
  </g>
  <g fill="#cfe9ff" opacity="0.9">
    <ellipse cx="52" cy="168" rx="22" ry="8"/>
    <ellipse cx="148" cy="168" rx="22" ry="8"/>
  </g>
  <path d="M0 180 q50 -12 100 0 q50 12 100 0 v20 H0 z" fill="#8fd45a"/>
  <g fill="#6dbb3c">
    <path d="M28 184 q4 -12 8 0 z"/>
    <path d="M86 184 q4 -12 8 0 z"/>
    <path d="M154 184 q4 -12 8 0 z"/>
  </g>
</svg>"""

TREE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <defs>
    <linearGradient id="trSky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#c9ecff"/>
      <stop offset="100%" stop-color="#f4ffe9"/>
    </linearGradient>
    <linearGradient id="trTrunk" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#a9713d"/>
      <stop offset="100%" stop-color="#7a4b22"/>
    </linearGradient>
    <radialGradient id="trLeaf" cx="40%" cy="35%" r="70%">
      <stop offset="0%" stop-color="#9ede6a"/>
      <stop offset="100%" stop-color="#4f9e3a"/>
    </radialGradient>
  </defs>
  <rect width="200" height="200" fill="url(#trSky)"/>
  <circle cx="36" cy="38" r="18" fill="#ffe066"/>
  <circle cx="36" cy="38" r="24" fill="#ffe066" opacity="0.25"/>
  <path d="M0 164 q50 -16 100 0 q50 16 100 0 v36 H0 z" fill="#8fd45a"/>
  <path d="M0 176 q54 -12 108 2 q46 12 92 -2 v24 H0 z" fill="#6dbb3c"/>
  <path d="M92 170 q-4 -38 2 -58 l14 0 q6 20 2 58 z" fill="url(#trTrunk)"
        stroke="#6a3f1b" stroke-width="2"/>
  <path d="M100 128 q-14 -4 -20 -18 q14 2 20 18 z" fill="#7a4b22"/>
  <g stroke="#3d7d2b" stroke-width="1.5">
    <circle cx="100" cy="78" r="34" fill="url(#trLeaf)"/>
    <circle cx="70" cy="94" r="24" fill="url(#trLeaf)"/>
    <circle cx="130" cy="94" r="24" fill="url(#trLeaf)"/>
    <circle cx="84" cy="62" r="22" fill="url(#trLeaf)"/>
    <circle cx="118" cy="62" r="22" fill="url(#trLeaf)"/>
  </g>
  <g fill="#a8e063" opacity="0.55">
    <circle cx="88" cy="62" r="8"/>
    <circle cx="64" cy="86" r="6"/>
    <circle cx="128" cy="82" r="7"/>
  </g>
  <g fill="#ff5d5d" stroke="#c93a3a" stroke-width="1">
    <circle cx="84" cy="86" r="6"/>
    <circle cx="116" cy="78" r="6"/>
    <circle cx="102" cy="104" r="6"/>
    <circle cx="70" cy="102" r="5"/>
    <circle cx="132" cy="106" r="5"/>
  </g>
  <g fill="#6dbb3c">
    <path d="M40 166 q4 -14 8 0 z"/>
    <path d="M156 170 q4 -14 8 0 z"/>
  </g>
</svg>"""

HOUSE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <defs>
    <linearGradient id="hoSky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#b7e4ff"/>
      <stop offset="100%" stop-color="#eafaff"/>
    </linearGradient>
    <linearGradient id="hoWall" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#fff1c9"/>
      <stop offset="100%" stop-color="#f0d59a"/>
    </linearGradient>
    <linearGradient id="hoRoof" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#e8705a"/>
      <stop offset="100%" stop-color="#c94a3a"/>
    </linearGradient>
  </defs>
  <rect width="200" height="200" fill="url(#hoSky)"/>
  <circle cx="164" cy="38" r="16" fill="#ffd94d"/>
  <path d="M0 168 q50 -14 100 0 q50 14 100 0 v32 H0 z" fill="#8fd45a"/>
  <path d="M0 180 q54 -10 108 2 q46 10 92 -2 v20 H0 z" fill="#6dbb3c"/>
  <rect x="46" y="104" width="108" height="70" fill="url(#hoWall)"
        stroke="#b58b45" stroke-width="2.5"/>
  <path d="M36 106 L100 58 L164 106 Z" fill="url(#hoRoof)"
        stroke="#a83a2c" stroke-width="2.5" stroke-linejoin="round"/>
  <rect x="126" y="66" width="14" height="26" fill="#b06a4a" stroke="#8c4f33" stroke-width="2"/>
  <g fill="#dcdcdc" opacity="0.8">
    <circle cx="134" cy="56" r="7"/>
    <circle cx="144" cy="46" r="9"/>
    <circle cx="158" cy="38" r="10"/>
  </g>
  <rect x="60" y="120" width="24" height="24" rx="2" fill="#9ad7ff"
        stroke="#6a4a2a" stroke-width="2"/>
  <path d="M72 120 v24 M60 132 h24" stroke="#6a4a2a" stroke-width="1.6"/>
  <rect x="116" y="120" width="24" height="24" rx="2" fill="#9ad7ff"
        stroke="#6a4a2a" stroke-width="2"/>
  <path d="M128 120 v24 M116 132 h24" stroke="#6a4a2a" stroke-width="1.6"/>
  <rect x="88" y="140" width="26" height="34" rx="3" fill="#a9713d"
        stroke="#6a3f1b" stroke-width="2"/>
  <circle cx="108" cy="158" r="2.4" fill="#ffd34d"/>
  <ellipse cx="100" cy="176" rx="30" ry="6" fill="#5a7d3a" opacity="0.25"/>
  <g fill="#4f9e3a" stroke="#3d7d2b" stroke-width="1.5">
    <circle cx="32" cy="166" r="12"/>
    <circle cx="42" cy="158" r="9"/>
    <circle cx="24" cy="158" r="8"/>
    <circle cx="168" cy="164" r="11"/>
    <circle cx="178" cy="156" r="8"/>
  </g>
  <g fill="#7a4b22">
    <rect x="24" y="176" width="5" height="12"/>
    <rect x="166" y="174" width="5" height="14"/>
  </g>
</svg>"""

SNOWMAN = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <defs>
    <linearGradient id="snSky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#a9c8ef"/>
      <stop offset="100%" stop-color="#eaf4ff"/>
    </linearGradient>
    <radialGradient id="snBall" cx="40%" cy="32%" r="70%">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="100%" stop-color="#d7e6f7"/>
    </radialGradient>
  </defs>
  <rect width="200" height="200" fill="url(#snSky)"/>
  <circle cx="34" cy="36" r="14" fill="#fff6c9" opacity="0.9"/>
  <path d="M0 172 q50 -14 100 0 q50 14 100 0 v28 H0 z" fill="#ffffff"/>
  <path d="M0 184 q54 -8 108 2 q46 8 92 -2 v16 H0 z" fill="#e2eefb"/>
  <circle cx="100" cy="156" r="32" fill="url(#snBall)" stroke="#b9cde4" stroke-width="2"/>
  <circle cx="100" cy="114" r="25" fill="url(#snBall)" stroke="#b9cde4" stroke-width="2"/>
  <circle cx="100" cy="78" r="20" fill="url(#snBall)" stroke="#b9cde4" stroke-width="2"/>
  <circle cx="93" cy="74" r="2.6" fill="#2b2b2b"/>
  <circle cx="107" cy="74" r="2.6" fill="#2b2b2b"/>
  <path d="M94 84 l12 0 l-6 6 z" fill="#ff9a3c" stroke="#e07b1f" stroke-width="1.3"
        stroke-linejoin="round"/>
  <g fill="#2b2b2b">
    <circle cx="100" cy="90" r="1.2"/>
    <circle cx="100" cy="94" r="1.2"/>
    <circle cx="100" cy="98" r="1.2"/>
  </g>
  <path d="M92 88 q8 6 16 0" fill="none" stroke="#8a5a2a"
        stroke-width="1.6" stroke-linecap="round"/>
  <path d="M75 106 q-16 4 -20 14 M125 106 q16 4 20 14" fill="none"
        stroke="#8a5a2a" stroke-width="2.4" stroke-linecap="round"/>
  <path d="M76 112 l-14 -6 M124 112 l14 -6" fill="none" stroke="#8a5a2a"
        stroke-width="2.4" stroke-linecap="round"/>
  <path d="M80 96 q20 12 40 0 q-8 12 -40 0 z" fill="#e5473f"/>
  <path d="M108 96 l10 18 l-9 3 l-7 -17 z" fill="#c93a33"/>
  <rect x="82" y="52" width="36" height="5" rx="2" fill="#3a3a5a"/>
  <path d="M86 52 v-18 h28 v18 z" fill="#4a4a6b" stroke="#33334d" stroke-width="1.5"/>
  <rect x="84" y="33" width="32" height="4" rx="2" fill="#33334d"/>
  <circle cx="100" cy="128" r="2.6" fill="#2b2b2b"/>
  <circle cx="100" cy="140" r="2.6" fill="#2b2b2b"/>
  <circle cx="100" cy="152" r="2.6" fill="#2b2b2b"/>
  <g fill="#ffffff" opacity="0.9">
    <circle cx="30" cy="70" r="2"/>
    <circle cx="160" cy="60" r="2"/>
    <circle cx="150" cy="100" r="1.5"/>
    <circle cx="46" cy="120" r="1.6"/>
    <circle cx="168" cy="140" r="1.8"/>
  </g>
</svg>"""

COFFEE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <defs>
    <linearGradient id="coBg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#fff3e0"/>
      <stop offset="100%" stop-color="#f4d7b0"/>
    </linearGradient>
    <linearGradient id="coCup" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="100%" stop-color="#d9e2ec"/>
    </linearGradient>
    <radialGradient id="coDrink" cx="45%" cy="40%" r="65%">
      <stop offset="0%" stop-color="#9a5a2b"/>
      <stop offset="100%" stop-color="#5a3013"/>
    </radialGradient>
  </defs>
  <rect width="200" height="200" fill="url(#coBg)"/>
  <path d="M0 160 h200 v40 H0 z" fill="#c98a52"/>
  <path d="M0 160 h200 v6 H0 z" fill="#a9713d"/>
  <ellipse cx="100" cy="168" rx="70" ry="12" fill="#8a5a2a" opacity="0.25"/>
  <path d="M142 96 q26 2 24 24 q-2 20 -26 20 l2 -10 q14 0 16 -12 q1 -10 -16 -12 z"
        fill="url(#coCup)" stroke="#9aa8b8" stroke-width="2.5"/>
  <path d="M58 92 h84 l-8 64 q-2 12 -14 12 h-40 q-12 0 -14 -12 z"
        fill="url(#coCup)" stroke="#9aa8b8" stroke-width="2.5"/>
  <ellipse cx="100" cy="92" rx="42" ry="12" fill="#f6f9fc" stroke="#9aa8b8" stroke-width="2.5"/>
  <ellipse cx="100" cy="93" rx="33" ry="8.5" fill="url(#coDrink)"/>
  <path d="M100 100 c-6 -6 -16 -1 -14 6 c2 6 14 10 14 10 c0 0 12 -4 14 -10 c2 -7 -8 -12 -14 -6 z"
        fill="#f3e3cb" opacity="0.95"/>
  <g fill="none" stroke="#ffffff" stroke-width="3" stroke-linecap="round" opacity="0.55">
    <path d="M78 70 q-6 -12 2 -22 q8 -10 2 -20"/>
    <path d="M100 66 q-6 -12 2 -22 q8 -10 2 -20"/>
    <path d="M122 70 q-6 -12 2 -22 q8 -10 2 -20"/>
  </g>
  <ellipse cx="100" cy="170" rx="62" ry="10" fill="#eef3f8" stroke="#9aa8b8" stroke-width="2.5"/>
  <ellipse cx="100" cy="170" rx="48" ry="6" fill="#dbe6f0"/>
  <g transform="rotate(-12 156 150)">
    <circle cx="156" cy="150" r="12" fill="#e8b06b" stroke="#b97a3a" stroke-width="2"/>
    <circle cx="152" cy="147" r="2" fill="#6a3f1b"/>
    <circle cx="160" cy="149" r="2" fill="#6a3f1b"/>
    <circle cx="155" cy="154" r="2" fill="#6a3f1b"/>
  </g>
</svg>"""

DEFAULT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <defs>
    <linearGradient id="deSky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#161436"/>
      <stop offset="55%" stop-color="#3d2c6b"/>
      <stop offset="100%" stop-color="#7a4b8f"/>
    </linearGradient>
    <radialGradient id="deGlow">
      <stop offset="0%" stop-color="#ffe9a3" stop-opacity="0.5"/>
      <stop offset="100%" stop-color="#ffe9a3" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="deHill" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#6c4b9a"/>
      <stop offset="100%" stop-color="#33224f"/>
    </linearGradient>
    <linearGradient id="deStar" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#fff6b0"/>
      <stop offset="100%" stop-color="#ffb52e"/>
    </linearGradient>
  </defs>
  <rect width="200" height="200" fill="url(#deSky)"/>
  <circle cx="146" cy="56" r="48" fill="url(#deGlow)"/>
  <path d="M146 26 a32 32 0 1 0 0 64 a26 26 0 1 1 0 -64 z" fill="#ffe9a3"/>
  <circle cx="136" cy="46" r="4" fill="#e8c568" opacity="0.6"/>
  <circle cx="129" cy="64" r="3" fill="#e8c568" opacity="0.5"/>
  <circle cx="142" cy="76" r="2.5" fill="#e8c568" opacity="0.5"/>
  <g fill="#fff6cc">
    <path d="M38 34 l2 5.2 5.2 2 -5.2 2 -2 5.2 -2 -5.2 -5.2 -2 5.2 -2 z"/>
    <path d="M78 46 l1.5 3.9 3.9 1.5 -3.9 1.5 -1.5 3.9 -1.5 -3.9 -3.9 -1.5 3.9 -1.5 z" opacity="0.85"/>
    <path d="M62 96 l1.3 3.4 3.4 1.3 -3.4 1.3 -1.3 3.4 -1.3 -3.4 -3.4 -1.3 3.4 -1.3 z" opacity="0.7"/>
    <path d="M170 112 l1.5 4 4 1.5 -4 1.5 -1.5 4 -1.5 -4 -4 -1.5 4 -1.5 z" opacity="0.75"/>
  </g>
  <g fill="#ffffff" opacity="0.85">
    <circle cx="26" cy="62" r="1.6"/>
    <circle cx="90" cy="26" r="1.3"/>
    <circle cx="112" cy="60" r="1.2"/>
    <circle cx="56" cy="72" r="1.2"/>
    <circle cx="178" cy="44" r="1.5"/>
    <circle cx="160" cy="132" r="1.3"/>
  </g>
  <path d="M0 162 q42 -28 84 -6 q34 18 66 -2 q26 -16 50 2 v44 H0 z" fill="url(#deHill)"/>
  <path d="M0 178 q54 -16 108 2 q46 12 92 -2 v22 H0 z" fill="#241a3d"/>
  <g>
    <path d="M72 148 l5 12 12 5 -12 5 -5 12 -5 -12 -12 -5 12 -5 z" fill="url(#deStar)"
          stroke="#e8991a" stroke-width="1.5" stroke-linejoin="round"/>
    <circle cx="70" cy="162" r="1.8" fill="#7a4a00"/>
    <circle cx="77" cy="162" r="1.8" fill="#7a4a00"/>
    <path d="M70 168 q4 3 8 0" fill="none" stroke="#7a4a00"
          stroke-width="1.4" stroke-linecap="round"/>
  </g>
  <circle cx="42" cy="170" r="3" fill="#ffd94d" opacity="0.9"/>
  <circle cx="132" cy="172" r="2.4" fill="#ffd94d" opacity="0.8"/>
  <circle cx="154" cy="164" r="2" fill="#ffd94d" opacity="0.8"/>
</svg>"""

# Official self-portrait based on the user's milka_idle.svg line art.
# A dark background is baked in so the white strokes stay visible in the gallery.
SELFIE = """<svg xmlns="http://www.w3.org/2000/svg" width="640" height="640"
     viewBox="0 0 640 640" fill="none">
  <defs>
    <radialGradient id="selfieBg" cx="50%" cy="40%" r="72%">
      <stop offset="0%" stop-color="#3b3158"/>
      <stop offset="60%" stop-color="#241d38"/>
      <stop offset="100%" stop-color="#141020"/>
    </radialGradient>
    <radialGradient id="selfieGlow" cx="50%" cy="45%" r="50%">
      <stop offset="0%" stop-color="#ff9ecb" stop-opacity="0.30"/>
      <stop offset="100%" stop-color="#ff9ecb" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="640" height="640" fill="url(#selfieBg)"/>
  <circle cx="320" cy="310" r="250" fill="url(#selfieGlow)"/>
  <path d="M284 273C284 218 251 189 207 189C159 189 128 227 128 281C128 333 158 370 200 370C248 370 284 330 284 273Z" stroke-width="17" stroke-linecap="round" stroke-linejoin="round" stroke="white"/>
  <path d="M132 212L97 179" stroke-width="17" stroke-linecap="round" stroke-linejoin="round" stroke="white"/>
  <path d="M118 246L75 227" stroke-width="17" stroke-linecap="round" stroke-linejoin="round" stroke="white"/>
  <path d="M117 279L63 274" stroke-width="17" stroke-linecap="round" stroke-linejoin="round" stroke="white"/>
  <path d="M356 273C356 218 389 189 433 189C481 189 512 227 512 281C512 333 482 370 440 370C392 370 356 330 356 273Z" stroke-width="17" stroke-linecap="round" stroke-linejoin="round" stroke="white"/>
  <path d="M508 212L543 179" stroke-width="17" stroke-linecap="round" stroke-linejoin="round" stroke="white"/>
  <path d="M522 246L565 227" stroke-width="17" stroke-linecap="round" stroke-linejoin="round" stroke="white"/>
  <path d="M523 279L577 274" stroke-width="17" stroke-linecap="round" stroke-linejoin="round" stroke="white"/>
  <path d="M247 427C272 451 299 461 321 461C344 461 370 451 394 427" stroke-width="17" stroke-linecap="round" stroke-linejoin="round" stroke="white"/>
  <g fill="#ff9ecb">
    <path d="M96 96 l3 8 8 3 -8 3 -3 8 -3 -8 -8 -3 8 -3 z" opacity="0.9"/>
    <path d="M548 118 l2 6 6 2 -6 2 -2 6 -2 -6 -6 -2 6 -2 z" opacity="0.8"/>
    <path d="M520 500 l2.4 6.6 6.6 2.4 -6.6 2.4 -2.4 6.6 -2.4 -6.6 -6.6 -2.4 6.6 -2.4 z" opacity="0.7"/>
  </g>
  <g fill="#ffffff" opacity="0.5">
    <circle cx="150" cy="120" r="2"/>
    <circle cx="500" cy="320" r="2.4"/>
    <circle cx="120" cy="430" r="1.8"/>
    <circle cx="430" cy="120" r="1.6"/>
  </g>
</svg>"""

# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

_SUBJECTS = (
    ("cat", r"\bкот(?:ик\w*|[её]н\w*|ят\w*|ами|ах|а|у|ом|е|ы|ов)?\b|\bкошк\w*|\b(?:cat|kitten|kitty)\w*\b", CAT),
    ("dog", r"\bсобак\w*|\bсобач\w*|\bп[её]с(?:ик\w*|а|у|ом|е|ы|ов)?\b|\bщен(?:ок|к\w*)\b|\b(?:dog|puppy|pup)\w*\b", DOG),
    ("bunny", r"\bзай(?:чик\w*|ка|ке|ку|ком|цы|цев|чонок\w*)\b|\bзаяц\w*|\bкрол\w*|\b(?:bunny|rabbit|hare)\w*\b", BUNNY),
    ("snowman", r"\bснегов\w*|\b(?:snowman|snow\s?man)\w*\b", SNOWMAN),
    ("sun", r"\bсолн(?:це|ца|цу|цем|е|ышк\w*|ечн\w*)\b|\b(?:sun|sunshine|sunny)\w*\b", SUN),
    ("moon", r"\bлун(?:а|ы|е|у|ой|н\w*)\b|\bмесяц\w*|\b(?:moon|moonlight)\w*\b", MOON),
    ("star", r"\bзв[её]зд\w*|\b(?:star|stars)\w*\b", STAR),
    ("heart", r"\bсерд(?:це|ца|цу|цем|е|ечк\w*|ечн\w*)\b|\b(?:heart|love)\w*\b", HEART),
    ("flower", r"\bцвет(?:ок|ка|ку|ком|ке|ы|ов|очек|очка|очки)\b|\bроз(?:а|ы|у|е|ой|очк\w*)\b|\b(?:flower|rose|blossom|tulip)\w*\b", FLOWER),
    ("fish", r"\bрыб(?:а|ы|е|у|ой|к\w*)?\b|\b(?:fish|goldfish)\w*\b", FISH),
    ("butterfly", r"\bбабочк\w*|\b(?:butterfly|butterflies)\w*\b", BUTTERFLY),
    ("rainbow", r"\bрадуг\w*|\b(?:rainbow)\w*\b", RAINBOW),
    ("tree", r"\bдерев(?:о|а|у|ом|е|ья|ьев|ьям)\b|\bёлк\w*|\bелк\w*|\b(?:tree|pine|fir)\w*\b", TREE),
    ("house", r"\bдом(?:ик\w*)?\b|\b(?:house|home|cottage)\w*\b", HOUSE),
    ("coffee", r"\bкофе\w*|\bчашк\w*|\b(?:coffee|latte|cappuccino|espresso)\w*\b", COFFEE),
)

_SUBJECT_PATTERNS = tuple(
    (name, re.compile(pattern, re.IGNORECASE), svg)
    for name, pattern, svg in _SUBJECTS
)

_DRAW_RE = re.compile(
    r"\bнарису\w*|\bнарисова\w*|\bрисун\w*|\bрисова\w*|\bизобраз\w*|"
    r"\b(?:draw|drawing|paint|painting|sketch|illustrate|illustration)\w*\b|"
    r"\b(?:picture|image|artwork)\b|\bкартин\w*|\bизображени\w*|"
    r"\b(?:селфи|селфик|автопортрет)\w*\b|\bselfie\w*\b",
    re.IGNORECASE,
)

_SELFIE_RE = re.compile(
    r"\b(?:нарису\w*|нарисова\w*|изобраз\w*)\s+(?:мне\s+)?(?:себя|милк\w*)\b"
    r"|\bпортрет\s+(?:себя|милк\w*)\b"
    r"|\b(?:мой|свой)\s+портрет\b"
    r"|\b(?:селфи|селфик|автопортрет)\w*\b"
    r"|\b(?:покажи|показать)\s+себя\b"
    r"|\b(?:draw|paint|sketch|illustrate)\s+(?:a\s+)?"
    r"(?:yourself|milky|selfie)\b"
    r"|\b(?:draw|paint|sketch|illustrate)\s+(?:a\s+)?"
    r"(?:picture|image|drawing|portrait)\s+of\s+(?:yourself|milky)\b"
    r"|\bselfie\w*\b|\bself-portrait\w*\b",
    re.IGNORECASE,
)


def asked_to_draw(text):
    """Return True when the user asks Milky to draw or show a picture."""
    return bool(text) and _DRAW_RE.search(text) is not None


def wants_selfie(text):
    """Return True when the user asks Milky to draw herself."""
    return bool(text) and _SELFIE_RE.search(text) is not None


def subject_for(text):
    """Return the artwork key that matches the request, or None."""
    if not text:
        return None
    if wants_selfie(text):
        return "selfie"
    for name, pattern, _svg in _SUBJECT_PATTERNS:
        if pattern.search(text):
            return name
    return None


def draw_for(text):
    """Pick the best detailed artwork for the user's request."""
    if not text:
        return DEFAULT
    if wants_selfie(text):
        return SELFIE
    for _name, pattern, svg in _SUBJECT_PATTERNS:
        if pattern.search(text):
            return svg
    return DEFAULT
