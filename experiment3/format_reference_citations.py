"""Format existing numeric citations as superscript internal Word links."""
from copy import deepcopy
from pathlib import Path
from zipfile import ZipFile
import hashlib
import json
import re
import shutil
from lxml import etree

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS = {'w': W}
Q = lambda name: f'{{{W}}}{name}'
PATTERN = re.compile(r'\[([1-8])\]')


def text(element):
    return ''.join(element.xpath('.//w:t/text()', namespaces=NS))


def text_run(original, value, citation=False):
    run = etree.Element(Q('r'), attrib=dict(original.attrib))
    properties = original.find(Q('rPr'))
    properties = deepcopy(properties) if properties is not None else etree.Element(Q('rPr'))
    if citation:
        for tag in ['vertAlign', 'u', 'color']:
            for child in properties.findall(Q(tag)):
                properties.remove(child)
        etree.SubElement(properties, Q('color'), {Q('val'): '000000'})
        etree.SubElement(properties, Q('u'), {Q('val'): 'none'})
        etree.SubElement(properties, Q('vertAlign'), {Q('val'): 'superscript'})
    if len(properties):
        run.append(properties)
    node = etree.SubElement(run, Q('t'))
    node.text = value
    if value[:1].isspace() or value[-1:].isspace():
        node.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    return run


def format_reference_citations(path):
    path = Path(path)
    with ZipFile(path) as package:
        entries = [(info, package.read(info.filename)) for info in package.infolist()]
    data = dict((info.filename, value) for info, value in entries)
    root = etree.fromstring(data['word/document.xml'])
    before_text = root.xpath('.//w:t/text()', namespaces=NS)
    body = root.find(Q('body'))
    paragraphs = body.findall(Q('p'))
    heading = next(p for p in paragraphs if text(p).strip().startswith('七') and '参考文献' in text(p))
    heading_position = list(body).index(heading)
    references = {}
    for p in paragraphs[paragraphs.index(heading) + 1:]:
        match = re.match(r'^\[([1-8])\]', text(p).strip())
        if match:
            references[int(match.group(1))] = p
    assert set(references) == set(range(1, 9)), 'Expected eight bibliography entries'
    bookmark_ids = [int(value) for value in root.xpath('.//w:bookmarkStart/@w:id', namespaces=NS)]
    next_id = max(bookmark_ids, default=-1) + 1
    for number, paragraph in references.items():
        name = f'EcoSortRef_{number}'
        existing = root.xpath('.//w:bookmarkStart[@w:name=$name]', namespaces=NS, name=name)
        if existing:
            assert existing[0].getparent() is paragraph
            continue
        start = etree.Element(Q('bookmarkStart'), {Q('id'): str(next_id), Q('name'): name})
        end = etree.Element(Q('bookmarkEnd'), {Q('id'): str(next_id)})
        paragraph.insert(1 if paragraph.find(Q('pPr')) is not None else 0, start)
        paragraph.append(end)
        next_id += 1
    count = 0
    for block in list(body)[:heading_position]:
        candidates = [block] if block.tag == Q('p') else list(block.iter(Q('p')))
        for paragraph in candidates:
            for run in list(paragraph.findall(Q('r'))):
                value = text(run)
                matches = list(PATTERN.finditer(value))
                if not matches:
                    continue
                assert all(c.tag in {Q('rPr'), Q('t')} for c in run), 'Refuse to rewrite a run with non-text content'
                position = list(paragraph).index(run)
                parts = []
                previous = 0
                for match in matches:
                    if match.start() > previous:
                        parts.append(text_run(run, value[previous:match.start()]))
                    number = int(match.group(1))
                    link = etree.Element(Q('hyperlink'), {Q('anchor'): f'EcoSortRef_{number}', Q('history'): '1', Q('tooltip'): f'跳转到参考文献 [{number}]'})
                    link.append(text_run(run, match.group(0), citation=True))
                    parts.append(link)
                    previous = match.end()
                    count += 1
                if previous < len(value):
                    parts.append(text_run(run, value[previous:]))
                paragraph.remove(run)
                for offset, part in enumerate(parts):
                    paragraph.insert(position + offset, part)
    # Text, figures, tables and all unrelated DOCX package parts stay untouched.
    assert ''.join(before_text) == ''.join(root.xpath('.//w:t/text()', namespaces=NS))
    links = root.xpath('.//w:hyperlink[starts-with(@w:anchor,"EcoSortRef_")]', namespaces=NS)
    assert len(links) >= 8
    for link in links:
        number = int(text(link).strip('[]'))
        assert link.get(Q('anchor')) == f'EcoSortRef_{number}'
        assert link.xpath('./w:r/w:rPr/w:vertAlign/@w:val', namespaces=NS) == ['superscript']
    serialized = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
    temporary = path.with_suffix('.citation-tmp.docx')
    with ZipFile(temporary, 'w') as package:
        for info, value in entries:
            package.writestr(info, serialized if info.filename == 'word/document.xml' else value)
    temporary.replace(path)
    return {'new_citation_links': count, 'total_citation_links': len(links), 'reference_bookmarks': 8,
            'all_document_text_preserved': True, 'only_package_part_changed': 'word/document.xml',
            'output_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    report = root / 'reports/实验三报告_循智EcoSort.docx'
    records = root / 'records/superscript_reference_links'
    records.mkdir(parents=True, exist_ok=True)
    backup = records / 'before.docx'
    if not backup.exists():
        shutil.copy2(report, backup)
    result = format_reference_citations(report)
    (records / 'validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))
