/**
 * Muscle Tutor localization dictionary.
 *
 * All strings are pre-authored — no runtime translation / API call needed.
 * Add keys here and consume via getMuscleLocale(language).
 */

import type { Language } from '@/types'

// ─── UI string keys ───────────────────────────────────────────────────────────

export interface MuscleUIStrings {
  muscleTutor: string
  specializedTutor: string
  description: string
  exampleQuestionsFor: string   // prefix — append muscle name
  studyMode: string
  responseLanguage: string
  askAQuestion: string
  yourQuestion: string
  answer: string
  documentGroundedAnswer: string
  specializedAnatomyAnswer: string
  sources: string
  preparingAnswer: string
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
  consultingBase: string
  searchingDocs: string
}

// ─── Per-muscle localized data ────────────────────────────────────────────────

export interface MuscleLocaleEntry {
  location: string
  topics: string
  prompts: [string, string, string]
}

export interface MuscleLocaleData {
  ui: MuscleUIStrings
  muscles: {
    'pectoralis-major': MuscleLocaleEntry
    deltoid: MuscleLocaleEntry
    'biceps-brachii': MuscleLocaleEntry
    'triceps-brachii': MuscleLocaleEntry
    'quadriceps-femoris': MuscleLocaleEntry
  }
}

// ─── English ──────────────────────────────────────────────────────────────────

const en: MuscleLocaleData = {
  ui: {
    muscleTutor: 'Muscle Tutor',
    specializedTutor: 'Specialized Anatomy Tutor',
    description:
      'Ask questions about anatomy, actions, nerve supply, attachments, and related concepts for the supported muscle groups.',
    exampleQuestionsFor: 'Example questions for',
    studyMode: 'Study Mode',
    responseLanguage: 'Response Language',
    askAQuestion: 'Ask a Question',
    yourQuestion: 'Your Question',
    answer: 'Answer',
    documentGroundedAnswer: 'Document-grounded answer',
    specializedAnatomyAnswer: 'Specialized anatomy answer',
    sources: 'Sources',
    preparingAnswer: 'Consulting the anatomy knowledge base…',
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
    consultingBase: 'Consulting the anatomy knowledge base… (first request may take 3–5 min to warm up)',
    searchingDocs: 'Searching your documents and preparing an answer… (first request may take a few minutes)',
  },
  muscles: {
    'pectoralis-major': {
      location: 'Chest muscle',
      topics: 'Actions · nerve supply · attachments',
      prompts: [
        'What are the main actions of pectoralis major?',
        'Which nerves supply pectoralis major?',
        'Where does pectoralis major insert?',
      ],
    },
    deltoid: {
      location: 'Shoulder muscle',
      topics: 'Actions · nerve supply · attachments',
      prompts: [
        'What is the main function of the deltoid?',
        'Which nerve supplies the deltoid?',
        'Name the three parts of the deltoid.',
      ],
    },
    'biceps-brachii': {
      location: 'Anterior arm',
      topics: 'Actions · heads · nerve supply',
      prompts: [
        'What are the main actions of biceps brachii?',
        'Which nerve supplies biceps brachii?',
        'Name the two heads of biceps brachii.',
      ],
    },
    'triceps-brachii': {
      location: 'Posterior arm',
      topics: 'Actions · heads · nerve supply',
      prompts: [
        'What is the main action of triceps brachii?',
        'Which nerve supplies triceps brachii?',
        'Name the three heads of triceps brachii.',
      ],
    },
    'quadriceps-femoris': {
      location: 'Anterior thigh',
      topics: 'Actions · components · nerve supply',
      prompts: [
        'What is the main function of quadriceps femoris?',
        'Name the four quadriceps muscles.',
        'Which quadriceps muscle also assists hip flexion?',
      ],
    },
  },
}

// ─── Tamil ────────────────────────────────────────────────────────────────────

