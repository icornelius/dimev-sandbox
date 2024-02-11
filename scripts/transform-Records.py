# This script extracts a small sample of item records from Records.xml and
# transforms them into individual YAML files with consistent data structure.
# Warnings are emitted for known irregularities not yet accommodated.
# Successful transformations may be written to `../docs/_items`, where they are
# available to Jekyll's website builder

import os
import xmltodict
import re
import yaml

# Top-level variables
source = '../DIMEV_XML/Records.xml'
destination = '../docs/_items/'
test_sample= ['357', '2324', '2458', '2651', '2677', '6654']
warning_log = []
log_file = 'python-warnings.txt'

# Target data structure
record_target = \
    {
        'DIMEV': '',
        'IMEV': '',
        'NIMEV': '',
        'itemIncipit': '',
        'description': '',
        'descNote': '',
        'authors': [],
        'itemTitles': [],
        'subjects': [],
        'verseForms': [],
        'versePatterns': [],
        'languages': [],
        'ghosts': [],
        'witnesses': []
            }

author_target = \
    {
        'lastName': '',
        'firstName': '',
        'suffix': '',
        'key': ''
    }

ghost_target = \
    {
        'key': '',
        'note': ''
    }

witness_target = \
    {
        'wit_id': '',
        'illust': '',
        'music': '',
        'allLines': '',
        'firstLines': '',
        'lastLines': '',
        'sourceKey': '',
        'point_locators':
            {
                'prefix': '',
                'range': []
            },
        'note': '',
        'MSAuthor': '',
        'MSTitle': '',
        'facsimiles': [],
        'editions': []
        }

witness_range_target = \
    {
        'start': '',
        'end': ''
    }

witness_edFacs_target = \
    {
        'key': '',
        'point_locators': ''
    }

# Key lists for validation and processing
orig_item_fields_to_str = ['@xml:id', '@imev', '@nimev', 'name', 'description', 'descNote']
orig_item_fields_to_list = \
    ['title', 'titles', # both tag-forms in use
            'subjects', 'verseForms', 'versePatterns', 'languages']
orig_item_fields_to_list_of_dict = ['authors', 'ghosts', 'witnesses']
orig_keys_for_item_author = ['first', 'last', 'suffix']
orig_wit_fields_to_str = ['@xml:id', '@illust', '@music', 'allLines', 'firstLines', 'lastLines', 'sourceNote', 'MSAuthor', 'MSTitle']
orig_keys_for_witness_ranges = ['#text', '@loc', '@pre', '@col']

# Crosswalks
## Crosswalks old, to new
x_walk_item_fields_to_str = \
    [
        ('@xml:id', 'DIMEV'),
        ('@imev', 'IMEV'),
        ('@nimev', 'NIMEV'),
        ('name', 'itemIncipit'),
        ('description', 'description'), # unchanged
        ('descNote', 'descNote') #unchanged
    ]

x_walk_item_fields_to_list = \
    [
        ('titles', 'itemTitles'), # avoid clash with liquid template variable `page.title`
        ('title', 'itemTitles'),
        ('subjects', 'subjects'), # unchanged
        ('subject', 'subjects'),
        ('verseForms', 'verseForms'), # unchanged
        ('verseForm', 'verseForms'),
        ('versePatterns', 'versePatterns'), # unchanged
        ('versePattern', 'versePatterns'),
        ('languages', 'languages'), # unchanged
        ('language', 'languages')
    ]

# Unused; omits witnesses, handled separately
# x_walk_item_fields_to_structured_list = \
#     [
#         ('authors', 'authors'), # unchanged
#         ('author', 'authors'),
#         ('ghosts', 'ghosts'), # unchanged
#         ('ghost', 'ghosts')
#     ]

# Unused
# x_walk_author_fields = \
#     [
#         ('last', 'lastName'),
#         ('first', 'firstName')
#     ]

