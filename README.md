# open_urls_list
opens urls from list in floorp
Read URLs from a file, drop ones you already have or don't want, open the rest in Floorp in batches. A backup file is created before opening URLs, and the original file is cleared after Floorp closes.

Requirements

Linux, Python 3.11+

Floorp installed at /usr/bin/floorp

No pip packages

Configure

Edit constants at the top of the script:

DEFAULT_FILEPATH = Path("/home/youruser/dir/urls.txt")
CHECK_DIR = Path("/home/youruser/dir")      # or DEFAULT_FILEPATH.parent
BATCH_SIZE = 10
BATCH_DELAY_SECONDS = 60
FLOORP_PATH = Path("/usr/bin/floorp")
EXCLUDED_EXTENSIONS = {".webp", ".tiff", ".bmp"}

Usage

Put URLs in urls.txt, one per line.

Run:

python3 open_urls_list.py


The script creates a backup (urls_bak.txt), opens URLs in batches, waits for Floorp to close, then clears urls.txt.

Exit codes

0 success or nothing to open

1 error (missing file, launch failure)

130 interrupted with Ctrl+C

Troubleshooting

Message file not found: fix DEFAULT_FILEPATH or create the file.

Error Floorp not found: set FLOORP_PATH to your Floorp binary.

“No URLs to open after filtering”: all lines were blank/duplicates, had excluded extensions, or basenames already exist in CHECK_DIR. Adjust inputs or settings.
