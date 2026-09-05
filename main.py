import json
import os
import re
from io import BytesIO
from pathlib import Path
from typing import Literal

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from pypdf import PdfReader
from pypdf.errors import PdfReadError

load_dotenv()

APP_VERSION = "2.1.0"
BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"
MAX_UPLOAD_BYTES = 6 * 1024 * 1024
MAX_CONTEXT_CHARS = 12_000

DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() in {"1", "true", "yes", "on"}
AI_FALLBACK_TO_DEMO = os.getenv("AI_FALLBACK_TO_DEMO", "true").lower() in {"1", "true", "yes", "on"}
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4.1-mini")

app = FastAPI(title="Final Defence Coach", version=APP_VERSION)
Language = Literal["en", "ha", "yo", "ig", "sw", "zu"]
SUPPORTED_LANGUAGES: tuple[str, ...] = ("en", "ha", "yo", "ig", "sw", "zu")

LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "ha": "Hausa",
    "yo": "Yorùbá",
    "ig": "Igbo",
    "sw": "Kiswahili",
    "zu": "isiZulu",
}

LOCALES: dict[str, dict] = {
    "en": {
        "roles": [
            ("Research supervisor", "Problem & impact"),
            ("Methodology examiner", "Methodology"),
            ("Evidence reviewer", "Results & evidence"),
            ("External examiner", "Limitations"),
            ("Impact reviewer", "Practical application"),
        ],
        "questions": [
            "What problem does your research on '{topic}' solve, and who benefits most from the result?",
            "Why did you choose this methodology, and what alternative approach did you consider but reject?",
            "What is the most important result from your work, and what evidence best supports it?",
            "What is the biggest limitation of your research, and how should that limitation affect interpretation of the results?",
            "If you turned this research into a real-world solution, what would you do next and how would you measure success?",
        ],
        "labels": {"clarity": "clarity", "relevance": "relevance to the question", "evidence": "use of evidence", "structure": "answer structure"},
        "strength": "Your strongest area in this response is {label}.",
        "improvement": "Your biggest opportunity for the next answer is {label}.",
        "tips": {
            "clarity": "Lead with one sentence that directly answers the question before adding detail.",
            "relevance": "Echo the key part of the examiner's question and connect every point back to it.",
            "evidence": "Add one concrete result, number, example, or observation from your own research.",
            "structure": "Use a simple structure: claim → evidence → significance → limitation.",
        },
        "feedback": "Your response was assessed for clarity, relevance, evidence, and structure. This score does not judge whether your research is scientifically correct; it reflects how defensible the written answer sounds to a panel.",
        "framework": "A stronger answer structure you can fill with your real research:\n1. Main claim: [direct answer to the examiner's question].\n2. Evidence: [specific result, number, or observation from your study].\n3. Significance: [why that evidence matters].\n4. Limitation: [what the result cannot prove or where caution is needed].",
        "fallback": "The AI provider was unavailable, so local demo coaching was used to keep the practice session working.",
    },
    "ha": {
        "roles": [
            ("Mai kula da bincike", "Matsala da tasiri"),
            ("Mai nazarin hanya", "Hanyar bincike"),
            ("Mai duba hujja", "Sakamako da hujja"),
            ("Mai jarrabawa na waje", "Iyakoki"),
            ("Mai duba tasiri", "Amfani a aikace"),
        ],
        "questions": [
            "Wace matsala bincikenka kan '{topic}' yake warwarewa, kuma wa zai fi amfana da sakamakonsa?",
            "Me ya sa ka zaɓi wannan hanyar bincike, kuma wace hanya ce ka yi la'akari da ita amma ba ka yi amfani da ita ba?",
            "Mene ne mafi muhimmancin sakamako daga aikinka, kuma wace shaida ce ta fi goyon bayansa?",
            "Mene ne babban iyakar bincikenka, kuma ta yaya wannan iyakar ke shafar fassarar sakamakon?",
            "Idan za ka mayar da wannan bincike zuwa mafita ta zahiri, mene ne mataki na gaba kuma yaya za ka auna nasara?",
        ],
        "labels": {"clarity": "bayyananniyar amsa", "relevance": "dacewa da tambaya", "evidence": "amfani da hujja", "structure": "tsarin amsa"},
        "strength": "Mafi ƙarfin ɓangaren amsarka shi ne {label}.",
        "improvement": "Abin da ya fi dacewa ka inganta a amsa ta gaba shi ne {label}.",
        "tips": {
            "clarity": "Fara da jimla ɗaya da ke ba da amsa kai tsaye kafin ƙarin bayani.",
            "relevance": "Maimaita muhimmin ɓangaren tambayar sannan ka danganta kowace hujja da shi.",
            "evidence": "Ƙara sakamako, adadi, misali ko wata hujja takamaimai daga bincikenka.",
            "structure": "Yi amfani da tsari mai sauƙi: batu → hujja → muhimmanci → iyaka.",
        },
        "feedback": "An auna amsarka ta fuskar bayyanawa, dacewa da tambaya, hujja, da tsari. Makin ba ya nuna ko bincikenka daidai ne; yana nuna yadda amsar ta kasance mai sauƙin karewa a gaban kwamitin.",
        "framework": "Tsarin da za ka iya amfani da shi:\n1. Babban batu: [amsa kai tsaye ga tambayar].\n2. Hujja: [takamaiman sakamako, adadi ko misali daga bincikenka].\n3. Muhimmanci: [me wannan sakamakon yake nufi].\n4. Iyakar bincike: [abin da sakamakon ba zai iya tabbatarwa ba].",
        "fallback": "Ba a samu AI provider ba, don haka an yi amfani da local demo coaching domin kada atisayen ya tsaya.",
    },
    "yo": {
        "roles": [
            ("Olùtọ́jú ìwádìí", "Ìṣòro àti ipa"),
            ("Olùdánwò ọ̀nà ìwádìí", "Ọ̀nà ìwádìí"),
            ("Olùṣàyẹ̀wò ẹ̀rí", "Àbájáde àti ẹ̀rí"),
            ("Olùdánwò ita", "Ààlà ìwádìí"),
            ("Olùṣàyẹ̀wò ipa", "Ìlò ní ayé gidi"),
        ],
        "questions": [
            "Ìṣòro wo ni ìwádìí rẹ lórí '{topic}' ń yanjú, ta sì ni yóò jèrè jù lọ nínú àbájáde rẹ?",
            "Kí ló dé tí o fi yan ọ̀nà ìwádìí yìí, ọ̀nà míì wo ni o sì ronú lé lórí ṣùgbọ́n tí o kò lò?",
            "Kí ni àbájáde tó ṣe pàtàkì jù lọ nínú iṣẹ́ rẹ, ẹ̀rí wo sì ni ó ṣe atilẹyin rẹ jù lọ?",
            "Kí ni ààlà pàtàkì jù lọ nínú ìwádìí rẹ, báwo ni ààlà náà ṣe yẹ kí ó ní ipa lórí ìtumọ̀ àbájáde?",
            "Tí o bá fẹ́ yí ìwádìí yìí padà sí ojútùú gidi, kí ni ìgbésẹ̀ tó kàn, báwo ni o sì ṣe máa wọn àṣeyọrí?",
        ],
        "labels": {"clarity": "kíkedere", "relevance": "ìbáṣepọ̀ pẹ̀lú ìbéèrè", "evidence": "lílò ẹ̀rí", "structure": "ètò ìdáhùn"},
        "strength": "Agbára tó ga jù lọ nínú ìdáhùn rẹ ni {label}.",
        "improvement": "Ohun tó yẹ kí o dojú kọ jù lọ ní ìdáhùn tó kàn ni {label}.",
        "tips": {
            "clarity": "Bẹ̀rẹ̀ pẹ̀lú gbólóhùn kan tó dá ìbéèrè lóhùn taara kí o tó fi àlàyé kún un.",
            "relevance": "Darukọ apá pàtàkì ìbéèrè náà lẹ́ẹ̀kan síi, kí gbogbo kókó rẹ sì padà sí i.",
            "evidence": "Fi àbájáde kan, nọ́mbà, àpẹẹrẹ tàbí àkíyèsí gidi láti inú ìwádìí rẹ kún un.",
            "structure": "Lo ètò tó rọrùn: ìdáhùn → ẹ̀rí → ìtumọ̀ → ààlà.",
        },
        "feedback": "A ṣe àyẹ̀wò ìdáhùn rẹ lórí kíkedere, ìbáṣepọ̀ pẹ̀lú ìbéèrè, ẹ̀rí àti ètò. Dimegilio yìí kì í sọ bóyá ìwádìí rẹ tọ́ nípa sáyẹ́ǹsì; ó ń fi hàn bí ìdáhùn rẹ ṣe rọrùn láti dáàbò bo níwájú igbimọ̀.",
        "framework": "Ètò ìdáhùn tó lágbára tí o lè fi ìwádìí gidi rẹ kún:\n1. Kókó pàtàkì: [ìdáhùn taara sí ìbéèrè].\n2. Ẹ̀rí: [àbájáde, nọ́mbà tàbí àkíyèsí gidi].\n3. Ìtumọ̀: [ìdí tí ẹ̀rí náà fi ṣe pàtàkì].\n4. Ààlà: [ohun tí àbájáde kò lè fi hàn].",
        "fallback": "Olùpèsè AI kò sí ní àkókò yìí, nítorí náà a lo demo coaching agbègbè kí ìdánwò rẹ má bà a dá dúró.",
    },
    "ig": {
        "roles": [
            ("Onye nlekọta nyocha", "Nsogbu na mmetụta"),
            ("Onye nyocha usoro", "Usoro nyocha"),
            ("Onye nyochaa ihe akaebe", "Nsonaazụ na ihe akaebe"),
            ("Onye nyocha mpụga", "Oke nyocha"),
            ("Onye nyochaa mmetụta", "Ojiji n'ezi ndụ"),
        ],
        "questions": [
            "Kedu nsogbu nyocha gị gbasara '{topic}' na-edozi, onye kwa ga-erite uru kachasị na nsonaazụ ya?",
            "Gịnị mere i ji họrọ usoro nyocha a, kedu ụzọ ọzọ i tụlere ma hapụ?",
            "Kedu nsonaazụ kacha mkpa n'ọrụ gị, kedu ihe akaebe kacha akwado ya?",
            "Kedu oke kachasị mkpa nke nyocha gị, olee otú oke ahụ kwesịrị isi metụta nkọwa nsonaazụ?",
            "Ọ bụrụ na ị gbanwee nyocha a ka ọ bụrụ ngwọta n'ezi ndụ, gịnị bụ nzọụkwụ ọzọ, olee otú ị ga-esi tụọ ihe ịga nke ọma?",
        ],
        "labels": {"clarity": "ido anya", "relevance": "ịza ihe a jụrụ", "evidence": "iji ihe akaebe", "structure": "usoro azịza"},
        "strength": "Akụkụ kacha sie ike n'azịza gị bụ {label}.",
        "improvement": "Ihe kacha mkpa ị ga-emezi n'azịza ọzọ bụ {label}.",
        "tips": {
            "clarity": "Malite na otu ahịrịokwu na-aza ajụjụ ahụ ozugbo tupu ịgbakwunye nkọwa.",
            "relevance": "Kpọghachi isi ihe dị n'ajụjụ ahụ ma jikọta isi okwu ọ bụla na ya.",
            "evidence": "Tinye otu nsonaazụ, ọnụọgụ, ihe atụ ma ọ bụ nchọpụta kpọmkwem sitere na nyocha gị.",
            "structure": "Jiri usoro dị mfe: nkwupụta → ihe akaebe → ihe ọ pụtara → oke.",
        },
        "feedback": "A tụlere azịza gị n'ido anya, ịdị mkpa, ihe akaebe na usoro. Akara a anaghị ekpebi ma nyocha gị ziri ezi n'ụzọ sayensị; ọ na-egosi otú azịza ederede si dị mfe ịgbachitere n'ihu ndị nyocha.",
        "framework": "Usoro azịza ka mma ị nwere ike jupụta na nyocha gị n'ezie:\n1. Isi nkwupụta: [azịza ozugbo].\n2. Ihe akaebe: [nsonaazụ, ọnụọgụ ma ọ bụ nchọpụta kpọmkwem].\n3. Ihe ọ pụtara: [ihe mere ihe akaebe ji dị mkpa].\n4. Oke: [ihe nsonaazụ ahụ na-enweghị ike igosi].",
        "fallback": "Onye na-enye AI adịghị, ya mere ejiri local demo coaching mee ka mmemme ahụ gaa n'ihu.",
    },
    "sw": {
        "roles": [
            ("Msimamizi wa utafiti", "Tatizo na athari"),
            ("Mtahini wa mbinu", "Mbinu za utafiti"),
            ("Mkaguzi wa ushahidi", "Matokeo na ushahidi"),
            ("Mtahini wa nje", "Mipaka"),
            ("Mkaguzi wa athari", "Matumizi halisi"),
        ],
        "questions": [
            "Utafiti wako kuhusu '{topic}' unatatua tatizo gani, na nani atanufaika zaidi na matokeo yake?",
            "Kwa nini ulichagua mbinu hii ya utafiti, na ni njia gani mbadala uliyoifikiria lakini ukaiacha?",
            "Ni matokeo gani muhimu zaidi katika kazi yako, na ni ushahidi gani unaoyaunga mkono zaidi?",
            "Ni upungufu gani mkubwa zaidi wa utafiti wako, na unapaswa kuathirije tafsiri ya matokeo?",
            "Kama ungegeuza utafiti huu kuwa suluhisho la matumizi halisi, hatua inayofuata ingekuwa ipi na ungepimaje mafanikio?",
        ],
        "labels": {"clarity": "uwazi", "relevance": "uhusiano na swali", "evidence": "matumizi ya ushahidi", "structure": "muundo wa jibu"},
        "strength": "Eneo lenye nguvu zaidi katika jibu lako ni {label}.",
        "improvement": "Eneo muhimu zaidi la kuboresha katika jibu linalofuata ni {label}.",
        "tips": {
            "clarity": "Anza na sentensi moja inayojibu swali moja kwa moja kabla ya kuongeza maelezo.",
            "relevance": "Rudia sehemu muhimu ya swali la mtahini na uunganishe kila hoja nayo.",
            "evidence": "Ongeza matokeo moja, namba, mfano au uchunguzi halisi kutoka kwenye utafiti wako.",
            "structure": "Tumia muundo rahisi: dai → ushahidi → umuhimu → kikomo.",
        },
        "feedback": "Jibu lako limepimwa kwa uwazi, uhusiano na swali, ushahidi na muundo. Alama hii haiamui kama utafiti wako ni sahihi kisayansi; inaonyesha jinsi jibu lako lilivyo rahisi kulitetea mbele ya jopo.",
        "framework": "Muundo bora wa jibu unaoweza kujaza kwa utafiti wako halisi:\n1. Dai kuu: [jibu la moja kwa moja].\n2. Ushahidi: [matokeo, namba au uchunguzi maalum].\n3. Umuhimu: [kwa nini ushahidi huo ni muhimu].\n4. Kikomo: [kile ambacho matokeo hayawezi kuthibitisha].",
        "fallback": "Mtoa huduma wa AI hakupatikana, kwa hiyo local demo coaching imetumika ili mazoezi yako yaendelee.",
    },
    "zu": {
        "roles": [
            ("Umqondisi wocwaningo", "Inkinga nomthelela"),
            ("Umhloli wezindlela", "Indlela yocwaningo"),
            ("Umhloli wobufakazi", "Imiphumela nobufakazi"),
            ("Umhloli wangaphandle", "Imikhawulo"),
            ("Umhloli womthelela", "Ukusetshenziswa empilweni"),
        ],
        "questions": [
            "Ucwaningo lwakho ngo-'{topic}' luxazulula yiphi inkinga, futhi ubani ozohlomula kakhulu emiphumeleni yalo?",
            "Kungani ukhethe le ndlela yocwaningo, futhi iyiphi enye indlela oyicabangile kodwa wangayisebenzisa?",
            "Yimuphi umphumela obaluleke kakhulu emsebenzini wakho, futhi yibuphi ubufakazi obuwusekela kakhulu?",
            "Yimuphi umkhawulo omkhulu wocwaningo lwakho, futhi lowo mkhawulo kufanele uthinte kanjani ukuhunyushwa kwemiphumela?",
            "Uma ungaguqula lolu cwaningo lube yisixazululo sangempela, yisiphi isinyathelo esilandelayo futhi ungalinganisa kanjani impumelelo?",
        ],
        "labels": {"clarity": "ukucaca", "relevance": "ukuhambisana nombuzo", "evidence": "ukusebenzisa ubufakazi", "structure": "isakhiwo sempendulo"},
        "strength": "Ingxenye enamandla kakhulu empendulweni yakho ngu-{label}.",
        "improvement": "Into ebaluleke kakhulu ongayithuthukisa empendulweni elandelayo ngu-{label}.",
        "tips": {
            "clarity": "Qala ngomusho owodwa ophendula umbuzo ngqo ngaphambi kokwengeza imininingwane.",
            "relevance": "Phinda ingxenye ebalulekile yombuzo bese uxhumanisa wonke amaphuzu akho nayo.",
            "evidence": "Faka umphumela owodwa, inombolo, isibonelo noma okubonile ngokuqondile ocwaningweni lwakho.",
            "structure": "Sebenzisa isakhiwo esilula: iphuzu → ubufakazi → ukubaluleka → umkhawulo.",
        },
        "feedback": "Impendulo yakho ihlolwe ngokucaca, ukuhambisana nombuzo, ubufakazi nesakhiwo. Leli phuzu alisho ukuthi ucwaningo lwakho lunembile ngokwesayensi; libonisa ukuthi impendulo ibonakala ivikeleka kangakanani phambi kwejopo.",
        "framework": "Isakhiwo esiqinile sempendulo ongagcwalisa ngocwaningo lwakho lwangempela:\n1. Iphuzu eliyinhloko: [impendulo eqondile].\n2. Ubufakazi: [umphumela, inombolo noma okubonile].\n3. Ukubaluleka: [kungani lobo bufakazi bubalulekile].\n4. Umkhawulo: [lokho umphumela ongakwazi ukukufakazela].",
        "fallback": "Umhlinzeki we-AI akatholakali, ngakho kusetshenziswe local demo coaching ukuze ukuqeqeshwa kuqhubeke.",
    },
}


