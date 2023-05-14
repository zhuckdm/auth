import uvicorn
from app.services import get_app_config


if __name__ == "__main__":
    config = get_app_config()
    uvicorn.run("app.api:app", host=config['host'], port=config['port'], reload=False)