x_walk_wit_fields_to_str = \
    [
        ('@xml:id', 'wit_id'),
        ('@illust', 'illust'),
        ('@music', 'music'),
        ('allLines', 'allLines'), # unchanged
        ('firstLines', 'firstLines'), # unchanged
        ('lastLines', 'lastLines'), # unchanged
        ('sourceNote', 'note'),
        ('MSAuthor', 'MSAuthor'), # unchanged
        ('MSTitle', 'MSTitle') # unchanged
    ] # omitting 'key', which requires separate treatment

# Cross-walk, parent to child
x_walk_orig_parent_to_orig_child = \
    [
        ('titles', 'title'),
        ('subjects', 'subject'),
        ('verseForms', 'verseForm'),
        ('versePatterns', 'versePattern'),
        ('languages', 'language'),
        ('ghosts', 'ghost'),
        ('authors', 'author'),
        ('witnesses', 'witness'),
        ('facsimiles', 'facsimile'),
        ('editions', 'edition')
    ]

def read_xml_to_string(source):
    print(f'Reading source file `{source}` to string...')
    with open(source) as f:
        xml_string = f.read()
    print('Preprocessing string...')
    xml_string = re.sub(' {2,}', ' ', xml_string) # remove whitespace
    xml_string = re.sub('\\n', '', xml_string) # remove newlines
    xml_string = re.sub('<lb/>', 'LINE_BREAK', xml_string) # replace <lb/> elements with newlines and spaced indent
    # xml_string = re.sub('<lb/>', '\\n', xml_string) # replace <lb/> elements with newlines and spaced indent
    xml_string = re.sub('<sup>', 'BEGIN_SUP', xml_string) # replace <sup> tags
    xml_string = re.sub('</sup>', 'END_SUP', xml_string)
    xml_string = re.sub('<i>', 'BEGIN_ITALICS', xml_string)  # replace <i> tags
    xml_string = re.sub('</i>', 'END_ITALICS', xml_string)
    xml_string = re.sub(r'<ref xml:target="([\.0-9]+)" *>[0-9]+</ref>', 'DIMEV_' + r'\1', xml_string)
    # xml_string = re.sub(r'<mss key="([A-Za-z0-9]+)"/>', 'MS_' + r'\1', xml_string) # This substitution disrupts rendering of <ghost>
    return xml_string

def xml_to_dict(xml_string):
    print('Parsing string as a Python dictionary...')
    xml_dict = xmltodict.parse(xml_string)
    items = xml_dict['records']['record'] # strip outer keys
    return items

def get_valid_input(prompt, options):
    while True:
        choice = input(prompt).lower()
        if choice in options:
            return choice
        prompt = "Invalid selection. Try again. "

def get_id_list(items):
    dimev_ids = []
    for idx in range(len(items)):
        if type(items[idx]) == dict and '@xml:id' in items[idx]: # necessary conditions, given data irregularities
            dimev_id = re.sub('record-', '', items[idx]['@xml:id'])
            dimev_ids.append(dimev_id)
    return dimev_ids

def get_item(dimev_id):
    for idx in range(len(items)):
        if '@xml:id' in items[idx]:
            if items[idx]['@xml:id'] == 'record-' + dimev_id:
                item = items[idx]
                return item

