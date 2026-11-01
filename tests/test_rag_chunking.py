from api.rag import chunks


def test_chunks_empty_text():
    assert chunks('   ') == []


def test_chunks_preserve_content_and_overlap():
    text = ' '.join(f'word{i}' for i in range(700))
    result = chunks(text, size=500, overlap=80)
    assert len(result) > 1
    assert result[0].startswith('word0')
    assert result[-1].endswith('word699')
    assert all(result)


def test_chunks_short_document_is_single_chunk():
    assert chunks('A short policy paragraph.') == ['A short policy paragraph.']
