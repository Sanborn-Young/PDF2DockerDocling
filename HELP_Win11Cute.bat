@echo off
chcp 65001 >nul
echo.
echo =======================================================================
echo   📄 DOCLING PDF ^& JPEG SLIDE CONVERTER  --  USER GUIDE
echo =======================================================================
echo.
echo   🧰 WHAT THIS TOOL DOES:
echo   Converts PDF files and JPEG slide decks into Markdown (.md) files
echo   optimized for AnythingLLM RAG ingestion or general archiving.
echo   All embedded images are automatically recompressed to WebP to
echo   keep output file sizes small.
echo.
echo   🚀 HOW TO RUN:
echo   Start-Docling.bat can be clicked from Windows Explorer to kick off the proceses.  
echo   The tool will start Docker, wait for Docling to be ready,
echo   then show you the mode selection window.
echo.
echo =======================================================================
echo   🧪 STEP 1 -- CHOOSE A MODE
echo =======================================================================
echo.
echo   [1] One PDF      -- Convert a single PDF file
echo   [2] PDF Folder   -- Convert all PDFs in a folder (pick which ones)
echo   [3] JPEG Slides  -- Convert a folder of JPEGs into one Markdown file
echo                       (e.g. PowerPoint exported as images)
echo.
echo =======================================================================
echo   🧪 STEP 2 -- CHOOSE IMAGE HANDLING
echo =======================================================================
echo.
echo +-------------------------+---------------------------+---------------------------+
echo ^| Mode                   ^| PDF (text-based)          ^| JPEG Slides               ^|
echo +-------------------------+---------------------------+---------------------------+
echo ^| Strip Images           ^| Removes all images.       ^| OCRs text only.           ^|
echo ^|                        ^| Text-only Markdown.       ^| Photo-only slides blank.  ^|
echo +-------------------------+---------------------------+---------------------------+
echo ^| Placeholder            ^| Replaces images with      ^| OCRs text, inserts        ^|
echo ^|                        ^| ^<^!-- image --^> tag.        ^| ^<^!-- image --^> tag        ^|
echo +-------------------------+---------------------------+---------------------------+
echo ^| Embed Text Images      ^| Embeds charts/diagrams    ^| OCRs text, embeds only    ^|
echo ^|                        ^| as base64 WebP.           ^| chart/diagram slides.     ^|
echo +-------------------------+---------------------------+---------------------------+
echo ^| Embed All Images       ^| Embeds every image as     ^| OCRs text AND embeds      ^|
echo ^|                        ^| base64 WebP inline.       ^| every slide as WebP.      ^|
echo +-------------------------+---------------------------+---------------------------+
echo.
echo   NOTE: All base64 images are recompressed to WebP automatically
echo   before saving. File sizes are much smaller than raw JPEG/PNG.
echo.
echo =======================================================================
echo   🧪 STEP 3 -- CHOOSE OUTPUT FOLDER
echo =======================================================================
echo.
echo   [1] One PDF      -- NO folder dialog. Output goes directly to
echo                       SINGLE_PDF_OUTPUT_DIR from docling_settings.env.
echo                       If blank, defaults to .\outputs in the script folder.
echo                       This makes single PDF the fastest mode.
echo.
echo   [2] PDF Folder   -- A folder picker dialog appears.
echo   [3] JPEG Slides     Quick name buttons: folder_md, markdown_output,
echo                       converted, rag_ready
echo.
echo =======================================================================
echo   💡 TIPS
echo =======================================================================
echo.
echo   - Strip / Placeholder    produce the smallest .md files
echo   - Embed All              produces larger files (WebP keeps it manageable)
echo   - For AnythingLLM RAG    use Strip Images mode
echo   - For archiving slides   use Embed All Images mode
echo   - Scanned PDFs           use JPEG Slides mode, NOT PDF mode
echo   - JPEG Slides mode       always uses OCR automatically
echo   - Output is named after the source folder
echo   - Docker must be running before you launch the tool
echo   - The Docling container stays running after conversion finishes
echo.
echo =======================================================================
echo   📦 FILES
echo =======================================================================
echo.
echo   rundocling-fixed.py    -- Main converter script (run this)
echo   pull-updated.ps1       -- PowerShell script that starts Docker
echo   docling_settings.env   -- WebP + output directory settings (edit this)
echo   docling_convert.log    -- Full log of last session
echo   help.bat               -- This help file
echo.
echo =======================================================================
echo   ⚙️  DOCLING SETTINGS  (docling_settings.env)
echo =======================================================================
echo.
echo   Edit docling_settings.env to control output and image settings.
echo.
echo   ╭──────────────────────────────────────────────────────────────╮
echo   │  📁 SINGLE_PDF_OUTPUT_DIR=                                   │
echo   │      Output folder for single PDF conversions.               │
echo   │      Leave blank to use .\outputs.                           │
echo   │      Example: C:\Users\%%USERNAME%%\Documents\Converted_PDFs │
echo   │                                                              │
echo   │  🖼️ WEBP_ENABLED=true                                        │
echo   │      Set to false to skip WebP recompression.                │
echo   │                                                              │
echo   │  🎚️ WEBP_QUALITY=65                                          │
echo   │      0-100. Lower = smaller file.                            │
echo   │                                                              │
echo   │  🐢 WEBP_METHOD=6                                             │
echo   │      0-6. Higher = better compression.                       │
echo   │                                                              │
echo   │  ↔️ WEBP_MAX_WIDTH=1920                                       │
echo   │  ↕️ WEBP_MAX_HEIGHT=1080                                      │
echo   │      Set to 0 to disable resizing.                           │
echo   ╰──────────────────────────────────────────────────────────────╯
echo.
echo =======================================================================
echo   🧰 MENU
echo =======================================================================
echo.
echo   [E]  Open docling_settings.env in Notepad
echo   [Any other key]  Exit
echo.
set "ENV_FILE=docling_settings.env"
set /P "USER_CHOICE=   Select option: "
if /I "%USER_CHOICE%"=="E" (
  if exist "%ENV_FILE%" (
    start "" notepad "%ENV_FILE%"
  ) else (
    echo.
    echo   WARNING: docling_settings.env not found in the current folder.
    echo   Run rundocling-fixed.py once to generate it automatically.
  )
)
echo.
echo =======================================================================
pause