"""
AI-Powered Matching Engine (v3 — Maximum Accuracy)

7 Matching Layers:
  1. TF-IDF word-level cosine similarity
  2. Character n-gram similarity (typos: walat→wallet)
  3. Fuzzy token matching (SequenceMatcher word-by-word)
  4. Phonetic matching (Soundex/Metaphone — sounds-alike: fone→phone)
  5. Jaro-Winkler distance (edit-distance for short strings)
  6. Synonym & category awareness (mobile=phone=cell, bag=backpack=purse)
  7. Image similarity (HSV histogram + grayscale + ORB features + template match)

Scoring:
  title_score  = best of all 7 text layers on TITLE only (most important)
  full_score   = best of layers 1-5 on full text (title+desc+location)
  text_score   = 0.6 * title_score + 0.4 * full_score
  final_score  = TEXT_WEIGHT * text_score + IMAGE_WEIGHT * image_score
               + location_bonus + synonym_bonus
"""

import base64
import re
from difflib import SequenceMatcher
from typing import List, Tuple, Set

import cv2
import jellyfish
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session

from models import Item, ItemCategory, ItemStatus
from email_service import send_match_notification


# ═══════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════

MATCH_THRESHOLD = 0.22       # Minimum score to trigger a match
TEXT_WEIGHT = 0.65
IMAGE_WEIGHT = 0.35
LOCATION_BONUS = 0.15        # Bonus when locations match exactly
LOCATION_PARTIAL_BONUS = 0.10  # Bonus for partial location match
SYNONYM_BONUS = 0.12         # Bonus when synonym categories match
FUZZY_WORD_THRESHOLD = 0.65  # Min ratio to consider two words "the same"
TITLE_WEIGHT = 0.6           # How much title matters vs full text
FULL_TEXT_WEIGHT = 0.4


# ═══════════════════════════════════════════════════════════
# SYNONYM DATABASE — common item categories & aliases
# ═══════════════════════════════════════════════════════════

SYNONYM_GROUPS = [
    {"phone", "mobile", "cell", "cellphone", "smartphone", "iphone", "android", "samsung", "galaxy", "pixel", "oneplus", "redmi", "realme", "oppo", "vivo", "fone"},
    {"wallet", "purse", "billfold", "pocketbook", "walat", "walet"},
    {"laptop", "notebook", "macbook", "chromebook", "loptop", "labtop"},
    {"bag", "backpack", "rucksack", "satchel", "handbag", "tote", "suitcase", "luggage", "bagpack"},
    {"key", "keys", "keychain", "keyring", "carkey", "carkeys", "housekey"},
    {"watch", "wristwatch", "smartwatch", "fitbit", "applewatch"},
    {"glasses", "spectacles", "sunglasses", "shades", "eyeglasses", "specs"},
    {"earphone", "earphones", "earbud", "earbuds", "headphone", "headphones", "airpod", "airpods", "earpiece"},
    {"charger", "cable", "charging", "adapter", "powerbank", "power"},
    {"bottle", "waterbottle", "flask", "thermos", "sipper"},
    {"card", "idcard", "id", "identity", "aadhar", "aadhaar", "pan", "license", "licence", "passport", "driving"},
    {"pen", "pencil", "pencils", "pencile", "pens", "marker", "highlighter", "stationary", "stationery"},
    {"book", "textbook", "notebook", "diary", "journal", "register"},
    {"ring", "rings", "necklace", "chain", "bracelet", "bangle", "jewelry", "jewellery", "earring", "earrings"},
    {"umbrella", "umbrela", "parasol"},
    {"mouse", "keyboard", "usb", "pendrive", "flashdrive", "harddisk", "harddrive", "ssd"},
    {"calculator", "calc", "scientific"},
    {"camera", "dslr", "gopro", "camcorder"},
    {"tablet", "ipad", "tab"},
    {"coat", "jacket", "hoodie", "sweater", "blazer"},
    {"shoe", "shoes", "sandal", "sandals", "slipper", "slippers", "sneaker", "sneakers", "footwear"},
    {"cap", "hat", "beanie", "helmet"},
]

# Build reverse lookup: word → set of synonyms
_SYNONYM_MAP = {}
for group in SYNONYM_GROUPS:
    for word in group:
        _SYNONYM_MAP[word] = group


def get_synonym_group(word: str) -> Set[str]:
    """Get all synonyms for a word."""
    return _SYNONYM_MAP.get(word.lower(), set())


