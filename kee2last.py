#!/usr/bin/env python3

import os
import pprint
import sys
import xml.etree.ElementTree as ET

modified_entries = []

# LastPass special URL to indicate a note is a secured note
SECURE_NOTE_URL = 'http://sn'

# Name of the shared folder within KeePass that holds all shared passwords
OLD_SHARED_FOLDER_NAME = 'SharedPasswords'

# Name of the shared folder within LastPass that holds all shared passwords
NEW_SHARED_FOLDER_NAME = 'New-Folder-Name'

def get_item_template(item, local_variables):
    """Function that substitutes values in a dictionary with variables whose
    name match the keys.

    """

    if not isinstance(item, dict):
        return {}

    for key in item:
        key_lower = key.casefold()

        # https://docs.python.org/3.6/library/functions.html#locals
        if key_lower in local_variables and local_variables[key_lower]:
            item[key] = local_variables[key_lower]

    return item

def get_secure_note_item(url=SECURE_NOTE_URL):
    """

    """

    item = {
        'URL': url,
        'Notes': ''
    }

    return item

def get_server_item(hostname='', notes=''):
    """Allows quick customization of fields for a LastPass Server item type.

    """

    item = {
        'NoteType': 'Server',
        'Language': 'en-US',
        # You can set a default hostname here, for example, if most server
        # accounts are AD accounts
        'Hostname': '',
        'Username': '',
        'Password': '',
        'Notes': ''
    }

    return get_item_template(item, locals())


def get_database_item(type='', hostname='', port='', database='', sid='', alias='', notes=''):
    """Allows quick customization of fields for a LastPass Database item type.

    """

    item = {
        'NoteType': 'Database',
        'Language': 'en-US',
        'Type': 'Oracle',
        'Hostname': '',
        'Port': '1521',
        'Database': '',
        'Username': '',
        'Password': '',
        'SID': '',
        'Alias': '',
        'Notes': ''
    }

    item = get_item_template(item, locals())

    if not item['Notes']:
        item['Notes'] = '//' + item['Hostname'] + ':' + item['Port'] + '/' + item['Database']

    return item


def delete_histories(node):
    """Recursively deletes all <History> objects from the password entries, as
    they tend to confuse the LastPass importer.

    """

    # Recursion base case: node does not have a <Group>
    groups = node.findall("./Group")

    # See if there are entries
    entries = node.findall("./Entry")
    # histories = node.findall("./Entry/History")
    count = 0

    for entry in entries:
        found = False
        histories = entry.findall("./History")
        for history in histories:
            if history in entry:
                found = True
                entry.remove(history)

        if found:
            count += 1

    for group in groups:
        count += delete_histories(group)

    return count

def get_entry_value(entry, name=''):
    """Returns the string value from the given entry in the KeePass XML.

    """

    if not isinstance(entry, ET.Element) or not name:
        return ''

    key = entry.find("./String[Key='%s']" % (name))

    if key is None:
        return ''

    value = key.find("./Value")

    return value.text if value is not None else ''

def set_entry_text(entry, name, new_value=''):
    """Sets the text content of the given entry in the KeePass XML.

    """

    if not isinstance(entry, ET.Element) or not name:
        return False

    key = entry.find("./String[Key='%s']" % (name))

    if key is None:
        return False

    value = key.find("./Value")

    if value is None:
        print('String value for key %s could not be found...')
        # TODO: If this is not found, how about we add it? We have never
        # encountered this scenario.
        sys.exit(1)
        return False

    value.text = new_value
    # print('Set new value to field %s: %s' % (name, new_value))

    return True

def str_is_url(url=''):
    """Returns True if the specified string is possible a URL

    """

    return any(x in (str(url)).casefold() for x in ['http://', 'https://']) and \
        url.casefold() != SECURE_NOTE_URL

