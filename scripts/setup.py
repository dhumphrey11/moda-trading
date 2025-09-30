"""
Setup and Installation Guide for Moda Trading

This script helps set up the development environment and guides through the deployment process.
"""

import subprocess
import sys
import os
import platform
from pathlib import Path


def run_command(command, description, check=True):
    """Run a shell command with error handling."""
    print(f"🔧 {description}...")
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                command, shell=True, check=check, capture_output=True, text=True)
        else:
            result = subprocess.run(
                command.split(), check=check, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"✅ {description} completed successfully")
            if result.stdout:
                print(f"   Output: {result.stdout.strip()}")
        else:
            print(f"❌ {description} failed")
            if result.stderr:
                print(f"   Error: {result.stderr.strip()}")
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        return False
    except FileNotFoundError:
        print(f"❌ Command not found for {description}")
        return False


def check_prerequisites():
    """Check if required tools are installed."""
    print("🔍 Checking prerequisites...")

    checks = {
        "Python": ["python", "--version"],
        "Node.js": ["node", "--version"],
        "NPM": ["npm", "--version"],
        "Git": ["git", "--version"]
    }

    results = {}
    for tool, command in checks.items():
        print(f"  Checking {tool}...")
        result = run_command(" ".join(command) if platform.system(
        ) == "Windows" else command, f"Check {tool}", check=False)
        results[tool] = result

    return results


def install_dependencies():
    """Install all project dependencies."""
    print("\n📦 Installing dependencies...")

    # Install root dependencies
    if not run_command("npm install", "Install root NPM packages"):
        return False

    # Install frontend dependencies
    frontend_path = Path("frontend")
    if frontend_path.exists():
        original_dir = os.getcwd()
        try:
            os.chdir(frontend_path)
            if not run_command("npm install", "Install frontend dependencies"):
                return False
        finally:
            os.chdir(original_dir)

    # Install Python dependencies
    requirements_file = Path("requirements.txt")
    if requirements_file.exists():
        if not run_command(f"{sys.executable} -m pip install -r requirements.txt", "Install Python dependencies"):
            return False

    # Install additional ML dependencies
    ml_packages = ["scikit-learn==1.3.2", "xgboost==2.0.2", "joblib==1.3.2"]
    for package in ml_packages:
        if not run_command(f"{sys.executable} -m pip install {package}", f"Install {package}"):
            return False

    return True


def check_gcloud_sdk():
    """Check if Google Cloud SDK is installed."""
    print("\n☁️ Checking Google Cloud SDK...")

    if run_command("gcloud version", "Check Google Cloud SDK", check=False):
        print("✅ Google Cloud SDK is installed")
        return True
    else:
        print("❌ Google Cloud SDK is not installed")
        print("\n📋 To install Google Cloud SDK:")

        if platform.system() == "Windows":
            print(
                "  1. Download from: https://cloud.google.com/sdk/docs/install-sdk#windows")
            print("  2. Run the installer")
            print("  3. Restart PowerShell/Command Prompt")
        elif platform.system() == "Darwin":  # macOS
            print("  1. Using Homebrew: brew install google-cloud-sdk")
            print(
                "  2. Or download from: https://cloud.google.com/sdk/docs/install-sdk#mac")
        else:  # Linux
            print(
                "  1. Follow instructions at: https://cloud.google.com/sdk/docs/install-sdk#linux")

        print("  4. Run: gcloud init")
        print("  5. Run: gcloud auth application-default login")
        return False