const ta: MuscleLocaleData = {
  ui: {
    muscleTutor: 'தசை பயிற்றுநர்',
    specializedTutor: 'சிறப்பு உடற்கூறியல் பயிற்றுநர்',
    description:
      'Pectoralis major, deltoid போன்ற தசைகளின் செயல்கள், நரம்பு வழங்கல், இணைப்புகள் மற்றும் தொடர்புடைய கேள்விகளை கேளுங்கள்.',
    exampleQuestionsFor: 'உதாரணக் கேள்விகள்:',
    studyMode: 'படிப்பு முறை',
    responseLanguage: 'பதில் மொழி',
    askAQuestion: 'கேள்வி கேளுங்கள்',
    yourQuestion: 'உங்கள் கேள்வி',
    answer: 'பதில்',
    documentGroundedAnswer: 'ஆவண அடிப்படையிலான பதில்',
    specializedAnatomyAnswer: 'சிறப்பு உடற்கூறியல் பதில்',
    sources: 'ஆதாரங்கள்',
    preparingAnswer: 'உடற்கூறியல் தகவல் தளத்தை அணுகுகிறோம்…',
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
    consultingBase: 'உடற்கூறியல் தகவல் தளத்தை அணுகுகிறோம்… (முதல் கேள்விக்கு 3-5 நிமிடம் ஆகலாம்)',
    searchingDocs: 'உங்கள் ஆவணங்களில் தேடுகிறோம்… (முதல் கேள்விக்கு சிறிது நேரம் ஆகலாம்)',
  },
  muscles: {
    'pectoralis-major': {
      location: 'மார்பு தசை',
      topics: 'செயல்கள் · நரம்பு வழங்கல் · இணைப்புகள்',
      prompts: [
        'Pectoralis major-ன் முக்கிய செயல்கள் என்ன?',
        'Pectoralis major-க்கு nerve supply செய்யும் nerves எவை?',
        'Pectoralis major எங்கே insert ஆகிறது?',
      ],
    },
    deltoid: {
      location: 'தோள்பட்டை தசை',
      topics: 'செயல்கள் · நரம்பு வழங்கல் · இணைப்புகள்',
      prompts: [
        'Deltoid muscle-ன் முக்கிய வேலை என்ன?',
        'Deltoid muscle-க்கு nerve supply செய்யும் nerve எது?',
        'Deltoid muscle-ன் மூன்று பகுதிகள் என்ன?',
      ],
    },
    'biceps-brachii': {
      location: 'முன் கை தசை',
      topics: 'செயல்கள் · தலைகள் · நரம்பு வழங்கல்',
      prompts: [
        'Biceps brachii-ன் முக்கிய செயல்கள் என்ன?',
        'Biceps brachii-க்கு nerve supply செய்யும் nerve எது?',
        'Biceps brachii-ன் இரண்டு heads என்ன?',
      ],
    },
    'triceps-brachii': {
      location: 'பின் கை தசை',
      topics: 'செயல்கள் · தலைகள் · நரம்பு வழங்கல்',
      prompts: [
        'Triceps brachii-ன் முக்கிய செயல் என்ன?',
        'Triceps brachii-க்கு nerve supply செய்யும் nerve எது?',
        'Triceps brachii-ன் மூன்று heads என்ன?',
      ],
    },
    'quadriceps-femoris': {
      location: 'முன் தொடை தசை',
      topics: 'செயல்கள் · கூறுகள் · நரம்பு வழங்கல்',
      prompts: [
        'Quadriceps femoris-ன் முக்கிய வேலை என்ன?',
        'Quadriceps group-ல் உள்ள நான்கு muscles என்ன?',
        'எந்த quadriceps muscle hip flexion-க்கும் உதவுகிறது?',
      ],
    },
  },
}

// ─── Sinhala ──────────────────────────────────────────────────────────────────

