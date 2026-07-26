import uvicorn

from .main import SIMULATOR_HOST, SIMULATOR_PORT, app


if __name__ == "__main__":
    uvicorn.run(app, host=SIMULATOR_HOST, port=SIMULATOR_PORT)
