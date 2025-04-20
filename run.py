import os
import uvicorn
import multiprocessing
import signal
import sys
import subprocess
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
RELOAD = os.getenv("RELOAD", "False").lower() in ("true", "1", "t")
LOG_LEVEL = os.getenv("LOG_LEVEL", "info")
APP_MODULE = "app.main:app"
CELERY_APP_MODULE = "app.celery_app"

# --- Process Functions ---


def run_uvicorn():
    print(f"Starting Uvicorn server on {HOST}:{PORT}...")
    uvicorn.run(
        APP_MODULE,
        host=HOST,
        port=PORT,
        reload=RELOAD,
        log_level=LOG_LEVEL,
    )


def run_celery_worker():
    """Starts the Celery worker using subprocess."""
    print("Starting Celery worker...")
    command = [
        sys.executable,
        "-m",
        "celery",
        "-A",
        CELERY_APP_MODULE,
        "worker",
        "--loglevel=INFO",
        "--pool=solo",
    ]
    # Run the command as a subprocess
    # This will block until the worker stops (e.g., via signal)
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Celery worker failed with error: {e}", file=sys.stderr)
    except FileNotFoundError:
        print(
            "Error: 'celery' command not found. Is Celery installed and in the PATH?",
            file=sys.stderr,
        )
    except Exception as e:
        print(
            f"An unexpected error occurred running Celery worker: {e}", file=sys.stderr
        )


# --- Signal Handling ---
def signal_handler(sig, frame):
    print("\nStopping processes...")
    # Terminate processes - send SIGTERM first, then SIGKILL if needed
    if uvicorn_process and uvicorn_process.is_alive():
        uvicorn_process.terminate()
    if celery_process and celery_process.is_alive():
        celery_process.terminate()
    sys.exit(0)


# --- Main Execution ---
if __name__ == "__main__":
    print("Starting application processes...")

    # Set up signal handling for graceful shutdown (Ctrl+C)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create processes
    uvicorn_process = multiprocessing.Process(target=run_uvicorn, name="Uvicorn")
    celery_process = multiprocessing.Process(
        target=run_celery_worker, name="CeleryWorker"
    )

    # Start processes
    uvicorn_process.start()
    celery_process.start()

    # Wait for processes to complete (they won't unless interrupted)
    # We rely on the signal handler to terminate them
    uvicorn_process.join()
    celery_process.join()

    print("Application stopped.")
