from typing import List, Dict, Tuple
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import re
from collections import defaultdict
from nltk.stem import PorterStemmer
import nltk
from schema.jaccard import JaccardMatch


# Initialize stemmer and tokenizer (if nltk is used)
stemmer = PorterStemmer()
try:
    stop_words = set(stopwords.words("english"))
except LookupError:
    nltk.download("stopwords", quiet=True, raise_on_error=True)
    stop_words = set(stopwords.words("english"))


def best_jaccard_matches(target_text: str, match_text: str, window_size: int, max_matches: int, slide: int = 10) -> List[JaccardMatch]:
    """Rank non-overlapping windows by token-set Jaccard similarity."""
    if window_size < 1 or slide < 1 or max_matches < 1:
        raise ValueError("window_size, slide, and max_matches must be positive")
    target = set(get_word_occurrences(target_text))
    lines = match_text.split('\n')
    tokens = [set(get_word_occurrences(line)) for line in lines]
    windows = []
    # A short file contributes one window; longer files use full-width windows.
    for start in range(0, max(1, len(lines) - window_size + 1), slide):
        end = min(start + window_size, len(lines))
        candidate = set().union(*tokens[start:end])
        score = jaccard_similarity(len(target), len(candidate), len(target & candidate))
        windows.append(JaccardMatch(score=score, content="\n".join(lines[start:end]),
                                    start_line=start, end_line=end - 1))
    windows.sort(key=lambda window: (-window.score, window.start_line))
    retained, included = [], set()
    for window in windows:
        span = set(range(window.start_line, window.end_line + 1))
        if not included.intersection(span):
            retained.append(window)
            included.update(span)
            if len(retained) == max_matches:
                break
    return retained

def jaccard_similarity(left: int, right: int, intersection: int) -> float:
    union = left + right - intersection
    if union <= 0:
        return 0
    return intersection / union

def get_word_occurrences(s: str) -> Dict[str, int]:
    frequency_counter = defaultdict(int)
    words = word_tokenize(s, preserve_line=True)
    
    # Break compound words and filter out stopwords
    filtered_words = [
        word.lower() 
        for w in words 
        for word in break_camel_and_snake_case(w)
        if word.lower() not in stop_words
    ]
    
    # Apply stemming and count occurrences
    for word in filtered_words:
        stemmed_word = stemmer.stem(word)
        frequency_counter[stemmed_word] += 1
        
    return frequency_counter

def break_camel_and_snake_case(word: str) -> List[str]:
    camel_case_regex = re.compile(r'([a-z])([A-Z])')
    snake_case_regex = re.compile(r'_')
    
    # Break camelCase words
    broken_word = camel_case_regex.sub(r'\1 \2', word)
    # Break snake_case words
    broken_word = snake_case_regex.sub(' ', broken_word)
    
    # If no changes, return original word
    if broken_word == word:
        return [word]
    
    word_parts = broken_word.split()
    word_parts.append(word)  # Add original word for exact matches
    return word_parts