def transform_item(dimev_id):
    item = get_item(dimev_id)
    item_keys = list(item.keys())
    new_record = record_target.copy()
    # translate item-level string fields
    # TODO: Accommodate `descNote` values with inline references to witness-keys (e.g., DIMEV 2458)
    for orig_key in item_keys:
        if orig_key == 'alpha':
            continue # Do not convert; shifting case is trivial
        elif orig_key in orig_item_fields_to_str:
            for key_pair in x_walk_item_fields_to_str:
                if key_pair[0] == orig_key:
                    if orig_key == '@xml:id':
                        new_record[key_pair[1]] = re.sub('record-', '', item[orig_key])
                    elif type(item[orig_key]) == str:
                        new_record[key_pair[1]] = format_string(item[orig_key])
                    elif item[orig_key] is None:
                        # TODO: What is the appropriate null value for string fields? `null` or '' or something else?
                        continue
                    else:
                        warn('type', orig_key, '', dimev_id, item[orig_key])
        # translate item-level fields targetted to list
        elif orig_key in orig_item_fields_to_list:
            thislist = []
            if type(item[orig_key]) == str:
                for key_pair in x_walk_item_fields_to_list:
                    if key_pair[0] == orig_key:
                        thislist.append(format_string(item[orig_key]))
                        new_record[key_pair[1]] = thislist
            elif type(item[orig_key]) == dict:
                for parentChild in x_walk_orig_parent_to_orig_child:
                    # Walk the structure, parent to child
                    if orig_key == parentChild[0]:
                        if len(item[orig_key].keys()) == 1 and parentChild[1] in item[orig_key].keys():
                            childItem = item[parentChild[0]][parentChild[1]]
                            # Identify data type and extract value(s) as list
                            if type(childItem) == list:
                                for list_item in childItem:
                                    thislist.append(format_string(list_item))
                            elif type(childItem) == str:
                                thislist.append(format_string(childItem))
                            elif childItem is None:
                                continue
                            else:
                                warn('type', orig_key, '', dimev_id, item[orig_key])
                            # Identify key and assign value
                            for key_pair in x_walk_item_fields_to_list:
                                if key_pair[0] == orig_key:
                                    new_record[key_pair[1]] = thislist
                        else:
                            warn('field', orig_key, '', dimev_id, item[orig_key])
        # translate item-level structured list fields
        elif orig_key in orig_item_fields_to_list_of_dict:
            thislist = []
            if orig_key == 'witnesses':
                new_record['witnesses'] = transform_witnesses(dimev_id, item)
            elif orig_key == 'ghosts':
                if item[orig_key] is None:
                    thislist.append(ghost_target)
                else:
                    ghost_element = item[orig_key]['ghost']
                    if type(ghost_element) == dict:
                        transformed_ghost = transform_ghost(ghost_element, dimev_id)
                        thislist.append(transformed_ghost)
                    elif type(ghost_element) == list:
                        for ghost in ghost_element:
                            transformed_ghost = transform_ghost(ghost, dimev_id)
                            thislist.append(transformed_ghost)
                    else:
                        thislist.append(ghost_target)
                        warn('type', orig_key, '', dimev_id, item[orig_key])
                new_record['ghosts'] = thislist
            elif orig_key == 'authors':
                author_element = item[orig_key]['author']
                if author_element is None:
                    thislist.append(author_target)
                elif type(author_element) == dict:
                    transformed_author = transform_author(author_element, dimev_id)
                    thislist.append(transformed_author)
                elif type(author_element) == list:
                    for author in author_element:
                        transformed_author = transform_author(author, dimev_id)
                        thislist.append(transformed_author)
                else:
                    thislist.append(author_target)
                    warn('type', orig_key, '', dimev_id, item[orig_key])
                new_record['authors'] = thislist
        else:
            warn('field', orig_key, '', dimev_id, item[orig_key])
    return new_record

def format_string(value):
    if type(value) == str:
        value = re.sub('^: ', '', value)
        value = re.sub('BEGIN_ITALICS', '<i>', value)
        value = re.sub('END_ITALICS', '</i>', value)
        value = re.sub('BEGIN_SUP', '<sup>', value)
        value = re.sub('END_SUP', '</sup>', value)
        value = re.sub('LINE_BREAK', '<br />', value)
    return value

def transform_ghost(ghost, dimev_id):
    # validate top-level keys
    for key in ghost.keys():
        if key not in ['mss', '#text']:
            warn('field', key, '', dimev_id, author)
    # transform
    note_value = format_string(ghost.get('#text', ''))
    transformed_ghost = {
            'key': ghost['mss'].get('@key'),
            'note': note_value
        }
    return transformed_ghost