def texts_share_synonym(text1: str, text2: str) -> bool:
    """Check if two texts contain words from the same synonym group."""
    words1 = set(tokenize(text1))
    words2 = set(tokenize(text2))
    for w1 in words1:
        group = get_synonym_group(w1)
        if group and group.intersection(words2):
            return True
    return False


# ═══════════════════════════════════════════════════════════
# TEXT HELPERS
# ═══════════════════════════════════════════════════════════

def build_text(item) -> str:
    """Combine title, description, and location."""
    parts = []
    if item.title:
        parts.append(item.title)
    if item.description:
        parts.append(item.description)
    if item.location:
        parts.append(item.location)
    return " ".join(parts).lower().strip()


def get_title(item) -> str:
    """Get normalized title."""
    return (item.title or "").strip().lower()


def get_location(item) -> str:
    """Get normalized location."""
    return (item.location or "").strip().lower()


def tokenize(text: str) -> List[str]:
    """Split text into word tokens."""
    return re.findall(r'[a-z0-9]+', text.lower())


def expand_with_synonyms(text: str) -> str:
    """Expand text by appending synonym words for better TF-IDF matching."""
    words = tokenize(text)
    expanded = list(words)
    for w in words:
        group = get_synonym_group(w)
        if group:
            expanded.extend(group)
    return " ".join(expanded)


# ═══════════════════════════════════════════════════════════
# LAYER 1: TF-IDF Word Similarity
# ═══════════════════════════════════════════════════════════

def tfidf_word_similarity(text1: str, text2: str) -> float:
    if not text1 or not text2:
        return 0.0
    try:
        vec = TfidfVectorizer(stop_words="english", analyzer="word")
        matrix = vec.fit_transform([text1, text2])
        return float(cosine_similarity(matrix[0:1], matrix[1:2])[0][0])
    except ValueError:
        return 0.0


# ═══════════════════════════════════════════════════════════
# LAYER 2: Character N-Gram Similarity
# ═══════════════════════════════════════════════════════════

def char_ngram_similarity(text1: str, text2: str) -> float:
    if not text1 or not text2:
        return 0.0
    try:
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5))
        matrix = vec.fit_transform([text1, text2])
        return float(cosine_similarity(matrix[0:1], matrix[1:2])[0][0])
    except ValueError:
        return 0.0


# ═══════════════════════════════════════════════════════════
# LAYER 3: Fuzzy Token Matching
# ═══════════════════════════════════════════════════════════

def fuzzy_token_similarity(text1: str, text2: str) -> float:
    """Word-by-word SequenceMatcher comparison (bidirectional)."""
    tokens1 = tokenize(text1)
    tokens2 = tokenize(text2)
    if not tokens1 or not tokens2:
        return 0.0

    def directional_score(src, tgt):
        matched = 0
        for w1 in src:
            best = max((SequenceMatcher(None, w1, w2).ratio() for w2 in tgt), default=0)
            if best >= FUZZY_WORD_THRESHOLD:
                matched += 1
        return matched / len(src)

    return (directional_score(tokens1, tokens2) + directional_score(tokens2, tokens1)) / 2


# ═══════════════════════════════════════════════════════════
# LAYER 4: Phonetic Matching (Soundex + Metaphone)
# ═══════════════════════════════════════════════════════════

def phonetic_similarity(text1: str, text2: str) -> float:
    """Compare words by how they SOUND — catches fone→phone, umbrela→umbrella."""
    tokens1 = tokenize(text1)
    tokens2 = tokenize(text2)
    if not tokens1 or not tokens2:
        return 0.0

    def get_phonetic_codes(word):
        """Get Soundex and Metaphone codes for a word."""
        codes = set()
        try:
            codes.add(jellyfish.soundex(word))
        except Exception:
            pass
        try:
            codes.add(jellyfish.metaphone(word))
        except Exception:
            pass
        return codes

    def directional_match(src, tgt):
        tgt_codes = [get_phonetic_codes(w) for w in tgt]
        matched = 0
        for w1 in src:
            codes1 = get_phonetic_codes(w1)
            for codes2 in tgt_codes:
                if codes1.intersection(codes2):
                    matched += 1
                    break
        return matched / len(src) if src else 0

    return (directional_match(tokens1, tokens2) + directional_match(tokens2, tokens1)) / 2


# ═══════════════════════════════════════════════════════════
# LAYER 5: Jaro-Winkler Distance
# ═══════════════════════════════════════════════════════════

