import os

import pickle

def prompt_user(options, exit=True, title='Options', details=None):
    if details is None:
        details = [''] * len(options)

    print()
    print(title)
    print('=' * len(title))
    for index, (option, detail) in enumerate(zip(options, details)):
        print('{:4s}{}  {}'.format('[{}]'.format(str(index + 1)), option, detail))

    if exit:
        print('{:4s}{}'.format('[0]', 'Exit'))

    while True:
        user_input = input('Option: ')
        try:
            user_input = int(user_input)
        except:
            pass
        else:
            if user_input < len(options) + 1:
                if 0 < user_input:
                    break
                elif exit and user_input == 0:
                    break

    print()

    return options[user_input - 1] if user_input != 0 else 'Exit'

# Setup authentication file
auth = None
if os.path.exists('auth'):
    try:
        with open('auth', 'rb') as file:
            auth = pickle.load(file)
    except:
        print('Auth File is invalid')
        os.remove('auth')
            
if auth is None:
    print('Authentication Needed for Outlook')
    email = input('Enter Email: ')
    password = input('Enter Password: ')
    auth = (email, password)
    with open('auth', 'wb') as file:
        pickle.dump(auth, file)

# Main
from core import *
browser, session = None, None

while True:
    user = prompt_user(['Auto', 'Manual'], title='Preference')
    if user == 'Exit':
        if browser: browser.quit()
        break
    else:
        if user == 'Auto':
            if browser is None: browser, session = initialise_browser(webdriver_type, auth)
            print('Obtaining Courses Automatically...')
            print('Please ensure that the browser is not minimised')
            structure = obtain_courses(browser)
            print('Obtaining File Structure...')
            obtain_structure(session, structure)
            print('Downloading File Attachments')
            get_attachments(session)
            
        elif user == 'Manual':
            user = prompt_user(['Obtain File Structure', 'Download Attachments'], title='Manual')
            
            if user == 'Obtain File Structure':
                if browser is None: browser, session = initialise_browser(webdriver_type, auth)
                print('Obtaining Courses Automatically...')
                print('Please ensure that the browser is not minimised')
                structure = obtain_courses(browser)
                print('Obtaining File Structure...')
                obtain_structure(session, structure)
                
            elif user == 'Download Attachments':
                if browser is None: browser, session = initialise_browser(webdriver_type, auth)
                print('Downloading File Attachments')
                get_attachments(session)