def transform_author(author, dimev_id):
    # validate keys
    for key in author.keys():
        if key not in orig_keys_for_item_author:
            warn('field', key, '', dimev_id, author)
    # transform
    transformed_author = {
            'lastName': author.get('last', ''),
            'firstName': author.get('first', ''),
            'suffix': author.get('suffix', '')
        }
    # create author_key
    author_key = transformed_author['lastName'] + transformed_author['firstName']
    author_key = re.sub(' ', '', author_key)
    transformed_author['key'] = author_key
    return transformed_author

def transform_witnesses(dimev_id, item):
    wit_list = []
    witness_element = item['witnesses']['witness']
    if type(witness_element) == dict:
        witness_element = [witness_element] # Perhaps use this trick elsewhere?
    for witness in witness_element:
        transformed_witness = witness_target.copy()
        for orig_key in witness.keys():
            if orig_key in orig_wit_fields_to_str:
                if orig_key == '@xml:id':
                    # TODO: accommodate decimals
                    formatted_value = re.sub(r'wit-\d*-', '', witness[orig_key]) # strip prefixed DIMEV item number as redundant
                    transformed_witness['wit_id'] = int(formatted_value) # should this be string? Yes, b/c decimals
                else:
                    for key_pair in x_walk_wit_fields_to_str:
                        if key_pair[0] == orig_key:
                            if type(witness[orig_key]) == str:
                                transformed_witness[key_pair[1]] = format_string(witness[orig_key])
                            elif witness[orig_key] is None:
                                continue
                            else:
                                # TODO: accommodate `sourceNote` with inline references to other source keys (e.g., DIMEV 6654)
                                warn('type', orig_key, witness['@xml:id'], dimev_id, witness[orig_key])
            elif orig_key == 'source':
                # TODO: create for loop to accommodate discontinuous ranges described in XML editing manual, pp. 14-15
                transformed_witness['sourceKey'] = witness[orig_key]['@key']
                start_string = transform_wit_point_locators(dimev_id, witness, 'start')
                end_string = transform_wit_point_locators(dimev_id, witness, 'end')
                transformed_witness['point_locators'] = {
                        'prefix': witness[orig_key].get('@prefix', ''),
                        'range': [ {
                            'start': start_string,
                            'end': end_string
                            }
                        ]
                    }
            elif orig_key == 'facsimiles' or orig_key == 'editions':
                new_key = orig_key
                thislist = []
                if type(witness[orig_key]) == dict:
                    for key_pair in x_walk_orig_parent_to_orig_child:
                        if orig_key == key_pair[0]:
                            childItem = witness[orig_key][key_pair[1]]
                            if type(childItem) == dict:
                                transformed_field = transform_edFacs(childItem, witness, dimev_id)
                                thislist.append(transformed_field)
                            elif type(childItem) == list:
                                for edFacs in childItem:
                                    transformed_field = transform_edFacs(edFacs, witness, dimev_id)
                                    thislist.append(transformed_field)
                            elif witness[orig_key][key_pair[1]] is None:
                                thislist.append(witness_edFacs_target.copy())
                            else:
                                warn('type', orig_key, witness['@xml:id'], dimev_id, witness[orig_key])
                            transformed_witness[new_key] = thislist
                else:
                    warn('type', orig_key, witness['@xml:id'], dimev_id, witness[orig_key])
            else:
                warn('field', orig_key, witness['@xml:id'], dimev_id, witness[orig_key])
        wit_list.append(transformed_witness)
    return wit_list

def transform_wit_point_locators(dimev_id, witness, terminus):
    point_locator = rectoVerso = rangeFlag = column = ''
    rangedata = witness['source'][terminus]
    if type(rangedata) == dict:
        for key in rangedata.keys():
            if key not in orig_keys_for_witness_ranges:
                warn('field', key, witness['@xml:id'], dimev_id, witness[key])
        if '@loc' in rangedata.keys():
            rectoVerso = rangedata['@loc']
        if '@pre' in rangedata.keys():
            rangeFlag = rangedata['@pre']
        if '@col' in rangedata.keys():
            column = ' col. ' + rangedata['@col']
        point_locator = rangedata['#text'] + rangeFlag + rectoVerso + column
    elif rangedata:
        point_locator = str(rangedata)
    return point_locator

