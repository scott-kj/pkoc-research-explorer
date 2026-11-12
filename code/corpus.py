from __future__ import annotations
import re, unicodedata
from dataclasses import dataclass
from pathlib import Path

TOKEN_RE = re.compile("\\b[\\w]+(?:[.’'\\-][\\w]+)*\\b", re.UNICODE)

NUMBERED_MARKER_RE = re.compile('(?m)^[ \\t]*(\\d{1,3})\\.[ \\t]*(?:\\r?\\n)?')

@dataclass(frozen=True)
class Context:
    context_id: str
    document_id: str
    year: int
    paragraph_number: int
    unit_number: int
    text: str

def normalise_text(text: str) -> str:
    text = unicodedata.normalize('NFKC', text)
    text = text.replace('’', "'").replace('‘', "'").replace('‐', '-')
    text = text.replace('–', '-').replace('—', '-')
    return text

def longest_numbered_sequence(text: str) -> tuple[list[re.Match[str]], int]:
    """Select the longest 1, 2, ..., n marker chain in document order."""
    markers = list(NUMBERED_MARKER_RE.finditer(text))
    if not markers:
        return ([], 0)
    lengths = [0] * len(markers)
    previous = [-1] * len(markers)
    best_for_number: dict[int, int] = {}
    for idx, marker in enumerate(markers):
        number = int(marker.group(1))
        if number == 1:
            lengths[idx] = 1
        elif number - 1 in best_for_number:
            prior = best_for_number[number - 1]
            lengths[idx] = lengths[prior] + 1
            previous[idx] = prior
        current = best_for_number.get(number)
        if lengths[idx] > 0 and (current is None or lengths[idx] >= lengths[current]):
            best_for_number[number] = idx
    end = max(range(len(markers)), key=lambda i: lengths[i])
    if lengths[end] == 0:
        return ([], len(markers))
    chosen_indices: list[int] = []
    while end >= 0:
        chosen_indices.append(end)
        end = previous[end]
    chosen_indices.reverse()
    return ([markers[i] for i in chosen_indices], len(markers))

def clean_paragraph_text(text: str) -> str:
    text = normalise_text(text).replace('\x0c', ' ')
    text = re.sub('(?m)^\\s*S/\\d{4}/\\d+(?:/Corr\\.\\d+)?\\s*$', ' ', text)
    text = re.sub('(?m)^\\s*\\d{1,3}\\s*$', ' ', text)
    text = re.sub('(?m)^\\s*\\d{2}-\\d{4,6}\\s*(?:\\([A-Z]\\))?.*$', ' ', text)
    text = re.sub('\\s+', ' ', text).strip()
    return text

def extract_blankline_paragraphs(raw: str) -> list[str]:
    """Fallback reflow for substantive UN documents that do not number paragraphs."""
    text = normalise_text(raw).replace('\x0c', '\n\n')
    artifact_patterns = ['^\\s*S/\\d{4}/\\d+(?:/Corr\\.\\d+)?\\s*$', '^\\s*\\d{1,3}/\\d{1,3}\\s*$', '^\\s*\\d{6}\\s*$', '^\\s*\\d{2}-\\d{4,6}(?:\\s*\\([A-Z]\\))?.*$', '^\\s*\\*\\d+\\*\\s*$', '^\\s*United Nations\\s*$', '^\\s*Security Council\\s*$']
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        if any((re.match(pattern, line) for pattern in artifact_patterns)):
            cleaned_lines.append('')
        else:
            cleaned_lines.append(line.strip())
    rough_blocks: list[str] = []
    current: list[str] = []
    for line in cleaned_lines:
        if not line:
            if current:
                rough_blocks.append(' '.join(current))
                current = []
            continue
        if current and re.search('[.!?][\\"\']?$', current[-1]) and re.match('^[A-Z]', line):
            rough_blocks.append(' '.join(current))
            current = []
        current.append(line)
    if current:
        rough_blocks.append(' '.join(current))
    blocks = [clean_paragraph_text(block) for block in rough_blocks]
    blocks = [block for block in blocks if len(TOKEN_RE.findall(block)) >= 12]
    merged: list[str] = []
    for block in blocks:
        if merged and merged[-1][-1:] not in '.!?;:' and block[:1].islower():
            merged[-1] = f'{merged[-1]} {block}'
        else:
            merged.append(block)
    return merged

