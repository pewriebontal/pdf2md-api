import os
import uvicorn
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    env = os.environ.get("ENVIRONMENT", "development")
    port = int(os.environ.get("PORT", 8000))    
    host = os.environ.get("HOST", "0.0.0.0")
    
    reload = env.lower() != "production"
    
    print(f"Starting server in {env} mode")
    print(f"Host: {host}, Port: {port}, Reload: {reload}")
    
    uvicorn.run(
        "app.main:app", 
        host=host, 
        port=port, 
        reload=reload
    )