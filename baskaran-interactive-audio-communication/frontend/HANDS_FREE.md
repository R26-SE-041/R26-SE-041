# Hands-free Study tools

Open Study tools, select a document or open a saved revision, then choose **Enable hands-free** and allow microphone access. Keep the page visible. The manual recorder is disabled while this listener is enabled.

Speak English commands with the prefix **VoiceLearn**. For example, while audio is playing:

- “VoiceLearn, pause audio” pauses after recognition without submitting a recording or clicking Run action.
- “VoiceLearn, resume audio”, “VoiceLearn, stop audio”.
- “VoiceLearn, next section”, “VoiceLearn, previous section”, “VoiceLearn, replay this section”, “VoiceLearn, play section two”. Section navigation requires sectioned audio.
- “VoiceLearn, skip forward ten seconds”, “VoiceLearn, go back ten seconds”.
- “VoiceLearn, set playback speed to zero point seven five” or “…one point two five”.

All displayed creation and summary commands also work with this prefix. They prepare a pending command; say **“VoiceLearn confirm”** within 20 seconds to run it, or **“VoiceLearn cancel”**. A language named in a command overrides the output-language selector. Section-only creation uses the selected source section. New work uses the existing backend job and saving flow.

**“VoiceLearn delete this saved revision”** targets the currently opened saved result. It requires **“VoiceLearn confirm delete”** within 20 seconds. Changing the document, result, source section, output language, revision format, or processing mode cancels pending confirmation. Confirmations are consumed once.

For headphones, an optional setting allows short playback phrases such as “pause”, without the prefix. Creation, deletion, and confirmation still require the prefix. Say **“VoiceLearn stop listening”** or use Turn off hands-free to stop.

Playback uses local HTML audio controls, with no action-generation or transcription API request. Listening uses the browser's SpeechRecognition service, which may process microphone audio online. It is a continuous recognition session with a phrase filter, not an offline wake-word engine. Browser support, recognition latency, and speaker echo vary; headphones are preferable. No background or lock-screen listening is promised. Leaving Study tools, hiding the page, or a permission/network error disables listening. During an existing job, listening pauses and resumes when the job completes if the page is still active.

## Verification

`npm test` covers phrase classification and playback semantics. `e2e/hands-free.spec.ts` injects a recognition double and uses real browser audio playback with a mocked backend. It covers all displayed commands, confirmation, context invalidation, duplicate/stale finals, cancellation/expiry, busy suspension, microphone/network errors, silence restart, tab/page cleanup, unsupported browsers, and mobile layout. These tests do not establish physical microphone recognition accuracy.

On a physical phone, test foreground Chrome with headphones first: start a saved revision, enable hands-free, speak pause/resume/skip/section/speed phrases, then repeat on the speaker at normal volume. Verify unrelated narration does not act, denied permission shows an error, hiding the page stops listening, and re-enabling restores it. Check creation with a small test document and delete only the resulting test revision. Speech recognition can add delay, so measure observed response rather than promising instantaneous execution.