class ThesisInput(BaseModel):
    topic: str = Field(min_length=1, max_length=300)
    abstract: str = Field(default="", max_length=MAX_CONTEXT_CHARS)
    language: Language = "en"


class AnswerInput(BaseModel):
    topic: str = Field(min_length=1, max_length=300)
    question: str = Field(min_length=1, max_length=1200)
    answer: str = Field(min_length=1, max_length=6000)
    language: Language = "en"


def language_name(language: Language) -> str:
    return LANGUAGE_NAMES[language]


def panel_templates(language: Language) -> list[dict[str, str]]:
    return [
        {"role": role, "category": category}
        for role, category in LOCALES[language]["roles"]
    ]


def demo_questions(topic: str, language: Language) -> list[dict[str, str]]:
    questions = [template.format(topic=topic) for template in LOCALES[language]["questions"]]
    return [
        {"id": f"q{index + 1}", **panel, "question": question}
        for index, (panel, question) in enumerate(zip(panel_templates(language), questions, strict=True))
    ]


def normalize_questions(raw_questions: object, language: Language) -> list[dict[str, str]]:
    if not isinstance(raw_questions, list) or len(raw_questions) != 5:
        raise ValueError("Exactly five questions are required")

    templates = panel_templates(language)
    normalized: list[dict[str, str]] = []
    for index, item in enumerate(raw_questions):
        if isinstance(item, str):
            question = item.strip()
            role = templates[index]["role"]
            category = templates[index]["category"]
        elif isinstance(item, dict):
            question = str(item.get("question") or item.get("text") or "").strip()
            role = str(item.get("role") or templates[index]["role"]).strip()
            category = str(item.get("category") or templates[index]["category"]).strip()
        else:
            raise ValueError("Question format is invalid")

        if not question:
            raise ValueError("Question cannot be empty")
        normalized.append({"id": f"q{index + 1}", "role": role, "category": category, "question": question})
    return normalized


STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "is", "are", "was", "were", "this", "that",
    "what", "why", "how", "your", "you", "my", "our", "with", "from", "it", "be", "as", "at", "by", "we", "i",
    "da", "na", "ne", "ce", "ya", "ta", "su", "ko", "me", "yaya", "wace", "mene", "kuma", "daga", "don",
    "ni", "na", "kwa", "ya", "la", "wa", "au", "hii", "hiyo", "nini", "jinsi", "kati", "kwenye",
}
WORD_RE = re.compile(r"[\w'’-]+", re.UNICODE)

REASONING_MARKERS = [
    "because", "therefore", "result", "evidence", "data", "found", "showed", "sample", "study",
    "saboda", "don haka", "sakamako", "shaida", "bayanai", "bincike",
    "nítorí", "ẹ̀rí", "àbájáde", "ìwádìí",
    "n'ihi", "ihe akaebe", "nsonaazụ", "nnyocha",
    "kwa sababu", "ushahidi", "matokeo", "utafiti",
    "ngoba", "ubufakazi", "imiphumela", "ucwaningo",
]
STRUCTURE_MARKERS = [
    "first", "second", "finally", "however", "although", "in conclusion", "for example",
    "na farko", "sannan", "a ƙarshe", "amma", "misali",
    "àkọ́kọ́", "lẹ́yìn náà", "ní ìparí", "fún àpẹẹrẹ",
    "nke mbụ", "mgbe ahụ", "n'ikpeazụ", "dịka ọmụmaatụ",
    "kwanza", "pili", "hatimaye", "kwa mfano",
    "okokuqala", "bese", "ekugcineni", "isibonelo",
]