def jaro_winkler_similarity(text1: str, text2: str) -> float:
    """Edit-distance based — great for short strings and minor typos."""
    tokens1 = tokenize(text1)
    tokens2 = tokenize(text2)
    if not tokens1 or not tokens2:
        return 0.0

    def directional_score(src, tgt):
        matched = 0
        for w1 in src:
            best = max((jellyfish.jaro_winkler_similarity(w1, w2) for w2 in tgt), default=0)
            if best >= 0.80:
                matched += 1
        return matched / len(src)

    return (directional_score(tokens1, tokens2) + directional_score(tokens2, tokens1)) / 2


# ═══════════════════════════════════════════════════════════
# LAYER 6: Synonym-Expanded TF-IDF
# ═══════════════════════════════════════════════════════════

def synonym_tfidf_similarity(text1: str, text2: str) -> float:
    """Expand text with synonyms first, then run TF-IDF."""
    exp1 = expand_with_synonyms(text1)
    exp2 = expand_with_synonyms(text2)
    return tfidf_word_similarity(exp1, exp2)


# ═══════════════════════════════════════════════════════════
# COMBINED TEXT SIMILARITY
# ═══════════════════════════════════════════════════════════

def compute_text_similarity(text1: str, text2: str) -> float:
    """Run all text layers, return the best score."""
    if not text1 or not text2:
        return 0.0

    scores = [
        tfidf_word_similarity(text1, text2),
        char_ngram_similarity(text1, text2),
        fuzzy_token_similarity(text1, text2),
        phonetic_similarity(text1, text2),
        jaro_winkler_similarity(text1, text2),
        synonym_tfidf_similarity(text1, text2),
    ]

    return max(scores)


# ═══════════════════════════════════════════════════════════
# IMAGE SIMILARITY (Multi-Method)
# ═══════════════════════════════════════════════════════════

def decode_base64_image(base64_str: str) -> np.ndarray | None:
    if not base64_str:
        return None
    try:
        if "," in base64_str:
            base64_str = base64_str.split(",", 1)[1]
        img_bytes = base64.b64decode(base64_str)
        img_array = np.frombuffer(img_bytes, dtype=np.uint8)
        return cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    except Exception:
        return None


