import type { Language } from '@/types'

export interface StudyLocaleData {
  ui: {
    responseLanguage: string
    askAQuestion: string
    yourQuestion: string
    answer: string
    documentGroundedAnswer: string
    sources: string
    preparingAudio: string
    playAnswer: string
    retryAudio: string
    askAnother: string
    fixTranscript: string
    fixing: string
    asking: string
    retryAnswer: string
    askArrow: string
    audioUnavailable: string
    noSpeechDetected: string
    searchingDocs: string
  }
}

const en: StudyLocaleData = {
  ui: {
    responseLanguage: 'Response Language',
    askAQuestion: 'Ask a Question',
    yourQuestion: 'Your Question',
    answer: 'Answer',
    documentGroundedAnswer: 'Document-grounded answer',
    sources: 'Sources',
    preparingAudio: 'Preparing answer audio…',
    playAnswer: 'Play Answer',
    retryAudio: 'Retry Audio',
    askAnother: 'Ask another question',
    fixTranscript: 'Fix Transcript',
    fixing: 'Fixing…',
    asking: 'Asking…',
    retryAnswer: 'Retry Answer',
    askArrow: 'Ask →',
    audioUnavailable: 'Answer audio is unavailable right now. The text answer is complete.',
    noSpeechDetected: 'No speech was detected. Please try again and speak clearly.',
    searchingDocs: 'Searching your documents and preparing an answer… (first request may take a few minutes)',
  },
}

const ta: StudyLocaleData = {
  ui: {
    responseLanguage: 'பதில் மொழி',
    askAQuestion: 'கேள்வி கேளுங்கள்',
    yourQuestion: 'உங்கள் கேள்வி',
    answer: 'பதில்',
    documentGroundedAnswer: 'ஆவண அடிப்படையிலான பதில்',
    sources: 'ஆதாரங்கள்',
    preparingAudio: 'பதில் ஆடியோ தயாரிக்கப்படுகிறது…',
    playAnswer: 'பதிலை இயக்கு',
    retryAudio: 'மீண்டும் முயற்சி செய்',
    askAnother: 'மற்றொரு கேள்வி கேளுங்கள்',
    fixTranscript: 'உரையை சரிசெய்',
    fixing: 'சரிசெய்கிறோம்…',
    asking: 'கேட்கிறோம்…',
    retryAnswer: 'மீண்டும் முயற்சி செய்',
    askArrow: 'கேளுங்கள் →',
    audioUnavailable: 'இப்போது பதில் ஆடியோ கிடைக்கவில்லை. உரை பதில் காட்டப்படுகிறது.',
    noSpeechDetected: 'பேச்சு கண்டறியப்படவில்லை. தயவுசெய்து தெளிவாக பேசி மீண்டும் முயற்சி செய்யவும்.',
    searchingDocs: 'உங்கள் ஆவணங்களில் தேடுகிறோம்… (முதல் கேள்விக்கு சிறிது நேரம் ஆகலாம்)',
  },
}

const si: StudyLocaleData = {
  ui: {
    responseLanguage: 'පිළිතුරු භාෂාව',
    askAQuestion: 'ප්‍රශ්නයක් අසන්න',
    yourQuestion: 'ඔබේ ප්‍රශ්නය',
    answer: 'පිළිතුර',
    documentGroundedAnswer: 'ලේඛන-පදනම් කළ පිළිතුර',
    sources: 'මූලාශ්‍ර',
    preparingAudio: 'පිළිතුරු ශ්‍රව්‍ය සූදානම් කරමින්…',
    playAnswer: 'පිළිතුර වාදනය කරන්න',
    retryAudio: 'නැවත උත්සාහ කරන්න',
    askAnother: 'තවත් ප්‍රශ්නයක් අසන්න',
    fixTranscript: 'පිටපත සකසන්න',
    fixing: 'සකසමින්…',
    asking: 'අසමින්…',
    retryAnswer: 'නැවත උත්සාහ කරන්න',
    askArrow: 'අසන්න →',
    audioUnavailable: 'දැනට පිළිතුරු ශ්‍රව්‍ය නොමැත. පෙළ පිළිතුර දිස් වේ.',
    noSpeechDetected: 'කථාව හඳුනා නොගත්තේය. කරුණාකර පැහැදිලිව කතා කර නැවත උත්සාහ කරන්න.',
    searchingDocs: 'ඔබේ ලේඛනවල සෙවීම… (පළමු ඉල්ලීමට ටික වේලාවක් ගතවිය හැකිය)',
  },
}

const LOCALE_MAP: Record<Language, StudyLocaleData> = { english: en, tamil: ta, sinhala: si }

export function getStudyLocale(language: Language): StudyLocaleData {
  return LOCALE_MAP[language]
}
