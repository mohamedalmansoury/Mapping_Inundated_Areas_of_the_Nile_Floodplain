import subprocess
import sys
import os

def check_python_version():
    if sys.version_info < (3, 8):
        print("ERROR: Python 3.8 or higher is required!")
        print(f"Current version: {sys.version}")
        sys.exit(1)
    print(f"Python version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")

def install_dependencies():
    print("\nInstalling dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("Dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError:
        print("ERROR: Failed to install dependencies!")
        return False

def authenticate_gee():
    print("\nChecking Google Earth Engine authentication...")
    try:
        import ee
        try:
            ee.Initialize()
            print("Earth Engine already authenticated!")
            return True
        except:
            print("Earth Engine not authenticated. Starting authentication...")
            subprocess.check_call(["earthengine", "authenticate"])
            print("Earth Engine authenticated successfully!")
            return True
    except ImportError:
        print("ERROR: Earth Engine API not installed!")
        return False

def run_app():
    print("\nStarting Streamlit application...")
    print("\n" + "="*60)
    print("The app will open in your browser at http://localhost:8501")
    print("Press Ctrl+C to stop the application")
    print("="*60 + "\n")
    
    try:
        subprocess.run([sys.executable, "-m", "streamlit", "run", "flood_app_streamlit.py"])
    except KeyboardInterrupt:
        print("\n\nApplication stopped!")

def main():
    print("="*60)
    print("SENTINEL-1 FLOOD MAPPER - SETUP & RUN")
    print("="*60)
    
    check_python_version()
    
    if not install_dependencies():
        print("\nPlease install dependencies manually:")
        print("   pip install -r requirements.txt")
        sys.exit(1)
    
    if not authenticate_gee():
        print("\nPlease authenticate Earth Engine manually:")
        print("   earthengine authenticate")
        sys.exit(1)
    
    run_app()

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    main()
