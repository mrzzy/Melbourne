import time
import os
import re

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
import requests
from bs4 import BeautifulSoup
import pickle

from pprint import pprint

# User Setup
download_path = 'downloads'

create_attachment_folders = False

exempted_courses = ['Notebook Service Survey', 'INNOVATION TOOLKIT(7INNOVA_010235)', 'Multiple Internships Opportunities']
exempted_file_extensions = ['.mp3', '.mov']

webdriver_type = 'chrome'

# Setup
login_url = 'https://mel.np.edu.sg/auth-saml/saml/login?apId=_155_1&redirectUrl=https://mel.np.edu.sg/ultra'
home_url = 'https://mel.np.edu.sg/ultra/course'
api_url = 'https://mel.np.edu.sg/learn/api/public/v1'
content_fmt_url = 'https://mel.np.edu.sg/webapps/blackboard/content/listContent.jsp?course_id={}&content_id={}'
download_url = 'https://mel.np.edu.sg'

bounce_duration = 0.5

api_count = 0
download_count = 0

def convert2valid_file_name(file_name):
    return re.sub(r'(\\|\/|\:|\*|\?|\"|\<|\>|\|)', '-', file_name)

def wait_till(func, *args, sleep = 0.5, timeout = None, **kwargs):
    start = time.time()
    while True:
        try:
            element = func(*args, **kwargs)
        except:
            sleep2 = sleep
            if timeout:
                if time.time() - start > timeout:
                    return False
                elif time.time() - start + sleep > timeout:
                    sleep2 = timeout - (time.time() - start)
                    
            time.sleep(sleep2)
        else:
            break

    return True

def get_children(session, base_url, url):
    global api_count
    print('URL Accessed:', base_url + url)
    api_count += 1
    ret = {}
    response = session.get(base_url + url)
    response_json = response.json()
    if response_json.get('results'):        
        for content in response_json['results']:
            content_id = content['id']
            content_handler = content['contentHandler']['id']
            
            ret[content_id] = {'name': convert2valid_file_name(content['title'])}
            if content_handler == 'resource/x-bb-folder':
                ret[content_id]['content type'] = 'folder'
                if content['availability']['allowGuests'] and content['availability']['available'] == 'Yes':
                    ret[content_id]['content'] = get_children(session, base_url, '/{}/children'.format(content_id))
                else:
                    ret[content_id]['content'] = 'restricted'
            elif content_handler == 'resource/x-bb-document':
                ret[content_id]['content type'] = 'document'
                if content.get('body'):
                    ret[content_id]['text'] = content['body']
            else:
                ret[content_id]['content type'] = content_handler
    elif response_json.get('status'):
        if response_json['status'] == 403:
            return 'Dev: Status 403'
        else:
            return 'Dev: Uncatched Error - Status: {}'.format(response_json['status'])
    else:
        return 'Dev: Uncatched Error - No Result or Status Returned.'

    return ret
    
def download_file(session, url, name, path, overwrite = False): ### Thanks StackOverflow
    global download_count
    if not os.path.isdir(path):
        os.makedirs(path)
    if os.path.splitext(name)[1] not in exempted_file_extensions:
        if not os.path.exists(os.path.join(path, name)) or overwrite:
            print('Download URL:', url)
            download_count += 1
            r = session.get(url, stream=True)
            with open(os.path.join(path, name), 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024): 
                    if chunk:
                        f.write(chunk)
    return name

def download_course_attachments(session, course_id, structure, base):
    attachments = []
    for content_id, content_attributes in structure.items():
        if content_attributes['content type'] == 'folder':
            if type(content_attributes['content']) is dict:
                child_attachments = download_course_attachments(session, course_id, content_attributes['content'], base + [content_attributes['name']])
                if child_attachments:
                    print('URL Accessed:', content_fmt_url.format(course_id, content_id))
                    response = session.get(content_fmt_url.format(course_id, content_id))
                    bs_html = BeautifulSoup(response.text, 'lxml')
                    for child_content_id in child_attachments:
                        bs_children = bs_html.find('div', id=child_content_id).parent.find_all('a', target='_blank')
                        structure[content_id]['content'][child_content_id]['content'] = {}
                        for bs_child in bs_children:
                            attachment_link = bs_child['href']
                            file_name = bs_child.text
                            if attachment_link[0] == '/':
                                attachment_link = download_url + attachment_link
                            structure[content_id]['content'][child_content_id]['content'][file_name] = attachment_link
                            if create_attachment_folders:
                                path = base + [content_attributes['name'], content_attributes['content'][child_content_id]['name']]
                            else:
                                path = base + [content_attributes['name']]
                                
                            download_file(session, attachment_link, convert2valid_file_name(file_name), os.path.join(download_path, *path)) 
                    
        elif content_attributes['content type'] == 'document':
            attachments.append(content_id)

    return attachments


