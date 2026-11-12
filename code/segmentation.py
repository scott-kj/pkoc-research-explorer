import re

ABBREVIATIONS = {'mr', 'mrs', 'ms', 'dr', 'prof', 'gen', 'lt', 'col', 'sgt', 'capt', 'rev', 'hon', 'st', 'no', 'nos', 'para', 'paras', 'art', 'arts', 'fig', 'figs', 'vol', 'pp', 'e.g', 'i.e', 'u.s', 'u.n', 'u.k'}

def sentence_spans(text):
    """Versioned rules: boundaries inside original paragraphs; offsets retained.

    Terminal punctuation followed by whitespace and an uppercase/digit/quote
    starts a unit, except protected titles, initials, decimal/abbreviation forms.
    Trailing headings/fragments remain units; no text is dropped.
    """
    cuts = [0]
    for match in re.finditer('[.!?]+[\\"\\u201d\\u2019\\)\\]]*\\s+(?=[A-Z0-9\\"\\u201c(])', text):
        punct = match.start()
        prefix = text[:punct]
        word_match = re.search('([A-Za-z.]+)$', prefix)
        word = word_match.group(1) if word_match else ''
        if text[punct] == '.' and (word.lower() in ABBREVIATIONS or re.fullmatch('[A-Z]', word) or re.fullmatch('(?:[A-Z]\\.)+[A-Z]', word)):
            continue
        if match.end() > cuts[-1]:
            cuts.append(match.end())
    if cuts[-1] != len(text):
        cuts.append(len(text))
    return [(a, b) for a, b in zip(cuts, cuts[1:]) if text[a:b].strip()]
