import csv
import unicodedata
import re

USER_CSV = 'user.csv'
USER_NO_CSV = 'user-no.csv'
OUTPUT_CSV = 'digital_contacts_list.csv'

POSTAL_CODE_TO_COUNTY = {
    range(0, 13): 'Oslo',
    range(13, 15): 'Akershus',
    range(15, 19): '0stfold',
    range(19, 22): 'Akershus',
    range(22, 27): 'Innlandet',
    range(27, 30): 'Innlandet',
    range(30, 33): 'Vestfold',
    range(33, 37): 'Buskerud',
    range(36, 40): 'Telemark',
    range(40, 45): 'Rogaland',
    range(45, 48): 'Agder',
    range(47, 50): 'Agder',
    range(50, 60): 'Vestland',
    range(57, 58): 'Vestland',
    range(60, 67): 'More og Romsdal',
    range(67, 70): 'Vestland',
    range(70, 76): 'Trondelag',
    range(76, 80): 'Trondelag',
    range(79, 90): 'Nordland',
    range(84, 95): 'Troms',
    range(91, 100): 'Finnmark',
}

def get_county_by_postal_code(postal_code):
    if postal_code.isdigit() and len(postal_code) == 4:
        prefix = int(postal_code[:2])
        for postal_range, county in POSTAL_CODE_TO_COUNTY.items():
            if prefix in postal_range:
                return county
    return ''

def load_user_data(filename):
    user_data = {}
    with open(filename, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            row['RADIO_ID'] = str(row['RADIO_ID']) if row['RADIO_ID'].isdigit() else '0'
            row['CALLSIGN'] = format_callsign(row['CALLSIGN'])
            row['FIRST_NAME'] = normalize_text(row.get('FIRST_NAME', ''))
            row['LAST_NAME'] = normalize_text(row.get('LAST_NAME', ''))
            row['CITY'] = normalize_text(row.get('CITY', ''))
            row['STATE'] = row.get('STATE', '')
            row['COUNTRY'] = normalize_text(row.get('COUNTRY', ''))
            user_data[row['CALLSIGN']] = row
    return user_data

def load_user_no_data(filename):
    user_no_data = {}
    with open(filename, mode='r', encoding='ISO-8859-1') as file:
        reader = csv.DictReader(file, delimiter=';')
        for row in reader:
            row['Kallesignal'] = format_callsign(row['Kallesignal'])
            row['Fornavn'] = normalize_text(row.get('Fornavn', ''))
            row['Etternavn'] = normalize_text(row.get('Etternavn', ''))
            row['Poststed'] = normalize_text(row.get('Poststed', ''))
            postnummer = row.get('Postnr', '').strip()
            if len(postnummer) == 4 and postnummer.isdigit():
                row['Postnummer'] = postnummer
            row['Land'] = normalize_text(row.get('Land', ''))
            user_no_data[row['Kallesignal']] = row
    return user_no_data

def normalize_text(text):
    if not text:
        return ''
    # Erstatt norske bokstaver med engelske ekvivalenter
    replacements = {'Æ': 'AE', 'æ': 'ae', 'Ø': '0', 'ø': 'o', 'Å': 'A', 'å': 'a'}
    for original, replacement in replacements.items():
        text = text.replace(original, replacement)
    text = unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode('utf-8')

    # Gjør første bokstav i hvert navn stor og etter bindestreker
    text = re.sub(r'\b\w+\b', lambda match: match.group(0).capitalize(), text)
    text = re.sub(r'(\w+)-(\w+)', lambda match: f"{match.group(1).capitalize()}-{match.group(2).capitalize()}", text)

    return text

def format_callsign(callsign):
    return re.sub(r'[^A-Z0-9]', '', callsign.upper())

def truncate_name(first_name, last_name, max_length=16):
    """Truncates name by including first name and last name, removing middle name if necessary
    to fit within max length.

    Args:
        first_name: The first name.
        last_name: The last name.
        max_length: The maximum allowed length.

    Returns:
        The truncated name string.
    """
    # Sjekk at first_name og last_name ikke er tomme strenger
    if not first_name:
        first_name = ""
    if not last_name:
        last_name = ""

    # Split og forbered fornavn og etternavn
    first_name_parts = first_name.split()
    primary_first_name = first_name_parts[0] if first_name_parts else ""
    middle_initial = (
        f"{first_name_parts[1][0]}" if len(first_name_parts) > 1 and '-' not in first_name_parts[1] else ""
    )

    # Normaliser etternavn ved å ta kun første del, hvis tilgjengelig
    last_name_abbrev = last_name.split()[0] if last_name.split() else ""

    # Kombiner navn uten dobbel mellomrom
    full_name = f"{primary_first_name} {middle_initial} {last_name_abbrev}".strip()
    full_name = re.sub(r'\s+', ' ', full_name)  # Fjern eventuelle doble mellomrom

    # Fjern mellomnavn/forkortelse dersom full_name overstiger max_length
    if len(full_name) > max_length:
        full_name = f"{primary_first_name} {last_name_abbrev}".strip()
        full_name = re.sub(r'\s+', ' ', full_name)  # Fjern eventuelle doble mellomrom

    return full_name[:max_length]

def truncate_city(city, max_length=15):
    return city[:max_length]

def update_user_data(user_data, user_no_data):
    for callsign, data_no in user_no_data.items():
        if callsign in user_data:
            user_data[callsign]['FIRST_NAME'] = data_no.get('Fornavn', user_data[callsign].get('FIRST_NAME', ''))
            user_data[callsign]['LAST_NAME'] = data_no.get('Etternavn', user_data[callsign].get('LAST_NAME', ''))
            user_data[callsign]['CITY'] = data_no.get('Poststed', user_data[callsign].get('CITY', ''))
            postal_code = data_no.get('Postnummer', '')
            user_data[callsign]['STATE'] = get_county_by_postal_code(postal_code)
            if not user_data[callsign].get('COUNTRY'):
                user_data[callsign]['COUNTRY'] = data_no.get('Land', '')
    return user_data

def save_updated_data(user_data, filename):
    fieldnames = [
        'No.', 'Radio ID', 'Callsign', 'Name', 'City', 'State', 'Country',
        'Remarks', 'Call Type', 'Call Alert'
    ]
    with open(filename, mode='w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for i, (callsign, row) in enumerate(user_data.items(), start=1):
            truncated_name = truncate_name(row.get('FIRST_NAME', ''), row.get('LAST_NAME', ''))
            truncated_city = truncate_city(row.get('CITY', ''))
            writer.writerow({
                'No.': i,
                'Radio ID': row['RADIO_ID'],
                'Callsign': callsign,
                'Name': truncated_name,
                'City': truncated_city,
                'State': row.get('STATE', ''),
                'Country': row.get('COUNTRY', ''),
                'Remarks': '',
                'Call Type': 'Private Call',
                'Call Alert': 'None'
            })

def main():
    user_data = load_user_data(USER_CSV)
    user_no_data = load_user_no_data(USER_NO_CSV)
    updated_data = update_user_data(user_data, user_no_data)
    save_updated_data(updated_data, OUTPUT_CSV)
    print(f"Oppdaterte data har blitt lagret til {OUTPUT_CSV}")

if __name__ == "__main__":
    main()