def meaningful_words(text: str) -> set[str]:
    return {
        token.lower()
        for token in WORD_RE.findall(text)
        if len(token) > 2 and token.lower() not in STOPWORDS
    }


def score_dimensions(topic: str, question: str, answer: str) -> dict[str, int]:
    words = WORD_RE.findall(answer)
    word_count = len(words)
    answer_lower = answer.lower()
    sentence_count = max(1, len(re.findall(r"[.!?]+", answer)))
    context_terms = meaningful_words(f"{topic} {question}")
    answer_terms = meaningful_words(answer)
    overlap = len(context_terms & answer_terms)
    has_reasoning = any(marker in answer_lower for marker in REASONING_MARKERS)
    has_structure = any(marker in answer_lower for marker in STRUCTURE_MARKERS)
    has_number = bool(re.search(r"\d", answer))

    clarity = 50 + min(28, word_count) + min(8, sentence_count * 2)
    if word_count > 180:
        clarity -= 8
    relevance = 50 + min(34, overlap * 7) + min(10, word_count // 8)
    evidence = 44 + min(20, word_count // 3) + (14 if has_reasoning else 0) + (8 if has_number else 0)
    structure = 48 + min(20, word_count // 4) + (16 if has_structure else 0) + min(8, sentence_count * 2)

    return {
        "clarity": max(35, min(96, clarity)),
        "relevance": max(35, min(96, relevance)),
        "evidence": max(35, min(96, evidence)),
        "structure": max(35, min(96, structure)),
    }


def demo_evaluation(payload: AnswerInput) -> dict:
    dimensions = score_dimensions(payload.topic, payload.question, payload.answer)
    score = round(sum(dimensions.values()) / len(dimensions))
    locale = LOCALES[payload.language]
    strongest = max(dimensions, key=dimensions.get)
    weakest = min(dimensions, key=dimensions.get)
    strengths = [locale["strength"].format(label=locale["labels"][strongest])]
    improvements = [locale["improvement"].format(label=locale["labels"][weakest])]

    return {
        "score": score,
        "dimensions": dimensions,
        "strengths": strengths,
        "improvements": improvements,
        "feedback": locale["feedback"],
        "improved_answer": locale["framework"],
        "next_tip": locale["tips"][weakest],
        "word_count": len(WORD_RE.findall(payload.answer)),
        "mode": "demo",
        "language": payload.language,
    }


def extract_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


async def call_llm(messages: list[dict]) -> dict:
    if not LLM_API_KEY:
        raise HTTPException(status_code=503, detail="LLM_API_KEY is not configured")

    headers = {"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"}
    base_body = {"model": LLM_MODEL, "messages": messages, "temperature": 0.25}

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=10.0)) as client:
            for use_json_mode in (True, False):
                body = dict(base_body)
                if use_json_mode:
                    body["response_format"] = {"type": "json_object"}
                response = await client.post(f"{LLM_BASE_URL}/chat/completions", headers=headers, json=body)
                if use_json_mode and response.status_code in {400, 404, 415, 422}:
                    continue
                response.raise_for_status()
                data = response.json()
                return extract_json(data["choices"][0]["message"]["content"])
    except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail="The AI provider returned an invalid or unavailable response") from exc

    raise HTTPException(status_code=502, detail="The AI provider did not accept the request format")