def extract_numbered_paragraphs(path: Path, year: int) -> tuple[list[Context], dict[str, object]]:
    raw = path.read_text(encoding='utf-8', errors='replace')
    selected, all_marker_count = longest_numbered_sequence(raw)
    document_id = path.name.removesuffix('.pdf.txt')
    contexts: list[Context] = []
    segmentation_method = 'numbered paragraphs'
    annex_truncated = False
    if selected:
        for idx, marker in enumerate(selected):
            paragraph_number = int(marker.group(1))
            end = selected[idx + 1].start() if idx + 1 < len(selected) else len(raw)
            if idx + 1 == len(selected):
                final_segment = raw[marker.end():end]
                annex = re.search('(?im)^[ \\t\\f]*(?:Annex(?:[ \\t]+(?:[IVXLC]+|\\d+))?|United Nations Mission in Liberia:[^\\r\\n]*strength)[ \\t]*$', final_segment)
                if annex:
                    end = marker.end() + annex.start()
                    annex_truncated = True
            paragraph = clean_paragraph_text(raw[marker.end():end])
            if not paragraph:
                continue
            contexts.append(Context(context_id=f'{document_id}:p{paragraph_number:03d}', document_id=document_id, year=year, paragraph_number=paragraph_number, unit_number=paragraph_number, text=paragraph))
    else:
        segmentation_method = 'blank-line fallback (unnumbered document)'
        for paragraph_number, paragraph in enumerate(extract_blankline_paragraphs(raw), start=1):
            contexts.append(Context(context_id=f'{document_id}:u{paragraph_number:03d}', document_id=document_id, year=year, paragraph_number=paragraph_number, unit_number=paragraph_number, text=paragraph))
    summary = {'document_id': document_id, 'year': year, 'all_numeric_markers': all_marker_count, 'selected_numbered_paragraphs': len(contexts) if selected else 0, 'fallback_paragraphs': len(contexts) if not selected else 0, 'extracted_contexts': len(contexts), 'segmentation_method': segmentation_method, 'annex_truncated_after_final_context': annex_truncated, 'first_selected_number': contexts[0].paragraph_number if contexts else None, 'last_selected_number': contexts[-1].paragraph_number if contexts else None, 'sequence_complete': bool(selected and contexts and ([c.paragraph_number for c in contexts] == list(range(1, contexts[-1].paragraph_number + 1))))}
    return (contexts, summary)

@dataclass
class MappedText:
    text: str
    spans: list[tuple[int, int]]

    def slice(self, start: int, end: int | None=None) -> 'MappedText':
        return MappedText(self.text[start:end], self.spans[start:end])

    def strip(self) -> 'MappedText':
        left = len(self.text) - len(self.text.lstrip())
        right = len(self.text.rstrip())
        return self.slice(left, max(left, right))

    def sub(self, pattern: str, replacement: str) -> 'MappedText':
        parts, spans, cursor = ([], [], 0)
        for match in re.finditer(pattern, self.text):
            parts.extend((self.text[cursor:match.start()], replacement))
            spans.extend(self.spans[cursor:match.start()])
            origin = self.spans[match.start():match.end()]
            if replacement:
                if not origin:
                    raise ValueError('Cannot map insertion with no source span')
                interval = (min((a for a, _ in origin)), max((b for _, b in origin)))
                spans.extend([interval] * len(replacement))
            cursor = match.end()
        parts.append(self.text[cursor:])
        spans.extend(self.spans[cursor:])
        return MappedText(''.join(parts), spans)

def mapped_normalize(raw: str, offset: int=0) -> MappedText:
    """Map Unicode normalization clusters; reject unsupported compositions."""
    parts, spans, start = ([], [], 0)
    for index in range(1, len(raw) + 1):
        if index < len(raw) and unicodedata.combining(raw[index]):
            continue
        cluster = raw[start:index]
        normalized = unicodedata.normalize('NFKC', cluster)
        normalized = normalized.translate(str.maketrans({'’': "'", '‘': "'", '‐': '-', '–': '-', '—': '-'}))
        parts.append(normalized)
        spans.extend([(offset + start, offset + index)] * len(normalized))
        start = index
    return MappedText(''.join(parts), spans)

