from __future__ import print_function
import pickle
import os.path
import os
import logging
import yaml
import re
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

logger = logging.getLogger(__name__)

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/documents.readonly']

# The ID of the google doc with the course content.
DOCUMENT_ID = '1KUTVBQRaXmw33nuA-Vj44mUIbRZIRgb_nIMj-QNowEc'

NEW_TAB_LINKS = [
    r'https://community.p2pu.org/t/introduce-yourself/1571/',
    r'https://docs.google.com/presentation/d/1_s0FFtAPG8MHxL8yRFrdxaI22obFrX_ZsONz-sIZJSY/edit#slide=id.g3c793ae459_0_0',
    r'https://www.p2pu.org/en/courses/',
    r'https://learningcircles.p2pu.org/en/accounts/register.*?',
    r'https://learningcircles.p2pu.org.*?',
    r'https://community.p2pu.org/t/what-topics-are-missing/2786',
]


def get_doc(document_id):
    """Shows basic usage of the Docs API.
    Prints the title of a sample document.
    """
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server()
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('docs', 'v1', credentials=creds)

    # Retrieve the documents contents from the Docs service.
    document = service.documents().get(documentId=document_id).execute()
    #print('The title of the document is: {}'.format(document.get('title')))
    return document


# Image formats to embed
IMAGE_FORMATS = ['jpeg', 'jpg', 'png', 'svg'] 

def smart_link(text, url, embed=False):
    #print('' + url + (' embed' if embed else '') )
    if any(map(lambda x: re.match(x, url), NEW_TAB_LINKS)):
        return f'<a href="{url}" target="_blank">{text}</a>'
    if not embed:
        return f"[{text}]({url})"

    if url.split('.')[-1].lower() in IMAGE_FORMATS:
        return f"![{text}]({url})"

    return f"[{text}]({url})"



def convert_to_course_outline(document):
    # document is formatted doc > body > content
    # content is a list of structural element, for now handle paragraph and table

    content = document.get('body').get('content')
    content = filter(lambda se: 'paragraph' in se, content)
    modules = []  # [{'title': '', sections: [  ] }]
    intro = ''
    list_run = False
    for se in content:
        paragraph = se['paragraph']
        page_break = any([True for e in paragraph['elements'] if 'pageBreak' in e])
        if page_break:
            logger.debug('Encoutered page break, stop processing document')
            print('Encoutered page break, stop processing document')
            # Stop processing the document after the first page break
            break
        text = ''
        elements = paragraph['elements']
        #elements = filter(lambda e: e.get('textRun','').strip('\n') == '', elements)
        for eidx, element in enumerate(elements):
            if 'textRun' in element:
                textRun = element.get('textRun')
                textContent = textRun['content'].strip('\n')
                if 'iframe' in textContent:
                    textContent = f'<div class="embed-responsive embed-responsive-4by3">{textContent}</div>'
                bold = textRun['textStyle'].get('bold', False)
                italic = textRun['textStyle'].get('italic', False)
                link = textRun['textStyle'].get('link', {}).get('url')
                if not textContent:
                    if any([bold, italic, link]):
                        logger.warning(f'Ignoring empty textRun. bold: {bold} italic: {italic} link: {link}')
                    continue
                if bold:
                    textContent = f'**{textContent.strip(" ")}** '
                if italic:
                    textContent = f'*{textContent}* '
                if link:
                    text += smart_link(textContent, link, embed=True)
                else:
                    text += textContent

        if paragraph.get('paragraphStyle',{}).get('namedStyleType') == 'HEADING_3':
            text = '## ' + text

        if paragraph.get('paragraphStyle',{}).get('namedStyleType') == 'HEADING_4':
            text = '### ' + text

        if 'bullet' in paragraph:
            bullet = paragraph['bullet']
            nesting_level = bullet.get('nestingLevel', 0)
            list_properties = document.get('lists', {}).get(bullet.get('listId'), {}).get('listProperties',{})
            style = list_properties.get('nestingLevels')[nesting_level]
            if 'glyphType' in style and not style['glyphType'] == 'GLYPH_TYPE_UNSPECIFIED':
                glyph = '1.'
            else:
                glyph = '-'
            text = '   '*nesting_level + glyph + ' ' + text
            list_run = True
        elif list_run:
            list_run = False
            if paragraph.get('paragraphStyle',{}).get('namedStyleType') not in ['HEADING_1', 'HEADING_2']:
                text = f'\n{text}'

        # Split text into sections
        if paragraph.get('paragraphStyle',{}).get('namedStyleType') == 'HEADING_1':
            modules += [{'title': text, 'sections': []}]
            print('Got new module ' + text)
            continue 

        if len(modules) == 0:
            intro += text + '\n'
            continue

        module = modules[-1]
        if paragraph.get('paragraphStyle',{}).get('namedStyleType') == 'HEADING_2':
            module['sections'] += [{'title': text, 'md': ''}]
            print('Got new section ' + text)
            text = '# ' + text + '\n'

        if len(module['sections']) == 0:
            continue

        section = module['sections'][-1]
        section['md'] += text + '\n'

    course_outline = {
        'modules': modules,
        'title': document.get('title'),
        'intro': intro,
    }
    return course_outline


def write_module(title, sections):
    #slug = title.replace(' ', '-').lower()
    slug = title
    path = os.path.join('modules', slug, '_posts')
    if not os.path.isdir(path):
        os.makedirs(path)
    for index, section in enumerate(sections):
        section_slug = section['title'].replace(':', '').lower()
        section_slug = section_slug.replace(' ', '-')
        section_slug = section_slug.replace('/', '-')
        filename = '2019-01-' + '{:02}-'.format(index+1) + section_slug + '.md'
        file_path = os.path.join(path, filename)
        with open(file_path, 'w') as f:
            f.write('---\n')
            f.write(f'title: "{section["title"]}"\n')
            f.write('---\n')
            f.write(section['md'])


def write_index(text_md):
    with open('./index.md', 'w') as f:
        f.write('---\n')
        f.write(f'layout: index\n')
        f.write('---\n')
        f.write(text_md)


def write_course(course_outline):
    if course_outline.get('intro'):
        write_index(course_outline.get('intro'))
    for module in course_outline.get('modules'):
        write_module(**module)
    modules = [m['title'] for m in course_outline.get('modules')]
    with open('_data/course.yml', 'r') as course_yml:
        course_data = yaml.safe_load(course_yml)
    course_data['title'] = course_outline.get('title')
    course_data['modules'] = modules
    with open('_data/course.yml', 'w') as course_yml:
        course_yml.write(yaml.dump(course_data))


if __name__ == '__main__':
    doc = get_doc(DOCUMENT_ID)
    course_outline = convert_to_course_outline(doc)
    write_course(course_outline)