def fallback_notice(language: Language) -> str:
    return LOCALES[language]["fallback"]


def suggested_topic_from_text(text: str) -> str:
    for line in text.splitlines():
        candidate = line.strip().lstrip("#").strip()
        if 4 <= len(candidate) <= 180:
            return candidate
    return ""


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "microphone=(self)"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    if not INDEX_FILE.exists():
        raise HTTPException(status_code=500, detail="index.html is missing")
    return HTMLResponse(INDEX_FILE.read_text(encoding="utf-8"))


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": APP_VERSION,
        "mode": "demo" if DEMO_MODE else "llm",
        "fallback_to_demo": AI_FALLBACK_TO_DEMO,
        "languages": list(SUPPORTED_LANGUAGES),
        "upload_types": ["pdf", "txt", "md"],
    }


@app.post("/api/extract")
async def extract_research(file: UploadFile = File(...)) -> dict:
    filename = (file.filename or "research").strip()
    suffix = Path(filename).suffix.lower()
    if suffix not in {".pdf", ".txt", ".md"}:
        raise HTTPException(status_code=415, detail="Use a PDF, TXT, or Markdown file")

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is too large; maximum size is 6 MB")

    try:
        if suffix == ".pdf":
            reader = PdfReader(BytesIO(content))
            text = "\n\n".join((page.extract_text() or "").strip() for page in reader.pages)
        else:
            text = content.decode("utf-8-sig")
    except (PdfReadError, UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="The file could not be read as text") from exc

    text = text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="No extractable text was found in this file")

    truncated = len(text) > MAX_CONTEXT_CHARS
    context = text[:MAX_CONTEXT_CHARS]
    return {
        "filename": filename,
        "text": context,
        "suggested_topic": suggested_topic_from_text(context),
        "truncated": truncated,
        "characters": len(context),
    }