def initialise_browser(webdriver_type, auth, webdriver_path = None):
    if webdriver_type == 'chrome':
        if webdriver_path:
            browser = webdriver.Chrome(webdriver_path)
        else:
            browser = webdriver.Chrome('chromedriver.exe')
    elif webdriver_type == 'firefox':
        if webdriver_path:
            browser = webdriver.Firefox(webdriver_path)
        else:
            browser = webdriver.Firefox()

    ### Step Null - Preperation
    browser.get(login_url)
    # Sign in
    username_input = browser.find_element_by_id('i0116')
    username_input.send_keys(auth[0])

    next_button = browser.find_element_by_xpath('//input[@value=\"Next\"]')
    next_button.click()

    password_input = browser.find_element_by_id('i0118')
    password_input.send_keys(auth[1])

    wait_till(browser.find_element_by_xpath, '//input[@value=\"Sign in\"]')
    submit_button = browser.find_element_by_xpath('//input[@value=\"Sign in\"]')
    submit_button.click()

    no_button = browser.find_element_by_xpath('//input[@value=\"No\"]')
    no_button.click()

    # Transfer Session to Requests
    cookies = browser.get_cookies()

    session = requests.Session()
    for cookie in cookies:
        name = cookie.pop('name')
        value = cookie.pop('value')
        session.cookies.set(name, value)

    return browser, session

def obtain_courses(browser):
    ### Step 0 - Get Courses Automatically
    actions = ActionChains(browser)
    # Part 1 - Get Home Page Source
    wait_till(browser.find_element_by_id, 'course-columns-current')

    # Part 2 - Load Unloaded Modules
    bounce = -1
    while True:
        html_unloaded_modules = browser.find_elements_by_xpath('//div/a[@id=\'course-link-\']')

        if not html_unloaded_modules:
            break

        html_element = html_unloaded_modules[bounce].find_element_by_xpath('../..')
        actions.move_to_element(html_element).perform()
        time.sleep(bounce_duration)
        bounce = bounce * -1 - 1 # Toggle

    # Part 3 - Get Modules
    html_current_modules = browser.find_element_by_id('course-columns-current')

    html_modules = browser.find_elements_by_css_selector('a[id^=\'course-link-\']')

    structure = {}
    print('Course ID Found:')
    for html_module in html_modules:
        html_course_id = html_module.get_attribute('id')
        course_id = html_course_id[12:]
        structure[course_id] = None
        print(course_id)
    print()

    return structure

def obtain_structure(session, structure):
    ### Step 1 - Blackboard Api : Structure of Attachments
    # Part 1 - BlackBoard API
    for course_id in structure.keys():
        print('Course ID:', course_id)
        course_attributes_response = session.get(api_url + '/courses/{}'.format(course_id))
        course_attributes_response_json = course_attributes_response.json()

        structure[course_id] = {'name': course_attributes_response_json['name'],
                                'content_type': 'course',
                                'content': get_children(session, api_url + '/courses/{}/contents'.format(course_id), '')}

    with open('structure', 'wb') as file:
        pickle.dump(structure, file)

def get_attachments(session):
    ### Step 2 - Getting Attachments
    with open('structure', 'rb') as file:
        structure = pickle.load(file)

    for course_id, course_attributes in structure.items():
        if course_attributes['name'] not in exempted_courses:
            download_course_attachments(session, course_id, course_attributes['content'], [course_attributes['name']])

    with open('structure', 'wb') as file:
        pickle.dump(structure, file)

if __name__ == '__main__':
    with open('auth', 'rb') as file:
        auth = pickle.load(file)
    
    browser, session = initialise_browser(webdriver_type, auth)
    structure = obtain_courses(browser)
    obtain_structure(session, structure)
    get_attachments(session)
