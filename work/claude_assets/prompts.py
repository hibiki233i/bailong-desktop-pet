"""Prompt blocks shared by every generation.

The bridge accepts text only, so repeating these blocks verbatim is the main
tool for keeping the character and the art style stable between images.
"""

STYLE = """ART STYLE (most important, follow exactly):
A modern soft kawaii chibi sticker illustration in a gentle pastel style.
Proportions: about 2.5 heads tall, a huge round head, a small narrow body, very short legs, tiny soft hands.
Face: the face sits low on the head. Large, round, widely spaced eyes with a heavy dark tapered upper lash line and no lower lashes. The iris fades from a deep tone at the top to a light amber crescent at the bottom, with one big round white catchlight near the top of each eye. Almost no nose. A tiny minimal mouth. Soft oval peach blush under each eye. Calm, gentle, slightly shy mood.
Lineart: one bold, smooth, deep chestnut-brown contour around the entire outer silhouette, clearly darker than the hair and noticeably heavier than every interior line, and much thinner tone-on-tone inner lines tinted with the local colour (soft orange lines inside the hair, warm grey lines on cloth). Never use black inner lines.
Colouring: pale, airy, low-contrast pastel palette, simple soft two-tone shading with slightly blurred soft highlights, smooth and clean, light values, a fluffy and delicate feeling, finely drawn frills.
"""

CHARACTER = """CHARACTER (keep identical every time):
A gentle girl with extremely long, soft, voluminous pastel apricot-orange hair flowing down to her ankles and fanning out wide on both sides of her body, side-swept bangs, gentle waves near the ends. Warm amber eyes.
On the right side of her head (viewer's right): a large pastel orange sunflower hair ornament with a small black ribbon. Tiny gold tassel earrings.
Outfit: cream-white blouse with a ruffled high collar and puffy long sleeves, a short cream capelet with a small soft orange sun embroidery on each shoulder, a small black ribbon bow at the neck with a round amber sun brooch, a black corset sash at the waist with a thin gold chain and a small gold tassel, a cream pleated skirt with a frilly hem, an open overskirt in soft black and muted burnt orange with small gold sun patterns, white lace-up ankle boots with dark laces.
Mascot sitting on top of her head: a small chunky 8-bit pixel-art creature with a wide, flat-topped rectangular block body in terracotta orange #D97757 (a straight flat top edge, never domed or rounded), built from crisp square pixels, two small vertical black rectangular eyes, one short square nub on each side as tiny arms, four tiny square stubby legs. Flat colour, no mouth, no shading, about half as wide as her head. It is the only hard-edged pixel element in the picture.
"""

RULES = """BACKGROUND AND RULES:
The entire background is one completely flat, uniform pure chroma-key green #00FF00, with no gradient, no floor, no ground shadow and no other objects. The character and the mascot contain no green at all. Keep the whole figure, from the top of the mascot to the boots, fully visible with a generous margin on every side.
Not allowed: text, letters, logos, watermarks, revealing outfits, glowing eyes, glow, bloom, lens flare, light beams, sparkle particles, rim lighting, thick oil-paint texture, photorealism, 3D render, realistic proportions, cast shadows.
"""

