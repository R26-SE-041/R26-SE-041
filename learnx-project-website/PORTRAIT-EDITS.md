# Portrait edits

Tool: built-in image_gen (identity-preserve edit mode). No CLI/API fallback.

Public assets are saved in public/assets/images as kojithan.jpg, baskaran.jpg, nishara.jpg, sarmitha.jpg malithi-nawarathne.jpg and nuwan-kodagoda.jpg. Original portraits and full generated PNGs are preserved locally in source/portraits, excluded from publishing. Website JPEGs use quality 90.

Member outputs: 1254 × 1254. Co-supervisor output: 1122 × 1402. AI restoration improves apparent sharpness; fine details are reconstructed and are not recovered original-camera detail.

## Member prompt set

The following prompt was applied separately with the corresponding name and one original portrait per call:

Use case: identity-preserve. Edit target: the supplied low-resolution academic team portrait of [kojithan/baskaran/nishara/sarmitha]. Upscale and conservatively restore this exact photograph to a sharper high-resolution portrait. Preserve the person's exact identity, facial proportions, expression, eyes, nose, mouth, hairstyle, skin tone, clothing, pose and composition. Preserve the original monochrome appearance if the portrait is monochrome. Reduce compression artifacts and improve photographic clarity gently. Keep the pale blue background, all clothing details and framing unchanged. Do not create a different person, beautify, change age, reshape features, add accessories or invent fine detail. Natural photographic texture, no stylization, no text, no watermark. Output a square portrait.

## Co-supervisor prompt

Use case: identity-preserve. Edit target: attached photograph of Ms. Malithi Nawarathne. Create a clean, realistic head-and-shoulders portrait crop for an academic team website from this exact photo. Preserve her exact identity, facial proportions, age, natural skin tone, smile, hairstyle and yellow sari. Crop to head and upper shoulders, with comfortable space above her hair. Gently reduce compression/noise and improve clarity without altering her appearance or inventing facial features. Keep natural photographic texture; no beauty retouching or stylization. Remove distracting event text from the background by replacing only the background with a plain soft warm ivory studio backdrop. Portrait aspect ratio 4:5. Do not add text, logos or watermark.

## Supervisor prompt

Use case: identity-preserve. Edit target: the supplied low-resolution academic portrait of Prof. Nuwan Kodagoda. Upscale and conservatively restore this exact photograph to a sharper high-resolution square portrait. Preserve his exact identity, age, facial proportions, expression, eyes, nose, mouth, hairstyle, skin tone, glasses, suit, shirt, tie, pose and composition. Reduce compression artifacts and gently improve photographic clarity. Keep the pale blue background, clothing and framing unchanged. Do not beautify, reshape facial features, make him younger, change his glasses or invent accessories. Natural photographic texture, no stylization, no text, no watermark.

Supervisor output: 1254 × 1254; saved as public/assets/images/nuwan-kodagoda.jpg using the built-in image_gen tool.

## Kojithan T-shirt logo replacement — 15 October 2026

Tool: built-in image_gen, localized clothing edit. Final asset: `public/assets/images/kojithan-nike.png` (1254 × 1254). The original `kojithan.jpg` is retained.

Only the generated lower-shirt patch (x=475–1074, y=1075–1253) was composited onto the original decoded image, with feathered top and side boundaries. The result is saved losslessly as PNG. Pixel comparison confirmed zero changed pixels outside this patch, preserving the original face, hair, neck, background and upper shirt exactly.

Final prompt:

> Use case: identity-preserve / precise-object-edit. Edit target: the supplied square academic portrait of Kojithan. Replace ONLY the large black lettering on the bottom-center of his white T-shirt with one simple authentic black Nike swoosh logo (symbol only, no wordmark and no other text). Remove all of the old lettering cleanly and continue the white cotton fabric and its natural shading. Put the swoosh in the same lower-chest region, fully visible within the existing crop, approximately centered at x=760,y=1175 in this 1254x1254 source and about 270 pixels wide. Keep the shirt's weave, folds, lighting and perspective natural. CRITICAL INVARIANTS: do not modify the face in any way, identity, facial features, expression, eyes, smile, teeth, skin texture, hair, ears, neck, pose, body, background, crop, dimensions, or tonal appearance. Everything outside the lower T-shirt lettering region must remain exactly as in the source image. No face enhancement, retouching, beautification, sharpening, recoloring, reframing or additional logos. Preserve the original square photo composition, grayscale subject and pale blue background. This is a localized clothing logo replacement only.