@app.post("/api/questions")
async def generate_questions(payload: ThesisInput) -> dict:
    topic = payload.topic.strip()
    abstract = payload.abstract.strip()
    if not topic:
        raise HTTPException(status_code=422, detail="Topic cannot be empty")

    if DEMO_MODE:
        return {"questions": demo_questions(topic, payload.language), "mode": "demo", "language": payload.language}

    target_language = language_name(payload.language)
    context = abstract or "No thesis context was provided. Base the panel on the topic and ask broadly useful defence questions."
    try:
        result = await call_llm([
            {
                "role": "system",
                "content": (
                    "You are a realistic but supportive university thesis defence panel. Return JSON only with a 'questions' array of exactly five objects. "
                    "Each object must contain 'role', 'category', and 'question'. Cover problem/impact, methodology, evidence/results, limitations, and practical application. "
                    f"Write every visible field in {target_language}. Keep each question concise and specific to the provided research when possible."
                ),
            },
            {"role": "user", "content": f"Thesis topic: {topic}\n\nResearch context: {context}"},
        ])
        questions = normalize_questions(result.get("questions"), payload.language)
        return {"questions": questions, "mode": "llm", "language": payload.language}
    except (HTTPException, ValueError) as exc:
        if not AI_FALLBACK_TO_DEMO:
            if isinstance(exc, HTTPException):
                raise
            raise HTTPException(status_code=502, detail="The AI panel returned an invalid question format") from exc
        return {
            "questions": demo_questions(topic, payload.language),
            "mode": "fallback",
            "language": payload.language,
            "notice": fallback_notice(payload.language),
        }