def modify_entry(entry, template=None):
    """Modifies a KeePass password entry using the given template dictionary. If
    no template is provided, the entry will be handled according to the LastPass
    import process, which means that if a URL is provided, the item will be
    imported as a website password. If not, by default, items are secure notes.
    Secure notes seem to be the basis for all custom types in LastPass, like
    Database and Server, the two types ERDS will use the most.

    """

    is_secure_note_template = 'URL' in template and SECURE_NOTE_URL in template['URL']

    # 1. Capture the current notes, username, password, url, and title;
    # These items are common to all KeePass password entries
    notes = get_entry_value(entry, 'Notes')
    username = get_entry_value(entry, 'UserName')
    password = get_entry_value(entry, 'Password')
    url = get_entry_value(entry, 'URL')
    # Fix titles, changing tabs to spaces and stripping end spaces
    title = get_entry_value(entry, 'Title').replace('\t', ' ').strip()

    is_secure_note = url == SECURE_NOTE_URL
    is_website = str_is_url(url)

    # 1a. Add the title of this entry to the modified_entries list so it is
    # not accidentally processed multiple times. This is useful for "as-is"
    # items

    # 2. To prevent accidentally formatting the notes again, if the username
    # XML is missing or the notes start with 'NoteType:', then stop here
    if (notes is not None and 'NoteType:' in notes) or is_secure_note or is_website:
        note_type = 'Unknown'
        # Get the first line in the string
        if notes:
            note_type = 'Database'
            note_first_line = notes.split("\n")[0]
            note_type = note_first_line[len('NoteType:'):]
        if is_website:
            note_type = 'Website'
        if is_secure_note:
            note_type = 'Secure Note'
        print('Entry is of type "%s" and will not be changed.' % (note_type))
        return False

    # 3. Do not modify the entry if an empty template is provided, leaving it
    # to be imported as-is
    # Empty dictionaries evaluate to False in Python (wow)
    if not isinstance(template, dict) or not template:
        print('No template provided; entry will be imported as-is.')
        return False

    # 4. Update the template object with the variables whose name matches
    # keys in the template
    for key in template:
        key_lower = key.casefold()

        if key_lower not in locals():
            continue

        # If the variable is not empty, set the template key to that value
        if locals()[key_lower]:
            template[key] = locals()[key_lower]

    # 5. Normalize a few fields...
    # Attempt to set the hostname if it's provided from KeePass
    if url and 'Hostname' in template and not template['Hostname']:
        print('Using URL "%s" for empty hostname...' % (url))
        template['Hostname'] = url

    if 'Alias' in template:
        template['Alias'] = str(template['Alias']).upper()

    if 'Hostname' in template:
        template['Hostname'] = str(template['Hostname']).lower()

    if 'Username' in template:
        template['Username'] = str(template['Username']).lower()

    # 6. Using the template, create a string that will be the new note text:
    new_note = ''
    for key in template:
        new_note += '%s:%s\n' % (key, template[key])

    # Replace all tabs in notes with a space
    new_note = new_note.replace('\t', ' ')

    # 7. Set the note and title of the entry to the new value
    # If we are working with a secure note, set the URL
    set_entry_text(entry, 'Notes', new_note)
    set_entry_text(entry, 'Title', title)
    # Set the URL field as needed for secure notes
    if is_secure_note_template:
        url = SECURE_NOTE_URL
        print("Set URL as needed for secure note to '%s'..." % (url))
        set_entry_text(entry, 'URL', url)
    # If we are setting the URL for a website...
    if 'URL' in template and str_is_url(template['URL']) and template['URL'] != url:
        print("Set URL as needed for website to '%s'..." % (template['URL']))
        set_entry_text(entry, 'URL', template['URL'])

    # 8. If a special NoteType is used, delete all <String> objects except
    # title and notes
    if 'NoteType' in template:
        safe_strings = ['Title', 'Notes']

        all_strings = entry.findall("./String")

        for string in all_strings:
            key = string.find("./Key")

            # Remove all <String> objects that are not safe
            # This prevents extra, and potentially sensitive text, in the Notes
            # field
            if key.text not in safe_strings:
                entry.remove(string)

    # This indicates that an entry was modified
    print("Entry was modified.")
    return True


def find_entries(node, search='', template=None):
    """Uses recursion to find all entries whose title begins with or equals the
    search term, then uses the specified template to fill in missing fields.

    Note: An empty string as a search term matches all entries!

    """

    # Recursion base case: node has no groups
    groups = node.findall("./Group")
    entries = node.findall("./Entry")
    num_groups = len(groups)
    count = 0

    for entry in entries:

        title = get_entry_value(entry, 'Title')

        if search.casefold() in title.casefold():
            print('Attempting to modify entry "%s"...' % (title))
            if not isinstance(template, dict):
                template = {}
            if modify_entry(entry, template):
                count = count + 1

    for group in groups:
        count += find_entries(group, search, template)

    return count