def create_env_file():
    """Create .env file template."""
    print("\n📝 Creating environment file template...")

    env_content = """# Moda Trading Environment Variables

# Google Cloud Project Configuration
GCP_PROJECT_ID=your-project-id-here

# API Keys (store these in GCP Secret Manager for production)
# Get these from the respective providers:
ALPHAVANTAGE_API_KEY=your-alphavantage-key
FINNHUB_API_KEY=your-finnhub-key
POLYGON_API_KEY=your-polygon-key
TIINGO_API_KEY=your-tiingo-key

# Development Settings
ENVIRONMENT=development
DEBUG=true

# Local Development URLs (update these after deployment)
ALPHAVANTAGE_SERVICE_URL=http://localhost:8001
FINNHUB_SERVICE_URL=http://localhost:8002
POLYGON_SERVICE_URL=http://localhost:8003
TIINGO_SERVICE_URL=http://localhost:8004
ORCHESTRATOR_SERVICE_URL=http://localhost:8005
ML_PIPELINE_SERVICE_URL=http://localhost:8006
STRATEGY_ENGINE_SERVICE_URL=http://localhost:8007
PORTFOLIO_SERVICE_URL=http://localhost:8008
"""

    env_file = Path(".env")
    if not env_file.exists():
        with open(env_file, "w") as f:
            f.write(env_content)
        print("✅ Created .env file template")
        print("   Please update the values in .env file")
    else:
        print("⚠️  .env file already exists, skipping creation")


def display_next_steps():
    """Display next steps for the user."""
    print("\n🎯 Next Steps:")
    print("\n1. 📋 Get API Keys:")
    print("   - Alpha Vantage: https://www.alphavantage.co/support/#api-key")
    print("   - Finnhub: https://finnhub.io/register")
    print("   - Polygon.io: https://polygon.io/pricing")
    print("   - Tiingo: https://api.tiingo.com/")

    print("\n2. ☁️ Set up Google Cloud Platform:")
    print("   - Create a new GCP project")
    print("   - Enable required APIs:")
    print("     • Cloud Run API")
    print("     • Firestore API")
    print("     • Secret Manager API")
    print("     • Cloud Build API")
    print("     • Cloud Scheduler API")
    print("     • Pub/Sub API")

    print("\n3. 🔐 Set up Authentication:")
    print("   - Install Google Cloud SDK (if not already done)")
    print("   - Run: gcloud auth application-default login")
    print("   - Set project: gcloud config set project YOUR_PROJECT_ID")

    print("\n4. 🗄️ Initialize Firestore:")
    print("   - Enable Firestore in your GCP project")
    print("   - Run: python scripts/init_firestore.py")

    print("\n5. 🚀 Deploy the Application:")
    print("   - Windows: .\\scripts\\deploy.ps1 -ProjectId 'your-project' -AlphaVantageKey 'key' ...")
    print("   - Linux/macOS: ./scripts/deploy.sh your-project alphavantage-key ...")

    print("\n6. 🔧 Local Development:")
    print("   - Update .env file with your configuration")
    print("   - Start individual services:")
    print("     • cd data-ingestion/alphavantage-service && uvicorn main:app --reload --port 8001")
    print("     • cd ml-pipeline && uvicorn main:app --reload --port 8006")
    print("     • cd frontend && npm start")

    print("\n📚 Documentation:")
    print("   - README.md: Project overview and quick start")
    print("   - DEPLOYMENT.md: Detailed deployment guide")
    print("   - Individual service READMEs in each directory")


def main():
    """Main setup function."""
    print("🚀 Moda Trading Setup Assistant")
    print("=" * 50)

    # Check prerequisites
    prereq_results = check_prerequisites()

    missing_tools = [tool for tool,
                     installed in prereq_results.items() if not installed]
    if missing_tools:
        print(f"\n❌ Missing required tools: {', '.join(missing_tools)}")
        print("Please install the missing tools and run this script again.")
        return

    print("\n✅ All prerequisites are installed!")

    # Install dependencies
    if not install_dependencies():
        print("\n❌ Failed to install some dependencies. Please check the errors above.")
        return

    print("\n✅ All dependencies installed successfully!")

    # Check Google Cloud SDK
    gcloud_installed = check_gcloud_sdk()

    # Create environment file
    create_env_file()

    # Display next steps
    display_next_steps()

    if gcloud_installed:
        print("\n✅ Setup completed! You can now proceed with GCP configuration and deployment.")
    else:
        print(
            "\n⚠️  Setup partially completed. Please install Google Cloud SDK to continue.")

    print("\n🎉 Welcome to Moda Trading!")


if __name__ == "__main__":
    main()