const si: MuscleLocaleData = {
  ui: {
    muscleTutor: 'මාංශපේශි උපදේශක',
    specializedTutor: 'විශේෂිත ව්‍යුහ විද්‍යා උපදේශක',
    description:
      'Pectoralis major, deltoid වැනි මාංශපේශිවල ක්‍රියා, ස්නායු සැපයුම, සම්බන්ධතා සහ ආශ්‍රිත ප්‍රශ්න අසන්න.',
    exampleQuestionsFor: 'උදාහරණ ප්‍රශ්න:',
    studyMode: 'අධ්‍යයන ක්‍රමය',
    responseLanguage: 'පිළිතුරු භාෂාව',
    askAQuestion: 'ප්‍රශ්නයක් අසන්න',
    yourQuestion: 'ඔබේ ප්‍රශ්නය',
    answer: 'පිළිතුර',
    documentGroundedAnswer: 'ලේඛන-පදනම් කළ පිළිතුර',
    specializedAnatomyAnswer: 'විශේෂිත ව්‍යුහ විද්‍යා පිළිතුර',
    sources: 'මූලාශ්‍ර',
    preparingAnswer: 'ව්‍යුහ විද්‍යා දත්ත පදනම සමඟ සාකච්ඡා කරමින්…',
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
    consultingBase: 'ව්‍යුහ විද්‍යා දත්ත පදනම සමඟ සාකච්ඡා කරමින්… (පළමු ඉල්ලීමට මිනිත්තු 3-5 ගත විය හැකිය)',
    searchingDocs: 'ඔබේ ලේඛනවල සෙවීම… (පළමු ඉල්ලීමට ටික වේලාවක් ගතවිය හැකිය)',
  },
  muscles: {
    'pectoralis-major': {
      location: 'පපුවේ මාංශපේශිය',
      topics: 'ක්‍රියා · ස්නායු සැපයුම · සම්බන්ධතා',
      prompts: [
        'Pectoralis major හි ප්‍රධාන ක්‍රියා මොනවාද?',
        'Pectoralis major-ට nerve supply කරන nerves මොනවාද?',
        'Pectoralis major insert වෙන්නේ කොහෙද?',
      ],
    },
    deltoid: {
      location: 'උරහිස් මාංශපේශිය',
      topics: 'ක්‍රියා · ස්නායු සැපයුම · සම්බන්ධතා',
      prompts: [
        'Deltoid muscle එකේ ප්‍රධාන කාර්යය මොකක්ද?',
        'Deltoid muscle-ට nerve supply කරන nerve එක මොකක්ද?',
        'Deltoid muscle එකේ කොටස් තුන මොනවාද?',
      ],
    },
    'biceps-brachii': {
      location: 'ඉදිරි අත් මාංශපේශිය',
      topics: 'ක්‍රියා · heads · ස්නායු සැපයුම',
      prompts: [
        'Biceps brachii හි ප්‍රධාන ක්‍රියා මොනවාද?',
        'Biceps brachii-ට nerve supply කරන nerve එක මොකක්ද?',
        'Biceps brachii හි heads දෙක මොනවාද?',
      ],
    },
    'triceps-brachii': {
      location: 'පසු අත් මාංශපේශිය',
      topics: 'ක්‍රියා · heads · ස්නායු සැපයුම',
      prompts: [
        'Triceps brachii හි ප්‍රධාන ක්‍රියාව මොකක්ද?',
        'Triceps brachii-ට nerve supply කරන nerve එක මොකක්ද?',
        'Triceps brachii හි heads තුන මොනවාද?',
      ],
    },
    'quadriceps-femoris': {
      location: 'ඉදිරි කලවා මාංශපේශිය',
      topics: 'ක්‍රියා · කොටස් · ස්නායු සැපයුම',
      prompts: [
        'Quadriceps femoris හි ප්‍රධාන කාර්යය මොකක්ද?',
        'Quadriceps group එකේ muscles හතර මොනවාද?',
        'Hip flexion සඳහාත් උදව් කරන quadriceps muscle එක මොකක්ද?',
      ],
    },
  },
}

// ─── Public accessor ──────────────────────────────────────────────────────────

const LOCALE_MAP: Record<Language, MuscleLocaleData> = {
  english: en,
  tamil: ta,
  sinhala: si,
}

export function getMuscleLocale(language: Language): MuscleLocaleData {
  return LOCALE_MAP[language] ?? en
}

export type MuscleId = keyof MuscleLocaleData['muscles']