@app.post("/api/evaluate")
async def evaluate_answer(payload: AnswerInput) -> dict:
    if DEMO_MODE:
        return demo_evaluation(payload)

    target_language = language_name(payload.language)
    try:
        result = await call_llm([
            {
                "role": "system",
                "content": (
                    "Act as a thesis defence coach. Return JSON only with: object 'dimensions' containing integer 0-100 scores for clarity, relevance, evidence, and structure; "
                    "array 'strengths' with 1-3 concise items; array 'improvements' with 1-3 concise items; short 'feedback'; 'improved_answer'; and one-sentence 'next_tip'. "
                    "Never invent research findings, numbers, citations, or facts that the student did not provide. The improved answer should use placeholders when evidence is missing. "
                    f"Write all coaching text in {target_language}."
                ),
            },
            {
                "role": "user",
                "content": f"Topic: {payload.topic}\nQuestion: {payload.question}\nStudent answer: {payload.answer}",
            },
        ])
        dimensions_raw = result["dimensions"]
        dimensions = {
            key: max(0, min(100, int(dimensions_raw[key])))
            for key in ("clarity", "relevance", "evidence", "structure")
        }
        strengths = [str(item) for item in result["strengths"]][:3]
        improvements = [str(item) for item in result["improvements"]][:3]
        if not strengths or not improvements:
            raise ValueError("Coaching lists cannot be empty")
        return {
            "score": round(sum(dimensions.values()) / len(dimensions)),
            "dimensions": dimensions,
            "strengths": strengths,
            "improvements": improvements,
            "feedback": str(result["feedback"]),
            "improved_answer": str(result["improved_answer"]),
            "next_tip": str(result["next_tip"]),
            "word_count": len(WORD_RE.findall(payload.answer)),
            "mode": "llm",
            "language": payload.language,
        }
    except (HTTPException, KeyError, TypeError, ValueError) as exc:
        if not AI_FALLBACK_TO_DEMO:
            if isinstance(exc, HTTPException):
                raise
            raise HTTPException(status_code=502, detail="The AI evaluation format was invalid") from exc
        response = demo_evaluation(payload)
        response["mode"] = "fallback"
        response["notice"] = fallback_notice(payload.language)
        return response