def delete_sample_entries(root_group=None):
    """

    """

    if not isinstance(root_group, ET.Element):
        return False

     # Delete sample entries
    entries = root_group.findall("./Entry")

    sample_entries_found = False

    for entry in entries:
        title = get_entry_value(entry, 'Title')
        if 'Sample Entry'.casefold() in title.casefold():
            root_group.remove(entry)
            print('Deleted entry "%s" from root group.' % (title))
            sample_entries_found = True

    return sample_entries_found


def rename_root_group(root_group=None):
    """Renames the root group to Shared-ITS-ERDS to match the destination folder
    name in LastPass.

    """

    if not isinstance(root_group, ET.Element):
        return False

    # print('root_group tag: %s' % (root_group.tag))

    name_nodes = root_group.findall("./Name")

    for node in name_nodes:
        node.text = NEW_SHARED_FOLDER_NAME
        print('Renamed root group name from "%s" to "%s"' % (OLD_SHARED_FOLDER_NAME, node.text))
        return True

    return False


def process():
    """Cleans up the KeePass XML for import to suitable LastPass item types, like
    database and server, which are better suited than the default website
    password item types.

    """

    # filename = input('Specify the path of the KeePass XML file: ')
    filename = '~/Downloads/SharedPasswords.xml'

    # Replace any tilde (~) with the home directory
    filename = filename.replace("~", os.getenv('HOME'))

    if not os.path.exists(filename):
        print('The file "%s" does not exist.' % (filename))
        return process()

    # Get the root of the XML tree from the given filename, since it exists.
    tree = ET.parse(filename)
    # Not the actual tree root, but there is an object called <Root>
    root = tree.find("./Root")
    # The root group that contains all passwords
    root_group = root.find("./Group[Name='%s']" % (OLD_SHARED_FOLDER_NAME))

    # Change the name of the main folder to its new name
    # https://docs.python.org/3.6/library/xml.etree.elementtree.html#xml.etree.ElementTree.Element.find
    if root_group:
        print('Found a root group with the name "%s"...' % (OLD_SHARED_FOLDER_NAME))

        # Delete any sample entries from the root group
        delete_sample_entries(root_group)

        # Rename the root group to match the new name in LastPass
        rename_root_group(root_group)

    # Recursively delete all history objects as they are not needed
    num_histories = delete_histories(root)
    print("Clear history from # of entries: %s" % (num_histories))

    # Delete the <DeletedItems> object as well as it may not be needed
    deleted_items = root.find("./DeletedObjects")
    if deleted_items:
        root.remove(deleted_items)
        print("Deleted unnecessary object <DeletedObjects>...")

    # Delete the Recycle Bin object as those passwords are not needed
    recycle_bin = root_group.find("./Group[Name='Recycle Bin']")
    if recycle_bin:
        root_group.remove(recycle_bin)
        print("Deleted Recycle Bin and its discarded passwords...")

    # Customize templates with known fields (not passwords)
    # Finds password entries via case-insensitive search whose
    # title in KeePass starts with the key
    templates = {
        'twitter': get_secure_note_item(
            url='https://twitter.com'
        ),
        'oracle': get_database_item(
          alias='SOMEALIAS',
          database='db_service_name'
          hostname='db-hostname'
        ),
        'ldap_server': get_server_item(
          hostname='server_hostname'
        ),
        # This modifies all remaining items, assuming they are database types;
        # there is a check that prevents re-modifying items with a NoteType,
        # or websites
        '': get_database_item()
    }

    total_entries = 0

    for template in templates:
        num_entries = find_entries(
            root,
            template,
            templates[template]
        )
        total_entries += num_entries
        print("# of entries modified starting with '%s': %s\n" % (template, num_entries))

    print("# of all entries modified: %s" % (total_entries))
    tree.write(filename, 'utf-8', True)
    print("Wrote changes to %s." % (filename))


# Start the program here.
process()
