import os
import shutil
import PyInstaller.__main__
from pathlib import Path

# Configuration
APP_NAME = "IndianMarketsTrader"
ENTRY_POINT = "app/main.py"

def build():
    print(f"🚀 Starting build process for {APP_NAME}...")
    
    # 1. Clean previous builds
    for folder in ['build', 'dist']:
        if os.path.exists(folder):
            print(f"🧹 Cleaning {folder}...")
            shutil.rmtree(folder)

    # 2. Define arguments for PyInstaller
    args = [
        ENTRY_POINT,
        '--name', APP_NAME,
        '--onefile',                 # Create a single EXE
        '--windowed',                # Don't show console (optional, remove if you want logs)
        '--collect-all', 'uvicorn',
        '--collect-all', 'fastapi',
        '--collect-all', 'jinja2',
        '--collect-all', 'sqlalchemy',
        '--collect-all', 'dhanhq',
        '--collect-all', 'loguru',
        # Add internal assets (Templates and Static files)
        '--add-data', f'app/dashboard/templates;app/dashboard/templates',
        '--add-data', f'app/dashboard/static;app/dashboard/static',
        # Hidden imports that might be missed
        '--hidden-import', 'aiosqlite',
        '--hidden-import', 'uvicorn.protocols.http.httptools_impl',
        '--hidden-import', 'uvicorn.protocols.http.h11_impl',
        '--hidden-import', 'uvicorn.protocols.websockets.websockets_impl',
        '--hidden-import', 'uvicorn.lifespan.on',
    ]

    print("📦 Running PyInstaller...")
    PyInstaller.__main__.run(args)

    # 3. Post-build: Copy Plugins folder next to the EXE
    print("📂 Setting up external plugins directory...")
    dist_path = Path("dist")
    plugins_src = Path("plugins")
    plugins_dst = dist_path / "plugins"

    if plugins_src.exists():
        shutil.copytree(plugins_src, plugins_dst, dirs_exist_ok=True)
    else:
        plugins_dst.mkdir(exist_ok=True)

    # 4. Create a sample .env file if it doesn't exist
    env_dst = dist_path / ".env"
    if not env_dst.exists():
        with open(env_dst, "w") as f:
            f.write("# Trading Platform Configuration\nTRADING_MODE=paper\n")

    print(f"\n✅ Build complete! You can find your app in the 'dist' folder.")
    print(f"👉 To run: dist/{APP_NAME}.exe")

if __name__ == "__main__":
    build()