def mapped_clean(value: MappedText) -> MappedText:
    value = value.sub('\\f', ' ')
    value = value.sub('(?m)^\\s*S/\\d{4}/\\d+(?:/Corr\\.\\d+)?\\s*$', ' ')
    value = value.sub('(?m)^\\s*\\d{1,3}\\s*$', ' ')
    value = value.sub('(?m)^\\s*\\d{2}-\\d{4,6}\\s*(?:\\([A-Z]\\))?.*$', ' ')
    return value.sub('\\s+', ' ').strip()

def join_mapped(parts: list[MappedText]) -> MappedText:
    texts, spans = ([], [])
    for part in parts:
        if texts:
            texts.append(' ')
            spans.append((spans[-1][1], part.spans[0][0]))
        texts.append(part.text)
        spans.extend(part.spans)
    return MappedText(''.join(texts), spans)

def fallback_mapped(raw: str, parser: SimpleNamespace) -> list[MappedText]:
    value = mapped_normalize(raw).sub('\\f', '\n\n')
    if value.text != parser.normalise_text(raw).replace('\x0c', '\n\n'):
        raise ValueError('Unsupported cross-cluster Unicode normalization')
    patterns = ['^\\s*S/\\d{4}/\\d+(?:/Corr\\.\\d+)?\\s*$', '^\\s*\\d{1,3}/\\d{1,3}\\s*$', '^\\s*\\d{6}\\s*$', '^\\s*\\d{2}-\\d{4,6}(?:\\s*\\([A-Z]\\))?.*$', '^\\s*\\*\\d+\\*\\s*$', '^\\s*United Nations\\s*$', '^\\s*Security Council\\s*$']
    lines, cursor = ([], 0)
    for line_with_end in value.text.splitlines(keepends=True):
        line = line_with_end.splitlines()[0] if line_with_end.splitlines() else ''
        mapped = value.slice(cursor, cursor + len(line)).strip()
        lines.append(MappedText('', []) if any((re.match(p, line) for p in patterns)) else mapped)
        cursor += len(line_with_end)
    rough, current = ([], [])
    for line in lines:
        if not line.text:
            if current:
                rough.append(join_mapped(current))
                current = []
            continue
        if current and re.search('[.!?][\\"\']?$', current[-1].text) and re.match('^[A-Z]', line.text):
            rough.append(join_mapped(current))
            current = []
        current.append(line)
    if current:
        rough.append(join_mapped(current))
    blocks = [mapped_clean(block) for block in rough]
    blocks = [block for block in blocks if len(parser.TOKEN_RE.findall(block.text)) >= 12]
    merged = []
    for block in blocks:
        if merged and merged[-1].text[-1:] not in '.!?;:' and block.text[:1].islower():
            merged[-1] = join_mapped([merged[-1], block])
        else:
            merged.append(block)
    return merged

def source_segments(raw: str, parser: SimpleNamespace) -> list[tuple[int, int, MappedText]]:
    selected, _ = parser.longest_numbered_sequence(raw)
    if not selected:
        return [(value.spans[0][0], value.spans[-1][1], value) for value in fallback_mapped(raw, parser)]
    output = []
    for index, marker in enumerate(selected):
        start = marker.end()
        end = selected[index + 1].start() if index + 1 < len(selected) else len(raw)
        if index + 1 == len(selected):
            annex = re.search('(?im)^[ \\t\\f]*(?:Annex(?:[ \\t]+(?:[IVXLC]+|\\d+))?|United Nations Mission in Liberia:[^\\r\\n]*strength)[ \\t]*$', raw[start:end])
            if annex:
                end = start + annex.start()
        mapped = mapped_normalize(raw[start:end], start)
        if mapped.text != parser.normalise_text(raw[start:end]):
            raise ValueError('Unsupported cross-cluster Unicode normalization')
        mapped = mapped_clean(mapped)
        if mapped.text:
            output.append((start, end, mapped))
    return output
