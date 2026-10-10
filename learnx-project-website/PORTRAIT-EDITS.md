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