def compute_image_similarity(img1_base64: str, img2_base64: str) -> float:
    """Compare images using 4 methods — HSV hist, grayscale hist, ORB features, template match."""
    img1 = decode_base64_image(img1_base64)
    img2 = decode_base64_image(img2_base64)
    if img1 is None or img2 is None:
        return 0.0

    scores = []
    try:
        target = (256, 256)
        img1r = cv2.resize(img1, target)
        img2r = cv2.resize(img2, target)

        # Method 1: HSV histogram correlation
        hsv1 = cv2.cvtColor(img1r, cv2.COLOR_BGR2HSV)
        hsv2 = cv2.cvtColor(img2r, cv2.COLOR_BGR2HSV)
        hist1 = cv2.calcHist([hsv1], [0, 1], None, [50, 60], [0, 180, 0, 256])
        cv2.normalize(hist1, hist1, 0, 1, cv2.NORM_MINMAX)
        hist2 = cv2.calcHist([hsv2], [0, 1], None, [50, 60], [0, 180, 0, 256])
        cv2.normalize(hist2, hist2, 0, 1, cv2.NORM_MINMAX)
        scores.append(max(0.0, float(cv2.compareHist(hist1, hist2, cv2.HISTCOMP_CORREL))))

        # Method 2: Grayscale histogram
        gray1 = cv2.cvtColor(img1r, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(img2r, cv2.COLOR_BGR2GRAY)
        gh1 = cv2.calcHist([gray1], [0], None, [64], [0, 256])
        cv2.normalize(gh1, gh1, 0, 1, cv2.NORM_MINMAX)
        gh2 = cv2.calcHist([gray2], [0], None, [64], [0, 256])
        cv2.normalize(gh2, gh2, 0, 1, cv2.NORM_MINMAX)
        scores.append(max(0.0, float(cv2.compareHist(gh1, gh2, cv2.HISTCOMP_CORREL))))

        # Method 3: ORB feature matching
        try:
            orb = cv2.ORB_create(nfeatures=500)
            kp1, des1 = orb.detectAndCompute(gray1, None)
            kp2, des2 = orb.detectAndCompute(gray2, None)
            if des1 is not None and des2 is not None and len(des1) > 2 and len(des2) > 2:
                bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
                matches = bf.match(des1, des2)
                good = [m for m in matches if m.distance < 60]
                orb_score = len(good) / max(len(kp1), len(kp2), 1)
                scores.append(min(1.0, orb_score * 3))  # scale up
        except Exception:
            pass

        # Method 4: Template matching
        try:
            result = cv2.matchTemplate(gray1, gray2, cv2.TM_CCOEFF_NORMED)
            scores.append(max(0.0, float(result.max())))
        except Exception:
            pass

    except Exception:
        pass

    return max(scores) if scores else 0.0


# ═══════════════════════════════════════════════════════════
# COMBINED MATCHING
# ═══════════════════════════════════════════════════════════

def compute_match_score(found_item, lost_item) -> Tuple[float, float, float]:
    """
    Compute match score with title-focused weighting.
    Returns: (final_score, text_score, image_score)
    """
    # Title-focused scoring (titles are the most important signal)
    found_title = get_title(found_item)
    lost_title = get_title(lost_item)
    title_score = compute_text_similarity(found_title, lost_title)

    # Full text scoring (title + description + location)
    found_text = build_text(found_item)
    lost_text = build_text(lost_item)
    full_score = compute_text_similarity(found_text, lost_text)

    # Weighted text score: titles matter more
    text_score = (TITLE_WEIGHT * title_score) + (FULL_TEXT_WEIGHT * full_score)

    # Image similarity
    image_score = 0.0
    found_img = getattr(found_item, 'image_url', None)
    lost_img = getattr(lost_item, 'image_url', None)
    if found_img and lost_img:
        image_score = compute_image_similarity(found_img, lost_img)

    # Combine text + image
    if found_img and lost_img:
        final_score = (TEXT_WEIGHT * text_score) + (IMAGE_WEIGHT * image_score)
    else:
        final_score = text_score

    # Location bonus
    found_loc = get_location(found_item)
    lost_loc = get_location(lost_item)
    if found_loc and lost_loc:
        loc_sim = SequenceMatcher(None, found_loc, lost_loc).ratio()
        if loc_sim >= 0.9:
            final_score += LOCATION_BONUS
        elif loc_sim >= 0.6 or found_loc in lost_loc or lost_loc in found_loc:
            final_score += LOCATION_PARTIAL_BONUS

    # Synonym category bonus (phone↔mobile, bag↔backpack, etc.)
    if texts_share_synonym(found_title, lost_title):
        final_score += SYNONYM_BONUS

    final_score = min(final_score, 1.0)
    return final_score, text_score, image_score


def find_matching_lost_items(found_item: Item, db: Session) -> List[Tuple[Item, float, float, float]]:
    """Find LOST items that match a newly posted FOUND item."""
    lost_items = (
        db.query(Item)
        .filter(Item.category == ItemCategory.LOST)
        .filter(Item.status == ItemStatus.OPEN)
        .filter(Item.user_id != found_item.user_id)
        .all()
    )

    matches = []
    for lost_item in lost_items:
        final_score, text_score, image_score = compute_match_score(found_item, lost_item)

        if final_score >= MATCH_THRESHOLD:
            matches.append((lost_item, final_score, text_score, image_score))
            print(
                f"  MATCH: '{lost_item.title}' "
                f"(final={final_score:.2f}, text={text_score:.2f}, image={image_score:.2f})"
            )

    matches.sort(key=lambda x: x[1], reverse=True)
    return matches


def process_found_item_matches(found_item: Item, finder_user, db: Session) -> int:
    """When a FOUND item is posted, find matching LOST items and notify owners via email."""
    print(f"AI Matching: checking '{found_item.title}' against LOST items...")
    matches = find_matching_lost_items(found_item, db)
    notified = 0

    for lost_item, final_score, text_score, image_score in matches:
        owner = lost_item.owner
        if not owner or not owner.email:
            continue

        success = send_match_notification(
            to_email=owner.email,
            to_name=owner.full_name,
            lost_item_title=lost_item.title,
            found_item_title=found_item.title,
            finder_name=finder_user.full_name,
            finder_email=finder_user.email,
            found_location=found_item.location,
        )

        if success:
            notified += 1
            print(
                f"  Notified {owner.email} | "
                f"Score: {final_score:.0%} (text={text_score:.0%}, image={image_score:.0%})"
            )

    return notified