SCENES = {
    'master': """IMAGE: exactly one character, square 1:1 image, centered.
POSE: standing and facing the viewer, arms relaxed at her sides with tiny hands lightly open, feet close together, her hair spreading wide on both sides. Tiny closed-mouth smile, eyes open.
""",
    'poses': """IMAGE: one wide landscape character sheet, 3 columns by 2 rows, showing the SAME character six times. Every figure has exactly the same head size, body proportions, hair colour, outfit, line weight and colouring. Each figure is a complete full body and is separated from its neighbours by wide empty green gaps. No grid lines, no borders, no labels.
Top row, left to right:
1. sitting on the ground with legs tucked, typing on a small cream laptop on her lap, focused gentle face.
2. jumping with joy, both arms raised, eyes happily closed as two upward arcs, open smiling mouth.
3. standing, one finger on her chin, looking up in thought, small closed mouth.
Bottom row, left to right:
4. standing and leaning slightly forward, one hand raised as if asking for permission, worried eyebrows, tiny open mouth.
5. sitting and dozing off, eyes closed as two downward arcs, head tilted to one side, hands in her lap.
6. standing with a small proud smile, hands clasped in front of her chest, eyes open.
""",
    'walk': """IMAGE: one wide landscape animation strip, 4 columns by 1 row, showing the SAME character four times as consecutive frames of a cute walk cycle seen from the side, all facing right. Every frame has exactly the same head size, height, outfit and colouring, only the legs, arms and hair swing change. Frames are evenly spaced with wide empty green gaps. No grid lines, no labels.
Frame 1: right foot forward. Frame 2: feet passing together, body slightly higher. Frame 3: left foot forward. Frame 4: feet passing together, body slightly higher.
""",
    'props': """IMAGE: one wide landscape character sheet, 3 columns by 2 rows, showing the SAME character six times. Every figure has exactly the same head size, body proportions, hair colour, outfit, line weight and colouring. Each figure is a complete full body with the mascot on top of her head, and is separated from its neighbours by wide empty green gaps. No grid lines, no borders, no labels.
Top row, left to right:
1. sitting on the ground with legs tucked, holding an open cream picture book in both hands, looking down at it with a soft smile.
2. sitting on the ground, hugging a big soft cream pillow to her chest with her cheek resting on it, eyes closed as two downward arcs, tiny smile.
3. sitting on the ground, holding a small cream handheld game console in both hands, eyes open and focused on it, small closed mouth.
Bottom row, left to right:
4. standing, one hand reaching up to gently pat the mascot on her head, the other hand at her side, eyes happily closed as two upward arcs, small smile.
5. standing, nibbling a round cookie held in both hands near her mouth, one cheek puffed, eyes open.
6. standing, one arm raised high and waving hello with an open hand, the other hand at her side, eyes open, wide happy open mouth.
""",
    'moods': """IMAGE: one wide landscape character sheet, 3 columns by 2 rows, showing the SAME character six times. Every figure has exactly the same head size, body proportions, hair colour, outfit, line weight and colouring. Each figure is a complete full body with the mascot on top of her head, and is separated from its neighbours by wide empty green gaps. No grid lines, no borders, no labels.
Top row, left to right:
1. standing, one index finger pointing straight up beside her head, a small solid pastel yellow lightbulb floating just above that finger, eyes wide open, small open smile.
2. standing proudly with both hands on her hips and chest out, eyes closed as two upward arcs, a smug little smile.
3. standing, both arms stretched forward and open for a hug, eyes happily closed as two upward arcs, blushing, small open smile.
Bottom row, left to right:
4. standing with arms crossed over her chest, head turned away to one side, eyes open but glancing away, cheeks blushing, a small pout.
5. standing with both small fists clenched down at her sides, cheeks puffed out, eyebrows angled in cute anger, eyes open, tiny wavy mouth.
6. standing, one hand covering a big yawn, eyes half closed and sleepy, the other hand at her side.
""",
    'gifts': """IMAGE: one wide landscape character sheet, 3 columns by 2 rows, showing the SAME character six times. Every figure has exactly the same head size, body proportions, hair colour, outfit, line weight and colouring. Each figure is a complete full body with the mascot on top of her head, and is separated from its neighbours by wide empty green gaps. No grid lines, no borders, no labels.
Top row, left to right:
1. standing, both hands joined in front of her chest forming a heart shape with her fingers, eyes open, gentle smile.
2. standing, holding out one large sunflower on a short stem toward the viewer with both hands, eyes open, gentle smile.
3. standing with both arms spread wide and low, face tilted slightly up, eyes closed as two downward arcs, a peaceful smile, as if enjoying warm sunshine.
Bottom row, left to right:
4. standing, holding a small open wooden box filled with small golden sun charms in both hands, eyes open, delighted open smile.
5. standing, holding a small solid orange and cream paper pinwheel on a stick near her mouth with one hand, lips pursed in a small round shape as she blows on it, eyes open.
6. standing, one hand touching the sunflower ornament in her hair, the other hand at her chest, blushing and glancing shyly to one side, tiny smile.
""",
    'tasks': """IMAGE: one wide landscape character sheet, 3 columns by 2 rows, showing the SAME character six times. Every figure has exactly the same head size, body proportions, hair colour, outfit, line weight and colouring. Each figure is a complete full body with the mascot on top of her head, and is separated from its neighbours by wide empty green gaps. No grid lines, no borders, no labels.
Top row, left to right:
1. standing and saluting cheerfully with one hand at her forehead, holding a small blank cream note in the other hand, eyes open, small open smile.
2. standing, carrying a small stack of blank cream folders in both arms against her chest, eyes open, focused small mouth.
3. standing, holding an open blank cream document folder in both hands, looking down and reading it, eyes open, small closed mouth.
Bottom row, left to right:
4. standing and leaning slightly forward, holding up a large magnifying glass with a gold rim and a solid pale cream lens in one hand, looking through its side, eyes open, curious small mouth.
5. standing, holding a small blank cream clipboard in one hand and a small pencil in the other, looking at the clipboard, eyes open, small closed mouth.
6. dangling in mid-air as if lifted from behind by her collar, arms and legs hanging limp, feet not touching anything, eyes wide open, small round surprised mouth.
""",
    'run': """IMAGE: one wide landscape animation strip, 4 columns by 1 row, showing the SAME character four times as consecutive frames of a cute energetic run cycle seen from the side, all facing right. Every frame has exactly the same head size, height, outfit and colouring, only the legs, arms and hair swing change, and her long hair streams behind her. The mascot stays on top of her head. Frames are evenly spaced with wide empty green gaps. No grid lines, no labels.
Frame 1: right leg stretched forward, left leg back, both feet off the ground. Frame 2: legs passing under the body, knee raised. Frame 3: left leg stretched forward, right leg back, both feet off the ground. Frame 4: legs passing under the body, knee raised.
""",
    'float': """IMAGE: one wide landscape animation strip, 2 columns by 1 row, showing the SAME character twice, both seen from the side and facing right. Each figure is floating gently in the air, holding the stem of one huge sunflower above her head with both hands like a parasol, her feet dangling, her long hair trailing behind her, eyes open, small happy smile. The mascot sits on top of her head under the sunflower. The two figures differ only in the hair and skirt swing. Wide empty green gap between them. No grid lines, no labels.
""",
    'faces': """IMAGE: one wide landscape expression sheet, 4 columns by 2 rows, showing the SAME character's head and shoulders eight times, all facing the viewer in exactly the same position and size. Only the eyes and mouth change between cells. Wide empty green gaps, no grid lines, no labels.
Top row: 1. eyes open, tiny smile. 2. eyes half closed, tiny smile. 3. eyes fully closed as gentle downward arcs, tiny smile. 4. eyes happily closed as upward arcs, small open smile.
Bottom row: 5. eyes open, small round open mouth. 6. eyes open, wide happy open mouth. 7. worried eyes, small wavy mouth. 8. sleepy half-closed eyes, tiny yawn.
""",
}


def build(name):
    return '\n'.join((SCENES[name], STYLE, CHARACTER, RULES))
