"""Select source lines under tokenizer-measured FIM and retrieval budgets."""
from ranking.reciprocal_rank_fusion import merge_adjacent_lines


def token_count(tokenizer, text):
    return len(tokenizer.encode(text, add_special_tokens=False))


def serialize_context(extractor, spans):
    return ''.join(extractor.file_snippet_to_prompt_string(span.to_dict()) + '\n' for span in spans)


def fit_local_context(tokenizer, extractor, filename, prefix, suffix, input_budget):
    """Keep code nearest the hole, allocating space to both sides when needed."""
    def size(left, right):
        return token_count(tokenizer, extractor.get_infilling_prompt(filename, '', left, right))
    if size(prefix, suffix) <= input_budget:
        return prefix, suffix
    available = input_budget - size('', '')
    if available < 0:
        raise ValueError('Input token budget cannot fit the filename and FIM delimiters')
    left = tokenizer.encode(prefix, add_special_tokens=False)
    right = tokenizer.encode(suffix, add_special_tokens=False)
    left_count = min(len(left), available // 2)
    right_count = min(len(right), available - left_count)
    left_count = min(len(left), available - right_count)
    prefix = tokenizer.decode(left[-left_count:]) if left_count else ''
    suffix = tokenizer.decode(right[:right_count]) if right_count else ''
    # Re-tokenize the complete prompt: token boundaries may change at joins.
    while size(prefix, suffix) > input_budget:
        if len(prefix) >= len(suffix) and prefix:
            prefix = prefix[1:]
        elif suffix:
            suffix = suffix[:-1]
        else:
            raise ValueError('Input token budget cannot fit the FIM template')
    return prefix, suffix


def select_context_lines(lines, tokenizer, extractor, filename, prefix, suffix,
                         context_budget=2048, input_budget=8000):
    """Greedily select ranked whole lines, accounting for file headers and separators."""
    if context_budget < 0 or input_budget <= 0:
        raise ValueError('Token budgets must be nonnegative, with a positive input budget')
    selected = []
    for line in lines:
        candidate = selected + [line]
        intro = serialize_context(extractor, merge_adjacent_lines(candidate))
        if token_count(tokenizer, intro) > context_budget:
            continue
        prompt = extractor.get_infilling_prompt(filename, intro, prefix, suffix)
        if token_count(tokenizer, prompt) <= input_budget:
            selected = candidate
    return selected