def transform_edFacs(edFacs, witness, dimev_id):
    # validate keys
    for key in edFacs.keys():
        if key not in ['@key', '#text']:
            warn('field', key, witness['@xml:id'], dimev_id, edFacs)
    # transform
    transformed_edFacs = {
            'key': edFacs.get('@key'),
            'point_locators': edFacs.get('#text', '')
        }
    return transformed_edFacs

def warn(warning_type, field, parent_field, dimev_id, data):
    if 'wit' in str(parent_field):
        parent_field = ', ' + str(parent_field)
    if warning_type == 'type':
        warning_text = f'WARNING: Unexpected data type in element {field} of DIMEV {dimev_id}{parent_field}. Skipping.'
        print(warning_text)
        warning_log.append(warning_text)
    elif warning_type == 'field':
        warning_text = f'WARNING: Unexpected field {field} in DIMEV {dimev_id}{parent_field}. Skipping.'
        print(warning_text)
        warning_log.append(warning_text)
    print('\t', data)
    warning_log.append('\t' + str(data))

def validate_yaml(dimev_id, conversion):
    print(f'Validating YAML conversion for DIMEV {dimev_id}...')
    #TODO: Validate against the specific target, not just general syntax
    string = '\n'.join(conversion)
    try:
        yaml.safe_load(string)
        return True
    except yaml.YAMLError as e:
        print(e)
        return False

def yaml_dump(new_record):
    yml_out = yaml.dump(new_record, sort_keys=False, allow_unicode=True)
    print('---')
    print(yml_out)
    print('---')

def write_to_file(dimev_id, conversion):
    output_filename = destination + '0' * (4 - len(dimev_id)) + dimev_id + '.md'
    yml_out = yaml.dump(conversion, sort_keys=False, allow_unicode=True)
    with open(output_filename, 'w') as file:
        file.write('---\n')
        file.write(yml_out)
        file.write('---\n')
    print(f'  Wrote to `{output_filename}`.\n')

# read the source file to string and pre-process
xml_string = read_xml_to_string(source)

# create a dictionary
items = xml_to_dict(xml_string)

# define job
print(f'''
Select from the options below:
   (1) Enter a DIMEV item number to convert (Default)
   (2) Convert the test sample and write all results to `{destination}`''')
prompt= 'Selection: '
options = ['1', '2', '']
job = get_valid_input(prompt, options)
print()

# identify item(s) and run conversion(s)
if job == '2':
    for idx in range(len(test_sample)):
        dimev_id = test_sample[idx]
        print(f'Transforming DIMEV {dimev_id}...')
        conversion = transform_item(dimev_id)
        valid_yaml = validate_yaml(dimev_id, conversion)
        if valid_yaml:
            print('  Validation passing.')
            write_to_file(dimev_id, conversion)
        else:
            print('  YAML validation failed! Aborting write.')
else:
    prompt = 'Enter a DIMEV item number to convert. (Default is 2677.) '
    options = get_id_list(items) # create a list of dimev numbers to validate input
    options.append('')
    dimev_id = get_valid_input(prompt, options)
    if len(dimev_id) == 0:
        dimev_id = '2677'
    conversion = transform_item(dimev_id)
    yaml_dump(conversion)
    prompt = f'Validate this conversion and write it to `{destination}`? (Y/n) '
    options = ['y', 'n', '']
    decision = get_valid_input(prompt, options)
    if decision == 'y' or decision == '':
        valid_yaml = validate_yaml(dimev_id, conversion)
        if valid_yaml:
            print('  Validation passing.')
            write_to_file(dimev_id, conversion)
        else:
            print('  YAML validation failed! Aborting write.')
    else:
        print('Write aborted')

with open(log_file, 'w') as file:
    for line in warning_log:
        file.write(line + '\n')

print('Goodbye')
