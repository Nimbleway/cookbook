"""Read-only preflight for the Google action layer.

Confirms: creds load, prints the service-account email (share your Sheet + Drive
folder with THIS email as Editor), and checks the Sheet + folder are reachable.
Makes NO writes. Run after setting GOOGLE_SA_JSON / GOOGLE_SHEET_ID / GOOGLE_DRIVE_FOLDER_ID.
"""
import sys

import config as C


def main():
    if not C.GOOGLE_SA_JSON:
        sys.exit("GOOGLE_SA_JSON not set (path to service-account JSON)")
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
    except ImportError:
        sys.exit("pip install google-api-python-client google-auth")

    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/documents",
              "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(C.GOOGLE_SA_JSON, scopes=scopes)
    print(f"✓ creds loaded. Service-account email:\n    {creds.service_account_email}")
    print("  → Share your Google Sheet AND Drive folder with this email as EDITOR.\n")

    ok = True
    if C.GOOGLE_SHEET_ID:
        try:
            meta = build("sheets", "v4", credentials=creds).spreadsheets().get(
                spreadsheetId=C.GOOGLE_SHEET_ID).execute()
            print(f"✓ Sheet reachable: {meta.get('properties', {}).get('title')!r}")
        except Exception as e:  # noqa: BLE001
            ok = False; print(f"✗ Sheet NOT reachable ({C.GOOGLE_SHEET_ID}): {e}")
    else:
        print("• GOOGLE_SHEET_ID not set")

    if C.GOOGLE_DRIVE_FOLDER_ID:
        try:
            f = build("drive", "v3", credentials=creds).files().get(
                fileId=C.GOOGLE_DRIVE_FOLDER_ID, fields="id,name,mimeType", supportsAllDrives=True).execute()
            print(f"✓ Drive folder reachable: {f.get('name')!r}")
        except Exception as e:  # noqa: BLE001
            ok = False; print(f"✗ Drive folder NOT reachable ({C.GOOGLE_DRIVE_FOLDER_ID}): {e}")
    else:
        print("• GOOGLE_DRIVE_FOLDER_ID not set")

    print("\nPREFLIGHT " + ("PASSED — ready for `python actions.py`" if ok else "FAILED — fix sharing/IDs above"))


if __name__ == "__main__":
    main()
