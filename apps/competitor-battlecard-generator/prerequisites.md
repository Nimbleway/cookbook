# Prerequisites

## Required

- **Python 3.9+**

Install dependencies:

```bash
pip install -r requirements.txt
```

## Optional

- **Nimble API key** - required only for live web research. Not needed for the sample dashboard or dry-run mode.
  - Get your key at `online.nimbleway.com/account-settings/api-keys`
  - Add it to `.env` as `NIMBLE_API_KEY=your_key_here`

## No API key needed for

- Opening the sample dashboard (`streamlit run app.py`)
- Running a dry-run collection (`python3 collect.py --dry-run`)
- Exploring the bundled `data/sample_run/` output
