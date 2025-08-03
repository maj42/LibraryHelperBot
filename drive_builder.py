import json
from googleapiclient.discovery import build
from google.oauth2 import service_account
from datetime import datetime
from drive_model import DriveLibrary, InstrumentFolder, ProgramFolder, PdfFile
import re
from pytz import timezone, UTC

LOCAL_TZ = timezone('Asia/Yekaterinburg')

with open('config.json', encoding='utf-8') as f:
    config = json.load(f)

SCOPES = ['https://www.googleapis.com/auth/drive.metadata.readonly']
SERVICE_ACCOUNT_FILE = 'service_account.json'


def build_drive_tree():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    service = build('drive', 'v3', credentials=creds)

    folder_id = config["folder_id"]
    excluded = config["excluded_folders"]
    pattern = re.compile('|'.join([re.escape(word) for word in excluded]), re.IGNORECASE)

    # Step 1: list instrument folders in parent
    instrument_folders = list_folders(service, folder_id)
    instruments = []

    for instr in instrument_folders:
        if pattern.search(instr["name"]):
            continue

        instr_programs = list_folders(service, instr['id'])
        programs = []
        for prog in instr_programs:
            if pattern.search(prog['name']):
                continue
            files = list_pdfs(service, prog['id'])
            pdf_files = [PdfFile(
                name=f['name'],
                modified_time=format_time(f['createdTime']),
                link=f"https://drive.google.com/file/d/{f['id']}/view?usp=sharing"
            ) for f in files]
            programs.append(ProgramFolder(
                name=prog['name'],
                modified_time=format_time(prog['createdTime']),
                files=pdf_files
            ))
        instruments.append(InstrumentFolder(
            name=instr['name'],
            modified_time=format_time(instr['createdTime']),
            programs=programs
        ))

    # sort by custom order
    custom_order = config.get("instrument_order", [])
    instruments.sort(
        key=lambda x: custom_order.index(x.name) if x.name in custom_order else len(custom_order)
    )

    tree = DriveLibrary(
        instruments=instruments,
        last_updated=datetime.now().strftime("%d.%m.%Y %H:%M")
    )

    # save to JSON
    with open('drive_cache.json', 'w', encoding='utf-8') as f:
        json.dump(tree, f, default=lambda o: o.__dict__, ensure_ascii=False, indent=2)
    print("Drive tree updated.")
    return tree


def list_folders(service, parent_id):
    results = service.files().list(
        q=f"'{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
        fields="files(id, name, createdTime)"
    ).execute()
    return results.get('files', [])


def list_pdfs(service, parent_id):
    results = service.files().list(
        q=f"'{parent_id}' in parents and mimeType = 'application/pdf' and trashed = false",
        fields="files(id, name, createdTime)"
    ).execute()
    return results.get('files', [])


def format_time(iso_time):
    dt_utc = datetime.fromisoformat(iso_time.rstrip('Z')).replace(tzinfo=UTC)
    dt_local = dt_utc.astimezone(LOCAL_TZ)
    return dt_local.strftime("%d.%m.%Y %H:%M")
