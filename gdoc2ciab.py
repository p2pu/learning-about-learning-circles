from __future__ import print_function
import pickle
import os.path
import os
import yaml
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/documents.readonly']

# The ID of a sample document.
DOCUMENT_ID = '1kEk1FPgjX3gjoueXbodY-5CaEGM9ah69MRmjYbXT7Lo'

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


def smart_link(text, url, embed=False):
    #print('' + url + (' embed' if embed else '') )
    if not embed:
        return f"[{text}]({url})"

    if url.split('.')[-1].lower() in ['jpg', 'png', 'svg']:
        return f"![{text}]({url})"

    return f"[{text}]({url})"


def convert_to_course_outline(document):
    # document is formatted doc > body > content
    # content is a list of structural element, for now handle paragraph and table

    content = document.get('body').get('content')
    content = filter(lambda se: 'paragraph' in se, content)
    modules = []  # [{'title': '', sections: [  ] }]
    for se in content:
        paragraph = se['paragraph']
        text = ''
        for eidx, element in enumerate(paragraph['elements']):
            if 'textRun' in element:
                textRun = element.get('textRun')
                link = textRun['textStyle'].get('link', {}).get('url')
                textContent = element['textRun']['content'].strip('\n')
                if link:
                    text += smart_link(textContent, link, embed=True)
                else:
                    text += textContent

        if paragraph.get('paragraphStyle',{}).get('namedStyleType') == 'HEADING_1':
            modules += [{'title': text, 'sections': []}]
            continue 

        if len(modules) == 0:
            continue
        module = modules[-1]
        if paragraph.get('paragraphStyle',{}).get('namedStyleType') == 'HEADING_2':
            module['sections'] += [{'title': text, 'md': ''}]
            text = '# ' + text + '\n'

        if len(module['sections']) == 0:
            continue
        section = module['sections'][-1]
        if paragraph.get('paragraphStyle',{}).get('namedStyleType') == 'HEADING_3':
            text = '# ' + text
        if 'bullet' in paragraph:
            # TODO - handle list type, need to lookup document.lists
            nesting_level = paragraph['bullet'].get('nestingLevel', 0)
            text = '   '*nesting_level + '- ' + text
          
        section['md'] += text + '\n'
    return modules


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


def write_course(course_outline):
    for module in course_outline:
        write_module(**module)
    modules = [m['title'] for m in course_outline]
    with open('_data/course.yml', 'r') as course_yml:
        course_data = yaml.safe_load(course_yml)
    course_data['modules'] = modules
    with open('_data/course.yml', 'w') as course_yml:
        course_yml.write(yaml.dump(course_data))


if __name__ == '__main__':
    doc = get_doc(DOCUMENT_ID)
    course_outline = convert_to_course_outline(doc)
    write_course(course_outline)
