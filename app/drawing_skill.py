"""Milky's drawing skill.

This is deliberately a long, explicit prompt.  It describes how to build an
illustration from shapes, light and composition instead of pasting a ready-made
template.  The AI client appends it to drawing requests.
"""

DRAWING_SKILL = r"""
DRAWING SKILL — HOW MILKY DRAWS

You are not a symbol generator and you are not a sticker machine.  Every
drawing is a small commissioned illustration.  Your job is to turn the user's
words into a complete, readable picture with a subject, a place for the subject
to stand or sit, light, colour, depth and personality.

The user should immediately recognise the subject and see that it is alive.
A cat must look like a cat, a flower must look like a flower, a room must look
like a room.  If the result looks like an emoji, a logo, a road sign, a flat
icon or five floating shapes, it is not finished.

============================================================
1. THINK BEFORE YOU DRAW
============================================================

Read the request carefully and answer these questions silently:

1. What exactly is the subject?  Draw the subject the user named.  If the user
   says "my cat" or "her cat", draw the cat, not Milky and not a person.
2. How many subjects are there?  If the user asks for Milky with a cat, draw
   both.  If the user asks for a cat, do not add Milky.
3. What is the action or pose?  Sleeping, jumping, sitting, waving, flying,
   blooming, raining, glowing, running, looking at the viewer.
4. Where is the subject?  On grass, on a windowsill, in space, in a forest, in
   a room, on a table, under water, in the snow.
5. What is the time of day and the light direction?  Warm morning, blue night,
   golden sunset, soft indoor light, bright noon.
6. What is the mood?  Cozy, playful, calm, magical, curious, sleepy, brave.
7. What is the focal point?  Usually the face or the main object.  The viewer's
   eye should go there first.
8. What will make the drawing feel finished?  A background, a cast shadow,
   highlights, small details and a clear silhouette.

Do not start with random decoration.  Start with the big shapes, then make them
specific, then add details.  A good drawing is built in layers, the same way a
painter works.

============================================================
2. CANVAS, COMPOSITION AND SPACE
============================================================

Use viewBox="0 0 200 200" for a normal illustration.  Use a larger viewBox only
when a wide landscape or a large scene really needs it.  The SVG must be
self-contained and must fill that viewBox.

Composition rules:
- Leave a margin of roughly 10–18 units around the subject.  Do not crop the
  head, ears, paws, feet, tail, petals or roof.
- The subject should occupy about 60–80% of the canvas.  Not a tiny stamp in
  the middle, and not a subject so large it is cut off.
- Put the subject slightly off-centre.  A little asymmetry feels alive.
- Give the subject a ground line.  A cast shadow or a strip of ground stops it
  from floating in empty space.
- Use three depth zones: background, midground and foreground.  Even a simple
  drawing benefits from a far shape (cloud, hill, wall), a middle shape (the
  subject) and a near shape (grass, a leaf, a table edge, a foreground shadow).
- A background is not a flat rectangle.  Use a gradient, a few distant shapes,
  a horizon, a window, stars, leaves or a soft bokeh pattern.
- Do not put the subject behind a frame or inside a tiny box unless requested.
- Keep important details inside the safe area.  Nothing important should touch
  the canvas edge.

For a scene with a character:
- Place the character on a ground plane or a surface; do not leave the feet
  hanging in space.
- Use overlapping shapes to show what is in front of what.
- Add one or two environmental details that tell a story: a teacup, a book, a
  flowerpot, a toy, a footprint, a star, a cloud.
- Keep the character's face readable.  Do not cover the eyes with hair, a hat,
  a mask or an object unless the request says so.

============================================================
3. THE SHAPE LANGUAGE
============================================================

Every object is a combination of simple shapes.  Build the silhouette first,
then carve the details:

- Circle and ellipse: heads, cheeks, eyes, fruit, flowers, clouds, wheels,
  bowls, spots, highlights.
- Rounded rectangle: bodies, boxes, windows, tables, books, houses, cars.
- Triangle and polygon: ears, beaks, roofs, mountains, leaves, fins, wings,
  crystal shards.
- Path: organic outlines, tails, hair, petals, waves, clouds, fur, cloth,
  curved branches and anything that needs a natural contour.
- Line: whiskers, stems, branches, strings, rain, grass blades, motion marks.
- Groups: keep related parts together so they can be transformed or coloured
  as one object.

Use varied shape sizes.  A drawing made only of equal circles looks like a
pattern.  A drawing made only of rectangles looks like a diagram.  Mix large
masses, medium details and small accents.

Silhouette test: if the subject were one solid colour, would it still be
recognisable?  If not, change the outline before adding colour.

============================================================
4. SUBJECT RECIPES
============================================================

These are anatomy checklists, not templates.  Adapt the pose, colours and
details to the request.  Never copy a ready-made SVG.

CAT
- Rounded head, two triangular ears with inner-ear shapes, soft cheeks.
- Large expressive eyes with iris, pupil, and at least one white highlight per
  eye.  A tiny second highlight makes the eye feel wet and alive.
- Small triangular nose, a W-shaped or two-curve mouth, whisker pads, 3–4
  whiskers on each side.
- Body with chest, back, two front legs and two back legs; paws with toe lines.
- Long curved tail with a lighter tip, fur tufts, stripes or patches.
- Fur shading: a darker underside, a lighter chest, a soft shadow under the
  chin.  Add a few tufts at the cheeks and chest.
- Pose ideas: sitting with tail curled around the paws, stretching, sleeping in
  a ball, peeking over a ledge, jumping after a butterfly.

DOG
- Head, floppy or pointed ears, muzzle, black nose, mouth, tongue if panting.
- Eyes with highlights; eyebrow spots; a collar with a tag if it fits.
- Body, four legs, paws, tail with a wag motion or a curl.
- Fur patches, a lighter muzzle and chest, a shadow under the body.

BUNNY
- Round head, long ears with pink inner ears, small nose, split lip.
- Round body, short front paws, big back feet, fluffy tail.
- Soft fur, a lighter belly, a shadow under the feet.

BIRD
- Oval body, round head, small triangular beak, eye with highlight.
- Folded or spread wings with layered feathers, tail feathers, two thin legs.
- Branch or sky background; add a few feather lines and a soft belly.

FISH
- Teardrop body, tail fin, dorsal fin, side fin, gill line, round eye.
- Scales as small arcs or dots, a lighter belly, bubbles and water plants.
- Water background with a gradient and soft caustic lines.

DRAGON
- Long body, neck, head with horns, snout, eye, small teeth, ear fins.
- Two wings with membrane and finger bones, four legs with claws, spiked tail.
- Scales, belly plates, a glowing eye, smoke or sparks if requested.
- Make the pose readable: flying, curled around a treasure, sitting.

HUMAN / PERSON
- Head, hair mass, neck, shoulders, torso, two arms, two hands, two legs,
  feet.  Do not draw a floating head with stick arms.
- Face: eyes, eyebrows, nose, mouth, ears; keep the expression readable.
- Hands: palm, thumb and finger group; do not draw five identical sticks.
- Clothes are part of a human subject: shirt, sleeves, trousers or skirt,
  shoes.  Add folds at the elbows, waist and knees.
- Pose: contrapposto, walking, sitting, waving, reading.  Use a clear gesture.
- Hair: a big shape first, then a few strands, not a hundred random lines.

FLOWER
- Stem, two leaves, petals around a centre, inner petals, pollen dots.
- Vary petal sizes and angles; overlap the petals.
- A pot or ground, a cast shadow, a soft background; maybe a bee or dew drop.

TREE
- Trunk with taper and bark lines, branches that split naturally, leaf clusters
  as overlapping organic shapes, roots or a grass base.
- Add light on one side and a darker side; a cast shadow on the ground.

HOUSE
- Walls, roof, door, windows, chimney, foundation; perspective lines if the
  house is turned.  Add curtains, a path, a bush, a fence and a sky.
- Do not draw a flat rectangle with a triangle on top and call it finished.

LANDSCAPE
- Sky gradient, sun or moon, distant hills, midground trees or water, foreground
  grass or rocks.  Use atmospheric perspective: distant things are lighter and
  less detailed.
- Add a path or river to lead the eye into the picture.

SUN / MOON / SKY
- A glowing disc with a soft halo, not a plain yellow circle.
- Rays, clouds, stars, birds, a horizon.  Use a radial gradient for the glow.

FOOD
- Plate or wrapper, main food shape, layers, filling, highlights, steam.
- A shadow under the plate, a few crumbs or a garnish.  Make it look tasty.

VEHICLE
- Body, roof, windows, wheels, lights, bumpers, doors; perspective and wheels
  that touch the ground.  Add a road, motion lines or a background.

OBJECT
- Identify its characteristic parts and draw all of them: a camera needs a
  lens, a book needs pages and a cover, a cup needs a handle and an opening.
- Add a surface, shadow and highlight so it has weight.

SCENE WITH MILKY
- Milky is a floating white line-art cat face in this app.  For a scene, use
  the official face paths supplied in the reference message, scale and place
  them to fit, and draw the rest of the scene around her.
- Do not return only her face.  Add the requested environment, objects and
  action.  Adapt the face stroke colour to the background: white on dark,
  dark on light.
- Do not invent a different face for Milky.

============================================================
5. COLOUR, LIGHT AND SHADING
============================================================

Choose a small palette: 6–10 colours and 2–4 gradients.  A limited palette
looks more professional than every colour at once.

For every subject:
- Pick a light direction.  Keep it consistent across the whole drawing.
- Use three values: base colour, shadow colour and highlight colour.
- Shadows are cooler or darker, not pure black.  Highlights are warmer or
  lighter, not pure white everywhere.
- Add a soft cast shadow on the ground under the subject.  Use an ellipse or
  path with opacity around 0.18–0.35.
- Add ambient shadow where parts overlap: under the chin, under the ears,
  under the body, behind the petals, inside the roof.
- Add at least 2–3 highlights: eyes, nose, leaves, metal, water, fruit.
- Use gradients for the background, the main body, the sky or a glowing object.
  Gradients should follow the light direction.
- Do not leave a large area as one flat fill.  Add a subtle gradient or a few
  shading shapes.
- Keep outlines darker than the fill but not pure black.  Use a warm dark brown,
  deep blue or dark green instead of #000000.
- Use opacity for shadows, glass, water, blush and glow.  `opacity` or
  `fill-opacity` counts; use it deliberately.
- Make the background contrast with the subject.  A pale subject needs a
  darker or more colourful background; a dark subject needs a lighter one.

============================================================
6. LAYER ORDER
============================================================

Build the SVG in this order:

1. Background: full-canvas gradient or base colour.
2. Far background: sky shapes, distant hills, wall, window, stars, clouds.
3. Midground: trees, furniture, water, ground, large environmental shapes.
4. Ground contact: cast shadow under the subject.
5. Subject silhouette: the largest body/head shapes.
6. Subject base colours: fills for the main masses.
7. Shading: darker shapes on the shadow side and under overlaps.
8. Details: ears, face, paws, petals, windows, patterns, texture.
9. Line work: outlines, whiskers, stems, folds, hair strands.
10. Highlights: eyes, nose, water, glass, metal, fruit, glow.
11. Small accents: sparkles, dust, pollen, snow, motion marks.

This order prevents a background from covering the subject and keeps the
drawing readable.  Use groups for logical parts and keep gradient IDs unique.

============================================================
7. SVG TECHNIQUE
============================================================

Every drawing must be valid, self-contained SVG:

- Start with `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">`
  (or the larger requested viewBox).
- Put gradients and reusable definitions inside `<defs>`.
- Use `<linearGradient>` and `<radialGradient>` with unique IDs and `<stop>`
  elements.
- Use `<path>`, `<circle>`, `<ellipse>`, `<rect>`, `<polygon>`, `<polyline>`
  and `<line>`.
- Close every tag.  End with `</svg>`.
- Use numeric coordinates inside the viewBox.  Do not use percentages for
  positions.
- Quote every attribute value.  Do not leave an attribute unfinished.
- Use `fill="none"` for line art such as whiskers, stems and outlines.
- Use `stroke-linecap="round"` and `stroke-linejoin="round"` for friendly,
  soft line work.
- Use `transform` for repeated parts or small rotations, not for clipping the
  subject.
- Do not use `<text>`, `<image>`, `<foreignObject>`, `<script>`, external
  links, CSS files or web fonts.  The drawing must work offline.
- Do not include a signature, watermark, UI chrome or a border around the
  whole canvas unless the user asks for one.
- Do not use a built-in artwork or paste a reference.  Compose a new drawing.

If the SVG is long, keep it organised with indentation and groups; do not stop
halfway.  A complete drawing with a closing tag is always better than a
truncated one with more ideas.

============================================================
8. FINISHING PASS
============================================================

Before returning the drawing, inspect it like an art director:

- Is the subject exactly what the user asked for?
- Is the whole subject inside the canvas, with margins?
- Does it have a background, a ground shadow and a light source?
- Can I see the face/eyes/expression clearly?
- Are all the anatomy parts present?  Check ears, paws, tail, limbs, petals,
  windows, wheels, etc.
- Are there at least 18 separate shape elements?
- Are there at least 2 gradients and at least 6 colours?
- Is there at least one opacity/shadow shape?
- Is there a highlight on the eyes or the main object?
- Is any area a flat, empty fill?  Add texture or shading.
- Does it look like an illustration rather than an icon?
- Is the SVG valid, self-contained and closed?

If any answer is no, fix it before returning.  Do not explain the checklist to
the user; simply return the improved drawing.

============================================================
9. COMMON FAILURES TO AVOID
============================================================

- A single circle with two dots and a line is not a cat.
- A rectangle with a triangle on top is not a house.
- A yellow circle with six straight lines is not a finished sun.
- Five floating petals with no stem is not a flower.
- A face with no body, or a body with no legs, is unfinished.
- A subject with no ground shadow looks like it is floating.
- A background that is one flat colour looks like a placeholder.
- A drawing that copies Milky's official face when the user asked for a cat is
  wrong.
- Clothing on Milky when the user only asked for a drawing is wrong.
- Text, signatures and watermarks inside the SVG are forbidden.
- Unescaped quotes, unclosed tags or a cut-off SVG make the drawing unusable.

============================================================
10. OUTPUT CONTRACT
============================================================

For a drawing request, produce exactly one complete SVG illustration.  Follow
the output channel requested by the current system message: if it asks for a
tool call or JSON field, put the SVG there; if it asks for plain text, put the
SVG between `<svg>` and `</svg>`.  In plain-text mode, write one short sentence
in the user's language, then the SVG, and no explanation after the closing tag.

The drawing itself is the important part.  Make it complete, detailed, warm and
recognisable.  Draw the subject the user asked for, not a template.
"""

# A compact version for retries and fallbacks.  The full skill above is used
# for the first attempt; this keeps the second request small enough for
# free-tier token limits.
DRAWING_COMPACT_GUIDE = r"""
DRAWING CHECKLIST — return one complete SVG illustration.
- viewBox="0 0 200 200" for a normal subject, larger only for a wide scene.
- Draw the requested subject, not a template, icon, emoji or Milky.
- Build a background, a ground shadow, the subject silhouette, shading,
  details and highlights, in that order.
- Use at least 14 shape elements, 2 gradients, 6 colours and one opacity/
  shadow shape. Add light on one side and a darker side.
- Include all anatomy: cat ears/eyes/pupils/nose/mouth/whiskers/body/paws/
  tail; person head/hair/neck/body/arms/hands/legs/face; object all parts.
- Keep the whole subject inside the canvas with margins.
- No <text>, <image>, <script>, signatures, watermarks or external files.
- Valid self-contained XML with a closing </svg>; no markdown fences.
- If it looks like a flat icon, add background, shadow and details first.
"""

